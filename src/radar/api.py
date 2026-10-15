"""Local web API for the radar (`radar serve`): ticker profiles, chart series, search, the dashboard readings
from the last `radar run`, the live holdings table and watchlist edits, plus the built web app from web/dist.
Binds to 127.0.0.1 only; there is no authentication."""
from __future__ import annotations

import datetime as dt
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import date

import pandas as pd

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import dashboard, home, mine, net, ops, paths, portfolio, profile, tickers, universe, updater, userstore, valuation
from .api_models import (
    AppContext, CoverageView, DiscoveryView, MeView, MomentumView, PositioningView, Profile, RegimeView, RotationView, SearchHit,
    Series, TickerSummary, WatchState, UpdateStatus, ImportResult,
    PositionsView, PriceCheck, TxCheck, TxIn, TxResult, TxRow,
    MoveIn, MoveResult, Portfolio, PortfolioIn, TagCount, TagsIn, Comparison, Performance, ForkIn,
    ImportCommitResult, ImportPreview, ImportRecord, Preset,
    AlignCompact, AlignRequest, ViewIn, ViewRow, ViewsPage, VoteOption, VotesIn,
    DoctorCheck, OpsEvent, OpsJob, OpsJobDetail, OpsRequest, OpsSummary,
    GuideChapter, GuideHit, GuideTree, NotebookDocument, NotebookListing,
    HomeStatus, LegacyFound, SetupIn, SetupResult,
    BackupRow, DataHome, MirrorIn, OpenIn, RestoreIn, RestoreResult, UpdateCheck, UpdateCheckIn,
)
from .config import settings
from .config import ROOT

WEB_DIST = ROOT / "web" / "dist"

def _open_home() -> None:
    """Once a usable data home is known: tidy the operations log and record this version in the manifest."""
    global _gate
    _gate = home.gate()
    if _gate[0] != "ok":
        return
    from . import backup

    try:
        backup.before_upgrade()                  # a new version's first start: keep the data as it was
        home.upgrade(paths.locations().home)
        backup.daily()
    except Exception as e:                       # a full disk must not stop the app; the Data page shows the age
        ops.event("error", "job", f"backup: {type(e).__name__}: {e}", source="backup", exc=e)
    home.touch(paths.locations().home)
    ops.mark_interrupted()   # a job 'running' in the log from an earlier server can't still be running
    ops.prune()


@asynccontextmanager
async def _lifespan(_app):
    _open_home()
    yield


app = FastAPI(title="Market Radar", version=home.app_version(), lifespan=_lifespan)
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


def _selection(portfolio: list[int] | None, tag: list[str] | None, scope: str | None) -> list[int] | None:
    """Which portfolios a request is about: chosen ids and/or tags, else a scope (real | virtual | all); None
    means the default, your real portfolios."""
    if portfolio or tag:
        return userstore.portfolio_ids(ids=portfolio, tags=tag)
    if scope:
        if scope not in userstore.SCOPES:
            raise HTTPException(422, f"scope must be one of {', '.join(userstore.SCOPES)}")
        return userstore.portfolio_ids(scope)
    return None


PortfolioQ = Query(None, description="Portfolio ids (repeatable); default: your real portfolios")
TagQ = Query(None, description="Portfolios carrying any of these tags (repeatable)")
ScopeQ = Query(None, description="real | virtual | all (when no portfolio or tag is given)")


_gate: tuple[str, str | None] | None = None      # (state, why read-only), from home.gate() at start
SETUP_FREE = ("/api/setup", "/api/guide", "/api/ops/doctor")    # usable before the data folder is chosen
READS = {"GET", "HEAD", "OPTIONS"}


@app.middleware("http")
async def _data_home(request: Request, call_next):
    """No data folder yet (or it is missing): only the setup screen and the guide answer. Data written by a newer
    version: reads only."""
    path = request.url.path
    if path.startswith("/api/") and not path.startswith(SETUP_FREE):
        if _gate is None:
            _open_home()
        state, why = _gate
        if state in ("unset", "missing"):
            return JSONResponse({"detail": {"setup": state, "message": "Choose where your data is first."}}, 409)
        if why and request.method not in READS:
            return JSONResponse({"detail": {"read_only": why, "message": why}}, 409)
    return await call_next(request)


