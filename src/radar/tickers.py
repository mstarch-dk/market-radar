"""A compact summary of every ticker the radar tracks (stocks, ETFs, holdings, watchlist), for the web app's
hover cards and ownership markers. Market numbers come from the price store and the last dashboard; they are
cached until either changes. `my_status` is merged on every call so watchlist edits show at once."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from . import dashboard, universe
from .paths import CACHE
from .portfolios import trades
from .sources import tracked

if TYPE_CHECKING:
    from .market import Market

_cache: tuple[tuple, list[dict]] | None = None


def reset() -> None:
    """Forget the cached ticker list."""
    global _cache
    _cache = None


def _cached_currencies(tickers: list[str]) -> dict[str, str | None]:
    """Quote currencies from the local cache only (no Yahoo lookups on a hover)."""
    f = CACHE / "currencies.csv"
    cached = dict(pd.read_csv(f).values) if f.exists() else {}
    return {t: cached.get(t) for t in tickers}


def _ret(s: pd.Series, n: int) -> float | None:
    return float(s.iloc[-1] / s.iloc[-1 - n] - 1) if len(s) > n else None


def _market_rows(market: Market) -> list[dict]:
    closes = market.closes
    groups = tracked.stock_groups(offline=True)
    labels = tracked.stock_group_labels()
    etfs = tracked.etfs()
    etf_label = tracked.etf_group_labels()
    group_of: dict[str, tuple[str, str]] = {}
    for key, ts in groups.items():
        for t in ts:
            group_of.setdefault(t, ("stock", labels.get(key, key)))
    for e in etfs:
        for t in filter(None, (e.ticker, e.ucits)):
            group_of.setdefault(t, ("etf", etf_label.get(e.group, e.group)))
    h = trades.holdings()
    symbols = sorted((set(group_of) | set(h["symbol"].dropna()) | {tracked.benchmark()}) & set(closes.columns))

    d = dashboard.load() or {}
    quadrant = {}
    for g in (d.get("rotation") or {}).get("groups", []):
        for r in g["rows"]:
            quadrant[r["ticker"]] = r["quadrant"]
            if r.get("ucits"):
                quadrant[r["ucits"]] = r["quadrant"]
    lead = market.leaders()
    score = dict(zip(lead["ticker"], lead["score"]))
    names = universe.names(symbols)
    ccy = _cached_currencies(symbols)
    weekly = closes[symbols].resample("W-FRI").last().iloc[-27:]

    rows = []
    for t in symbols:
        s = closes[t].dropna()
        if s.empty:
            continue
        w = weekly[t].dropna()
        kind, group = group_of.get(t, (None, None))
        sc = score.get(t)
        rows.append({
            "symbol": t, "name": names.get(t), "kind": kind, "group": group, "currency": ccy.get(t),
            "last": float(s.iloc[-1]), "change_1d": _ret(s, 1), "r1m": _ret(s, 21), "r3m": _ret(s, 63),
            "score": None if sc is None or pd.isna(sc) else float(sc), "quadrant": quadrant.get(t),
            "spark": [float(v) for v in (100 * w / w.iloc[0]).values] if len(w) > 1 else [],
            "asof": s.index[-1].date().isoformat(),
        })
    return rows


def summary(market: Market) -> list[dict]:
    """One row per tracked symbol; `market` is a profile.Market."""
    global _cache
    p = dashboard.path()
    key = (market.mtime, id(market), p.stat().st_mtime if p.exists() else None)
    if _cache is None or _cache[0] != key:
        _cache = (key, _market_rows(market))
    h = trades.holdings()
    status = dict(zip(h["symbol"], h["status"])) if not h.empty else {}
    rows = [r | {"my_status": status.get(r["symbol"])} for r in _cache[1]]
    known = {r["symbol"] for r in rows}
    # a holding or watchlist symbol without prices yet is still listed, with nothing but its status
    rows += [{"symbol": s, "name": None, "kind": None, "group": None, "currency": None, "last": None, "change_1d": None,
              "r1m": None, "r3m": None, "score": None, "quadrant": None, "spark": [], "asof": None, "my_status": st}
             for s, st in status.items() if s not in known]
    return rows
