"""Local web API for the radar (`radar serve`): ticker profiles, chart series, search, the dashboard readings
from the last `radar run`, the live holdings table and watchlist edits, plus the built web app from web/dist.
Binds to 127.0.0.1 only; there is no authentication."""
from __future__ import annotations

import datetime as dt
import tempfile
import threading
from pathlib import Path
from datetime import date

import pandas as pd

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import dashboard, mine, portfolio, profile, tickers, universe, updater, userstore
from .api_models import (
    AppContext, CoverageView, MeView, MomentumView, PositioningView, Profile, RegimeView, RotationView, SearchHit,
    Series, TickerSummary, WatchState, UpdateStatus, ImportResult,
    Account, AccountIn, PositionsView, PriceCheck, TxCheck, TxIn, TxResult, TxRow,
    ImportCommitResult, ImportPreview, ImportRecord, Preset,
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
    """Regime and your holdings and watchlist, for the start page."""
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


# ---------------- your holdings and watchlist ----------------

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
                          settings(), sessions=lambda s: m.bars(s)["close"])
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


# ---------------- refreshing data and importing a portfolio (no terminal needed) ----------------

@app.get("/api/update", response_model=UpdateStatus)
def update_status() -> dict:
    """The data refresh started from the app: status, log lines and price-download progress."""
    return updater.JOB.state


@app.post("/api/update", response_model=UpdateStatus)
def start_update() -> dict:
    """Start downloading new data and rebuilding the dashboard in the background (one at a time)."""
    if not updater.JOB.start():
        raise HTTPException(409, "An update is already running.")
    return updater.JOB.state


MAX_IMPORT_BYTES = 5_000_000


@app.post("/api/import", response_model=ImportResult)
async def import_portfolio(request: Request) -> dict:
    """Import a Yahoo Finance portfolio CSV (sent as the request body) as holdings, sold positions and watchlist.
    Replaces the previous import; watchlist edits made in the app are kept."""
    body = await request.body()
    if not body.strip():
        raise HTTPException(400, "The file is empty.")
    if len(body) > MAX_IMPORT_BYTES:
        raise HTTPException(413, "That file is too large for a portfolio export.")
    header = body.decode("utf-8-sig", errors="replace").splitlines()[0]
    cols = {c.strip().strip('"') for c in header.split(",")}
    if not {"Symbol", "Quantity"} <= cols:
        raise HTTPException(400, "This doesn't look like a Yahoo Finance portfolio export: it needs the columns "
                                 "Symbol and Quantity (Yahoo: My Portfolio → Export).")
    # a temporary copy: the import rewrites holdings.csv / transactions.csv only once the file has been read
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "yahoo_portfolio.csv"
        path.write_bytes(body)
        try:
            df, warnings = universe.import_yahoo_csv(str(path))
        except Exception as e:
            raise HTTPException(400, f"Couldn't read this Yahoo Finance export ({type(e).__name__}: {e}).") from e
    counts = df["status"].value_counts()
    return {"holdings": int(counts.get("holding", 0)), "sold": int(counts.get("sold", 0)),
            "watch": int(counts.get("watch", 0)), "warnings": {k: list(v) for k, v in warnings.items()}}


# ---------------- portfolio editor: transactions in the local store ----------------

def _tx_row(body: TxIn) -> dict:
    return {"symbol": _symbol(body.symbol), "date": body.date[:10], "type": body.type, "quantity": body.quantity,
            "price": body.price, "fee": body.fee or 0.0, "account": body.account or None, "note": body.note or None}


def _validated(row: dict, exclude_id: int | None) -> list[dict]:
    global _market
    with _lock:
        if row["symbol"]:
            try:
                _market = profile.ensure_prices(row["symbol"], market())
            except profile.TickerNotFound:
                pass                                               # validate() reports the unknown symbol
        return portfolio.validate(row, market(), exclude_id=exclude_id)


def _checked(body: TxIn, exclude_id: int | None = None) -> tuple[dict, list[dict]]:
    """The row and its issues; 422 with the issues when it can't be saved (errors, or unconfirmed warnings)."""
    row = _tx_row(body)
    issues = _validated(row, exclude_id)
    errors = [i for i in issues if i["level"] == "error"]
    if errors or (issues and not body.confirm):
        raise HTTPException(422, {"message": errors[0]["message"] if errors else "Please confirm the warnings.",
                                  "issues": issues})
    return row, issues


@app.get("/api/portfolio/transactions", response_model=list[TxRow])
def list_transactions(symbol: str | None = None, account: str | None = None) -> list[dict]:
    universe.ensure_migrated()
    return userstore.transactions(_symbol(symbol) if symbol else None, account)


@app.post("/api/portfolio/validate", response_model=TxCheck)
def check_transaction(body: TxIn, id: int | None = None) -> dict:
    """Issues, the effect on the position and the price check for a row being typed, without saving it."""
    universe.ensure_migrated()
    row = _tx_row(body)
    issues = _validated(row, id)
    with _lock:
        pc = portfolio.price_check(market(), row["symbol"], row["date"], row["price"]) \
            if row["symbol"] in market().closes.columns else None
    blocking = {i["field"] for i in issues if i["level"] == "error"} & {"symbol", "type", "date"}
    return {"issues": issues, "effect": None if blocking else portfolio.effect(row, exclude_id=id), "price": pc}


@app.post("/api/portfolio/transactions", response_model=TxResult)
def add_transaction(body: TxIn) -> dict:
    universe.ensure_migrated()
    row, issues = _checked(body)
    return {"tx": userstore.get_tx(userstore.add_tx(row)), "issues": issues}