@app.get("/api/setup", response_model=HomeStatus)
def setup_status() -> dict:
    """Where the data is, whether it can be used, and (before setup) the old folders found with data in them."""
    return home.status()


@app.get("/api/setup/scan", response_model=LegacyFound)
def setup_scan(path: str = Query(..., min_length=1, max_length=1000)) -> dict:
    """What an old Market Radar folder the user points to holds (404 if nothing of theirs)."""
    found = home.legacy_summary(Path(path).expanduser())
    if found is None:
        raise HTTPException(404, f"No Market Radar data in {path}.")
    return found


@app.post("/api/setup", response_model=SetupResult)
def setup(body: SetupIn) -> dict:
    """Choose the data folder: copy an old version's data into it, start empty, or use one that exists. Refused
    once a folder is in use (409)."""
    if (_gate or home.gate())[0] not in ("unset", "missing"):
        raise HTTPException(409, "A data folder is already in use.")
    target = Path(body.home).expanduser() if body.home else None
    files: dict[str, int] = {}
    try:
        if body.action == "migrate":
            if not body.source:
                raise HTTPException(422, "Choose the old folder to copy from.")
            files = home.migrate(Path(body.source), target, copy_cache=body.copy_cache)["files"]
        elif body.action == "create":
            home.create(target)
        else:
            if not target:
                raise HTTPException(422, "Choose the data folder to use.")
            home.use(target)
    except home.HomeError as e:
        raise HTTPException(422, str(e)) from e
    _open_home()
    return {"status": home.status(), "files": files}


def _folders() -> list[dict]:
    from . import home as h

    loc = paths.locations()
    rows = [("data", "Your data folder", loc.home, "personal"), ("notes", "Notes", loc.home / "notes", "personal"),
            ("research", "Research", loc.home / "research", "personal"),
            ("journal", "Journal", loc.home / "journal", "personal"),
            ("briefs", "Briefs", loc.home / "briefs", "personal"),
            ("exports", "Exports", loc.home / "exports", "personal"),
            ("backups", "Backups", loc.userdata / "backups", "personal"),
            ("history", "History", loc.history, "history"), ("cache", "Market data (cache)", loc.cache, "cache")]
    out = []
    for key, label, d, tier in rows:
        fs = h._files(d) if key != "data" else ([loc.userdata / h.DB_NAME] if (loc.userdata / h.DB_NAME).exists() else [])
        out.append({"key": key, "label": label, "path": str(d), "tier": tier, "files": len(fs),
                    "mb": round(sum(f.stat().st_size for f in fs) / 1e6, 1)})
    return out


@app.get("/api/data-home", response_model=DataHome)
def data_home() -> dict:
    """Where your data, the history and the market data are; the backups and the second backup folder."""
    from . import backup

    m = backup.mirror() if backup.is_home() else None
    return {"status": home.status(), "folders": _folders(), "backups": backup.listing() if backup.is_home() else [],
            "mirror": str(m) if m else None, "mirror_backups": backup.listing(m) if m else []}


@app.post("/api/data-home/backup", response_model=BackupRow)
def data_home_backup() -> dict:
    from . import backup

    try:
        f = backup.create("manual")
    except backup.BackupError as e:
        raise HTTPException(409, str(e)) from e
    return next(r for r in backup.listing() if r["name"] == f.name)


@app.put("/api/data-home/mirror", response_model=DataHome)
def data_home_mirror(body: MirrorIn) -> dict:
    """Set (or clear) the second folder every backup is copied to."""
    from . import backup

    try:
        backup.set_mirror(Path(body.path) if body.path else None)
    except (backup.BackupError, OSError) as e:
        raise HTTPException(422, str(e)) from e
    return data_home()


@app.post("/api/data-home/restore", response_model=RestoreResult)
def data_home_restore(body: RestoreIn) -> dict:
    """Put one of the listed backups back (what is there now is backed up first)."""
    from . import backup

    m = backup.mirror()
    known = {r["name"]: r["path"] for r in [*backup.listing(), *(backup.listing(m) if m else [])]}
    if body.name not in known:
        raise HTTPException(404, f"No backup called {body.name}.")
    try:
        res = backup.restore(Path(known[body.name]))
    except backup.BackupError as e:
        raise HTTPException(422, str(e)) from e
    global _market
    _market = None
    return res


