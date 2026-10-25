"""What you hold and what it is exposed to: the book in DKK, each name's class (world fund, sector fund, other
fund, stock), sector / region / currency per name with funds looked through where the data allows, and exposures
against ACWI's own weights with their coverage."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from .. import money, universe
from ..config import typed, universe_config
from ..sources import external, tracked
from . import trades
from .prices import Prices

if TYPE_CHECKING:
    from ..market import Market


def holdings_book(market: Market, prices: Prices, portfolio_ids: list[int]) -> pd.DataFrame:
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


def _sector_etf_map() -> dict[str, tuple[str, str]]:
    """Sector ETF ticker -> (its sector, its region key) from universe.yaml sector_etfs, for held sector funds."""
    out = {}
    for region, secs in (universe_config().get("sector_etfs") or {}).items():
        for sec, t in secs.items():
            if isinstance(t, str):
                out[t] = (sec, region)
    return out


def look_through() -> set[str]:
    """Tickers counted with ACWI's own weights: ACWI, its UCITS share classes, the filler and broad world funds
    (settings risk.world_funds)."""
    c = typed()
    named = {tracked.benchmark(), (universe_config().get("benchmark") or {}).get("ucits"), c.propose.etf_filler.ticker,
             c.propose.etf_filler.model, *c.risk.world_funds}
    return {t for t in named if t is not None}


# Keys that are not a real sector, region or currency: they count against coverage and never as active weight
WORLD = "fund: world (ACWI's weights)"
NOT_LOOKED_THROUGH = "fund: not looked through"
FUND_OTHER = "fund: other"                  # the part of a fund's sector weights that Yahoo leaves unnamed
UNKNOWN = "?"
ACWI_UNKNOWN = "ACWI (look-through unknown)"
UNCOVERED = frozenset({NOT_LOOKED_THROUGH, FUND_OTHER, UNKNOWN, ACWI_UNKNOWN})
CLASSES = ("world", "sector_fund", "fund_sectors", "fund", "stock", "unknown")


def _fund_sectors(raw: dict | None) -> list[tuple[str, float]]:
    """A cached fund detail's sector weights, largest first (the names Yahoo uses for stocks)."""
    if not raw or (raw.get("info") or {}).get("quoteType") not in ("ETF", "MUTUALFUND"):
        return []
    look = external.parse_fund(raw.get("fund") or {}, raw.get("info") or {})
    return [(x["sector"], float(x["weight"])) for x in look["sector_weights"] if x["weight"]]


