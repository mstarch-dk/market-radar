"""The discovery scan: its report and starting a new one."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException

from .. import updater
from ..api_models import (
    DiscoveryView,
    UpdateStatus,
)
from ..config import typed
from ..reporting import dashboard
from ..sources import valuation

router = APIRouter()


# ---------------- discover: the separate wide scan ----------------

@router.get("/api/discover", response_model=DiscoveryView)
def get_discover() -> dict:
    """The last discovery scan (reports/discovery.json); stale once older than its price limit in settings."""
    from ..discovery import scan

    d = scan.load_report()
    if d is None:
        raise HTTPException(503, "No discovery scan yet: start one on this page or run `uv run radar discover`.")
    age = (date.today() - date.fromisoformat(d["asof"])).days
    ctx = valuation.context()
    markets = [m | {"rows": dashboard.with_valuation(m["rows"], ctx, "fund" if m["kind"] == "etf" else "stock", "disc")}
               for m in d["markets"]]
    return {"age_days": age, "stale": age > typed().coverage.max_age["discovery_prices"], **d,
            "markets": markets}


@router.get("/api/discover/scan", response_model=UpdateStatus)
def discover_status() -> dict:
    return updater.DISCOVER_JOB.state


@router.post("/api/discover/scan", response_model=UpdateStatus)
def start_discover() -> dict:
    """Start the discovery scan in the background (a few minutes; the first one longer)."""
    if not updater.DISCOVER_JOB.start():
        raise HTTPException(409, "A discovery scan is already running.")
    return updater.DISCOVER_JOB.state
