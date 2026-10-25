"""Attribution's benchmark segments: ACWI's weights by sector and by region on each day, and each segment's daily
DKK return from its proxy ETFs (universe.yaml `attribution:`).

ACWI's own segment returns aren't free, and iShares serves only today's holdings, so both sides are approximations,
and every result says which: the weights come from the radar's weekly snapshots (`constituents.acwi_segment_history`),
drifted with the segments' returns from the last snapshot (basis `snapshot`) or, before the first one, rolled back
from it (`back-drifted`); the returns come from MSCI World sector UCITS ETFs (the US sector ETFs before their first
price) and from country ETFs weighted by ACWI's country weights inside each region. A segment without a return on a
day has no weight that day either: missing, never 0 %. The method: plans/F4-attribution.md, 4.3."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import typed, universe_config
from .prices import Prices

DIMS = ("sector", "region")


def proxies() -> dict:
    """universe.yaml's `attribution:` section ({} when there is none)."""
    return universe_config().get("attribution") or {}


def daily_returns(prices: Prices, ticker: str, dates: pd.DatetimeIndex) -> pd.Series:
    """The ticker's DKK return on each day of `dates` (close to close); NaN where either close is unknown."""
    s = prices.dkk(ticker)
    if s is None:
        return pd.Series(np.nan, index=dates)
    px = s.reindex(dates)
    return px / px.shift(1) - 1


def sector_returns(prices: Prices, dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, list[str]]:
    """Each sector's daily DKK return from its proxy, and from the fallback map's ETF on days before the proxy's
    first return; with a note per sector that used the fallback or has no return at all."""
    conf = proxies()
    fallback = (universe_config().get("sector_etfs") or {}).get(conf.get("sector_fallback") or "") or {}
    cols, notes = {}, []
    for sector, ticker in (conf.get("sectors") or {}).items():
        r = daily_returns(prices, ticker, dates)
        first = r.first_valid_index()
        fb = fallback.get(sector) if isinstance(fallback.get(sector), str) else None
        late = first is None or (len(dates) > 1 and first > dates[1])   # dates[0] never has a return
        if fb is not None and late:
            early = daily_returns(prices, fb, dates)
            r = r.where(r.index >= first, early) if first is not None else early
            if early.notna().any():
                notes.append(f"{sector}: {fb} (US) stands in for {ticker} "
                             + (f"before {first:%Y-%m-%d}" if first is not None else "(no prices for it)"))
        if r.isna().all():
            notes.append(f"{sector}: no proxy prices ({ticker}): its benchmark return is missing")
        cols[sector] = r
    return pd.DataFrame(cols, index=dates), notes


