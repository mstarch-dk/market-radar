"""Inputs the app and the studies choose the same way: which tickers get stop / take-profit levels, and which
indicator groups vote in the regime. My holdings (mine.py), the dashboard and the point-in-time replay
(backtest/pit.py) all read them from here."""
from __future__ import annotations

import pandas as pd

from .. import external, universe, userstore
from ..config import settings


def level_universe(etfs: set[str], analyst_hist: pd.DataFrame | None = None) -> set[str]:
    """Tickers that get stop / take-profit levels: stocks (a sector from Yahoo, or in a stock group) and the
    sector/theme funds in `etfs` (level_etfs)."""
    ah = external.load_analyst() if analyst_hist is None else analyst_hist
    equity = set()
    if not ah.empty and "sector" in ah:
        latest = ah.sort_values("fetched").groupby("ticker").last()
        equity = set(latest.index[latest["sector"].fillna("").astype(str).str.strip() != ""])
    return equity | {t for g in universe.stock_groups(offline=True).values() for t in g} | set(etfs)


def level_etfs(cfg: dict) -> set[str]:
    """Sector/theme ETFs (and UCITS twins) that get stop levels; broad region funds don't."""
    return {t for i in universe.etfs() if i.group != "regions" for t in (i.ticker, i.ucits) if t} | set(cfg.get("include") or [])


def effective_votes() -> dict[str, bool]:
    """Which indicator groups count in the regime vote: the defaults in settings.yaml, then your choice."""
    votes = {k: bool(v) for k, v in (settings()["regime"].get("votes") or {}).items()}
    chosen = userstore.meta_get("regime_votes") or {}
    return votes | {k: bool(v) for k, v in chosen.items() if k in votes}
