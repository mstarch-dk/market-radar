"""Point-in-time panels of the stock universe (row D uses only data up to D) and the calendar the studies and the
proposals trade on: month-end formation dates and the fill session after a signal."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .. import universe
from ..config import settings
from ..signals import momentum
from ..signals.risk import TRADING_DAYS
from .score import COMPONENTS, mean_pct


@dataclass
class Panels:
    closes: pd.DataFrame                         # adjusted closes of the stock universe (listing currency)
    dkk: pd.DataFrame                            # the same in DKK (a column is NaN without a known rate)
    m: dict[str, pd.DataFrame]                   # momentum.metrics_panel
    vol: pd.DataFrame                            # 63-session realised volatility, annualised
    group: pd.Series                             # ticker -> stock group
    sector: pd.Series                            # ticker -> today's Yahoo sector ("" unknown)
    sessions: pd.DatetimeIndex                   # benchmark calendar
    bench_dkk: pd.Series
    volumes: pd.DataFrame | None = None          # traded volume (gaps forward-filled, as ingest.wide)
    fund: object | None = None                   # backtest.fund.FundPIT, for the fundamentals signals


def panels(market, tickers: list[str] | None = None) -> Panels:
    groups = universe.stock_groups(offline=True)
    group: dict[str, str] = {}
    for g, ts in groups.items():
        for t in ts:
            group.setdefault(t, g)
    stocks = sorted(t for t in (tickers or group) if t in market.closes.columns)
    c = market.closes[stocks]
    m = momentum.metrics_panel(market.closes, stocks, settings()["momentum"]["min_history_days"])
    vol = np.log(c).diff().rolling(63, min_periods=32).std() * math.sqrt(TRADING_DAYS)
    ccy = universe.currencies(stocks)
    fx_cache: dict = {}
    dkk = {}
    for t in stocks:
        k = ccy.get(t)
        if k not in fx_cache:
            fx_cache[k] = universe.fx_to_dkk(market.closes, k)
        fx = fx_cache[k]
        dkk[t] = c[t] * fx.reindex(c.index) if fx is not None else pd.Series(np.nan, index=c.index)
    from .. import performance

    sec = universe.sectors(stocks)["sector"].astype(str)
    return Panels(c, pd.DataFrame(dkk, index=c.index), m, vol, pd.Series(group).reindex(stocks), sec,
                  market.closes[universe.benchmark()].dropna().index, performance.bench_dkk(market),
                  market.volumes.reindex(columns=stocks) if getattr(market, "volumes", None) is not None else None)


def formation_dates(sessions: pd.DatetimeIndex, since=None) -> list[pd.Timestamp]:
    s = sessions.to_series()
    me = s.groupby(sessions.to_period("M")).max()
    me = me[me.index < sessions[-1].to_period("M")]           # the current month isn't over
    out = [pd.Timestamp(d) for d in me]
    return [d for d in out if since is None or d >= pd.Timestamp(since)]


def fill_session(sessions: pd.DatetimeIndex, day: pd.Timestamp, fill: str) -> int | None:
    i = int(sessions.searchsorted(day))
    if i >= len(sessions) or sessions[i] != day:
        i -= 1
    i += 1 if fill == "next" else 0
    return i if 0 <= i < len(sessions) else None


def score_at(p: Panels, day: pd.Timestamp) -> pd.Series:
    """The momentum score of every name on day D, pooled over the universe given, from data up to D."""
    return mean_pct(pd.DataFrame({c: p.m[c].loc[day] for c in COMPONENTS}))


def within(keys: pd.Series, df: pd.DataFrame, min_names: int = 2) -> pd.Series:
    """`mean_pct` of the columns within each group of `keys` (missing for a group with fewer than `min_names` complete
    rows: no peers to rank against)."""
    out = pd.Series(np.nan, index=df.index)
    for _, idx in keys.reindex(df.index).groupby(keys.reindex(df.index)).groups.items():
        sub = df.loc[idx]
        if sub.dropna().shape[0] >= min_names:
            out.loc[idx] = mean_pct(sub)
    return out


def ranked(p: Panels, day: pd.Timestamp) -> pd.DataFrame:
    """Every stock with a price on `day`, by score (best first; ties by ticker), with the inputs known then. What
    the hindsight baskets and the proposals (live and in their study) rank on."""
    last = p.m["last"].loc[day]
    df = pd.DataFrame({
        "score": score_at(p, day),
        "score_region": within(p.group, pd.DataFrame({c: p.m[c].loc[day] for c in COMPONENTS})),
        **{c: p.m[c].loc[day] for c in ("r1m", "r3m", "r6m", "r12_1", "from_high", "trend_ok", "above200")},
        "vol": p.vol.loc[day], "close": last, "group": p.group, "sector": p.sector,
        "dkk": p.dkk.loc[day].notna(),
    })[last.notna()]
    df.index.name = "ticker"
    df = df.reset_index().sort_values(["score", "ticker"], ascending=[False, True], na_position="last", kind="stable")
    df["rank"] = np.where(df["score"].notna(), np.arange(1, len(df) + 1), np.nan)
    df["id"] = [f"C{i:03d}" for i in range(1, len(df) + 1)]
    return df.reset_index(drop=True)