@app.post("/api/data-home/open", response_model=bool)
def data_home_open(body: OpenIn) -> bool:
    """Show one of the folders in Explorer / Finder / the file manager (the app only runs on your own computer)."""
    import os
    import subprocess
    import sys

    path = next((f["path"] for f in _folders() if f["key"] == body.key), None)
    if path is None:
        raise HTTPException(404, f"No folder {body.key}.")
    Path(path).mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)                                    # noqa: S606 (a folder the app itself chose)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])
    return True


@app.get("/api/updates", response_model=UpdateCheck)
def get_updates() -> dict:
    """Is a newer Market Radar out? Asks GitHub at most once a day, and only when switched on."""
    from . import updates

    return updates.status()


@app.put("/api/updates", response_model=UpdateCheck)
def put_updates(body: UpdateCheckIn) -> dict:
    from . import updates

    updates.set_enabled(body.enabled)
    return updates.status()


@app.get("/api/data-home/export", include_in_schema=False)
def data_home_export() -> Response:
    """Everything of yours in open formats, as a zip download (export.py)."""
    from . import export

    name = f"market-radar-export-{date.today().isoformat()}.zip"
    return Response(export.build(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


NOT_RECORDED = {503}   # "no dashboard / scan yet" is a state the pages explain, not an operational error


@app.middleware("http")
async def _record_errors(request: Request, call_next):
    """Attribute the app's own Yahoo calls to the page area asking ("app:ticker"), and keep server errors (5xx,
    with the traceback when one was raised) in the operations log. 4xx are user input, not recorded."""
    path = request.url.path
    area = path.split("/")[2] if path.startswith("/api/") and path.count("/") >= 2 else None
    with ops.context(source=f"app:{area}" if area else None):
        try:
            resp = await call_next(request)
        except Exception as e:
            ops.event("error", "api", f"{request.method} {path}: {type(e).__name__}: {e}", source=f"app:{area}",
                      exc=e)
            raise
    if resp.status_code >= 500 and resp.status_code not in NOT_RECORDED:
        ops.event("error", "api", f"{request.method} {path}: HTTP {resp.status_code}", source=f"app:{area}")
    return resp


@app.get("/api/ticker/{symbol}", response_model=Profile)
def get_profile(symbol: str, refresh: bool = False) -> dict:
    global _market
    symbol = _symbol(symbol)
    with _lock:
        try:
            _market = profile.ensure_prices(symbol, market(), refresh=refresh)
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
    """The regime of the last `radar run`, voted with your current choice of indicator groups."""
    view = _view("regime")
    view["overall"], view["indicators"] = dashboard.regime_now(_dashboard())
    return view | {"votes": dashboard.vote_options()}


@app.get("/api/settings/regime-votes", response_model=list[VoteOption])
def get_regime_votes() -> list[dict]:
    return dashboard.vote_options()


@app.put("/api/settings/regime-votes", response_model=list[VoteOption])
def put_regime_votes(body: VotesIn) -> list[dict]:
    """Which switchable indicator groups count in the regime vote (stored in userdata; the default is
    settings.yaml regime.votes). Takes effect at once here, and in summary.json from the next `radar report`."""
    known = set(settings()["regime"].get("votes") or {})
    unknown = sorted(set(body.votes) - known)
    if unknown:
        raise HTTPException(422, f"unknown group(s): {', '.join(unknown)}; known: {', '.join(sorted(known))}")
    userstore.meta_set("regime_votes", (userstore.meta_get("regime_votes") or {}) | body.votes)
    return dashboard.vote_options()


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
    """The coverage section, with each source's last attempt and error read live from sources.json (a
    failure after the last report build shows at once)."""
    from . import coverage

    return coverage.live(_view("coverage"))


# ---------------- operations: external requests, events, jobs, throttling (ops.py) ----------------

@app.get("/api/ops/summary", response_model=OpsSummary)
def ops_summary(days: int = Query(7, ge=1, le=90)) -> dict:
    return ops.summary(days, net.limits)


@app.get("/api/ops/events", response_model=list[OpsEvent])
def ops_events(level: str | None = None, kind: str | None = None, source: str | None = None,
               limit: int = Query(200, ge=1, le=1000), before: int | None = None) -> list[dict]:
    return ops.events(level, kind, source, limit, before)


@app.get("/api/ops/requests", response_model=list[OpsRequest])
def ops_requests(host: str | None = None, source: str | None = None, status: int | None = None,
                 limit: int = Query(200, ge=1, le=1000), before: int | None = None) -> list[dict]:
    return ops.requests(host, source, status, limit, before)


@app.get("/api/ops/jobs", response_model=list[OpsJob])
def ops_jobs(limit: int = Query(50, ge=1, le=500)) -> list[dict]:
    return ops.jobs(limit)


@app.get("/api/ops/jobs/{job_id}", response_model=OpsJobDetail)
def ops_job(job_id: int) -> dict:
    j = ops.job_detail(job_id)
    if j is None:
        raise HTTPException(404, f"No job {job_id}.")
    return j


@app.get("/api/ops/doctor", response_model=list[DoctorCheck])
def ops_doctor(probe: bool = False) -> list[dict]:
    """`radar doctor` from the app; with `probe`, every data source is contacted once (a few seconds)."""
    from . import health

    with ops.context(source="doctor"):
        return health.checks(offline=not probe)


@app.delete("/api/ops/cooldown/{host}", response_model=bool)
def ops_clear_cooldown(host: str) -> bool:
    """End a paused host's cooldown now; 404 if it isn't paused."""
    if not ops.clear_cooldown(host):
        raise HTTPException(404, f"{host} is not paused.")
    net.reset()
    ops.event("info", "throttle", f"{host}: pause cleared by hand")
    return True


# ---------------- your market views (subjective beliefs) ----------------

def _views_page() -> dict:
    from . import market_views as mv

    with _lock:
        closes = market().closes
    return {"disclaimer": mv.DISCLAIMER, "views": mv.with_evidence(None, closes), "templates": mv.templates(),
            "catalogue": mv.catalogue()}


def _view_body(body: ViewIn) -> dict:
    v = body.model_dump()
    v["statement"] = v["statement"].strip()
    if not v["statement"]:
        raise HTTPException(422, "A view needs a statement.")
    if not 1 <= v["conviction"] <= 5:
        raise HTTPException(422, "Conviction is 1 (a hunch) to 5 (very sure).")
    from . import market_views as mv

    known = set(mv.config()["indicators"])
    bad = [i["indicator"] for i in v["indicators"] if i["indicator"] not in known]
    if bad:
        raise HTTPException(422, f"Unknown indicator: {', '.join(bad)}.")
    return v


@app.get("/api/views", response_model=ViewsPage)
def get_views() -> dict:
    """Your market views (active and archived) with the radar's evidence, the templates and the vocabulary."""
    return _views_page()


@app.post("/api/views", response_model=ViewsPage)
def add_view(body: ViewIn) -> dict:
    userstore.save_view(_view_body(body))
    return _views_page()


@app.put("/api/views/{view_id}", response_model=ViewsPage)
def edit_view(view_id: int, body: ViewIn) -> dict:
    if not userstore.get_view(view_id):
        raise HTTPException(404, f"No view {view_id}.")
    userstore.save_view(_view_body(body), view_id)
    return _views_page()


@app.delete("/api/views/{view_id}", response_model=ViewRow)
def delete_view(view_id: int) -> dict:
    """Delete a view; the response is the deleted view, which /restore puts back (undo)."""
    v = userstore.delete_view(view_id)
    if not v:
        raise HTTPException(404, f"No view {view_id}.")
    return v


@app.post("/api/views/restore", response_model=ViewsPage)
def restore_view(row: ViewRow) -> dict:
    if userstore.get_view(row.id):
        raise HTTPException(409, "That view is already there.")
    userstore.restore_view(row.model_dump())
    return _views_page()


@app.post("/api/views/align", response_model=dict[str, AlignCompact])
def align_views(body: AlignRequest) -> dict:
    """How each of `tickers` lines up with your active views (for table columns); {} without views."""
    from . import market_views as mv

    with _lock:
        return mv.align_many([_symbol(t) for t in body.tickers][:5000], body.store)


# ---------------- discover: the separate wide scan ----------------

@app.get("/api/discover", response_model=DiscoveryView)
def get_discover() -> dict:
    """The last discovery scan (reports/discovery.json); stale once older than its price limit in settings."""
    from .discovery import scan

    d = scan.load_report()
    if d is None:
        raise HTTPException(503, "No discovery scan yet: start one on this page or run `uv run radar discover`.")
    age = (date.today() - date.fromisoformat(d["asof"])).days
    ctx = valuation.context()
    markets = [m | {"rows": dashboard.with_valuation(m["rows"], ctx, "fund" if m["kind"] == "etf" else "stock", "disc")}
               for m in d["markets"]]
    return {"age_days": age, "stale": age > settings()["coverage"]["max_age"]["discovery_prices"], **d,
            "markets": markets}


@app.get("/api/discover/scan", response_model=UpdateStatus)
def discover_status() -> dict:
    return updater.DISCOVER_JOB.state


@app.post("/api/discover/scan", response_model=UpdateStatus)
def start_discover() -> dict:
    """Start the discovery scan in the background (a few minutes; the first one longer)."""
    if not updater.DISCOVER_JOB.start():
        raise HTTPException(409, "A discovery scan is already running.")
    return updater.DISCOVER_JOB.state


# ---------------- your holdings and watchlist ----------------

@app.get("/api/me", response_model=MeView)
def get_me(portfolio: list[int] | None = PortfolioQ, tag: list[str] | None = TagQ, scope: str | None = ScopeQ) -> dict:
    """Holdings, watchlist and sold positions, computed now from the current prices (so watchlist edits show
    at once), pooled over the chosen portfolios (default: your real ones). Quadrants and the regime used for
    the stop levels come from the last `radar run`."""
    sel = _selection(portfolio, tag, scope)
    d = _dashboard()
    rot_rows = [r for g in d["rotation"]["groups"] for r in g["rows"]]
    regime_label = dashboard.regime_now(d)[0]["label"]
    with _lock:
        m = market()
        rows = mine.table(m.closes, m.highs, m.lows, m.volumes, m.raw_closes(), m.leaders(), rot_rows, regime_label,
                          settings(), sessions=lambda s: m.bars(s)["close"], portfolios=sel)
        asof = m.closes[universe.benchmark()].dropna().index[-1].date().isoformat()
    rows = dashboard.with_valuation(rows, valuation.context())
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
    """Take a symbol off the watchlist. A holding can't be removed (409): it comes from your trades."""
    symbol = _symbol(symbol)
    st = _status(symbol)
    if st == "holding":
        raise HTTPException(409, f"{symbol} is a holding, not a watchlist entry; holdings come from your trades.")
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
    trade = body.type in userstore.TRADE_TYPES
    return {"symbol": _symbol(body.symbol) or None, "date": body.date[:10], "type": body.type,
            "quantity": body.quantity if trade else None, "price": body.price if trade else None,
            "fee": (body.fee or 0.0) if trade else 0.0, "amount": None if trade else body.amount,
            "currency": None if trade else (body.currency or "DKK").upper(), "fx_rate": body.fx_rate if trade else None,
            "portfolio_id": body.portfolio_id, "note": body.note or None}


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
def list_transactions(symbol: str | None = None, portfolio: list[int] | None = PortfolioQ,
                      tag: list[str] | None = TagQ, scope: str | None = ScopeQ) -> list[dict]:
    universe.ensure_migrated()
    sel = _selection(portfolio, tag, scope)
    return userstore.transactions(_symbol(symbol) if symbol else None, userstore.portfolio_ids() if sel is None else sel)


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
    trade = row["type"] in userstore.TRADE_TYPES
    return {"issues": issues, "effect": portfolio.effect(row, exclude_id=id) if trade and not blocking else None,
            "price": pc}


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
def get_positions(portfolio: list[int] | None = PortfolioQ, tag: list[str] | None = TagQ,
                  scope: str | None = ScopeQ) -> dict:
    from . import portfolio as pf

    sel = _selection(portfolio, tag, scope)
    with _lock:
        return pf.positions_view(market(), sel)


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


@app.get("/api/portfolio/export.csv", response_class=Response)
def export_transactions(portfolio: list[int] | None = PortfolioQ, tag: list[str] | None = TagQ,
                        scope: str | None = ScopeQ) -> Response:
    """The chosen portfolios' transactions as CSV (default: your real ones; a backup you can keep, or open in a
    spreadsheet)."""
    universe.ensure_migrated()
    return Response(userstore.export_transactions_csv(_selection(portfolio, tag, scope)), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="transactions-{dt.date.today()}.csv"'})


# ---------------- portfolios: real ones (your accounts) and virtual ones, with tags ----------------

def _portfolio_or_404(pid: int) -> dict:
    p = userstore.get_portfolio(pid)
    if not p:
        raise HTTPException(404, f"No portfolio {pid}.")
    return p


def _save_portfolio(body: PortfolioIn, pid: int | None = None) -> dict:
    import sqlite3

    name = body.name.strip()
    if not name:
        raise HTTPException(422, "The portfolio needs a name.")
    other = userstore.portfolio_by_name(name)
    if other and other["id"] != pid:
        raise HTTPException(409, f"There is already a portfolio called {name}.")
    if pid is not None:
        old = _portfolio_or_404(pid)
        if old["origin"] == "sim" and body.mode == "real":
            raise HTTPException(422, "A simulated portfolio stays virtual: its trades never happened.")
    try:
        return userstore.get_portfolio(userstore.save_portfolio(body.model_dump() | {"name": name}, pid))
    except (ValueError, sqlite3.IntegrityError) as e:
        raise HTTPException(422, str(e)) from e


@app.get("/api/portfolios", response_model=list[Portfolio])
def list_portfolios(archived: bool = True) -> list[dict]:
    """Every portfolio with its tags, number of rows and date range."""
    universe.ensure_migrated()
    return userstore.portfolios(include_archived=archived)


@app.post("/api/portfolios", response_model=Portfolio)
def add_portfolio(body: PortfolioIn) -> dict:
    return _save_portfolio(body)


@app.put("/api/portfolios/{pid}", response_model=Portfolio)
def edit_portfolio(pid: int, body: PortfolioIn) -> dict:
    """Rename or change a portfolio (its rows stay with it)."""
    return _save_portfolio(body, pid)


@app.delete("/api/portfolios/{pid}", response_model=Portfolio)
def delete_portfolio(pid: int) -> dict:
    """Delete a virtual portfolio with its rows (a backup is taken first), or an empty real one. A real one
    with trades is 409: move them, or archive it."""
    _portfolio_or_404(pid)
    try:
        return userstore.delete_portfolio(pid)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.get("/api/portfolios/tags", response_model=list[TagCount])
def list_tags() -> list[dict]:
    return userstore.all_tags()


@app.put("/api/portfolios/{pid}/tags", response_model=Portfolio)
def set_tags(pid: int, body: TagsIn) -> dict:
    _portfolio_or_404(pid)
    try:
        userstore.set_tags(pid, body.tags)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return userstore.get_portfolio(pid)


@app.post("/api/portfolios/{pid}/default", response_model=list[Portfolio])
def set_default(pid: int) -> list[dict]:
    """Make this real portfolio the one new trades and imports go into unless another is chosen."""
    _portfolio_or_404(pid)
    try:
        userstore.set_default_portfolio(pid)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return userstore.portfolios()


@app.get("/api/portfolios/compare", response_model=Comparison)
def compare_portfolios(portfolio: list[int] | None = PortfolioQ, tag: list[str] | None = TagQ,
                       start: str | None = None) -> dict:
    """Portfolios and tag groups (each pooled into one line) side by side from a common start, every
    time-weighted index rebased to 100 there, with ACWI. Default: each of your real portfolios with rows."""
    from . import performance

    ids = portfolio if (portfolio or tag) else [p["id"] for p in userstore.portfolios(include_archived=False)
                                                 if p["mode"] == "real" and p["n_tx"]]
    with _lock:
        return performance.compare(market(), ids, tag, start)


@app.get("/api/portfolios/{pid}/performance", response_model=Performance)
def portfolio_performance(pid: int, start: str | None = None, end: str | None = None) -> dict:
    """One portfolio's value over time in DKK, its time- and money-weighted returns and ACWI's with the same
    cash flows. Gaps (a price or DKK rate missing) are None, never 0."""
    from . import performance

    with _lock:
        out = performance.portfolio_performance(pid, market(), start, end)
    if out is None:
        raise HTTPException(404, f"No portfolio {pid}.")
    return out


@app.post("/api/portfolios/{pid}/fork", response_model=Portfolio)
def fork_portfolio(pid: int, body: ForkIn) -> dict:
    """A virtual copy of this portfolio as it stood at a day's close (one deposit, one buy per holding), to
    A/B-test changes against it from there on (compare with start = that day)."""
    from . import simulate

    _portfolio_or_404(pid)
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "The copy needs a name.")
    try:
        with _lock:
            new = simulate.fork(pid, name, body.date, market(), body.extra_cash_dkk, body.tags)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return userstore.get_portfolio(new)


@app.post("/api/portfolios/{pid}/move", response_model=MoveResult)
def move_rows(pid: int, body: MoveIn) -> dict:
    """Move rows (all, or only these ids / tickers) to another portfolio; refused (422) if a sale would be left
    without its buy in either portfolio. A backup is taken first."""
    _portfolio_or_404(pid)
    _portfolio_or_404(body.to)
    if body.to == pid:
        raise HTTPException(422, "Choose another portfolio to move to.")
    symbols = [_symbol(s) for s in body.symbols] if body.symbols else None
    problems = portfolio.check_move(pid, body.to, body.ids, symbols)
    if problems:
        raise HTTPException(422, {"message": "Not moved: " + problems[0],
                                  "issues": [{"level": "error", "field": "portfolio", "message": p} for p in problems]})
    return {"moved": userstore.move_transactions(pid, body.to, body.ids, symbols)}


# ---------------- the notebook: briefs, research memos and the journal (notebook.py; read-only) ----------------

@app.get("/api/notebook", response_model=NotebookListing)
def notebook_listing() -> dict:
    from . import notebook

    return notebook.listing()


@app.get("/api/notebook/{kind}/{name}", response_model=NotebookDocument)
def notebook_document(kind: str, name: str) -> dict:
    from . import notebook

    try:
        return notebook.document(kind, name)
    except notebook.NotFound:
        raise HTTPException(404, f"No {kind} document {name}.") from None


# ---------------- the guide: Danish user guide and textbook (guide/, guide.py) ----------------

@app.get("/api/guide", response_model=GuideTree)
def guide_tree() -> dict:
    from . import guide

    return guide.tree()


@app.get("/api/guide/search", response_model=list[GuideHit])
def guide_search(q: str = Query(..., min_length=2, max_length=80)) -> list[dict]:
    from . import guide

    return guide.search(q)


@app.get("/api/guide/{book}/{slug}", response_model=GuideChapter)
def guide_chapter(book: str, slug: str) -> dict:
    from . import guide

    try:
        return guide.chapter(book, slug)
    except guide.NotFound:
        raise HTTPException(404, f"No chapter {book}/{slug}.") from None


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
             portfolio: int | None) -> dict:
    import json

    from . import importers

    if not body.strip():
        raise HTTPException(400, "The file is empty.")
    if len(body) > MAX_IMPORT_BYTES:
        raise HTTPException(413, "That file is too large for a transaction export.")
    try:
        with _lock:
            return importers.preview(body, filename, market, _has_prices, preset or None,
                                     json.loads(mapping) if mapping else None, portfolio,
                                     json.loads(symbols) if symbols else None)
    except (ValueError, KeyError, UnicodeDecodeError) as e:
        raise HTTPException(400, f"Couldn't read this file as a table of trades ({type(e).__name__}: {e}).") from e


@app.get("/api/portfolio/import/presets", response_model=list[Preset])
def import_presets() -> list[dict]:
    from . import importers

    return [{"key": k, "label": p["label"], "verified": bool(p.get("verified"))} for k, p in importers.presets().items()]


@app.post("/api/portfolio/import/preview", response_model=ImportPreview)
async def import_preview(request: Request, filename: str = "", preset: str | None = None, mapping: str | None = None,
                         symbols: str | None = None, portfolio: int | None = None) -> dict:
    """What importing this file would do, without saving: format, column mapping, symbol matches, each row with
    its issues. `mapping` and `symbols` (JSON) override the detected columns and the suggested symbols; rows go
    into `portfolio` (default: the default portfolio) unless the file names one."""
    universe.ensure_migrated()
    return _preview(await request.body(), filename, preset, mapping, symbols, portfolio)


@app.post("/api/portfolio/import/commit", response_model=ImportCommitResult)
async def import_commit(request: Request, filename: str = "", preset: str | None = None, mapping: str | None = None,
                        symbols: str | None = None, portfolio: int | None = None, confirm: bool = False) -> dict:
    """Save the import exactly as the same preview shows it (re-run here, so nothing unchecked gets in)."""
    from . import importers

    universe.ensure_migrated()
    pv = _preview(await request.body(), filename, preset, mapping, symbols, portfolio)
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