def region_returns(prices: Prices, dates: pd.DatetimeIndex, country_weights: pd.DataFrame
                   ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Each region's daily DKK return: its country ETFs weighted by ACWI's country weights inside the region on that
    day (`country_weights`: one row per day of `dates`, columns 'region|country'). A day where the countries with a
    proxy cover less than `attribution.min_proxy_coverage` of the region's weight, or a proxy has no return, is
    missing. Also returns the coverage per region and day."""
    conf = proxies()
    least = typed().attribution.min_proxy_coverage
    out, cover = {}, {}
    w = country_weights.reindex(dates)
    for region, countries in (conf.get("regions") or {}).items():
        cols = [c for c in w.columns if c.split("|", 1)[0] == region]
        total = w[cols].sum(axis=1, min_count=1)
        num = pd.Series(0.0, index=dates)
        covered = pd.Series(0.0, index=dates)
        for country, ticker in (countries or {}).items():
            key = f"{region}|{country}"
            if key not in w:
                continue
            r = daily_returns(prices, ticker, dates)
            num = num + w[key] * r            # NaN when the proxy has no return: the day is missing
            covered = covered + w[key]
        share = covered / total
        cover[region] = share
        out[region] = (num / covered).where((share >= least) & (covered > 0))
    return pd.DataFrame(out, index=dates), pd.DataFrame(cover, index=dates)


def snapshots(history: pd.DataFrame, dim: str) -> pd.DataFrame:
    """One row per snapshot date (sorted), one column per key of `dim`; a key a snapshot doesn't list weighs 0."""
    sub = history[history["dim"] == dim]
    if sub.empty:
        return pd.DataFrame()
    wide = sub.pivot_table(index="asof", columns="key", values="weight", aggfunc="sum")
    wide.index = pd.to_datetime(wide.index)
    return wide.sort_index().fillna(0.0)   # zero: ACWI held nothing in that key on that day


def stepped_weights(snaps: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """The last snapshot on or before each day (the first one before any), undrifted: for the country weights
    inside a region, which only decide how the region's country ETFs are mixed."""
    if snaps.empty:
        return pd.DataFrame(index=dates)
    pos = np.clip(snaps.index.searchsorted(dates, side="right") - 1, 0, None)
    return pd.DataFrame(snaps.to_numpy()[pos], index=dates, columns=snaps.columns)


def drifted_weights(snaps: pd.DataFrame, returns: pd.DataFrame, dates: pd.DatetimeIndex
                    ) -> tuple[pd.DataFrame, pd.Series]:
    """ACWI's weights at each close of `dates`: the last snapshot on or before the day, drifted with the segments'
    returns since (buy and hold), or before the first snapshot, the first one rolled back with the returns between
    the day and it. w_s(t) ∝ w_s(a) · G_s(t) / G_s(a), with G the growth of 1 DKK. A day where a key with weight
    has no return between t and the snapshot is missing (NaN row). The basis per day: snapshot | back-drifted."""
    basis = pd.Series(None, index=dates, dtype=object)
    if snaps.empty or not len(dates):
        return pd.DataFrame(np.nan, index=dates, columns=snaps.columns), basis
    keys = list(snaps.columns)
    r = returns.reindex(index=dates, columns=keys)
    known = r.notna()
    grow = (1 + r.fillna(0.0)).cumprod()   # zero: a gap is marked through `known` below, never used as a 0 % return
    gaps = (~known).astype(int).cumsum()   # how many missing returns each key has had up to each day
    out = pd.DataFrame(np.nan, index=dates, columns=keys)
    for i, day in enumerate(dates):
        prior = snaps.index[snaps.index <= day]
        anchor = prior[-1] if len(prior) else snaps.index[0]
        a = int(dates.searchsorted(anchor, side="right")) - 1   # the last close on or before the snapshot
        w0 = snaps.loc[anchor]
        if a < 0:                          # a snapshot before the calendar starts: no growth to use
            continue
        lo, hi = sorted((a, i))
        held = w0 > 0
        if ((gaps.iloc[hi] - gaps.iloc[lo])[held] > 0).any():
            continue
        w = w0 * grow.iloc[i] / grow.iloc[a]
        out.iloc[i] = (w / w.sum()).to_numpy()
        basis.iloc[i] = "snapshot" if len(prior) else "back-drifted"
    return out, basis


def currency_mix(history: pd.DataFrame, dim: str, day: pd.Timestamp) -> dict[str, dict[str, float]]:
    """Each segment's currency shares in ACWI ({segment: {currency: share}}), from the last snapshot on or before
    `day` (the first one before any): the currency split of the benchmark's segment returns."""
    sub = history[history["dim"] == f"{dim}_currency"]
    if sub.empty:
        return {}
    dates = sorted(pd.to_datetime(sub["asof"].unique()))
    prior = [d for d in dates if d <= day]
    pick = (prior[-1] if prior else dates[0]).date().isoformat()
    out: dict[str, dict[str, float]] = {}
    for key, w in sub[sub["asof"] == pick][["key", "weight"]].itertuples(index=False):
        seg, ccy = str(key).split("|", 1)
        out.setdefault(seg, {})[ccy] = float(w)
    return {s: {c: v / sum(m.values()) for c, v in m.items()} for s, m in out.items() if sum(m.values()) > 0}
