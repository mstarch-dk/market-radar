"""What you hold and what it is exposed to: the book in DKK, sector ETFs looked through, sector / region /
currency per name, and exposures against ACWI's own weights."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .. import money, tracked, trades, universe
from ..config import universe_config
from . import pricing, rules


def book(market, prices: pricing.Prices, portfolio_ids: list[int]) -> pd.DataFrame:
    """Holdings of these portfolios valued at the last close in DKK: symbol, quantity, price, rate, value_dkk
    (None when the price or rate is unknown)."""
    tx = trades.transactions(portfolio_ids)
    pos, _ = trades.positions(tx)
    pos = pos[pos["status"] == "holding"] if not pos.empty else pos
    rows = []
    for _, r in pos.iterrows():
        sym, qty = r["symbol"], float(r["quantity"])
        px, rate = prices.last_px(sym), prices.rate(sym)
        rows.append({"symbol": sym, "quantity": qty, "price": px, "rate": rate,
                     "value_dkk": qty * px * rate if px is not None and rate is not None else None})
    return pd.DataFrame(rows, columns=["symbol", "quantity", "price", "rate", "value_dkk"])


def _sector_etf_map() -> dict[str, str]:
    """Sector ETF ticker -> its sector (universe.yaml sector_etfs), for look-through of held sector funds."""
    out = {}
    for region in (universe_config().get("sector_etfs") or {}).values():
        for sec, t in region.items():
            if isinstance(t, str):
                out[t] = sec
    return out


def look_through() -> set[str]:
    """Tickers counted with ACWI's own weights: ACWI, its UCITS share classes, the filler and broad world funds
    (settings propose.look_through)."""
    f = rules.cfg().get("etf_filler") or {}
    named = {tracked.benchmark(), (universe_config().get("benchmark") or {}).get("ucits"), f.get("ticker"), f.get("model"),
             *(rules.cfg().get("look_through") or [])}
    return {t for t in named if t is not None}


def info(tickers, prices: pricing.Prices) -> pd.DataFrame:
    """sector, region and currency per ticker (funds: a sector fund's sector, else '(fund)')."""
    from ..universe import region_for

    tickers = list(dict.fromkeys(tickers))
    if not tickers:
        return pd.DataFrame(columns=["sector", "region", "currency"])
    prices.preload(tickers)
    sec = universe.sectors(tickers)
    etf_sec = _sector_etf_map()
    funds = {e.ticker for e in tracked.etfs()} | look_through()
    rows = {}
    for t in tickers:
        s = sec["sector"].get(t) if t in sec.index else None
        s = s if isinstance(s, str) and s else None
        if t in funds or s is None:
            s = etf_sec.get(t, s or "(fund)")
        rows[t] = {"sector": s, "region": region_for(t), "currency": prices.ccy(t) or "?"}
    out = pd.DataFrame.from_dict(rows, orient="index")
    out.loc[out["currency"] == money.PENCE, "currency"] = money.main_unit(money.PENCE)
    return out


DIMS = ("sector", "region", "currency")


def annotate(df: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """`df` with its sector, region and currency columns taken from `meta` (info())."""
    return df.drop(columns=[x for x in DIMS if x in df]).join(meta[list(DIMS)])


def exposures(values: dict[str, float], meta: pd.DataFrame, acwi: dict | None) -> dict:
    """Weights by sector, region and currency of DKK `values` (ACWI look-through), and active weights vs ACWI."""
    lt = look_through()
    total = sum(v for v in values.values() if v)
    weights: dict[str, dict[str, float]] = {d: {} for d in DIMS}
    out: dict[str, Any] = {"total_dkk": total, "weights": weights, "active": None,
                           "note": None if acwi else "ACWI's own weights are unknown (no holdings file): active weights not shown"}
    if total <= 0:
        return out
    for t, v in values.items():
        if not v:
            continue
        if t in lt:
            for d in DIMS:
                if acwi:
                    for k, w in acwi[d].items():
                        weights[d][k] = weights[d].get(k, 0.0) + v * w / total
                else:
                    weights[d]["ACWI (look-through unknown)"] = weights[d].get(
                        "ACWI (look-through unknown)", 0.0) + v / total
            continue
        m = meta.loc[t] if t in meta.index else None
        for d in DIMS:
            k = (m[d] if m is not None else None) or "?"
            weights[d][k] = weights[d].get(k, 0.0) + v / total
    if acwi:
        out["active"] = {d: {k: weights[d].get(k, 0.0) - acwi[d].get(k, 0.0)
                             for k in set(weights[d]) | set(acwi[d])} for d in DIMS}
    return out
