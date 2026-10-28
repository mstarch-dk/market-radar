"""The operations log: requests, events, jobs, the doctor, paused hosts."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import (
    net,
    ops,
)
from ..api_models import (
    DoctorCheck,
    OpsEvent,
    OpsJob,
    OpsJobDetail,
    OpsRequest,
    OpsRunningJob,
    OpsSummary,
)

router = APIRouter()


# ---------------- operations: external requests, events, jobs, throttling (ops.py) ----------------

@router.get("/api/ops/summary", response_model=OpsSummary)
def ops_summary(days: int = Query(7, ge=1, le=90)) -> dict:
    return ops.summary(days, net.limits)


@router.get("/api/ops/events", response_model=list[OpsEvent])
def ops_events(level: str | None = None, kind: str | None = None, source: str | None = None,
               limit: int = Query(200, ge=1, le=1000), before: int | None = None) -> list[dict]:
    return ops.events(level, kind, source, limit, before)


@router.get("/api/ops/requests", response_model=list[OpsRequest])
def ops_requests(host: str | None = None, source: str | None = None, status: int | None = None,
                 limit: int = Query(200, ge=1, le=1000), before: int | None = None) -> list[dict]:
    return ops.requests(host, source, status, limit, before)


@router.get("/api/ops/jobs", response_model=list[OpsJob])
def ops_jobs(limit: int = Query(50, ge=1, le=500)) -> list[dict]:
    return ops.jobs(limit)


@router.get("/api/ops/running", response_model=list[OpsRunningJob])
def ops_running(tail: int = Query(20, ge=0, le=200)) -> list[dict]:
    """The jobs running now, whichever process runs them (the app, the MCP server, a terminal), with progress."""
    return ops.running_jobs(tail)


@router.get("/api/ops/jobs/{job_id}", response_model=OpsJobDetail)
def ops_job(job_id: int) -> dict:
    j = ops.job_detail(job_id)
    if j is None:
        raise HTTPException(404, f"No job {job_id}.")
    return j


@router.get("/api/ops/doctor", response_model=list[DoctorCheck])
def ops_doctor(probe: bool = False) -> list[dict]:
    """`radar doctor` from the app; with `probe`, every data source is contacted once (a few seconds)."""
    from .. import health

    with ops.context(source="doctor"):
        return health.checks(offline=not probe)


@router.delete("/api/ops/cooldown/{host}", response_model=bool)
def ops_clear_cooldown(host: str) -> bool:
    """End a paused host's cooldown now; 404 if it isn't paused."""
    if not ops.clear_cooldown(host):
        raise HTTPException(404, f"{host} is not paused.")
    net.reset()
    ops.event("info", "throttle", f"{host}: pause cleared by hand")
    return True
