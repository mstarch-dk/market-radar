"""Refreshing data from the app (update, rebuild) and the Yahoo portfolio import."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from .. import (
    errors,
    importers,
    studyrun,
    updater,
)
from ..api_models import (
    ImportResult,
    UpdateStatus,
)
from .common import (
    MAX_IMPORT_BYTES,
)

router = APIRouter()


# ---------------- refreshing data and importing a portfolio (no terminal needed) ----------------

@router.get("/api/update", response_model=UpdateStatus)
def update_status() -> dict:
    """The data refresh started from the app: status, log lines and progress. While the app runs none, an update
    another process runs (a terminal, the MCP server) is shown instead, with `elsewhere` set."""
    if updater.JOB.state["status"] != "running" and (other := updater.elsewhere()):
        return other
    return updater.JOB.state


@router.post("/api/update", response_model=UpdateStatus)
def start_update() -> dict:
    """Start downloading new data and rebuilding the dashboard in the background (one at a time). 409 while a
    study started from the app runs (it reads the prices the update rewrites)."""
    if studyrun.STUDY_JOB.running:
        raise HTTPException(409, "A study is running: update the data when it has finished.")
    if updater.JOB.state["status"] != "running" and updater.elsewhere():
        raise HTTPException(409, "An update is already running (in a terminal or from Claude): it shows here.")
    if not updater.JOB.start():
        raise HTTPException(409, "An update is already running.")
    return updater.JOB.state


@router.get("/api/report", response_model=UpdateStatus)
def report_status() -> dict:
    """The rebuild of the readings started from the app (no downloads)."""
    return updater.REPORT_JOB.state


@router.post("/api/report", response_model=UpdateStatus)
def start_report() -> dict:
    """Rebuild dashboard.json and summary.json from the data already downloaded, in the background. 409 while an
    update (which rebuilds them itself when it finishes) or another rebuild runs; a build in a terminal makes
    the job stop with its message."""
    if updater.JOB.state["status"] == "running":
        raise HTTPException(409, "An update is running: it rebuilds the readings when it finishes.")
    if studyrun.STUDY_JOB.running:
        raise HTTPException(409, "A study is running: rebuild the readings when it has finished.")
    if not updater.REPORT_JOB.start():
        raise HTTPException(409, "The readings are already being rebuilt.")
    return updater.REPORT_JOB.state






@router.post("/api/import", response_model=ImportResult)
async def import_portfolio(request: Request) -> dict:
    """Import a Yahoo Finance portfolio CSV (sent as the request body) as holdings, sold positions and watchlist.
    Replaces the previous import; watchlist edits made in the app are kept."""
    body = await request.body()
    if not body.strip():
        raise HTTPException(400, "The file is empty.")
    if len(body) > MAX_IMPORT_BYTES:
        raise HTTPException(413, "That file is too large for a portfolio export.")
    # a temporary copy: the import rewrites holdings.csv / transactions.csv only once the file has been read
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "yahoo_portfolio.csv"
        path.write_bytes(body)
        try:
            df, warnings = importers.import_yahoo_csv(str(path))
        except errors.RadarError:
            raise
        except Exception as e:
            raise HTTPException(400, f"Couldn't read this Yahoo Finance export ({type(e).__name__}: {e}).") from e
    counts = df["status"].value_counts()
    return {"holdings": int(counts.get("holding", 0)), "sold": int(counts.get("sold", 0)),
            "watch": int(counts.get("watch", 0)), "warnings": {k: list(v) for k, v in warnings.items()}}
