"""Inputs the app and the studies choose the same way: which tickers get stop / take-profit levels, which
indicator groups vote in the regime, and the regime of the last `radar run` voted with that choice. My holdings
(mine.py), the dashboard, profiles, proposals and the point-in-time replay (backtest/pit.py) all read them from
here."""
from __future__ import annotations

import json
from typing import NamedTuple

import pandas as pd

from .. import external, universe, userstore
from ..config import settings
from ..paths import REPORTS
from ..signals import regime

DASHBOARD_FILE = "dashboard.json"


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


class Regime(NamedTuple):
    overall: dict                # label, net, the votes counted
    indicators: list[dict]       # each indicator with its vote


def regime_now(d: dict) -> Regime:
    """The stored indicators of a dashboard.json, voted again with the current choice of groups (a switch on the
    Regime page takes effect at once, without a new `radar run`)."""
    inds = [dict(i) for i in d["regime"]["indicators"]]
    return Regime(regime.overall(inds, effective_votes()), inds)


def current_regime(d: dict | None = None) -> dict:
    """The overall regime of the last `radar run`, voted with your current choice of groups: what the start page,
    profiles, the stop levels and proposals all use. `d` is a loaded dashboard.json (default: read the file);
    label None before the first run."""
    if d is None:
        try:
            d = json.loads((REPORTS / DASHBOARD_FILE).read_text(encoding="utf-8"))
        except FileNotFoundError:
            d = None
    if d is None:
        return {"label": None, "asof": None}
    overall = regime_now(d).overall
    return {"label": overall["label"], "asof": d["asof"], "net": overall.get("net")}
