"""Tools that start the radar's long jobs and report on them: the update, the rebuild of the readings and a study.
They run like the app's (the update and the rebuild in a thread of this process, a study as a child process), are
recorded in the operations log, and check the same locks first, so a job already running in the app or a terminal
is reported, not started twice."""
from __future__ import annotations

from .. import errors, locks, ops, studyrun, updater
from ..config import AnyPath

KINDS = ("update", "report", "study")


def _job(kind: str):
    if kind not in KINDS:
        raise errors.Invalid(f"kind must be one of {', '.join(KINDS)}")
    return {"update": updater.JOB, "report": updater.REPORT_JOB, "study": studyrun.STUDY_JOB}[kind]


def _free(lock: AnyPath, busy: str) -> None:
    """Conflict when another process (the app, a terminal) holds `lock`."""
    try:
        with locks.file_lock(lock, timeout=0, what=busy):
            pass
    except locks.Busy as e:
        raise errors.Conflict(f"Not started: {e}.") from None


def _view(kind: str, tail: int) -> dict:
    """The job of `kind` this process runs or ran; when it runs none, an update another process runs (the app, a
    terminal), marked `elsewhere`. Paused hosts come along: they are why a step goes quiet or fails."""
    s = _job(kind).state
    if s["status"] != "running" and kind == "update" and (other := updater.elsewhere()):
        s = other
    return {"kind": kind, **s, "log": s["log"][-tail:] if tail > 0 else [],
            "paused_hosts": [{"host": c["host"], "until": c["cooldown_until"], "reason": c["reason"]}
                             for c in ops.cooldowns()]}


def job_start(kind: str, study: str | None = None) -> dict:
    """Start a long job in the background and return its status; follow it with `job_status`. `kind`: update
    (download new data, then rebuild the readings: several minutes, reaches Yahoo and the other sources), report
    (rebuild dashboard.json and summary.json from the data already downloaded, no downloads) or study (run the
    study `study`, a key from `study_reports`, e.g. score-study:momentum or propose-study; minutes to an hour).
    Refused while a clashing job runs here, in the app or in a terminal. It shows on the app's Operations page."""
    job = _job(kind)
    if kind == "study":
        if not study:
            raise errors.Invalid(f"Name the study: one of {', '.join(studyrun.commands())}.")
        studyrun.STUDY_JOB.start(study)                 # NotFound, or Conflict while anything clashes
        return _view(kind, 20)
    if studyrun.STUDY_JOB.running:
        raise errors.Conflict("A study is running: start this when it has finished.")
    _free(studyrun.LOCK, studyrun.BUSY)                 # a study in a terminal reads the prices an update rewrites
    if updater.JOB.state["status"] == "running":
        raise errors.Conflict("An update is already running." if kind == "update" else
                              "An update is running: it rebuilds the readings when it finishes.")
    if kind == "update":
        _free(updater.UPDATE_LOCK, updater.BUSY)
    else:                                               # an update waits for a build; a rebuild on its own doesn't
        _free(updater.REPORT_LOCK, updater.REPORT_BUSY)
    if not job.start():
        raise errors.Conflict("The readings are already being rebuilt.")
    return _view(kind, 20)


def job_status(kind: str, tail: int = 20) -> dict:
    """The status of the job of `kind` (update, report, study) started from this session: idle, running, done or
    failed, when it started and finished, the error if it failed, the study's key, and the last `tail` log lines.
    Progress: `step` (i of n, the step's label), `progress` (the running phase within it: label, done of total),
    `steps` (every step with status pending, running, ok or failed and its one-line result) and `issues` (the
    newest problems so far: level warn or error, source, message; `issues_total` counts them all), plus
    `paused_hosts` (hosts paused after too many 429s). An update another process runs (the app, a terminal) is
    shown when this session runs none, with `elsewhere` set to its kind. The app's Operations page shows the same."""
    return _view(kind, tail)


TOOLS = (job_start, job_status)
