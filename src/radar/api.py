"""Local web API for the radar (`radar serve`): ticker profiles, chart series, search, the dashboard readings
from the last `radar run`, the live holdings table and watchlist edits, plus the built web app from web/dist.
Binds to 127.0.0.1 only; there is no authentication."""
from __future__ import annotations

import threading
from datetime import date

import pandas as pd

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import dashboard, mine, profile, tickers, universe, userstore
from .api_models import (
    AppContext, CoverageView, MeView, MomentumView, PositioningView, Profile, RegimeView, RotationView, SearchHit,
    Series, TickerSummary, WatchState,
)
from .config import settings
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


# ---------------- dashboard: the readings of the last `radar run` ----------------

def _dashboard() -> dict:
    d = dashboard.load()
    if d is None:
        raise HTTPException(503, "No dashboard yet: run `uv run radar run` (or `radar report`) first.")
    return d


def _view(key: str) -> dict:
    """One dashboard section, with how old its data is: stale once older than the price limit in settings."""
    d = _dashboard()
    age = (date.today() - date.fromisoformat(d["asof"])).days
    limit = settings()["coverage"]["max_age"]["prices"]
    return {"asof": d["asof"], "generated": d["generated"], "age_days": age, "stale": age > limit, **d[key]}


@app.get("/api/regime", response_model=RegimeView)
def get_regime() -> dict:
    return _view("regime")


@app.get("/api/rotation", response_model=RotationView)
def get_rotation() -> dict:
    return _view("rotation")


@app.get("/api/momentum", response_model=MomentumView)
def get_momentum() -> dict:
    return _view("momentum")


@app.get("/api/positioning", response_model=PositioningView)
def get_positioning() -> dict:
    return _view("positioning")


@app.get("/api/coverage", response_model=CoverageView)
def get_coverage() -> dict:
    return _view("coverage")


# ---------------- the user's holdings and watchlist ----------------

@app.get("/api/me", response_model=MeView)
def get_me() -> dict:
    """Holdings, watchlist and sold positions, computed now from the current prices (so watchlist edits show
    at once). Quadrants and the regime used for the stop levels come from the last `radar run`."""
    d = _dashboard()
    rot_rows = [r for g in d["rotation"]["groups"] for r in g["rows"]]
    regime_label = d["regime"]["overall"]["label"]
    with _lock:
        m = market()
        rows = mine.table(m.closes, m.highs, m.lows, m.volumes, m.raw_closes(), m.leaders(), rot_rows, regime_label,
                          settings())
        asof = m.closes[universe.benchmark()].dropna().index[-1].date().isoformat()
    return {"asof": asof, "generated": pd.Timestamp.now().isoformat(timespec="seconds"), "regime": regime_label,
            "rows": rows}


@app.get("/api/tickers", response_model=list[TickerSummary])
def get_tickers() -> list[dict]:
    """Every tracked ticker in brief (price, returns, score or quadrant, a 6-month sparkline, your status), for
    hover cards and ownership markers."""
    with _lock:
        return tickers.summary(market())


def _status(symbol: str) -> str | None:
    h = universe.holdings()
    st = h.loc[h["symbol"] == symbol, "status"]
    return st.iloc[0] if len(st) else None


@app.put("/api/watchlist/{symbol}", response_model=WatchState)
def watch(symbol: str) -> dict:
    """Put a symbol on the watchlist; it joins the daily price and analyst updates. Unknown symbols are 404."""
    global _market
    symbol = _symbol(symbol)
    with _lock:
        try:
            _market = profile.ensure_prices(symbol, market())
        except profile.TickerNotFound as e:
            raise HTTPException(404, str(e)) from e
    if _status(symbol) == "holding":
        return {"symbol": symbol, "my_status": "holding"}
    userstore.watch(symbol)
    return {"symbol": symbol, "my_status": _status(symbol)}


@app.delete("/api/watchlist/{symbol}", response_model=WatchState)
def unwatch(symbol: str) -> dict:
    """Take a symbol off the watchlist. A holding can't be removed (409): that comes from the Yahoo import."""
    symbol = _symbol(symbol)
    st = _status(symbol)
    if st == "holding":
        raise HTTPException(409, f"{symbol} is a holding, not a watchlist entry; holdings come from the Yahoo import.")
    if st == "watch":
        userstore.unwatch(symbol)
    return {"symbol": symbol, "my_status": _status(symbol)}


if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        """The web app; every non-API path is a client-side route."""
        if path.startswith("api/"):
            raise HTTPException(404)
        f = WEB_DIST / path
        return FileResponse(f if path and f.is_file() else WEB_DIST / "index.html")