@app.put("/api/portfolio/transactions/{tx_id}", response_model=TxResult)
def edit_transaction(tx_id: int, body: TxIn) -> dict:
    if not userstore.get_tx(tx_id):
        raise HTTPException(404, f"No transaction {tx_id}.")
    row, issues = _checked(body, exclude_id=tx_id)
    userstore.update_tx(tx_id, row)
    return {"tx": userstore.get_tx(tx_id), "issues": issues}


@app.delete("/api/portfolio/transactions/{tx_id}", response_model=TxRow)
def delete_transaction(tx_id: int) -> dict:
    """Delete one transaction; the response is the deleted row, which /restore puts back (undo)."""
    row = userstore.delete_tx(tx_id)
    if not row:
        raise HTTPException(404, f"No transaction {tx_id}.")
    return row


@app.post("/api/portfolio/transactions/restore", response_model=TxRow)
def restore_transaction(row: TxRow) -> dict:
    if userstore.get_tx(row.id):
        raise HTTPException(409, "That transaction is already there.")
    return userstore.get_tx(userstore.restore_tx(row.model_dump()))


@app.get("/api/portfolio/positions", response_model=PositionsView)
def get_positions() -> dict:
    with _lock:
        return portfolio.positions_view(market())


@app.get("/api/portfolio/price-check", response_model=PriceCheck)
def get_price_check(symbol: str, date: str, price: float | None = None) -> dict:
    global _market
    sym = _symbol(symbol)
    with _lock:
        try:
            _market = profile.ensure_prices(sym, market())
        except profile.TickerNotFound as e:
            raise HTTPException(404, str(e)) from e
        return portfolio.price_check(market(), sym, date, price)


@app.get("/api/portfolio/accounts", response_model=list[Account])
def get_accounts() -> list[dict]:
    return userstore.accounts()


@app.post("/api/portfolio/accounts", response_model=list[Account])
def save_account(body: AccountIn) -> list[dict]:
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "The account needs a name.")
    userstore.save_account(name, body.kind, body.note, body.old_name)
    return userstore.accounts()


@app.get("/api/portfolio/export.csv", response_class=Response)
def export_transactions() -> Response:
    """Every transaction as CSV (a backup you can keep, or open in a spreadsheet)."""
    universe.ensure_migrated()
    return Response(userstore.export_transactions_csv(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="transactions-{dt.date.today()}.csv"'})


# ---------------- importing trades from broker exports ----------------

def _has_prices(symbol: str) -> bool:
    """Make sure prices exist for `symbol` (downloads an untracked one); False if Yahoo has none."""
    global _market
    try:
        _market = profile.ensure_prices(symbol, market())
        return True
    except profile.TickerNotFound:
        return False


def _preview(body: bytes, filename: str, preset: str | None, mapping: str | None, symbols: str | None,
             account: str | None) -> dict:
    import json

    from . import importers

    if not body.strip():
        raise HTTPException(400, "The file is empty.")
    if len(body) > MAX_IMPORT_BYTES:
        raise HTTPException(413, "That file is too large for a transaction export.")
    try:
        with _lock:
            return importers.preview(body, filename, market, _has_prices, preset or None,
                                     json.loads(mapping) if mapping else None, account or None,
                                     json.loads(symbols) if symbols else None)
    except (ValueError, KeyError, UnicodeDecodeError) as e:
        raise HTTPException(400, f"Couldn't read this file as a table of trades ({type(e).__name__}: {e}).") from e


@app.get("/api/portfolio/import/presets", response_model=list[Preset])
def import_presets() -> list[dict]:
    from . import importers

    return [{"key": k, "label": p["label"], "verified": bool(p.get("verified"))} for k, p in importers.presets().items()]


@app.post("/api/portfolio/import/preview", response_model=ImportPreview)
async def import_preview(request: Request, filename: str = "", preset: str | None = None, mapping: str | None = None,
                         symbols: str | None = None, account: str | None = None) -> dict:
    """What importing this file would do, without saving: format, column mapping, symbol matches, each row with
    its issues. `mapping` and `symbols` (JSON) override the detected columns and the suggested symbols."""
    universe.ensure_migrated()
    return _preview(await request.body(), filename, preset, mapping, symbols, account)


@app.post("/api/portfolio/import/commit", response_model=ImportCommitResult)
async def import_commit(request: Request, filename: str = "", preset: str | None = None, mapping: str | None = None,
                        symbols: str | None = None, account: str | None = None, confirm: bool = False) -> dict:
    """Save the import exactly as the same preview shows it (re-run here, so nothing unchecked gets in)."""
    from . import importers

    universe.ensure_migrated()
    pv = _preview(await request.body(), filename, preset, mapping, symbols, account)
    try:
        return importers.commit(pv, filename, confirm)
    except ValueError as e:
        raise HTTPException(422, {"message": f"Not imported: {e}.", "issues": []}) from e


@app.get("/api/portfolio/imports", response_model=list[ImportRecord])
def list_imports() -> list[dict]:
    return userstore.imports()


@app.delete("/api/portfolio/imports/{import_id}", response_model=int)
def undo_import(import_id: int) -> int:
    """Remove every trade an import added (a backup of the database is taken first)."""
    if not any(i["id"] == import_id for i in userstore.imports()):
        raise HTTPException(404, f"No import {import_id}.")
    return userstore.undo_import(import_id)


if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        """The web app; every non-API path is a client-side route."""
        if path.startswith("api/"):
            raise HTTPException(404)
        f = WEB_DIST / path
        return FileResponse(f if path and f.is_file() else WEB_DIST / "index.html")
