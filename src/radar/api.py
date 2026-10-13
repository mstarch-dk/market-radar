"""Local web API for the radar (`radar serve`): ticker profiles, chart series and search, plus the built
web app from web/dist. Binds to 127.0.0.1 only; there is no authentication."""
from __future__ import annotations

import threading

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import profile, universe
from .api_models import AppContext, Profile, SearchHit, Series
from .config import ROOT

WEB_DIST = ROOT / "web" / "dist"

app = FastAPI(title="Market Radar", version="0.1.0")
_lock = threading.Lock()  # one price download / market reload at a time
_market: profile.Market | None = None


def market() -> profile.Market:
    """The price store, reloaded when `radar update` has written a new one."""
    global _market
    if _market is None or _market.stale():
        _market = profile.Market.load()
    return _market


def _symbol(s: str) -> str:
    return s.strip().upper()


@app.get("/api/ticker/{symbol}", response_model=Profile)
def get_profile(symbol: str, refresh: bool = False) -> dict:
    global _market
    symbol = _symbol(symbol)
    with _lock:
        try:
            _market = profile.ensure_prices(symbol, market())
            return profile.build(symbol, _market, refresh=refresh)
        except profile.TickerNotFound as e:
            raise HTTPException(404, str(e)) from e


@app.get("/api/ticker/{symbol}/series", response_model=Series)
def get_series(symbol: str, days: int = Query(756, ge=20, le=5000)) -> dict:
    global _market
    symbol = _symbol(symbol)
    with _lock:
        try:
            _market = profile.ensure_prices(symbol, market())
            return profile.series(symbol, _market, days)
        except profile.TickerNotFound as e:
            raise HTTPException(404, str(e)) from e


@app.get("/api/search", response_model=list[SearchHit])
def search(q: str = Query(..., min_length=1, max_length=60)) -> list[dict]:
    """Yahoo's symbol search (stocks and funds), with tracked names first."""
    import yfinance as yf

    tracked = set(universe.all_price_tickers(offline=True))
    try:
        quotes = yf.Search(q, max_results=10, news_count=0).quotes
    except Exception as e:
        raise HTTPException(502, f"Yahoo search failed: {type(e).__name__}") from e
    hits = [{"symbol": x["symbol"], "name": x.get("longname") or x.get("shortname"),
             "exchange": x.get("exchDisp") or x.get("exchange"), "quote_type": x.get("quoteType"),
             "tracked": x["symbol"] in tracked}
            for x in quotes if x.get("symbol") and x.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND")]
    return sorted(hits, key=lambda h: not h["tracked"])


@app.get("/api/context", response_model=AppContext)
def context() -> dict:
    """Regime and the user's holdings and watchlist, for the start page."""
    h = universe.holdings()
    h = h[h["status"].isin(["holding", "watch"])] if not h.empty else h
    names = universe.names(list(h["symbol"])) if not h.empty else {}
    return {"regime": profile._regime(),
            "tickers": [{"symbol": s, "name": names.get(s), "status": st} for s, st in zip(h["symbol"], h["status"])]}


if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        """The web app; every non-API path is a client-side route."""
        if path.startswith("api/"):
            raise HTTPException(404)
        f = WEB_DIST / path
        return FileResponse(f if path and f.is_file() else WEB_DIST / "index.html")
