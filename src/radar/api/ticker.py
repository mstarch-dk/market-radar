"""One ticker: its profile and chart series, search, and the start page's context."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import dashboard, net, ops, profile, universe
from ..api_models import (
    AppContext,
    Profile,
    SearchHit,
    Series,
)
from ..model import inputs
from ..portfolios import trades
from . import state
from .common import (
    ticker_symbol,
)

router = APIRouter()


@router.get("/api/ticker/{symbol}", response_model=Profile)
def get_profile(symbol: str, refresh: bool = False) -> dict:
    symbol = ticker_symbol(symbol)
    with state.lock:
        state.ensure(symbol, refresh=refresh)
        return profile.build(symbol, state.market(), refresh=refresh)


@router.get("/api/ticker/{symbol}/series", response_model=Series)
def get_series(symbol: str, days: int = Query(756, ge=20, le=5000)) -> dict:
    symbol = ticker_symbol(symbol)
    with state.lock:
        state.ensure(symbol)
        return profile.series(symbol, state.market(), days)


@router.get("/api/search", response_model=list[SearchHit])
def search(q: str = Query(..., min_length=1, max_length=60)) -> list[dict]:
    """Yahoo's symbol search (stocks and funds), with tracked names first."""
    tracked = set(universe.all_price_tickers(offline=True))
    try:
        with ops.context(source="search"):
            quotes = net.yf().Search(q, max_results=10, news_count=0).quotes
    except Exception as e:
        raise HTTPException(502, f"Yahoo search failed: {type(e).__name__}") from e
    hits = [{"symbol": x["symbol"], "name": x.get("longname") or x.get("shortname"),
             "exchange": x.get("exchDisp") or x.get("exchange"), "quote_type": x.get("quoteType"),
             "tracked": x["symbol"] in tracked}
            for x in quotes if x.get("symbol") and x.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND")]
    return sorted(hits, key=lambda h: not h["tracked"])


@router.get("/api/context", response_model=AppContext)
def context() -> dict:
    """Regime and your holdings and watchlist, for the start page."""
    h = trades.holdings()
    h = h[h["status"].isin(["holding", "watch"])] if not h.empty else h
    names = universe.names(list(h["symbol"])) if not h.empty else {}
    return {"regime": inputs.current_regime(dashboard.load()),
            "tickers": [{"symbol": s, "name": names.get(s), "status": st} for s, st in zip(h["symbol"], h["status"])]}
