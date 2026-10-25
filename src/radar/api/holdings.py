"""Your holdings and watchlist, live from the current prices."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException

from .. import agenda, mine, universe, userstore
from ..api_models import (
    MeView,
    TickerSummary,
    WatchState,
)
from ..config import settings, typed
from ..model import inputs
from ..reporting import dashboard, tickers
from ..sources import tracked, valuation
from . import state
from .common import (
    PortfolioQ,
    ScopeQ,
    TagQ,
    dashboard_or_503,
    my_status,
    selection,
    ticker_symbol,
)

router = APIRouter()


# ---------------- your holdings and watchlist ----------------

@router.get("/api/me", response_model=MeView)
def get_me(portfolio: list[int] | None = PortfolioQ, tag: list[str] | None = TagQ, scope: str | None = ScopeQ) -> dict:
    """Holdings, watchlist and sold positions, computed now from the current prices (so watchlist edits show
    at once), pooled over the chosen portfolios (default: your real ones). Quadrants and the regime used for
    the stop levels come from the last `radar run`."""
    sel = selection(portfolio, tag, scope)
    d = dashboard_or_503()
    regime_label = inputs.current_regime(d)["label"]
    with state.lock:
        m = state.market()
        rows = mine.live(m, d, sel, settings())
        asof = m.closes[tracked.benchmark()].dropna().index[-1].date()
        from ..fundamentals import context as fcontext

        fctx = fcontext.context(m.closes, m.raw_closes(), universe.tracked_stocks(), m.mtime)
    vctx = valuation.context()
    rows = agenda.with_earnings_flags(rows, vctx, asof, typed().calendar)
    rows = dashboard.with_fundamentals(dashboard.with_valuation(rows, vctx), fctx)
    return {"asof": asof.isoformat(), "generated": pd.Timestamp.now().isoformat(timespec="seconds"),
            "regime": regime_label, "rows": rows}


@router.get("/api/tickers", response_model=list[TickerSummary])
def get_tickers() -> list[dict]:
    """Every tracked ticker in brief (price, returns, score or quadrant, a 6-month sparkline, your status), for
    hover cards and ownership markers."""
    with state.lock:
        return tickers.summary(state.market())




@router.put("/api/watchlist/{symbol}", response_model=WatchState)
def watch(symbol: str) -> dict:
    """Put a symbol on the watchlist; it joins the daily price and analyst updates. Unknown symbols are 404."""
    symbol = ticker_symbol(symbol)
    state.ensure(symbol)
    if my_status(symbol) == "holding":
        return {"symbol": symbol, "my_status": "holding"}
    userstore.watch(symbol)
    return {"symbol": symbol, "my_status": my_status(symbol)}


@router.delete("/api/watchlist/{symbol}", response_model=WatchState)
def unwatch(symbol: str) -> dict:
    """Take a symbol off the watchlist. A holding can't be removed (409): it comes from your trades."""
    symbol = ticker_symbol(symbol)
    st = my_status(symbol)
    if st == "holding":
        raise HTTPException(409, f"{symbol} is a holding, not a watchlist entry; holdings come from your trades.")
    if st == "watch":
        userstore.unwatch(symbol)
    return {"symbol": symbol, "my_status": my_status(symbol)}
