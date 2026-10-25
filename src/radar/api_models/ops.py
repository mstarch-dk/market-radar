"""Operations (ops.py): external requests, events, jobs, throttling, the doctor and the update status."""
from __future__ import annotations

from typing import Literal

from .common import Num, Strict


class UpdateProgress(Strict):
    done: int
    total: int
    label: str


class UpdateStatus(Strict):
    status: Literal["idle", "running", "done", "failed"]
    started: str | None = None
    finished: str | None = None
    log: list[str]
    progress: UpdateProgress | None = None
    error: str | None = None


class StudyRunStatus(UpdateStatus):
    """A study run from the app (studyrun.py): an update's status and which study (a head's `run_key`)."""
    study: str | None = None


class OpsJob(Strict):
    id: int
    kind: str
    started: str
    finished: str | None = None
    status: str
    error: str | None = None
    duration_s: Num = None


class OpsJobDetail(OpsJob):
    log: list[str]
    requests: int
    errors: int


class OpsCooldown(Strict):
    host: str
    until: str
    reason: str | None = None
    strikes: int


class OpsRow(Strict):
    """Requests to one host for one source over the window. p50/p95 are None without timed requests."""
    host: str
    source: str | None = None
    requests: int
    errors: int
    error_pct: float
    throttled: int
    p50_ms: Num = None
    p95_ms: Num = None
    last: str
    last_error: str | None = None
    last_error_at: str | None = None
    today: int
    budget: int | None = None
    cooldown_until: str | None = None
    daily: list[int]


class OpsSummary(Strict):
    days: int
    dates: list[str]
    generated: str
    requests_24h: int
    errors_24h: int
    error_events_24h: int
    last_update: OpsJob | None = None
    cooldowns: list[OpsCooldown]
    over_budget: list[str]
    rows: list[OpsRow]


class OpsEvent(Strict):
    id: int
    ts: str
    level: Literal["info", "warn", "error"]
    kind: str
    source: str | None = None
    message: str
    detail: str | None = None
    job_id: int | None = None


class OpsRequest(Strict):
    id: int
    ts: str
    job_id: int | None = None
    source: str | None = None
    host: str
    method: str
    path: str
    status: int | None = None
    ok: bool
    duration_ms: Num = None
    bytes: int | None = None
    attempt: int
    throttled: bool
    error: str | None = None


class DoctorCheck(Strict):
    name: str
    status: Literal["ok", "warn", "fail", "info"]
    detail: str
    fix: str | None = None
