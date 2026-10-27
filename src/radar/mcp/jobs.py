"""Tools that start the radar's long jobs and report on them: the update, the rebuild of the readings and a study.
They run like the app's (the update and the rebuild in a thread of this process, a study as a child process), are
recorded in the operations log, and check the same locks first, so a job already running in the app or a terminal
is reported, not started twice."""
from __future__ import annotations

from .. import errors, locks, studyrun, updater
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
    s = _job(kind).state
    return {"kind": kind, **s, "log": s["log"][-tail:] if tail > 0 else []}


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
    failed, when it started and finished, the error if it failed, its progress, the study's key, and the last
    `tail` log lines. A job started in the app or a terminal shows on the Operations page, not here."""
    return _view(kind, tail)


TOOLS = (job_start, job_status)