def ticker_meta(tickers, prices: Prices) -> pd.DataFrame:
    """Per ticker its class, sector, region and currency, and for funds the sector weights to spread over.

    world: counted with ACWI's weights. sector_fund: a universe.yaml sector ETF (its sector, and its region; USD
    for the US map), or a fund with one sector at 50 % or more in its cached Yahoo detail (the detail's weights).
    fund_sectors: another fund whose detail has sector weights. fund: a fund without them. stock: a stock with a
    known sector, its listing region and quote currency. unknown: neither a known fund nor a stock with a sector.
    A fund is looked through or labelled 'fund: not looked through': never filed under where it is listed. The
    fund detail is read from the cache only (no request), and its date is in `detail_asof`."""
    cols = ["class", "sector", "region", "currency", "sector_weights", "detail_asof"]
    tickers = list(dict.fromkeys(tickers))
    if not tickers:
        return pd.DataFrame(columns=cols)
    prices.preload(tickers)
    sec = universe.sectors(tickers)
    etf_sec = _sector_etf_map()
    lt = look_through()
    tracked_funds = {x for e in tracked.etfs() for x in (e.ticker, e.ucits) if x}
    rows = {}
    for t in tickers:
        s = sec["sector"].get(t) if t in sec.index else None
        s = s if isinstance(s, str) and s else None
        row: dict[str, Any] = {"sector_weights": None, "detail_asof": None}
        if t in lt:
            rows[t] = row | {"class": "world", "sector": WORLD, "region": WORLD, "currency": WORLD}
            continue
        if t in etf_sec:
            sector, region = etf_sec[t]
            rows[t] = row | {"class": "sector_fund", "sector": sector, "region": region,
                             "currency": "USD" if region == "us" else NOT_LOOKED_THROUGH}
            continue
        raw, _, fetched = external.cached_detail(t) if t in tracked_funds or s is None else (None, "", None)
        is_fund = t in tracked_funds or (raw or {}).get("info", {}).get("quoteType") in ("ETF", "MUTUALFUND")
        if not is_fund:
            ccy = prices.ccy(t)
            rows[t] = row | ({"class": "stock", "sector": s, "region": universe.region_for(t),
                              "currency": money.main_unit(ccy) if ccy == money.PENCE else ccy or UNKNOWN}
                             if s else {"class": "unknown", "sector": UNKNOWN, "region": UNKNOWN, "currency": UNKNOWN})
            continue
        weights = _fund_sectors(raw)
        row |= {"region": NOT_LOOKED_THROUGH, "currency": NOT_LOOKED_THROUGH,
                "detail_asof": fetched[:10] if fetched else None}
        if weights:
            top, w = weights[0]
            rows[t] = row | {"class": "sector_fund" if w >= 0.5 else "fund_sectors",
                             "sector": top if w >= 0.5 else NOT_LOOKED_THROUGH, "sector_weights": dict(weights)}
        else:
            rows[t] = row | {"class": "fund", "sector": NOT_LOOKED_THROUGH}
    return pd.DataFrame.from_dict(rows, orient="index")[cols]


DIMS = ("sector", "region", "currency")


def annotate(df: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """`df` with its sector, region and currency columns taken from `meta` (ticker_meta())."""
    return df.drop(columns=[x for x in DIMS if x in df]).join(meta[list(DIMS)])


def exposures(values: dict[str, float], meta: pd.DataFrame, acwi: dict | None) -> dict:
    """Weights by sector, region and currency of DKK `values` (world funds with ACWI's weights, funds by their
    sector weights), the coverage per dimension (the share of value with a real key, not 'fund: not looked
    through' or unknown), and active weights vs ACWI for the real keys only."""
    lt = look_through()
    total = sum(v for v in values.values() if v)
    weights: dict[str, dict[str, float]] = {d: {} for d in DIMS}
    out: dict[str, Any] = {"total_dkk": total, "weights": weights, "coverage": {d: None for d in DIMS}, "active": None,
                           "note": None if acwi else "ACWI's own weights are unknown (no holdings file): active weights not shown"}
    if total <= 0:
        return out

    def add(d: str, k: str, v: float) -> None:
        weights[d][k] = weights[d].get(k, 0.0) + v / total

    for t, v in values.items():
        if not v:
            continue
        if t in lt:
            for d in DIMS:
                if acwi:
                    for k, w in acwi[d].items():
                        add(d, k, v * w)
                else:
                    add(d, ACWI_UNKNOWN, v)
            continue
        m = meta.loc[t] if t in meta.index else None
        for d in DIMS:
            spread = m.get("sector_weights") if m is not None and d == "sector" else None
            if isinstance(spread, dict) and spread:
                for k, w in spread.items():
                    add(d, k, v * w)
                rest = 1 - sum(spread.values())
                if rest > 1e-9:
                    add(d, FUND_OTHER, v * rest)
            else:
                add(d, (m[d] if m is not None else None) or UNKNOWN, v)
    out["coverage"] = {d: max(0.0, 1 - sum(w for k, w in weights[d].items() if k in UNCOVERED)) for d in DIMS}
    if acwi:
        out["active"] = {d: {k: weights[d].get(k, 0.0) - acwi[d].get(k, 0.0)
                             for k in (set(weights[d]) | set(acwi[d])) - UNCOVERED} for d in DIMS}
    return out
