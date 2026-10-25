"""The local web API for the radar (`radar serve`): ticker profiles, chart series, search, the dashboard readings
from the last `radar run`, the live holdings table and watchlist edits, plus the built web app from web/dist.
Binds to 127.0.0.1 only; there is no authentication."""
from __future__ import annotations

import http
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .. import errors, manifest, ops, updater
from ..config import ROOT
from ..reporting import dashboard
from . import (
    agenda,
    attribution,
    discover,
    docs,
    evidence,
    holdings,
    imports,
    operations,
    portfolios,
    readings,
    refresh,
    setup,
    state,
    ticker,
    transactions,
    views,
    xray,
)

WEB_DIST = ROOT / "web" / "dist"

def rebuild_if_older(gate: tuple[str, str | None]) -> None:
    """A dashboard built by a version with an older shape is rebuilt at start (no downloads, about half a
    minute), so a new section doesn't answer 503 until the next update. Only in a usable data home (`gate`, as
    `home.gate()` gives it)."""
    if gate[0] != "ok":
        return
    try:
        d = dashboard.load()
        if d is not None and (o := dashboard.outdated(d)) and o["reason"] == "format":
            updater.REPORT_JOB.start()
    except Exception as e:                       # an unreadable dashboard: the pages say so; the app still starts
        ops.event("error", "job", f"report check: {type(e).__name__}: {e}", source="report", exc=e)


@asynccontextmanager
async def _lifespan(_app):
    rebuild_if_older(state.open_home())
    yield


app = FastAPI(title="Market Radar", version=manifest.app_version(), lifespan=_lifespan)


# ---------------- errors: one shape, {"detail": {"message", "issues"}} ----------------

def _error(status: int, message: str, issues: list | None = None, **extra) -> JSONResponse:
    return JSONResponse({"detail": {"message": message, "issues": issues or [], **extra}}, status)


@app.exception_handler(errors.RadarError)
async def _radar_error(_request: Request, e: errors.RadarError) -> JSONResponse:
    """The domain's errors (errors.py): NotFound 404, Conflict 409, Invalid 422 with its issues."""
    return _error(e.status, e.message, e.issues)


@app.exception_handler(StarletteHTTPException)
async def _http_error(_request: Request, e: StarletteHTTPException) -> JSONResponse:
    d = e.detail
    if isinstance(d, dict):
        resp = _error(e.status_code, str(d.get("message", "")), d.get("issues"))
    else:
        resp = _error(e.status_code, str(d) if d else http.HTTPStatus(e.status_code).phrase)
    resp.headers.update(e.headers or {})
    return resp


@app.exception_handler(RequestValidationError)
async def _validation_error(_request: Request, e: RequestValidationError) -> JSONResponse:
    """A request that doesn't fit its model: the first problem as the message, every one as an issue."""
    issues = [{"field": ".".join(str(x) for x in err["loc"] if x != "body"), "level": "error", "message": err["msg"]}
              for err in e.errors()]
    first = issues[0] if issues else {"field": "", "message": "invalid request"}
    return _error(422, f"{first['field']}: {first['message']}" if first["field"] else first["message"], issues)
SETUP_FREE = ("/api/setup", "/api/guide", "/api/ops/doctor")    # usable before the data folder is chosen
READS = {"GET", "HEAD", "OPTIONS"}


@app.middleware("http")
async def _data_home(request: Request, call_next):
    """No data folder yet (or it is missing): only the setup screen and the guide answer. Data written by a newer
    version: reads only."""
    path = request.url.path
    if path.startswith("/api/") and not path.startswith(SETUP_FREE):
        state_, why = state.gate if state.gate is not None else state.open_home()
        if state_ in ("unset", "missing"):
            return _error(409, "Choose where your data is first.", setup=state_)
        if why and request.method not in READS:
            return _error(409, why, read_only=why)
    return await call_next(request)


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


for _r in (setup, ticker, readings, operations, views, discover, holdings, refresh, transactions, portfolios, docs,
           imports, xray, agenda, evidence, attribution):    # new routers last: the OpenAPI order of the others stays put
    app.include_router(_r.router)


if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        """The web app; every non-API path is a client-side route."""
        if path.startswith("api/"):
            raise HTTPException(404)
        f = WEB_DIST / path
        return FileResponse(f if path and f.is_file() else WEB_DIST / "index.html")
