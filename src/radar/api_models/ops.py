"""Operations (ops.py): external requests, events, jobs, throttling, the doctor and the update status."""
from __future__ import annotations

from typing import Literal

from .common import Num, Strict


class UpdateProgress(Strict):
    """The running phase within a step: done of total."""
    done: int
    total: int
    label: str


class JobStep(Strict):
    """The step running: the i-th of n."""
    i: int
    n: int
    key: str
    label: str


class JobStepRow(Strict):
    key: str
    label: str
    status: Literal["pending", "running", "ok", "failed"]
    message: str | None = None


class JobIssue(Strict):
    """A problem met while the job runs: warn (data missing or late), error (a step failed; cached data kept)."""
    level: Literal["warn", "error"]
    source: str | None = None
    message: str


class JobProgress(Strict):
    """A job's progress (progress.Progress): its steps, the running one and its phase, and the newest issues."""
    step: JobStep | None = None
    steps: list[JobStepRow] = []
    phase: UpdateProgress | None = None
    issues: list[JobIssue] = []
    issues_total: int = 0


class UpdateStatus(Strict):
    """A job as the app polls it. `elsewhere` names the kind of a job another process runs (cli_run = a terminal,
    update = the MCP server), shown because this one runs none; it can't be stopped or started from here."""
    status: Literal["idle", "running", "done", "failed"]
    started: str | None = None
    finished: str | None = None
    log: list[str]
    progress: UpdateProgress | None = None
    error: str | None = None
    step: JobStep | None = None
    steps: list[JobStepRow] = []
    issues: list[JobIssue] = []
    issues_total: int = 0
    elsewhere: str | None = None


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
    progress: JobProgress | None = None
    heartbeat: str | None = None


class OpsRunningJob(OpsJob):
    """A job running now in any process. `stale`: no sign of life for minutes (its process may have died)."""
    heartbeat: str | None = None
    quiet_s: Num = None
    stale: bool
    progress: JobProgress | None = None
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
