"""Running a study from the Evidence page (studyrun.py): the study's own command as a child process, one at a time."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import studyrun
from ..api_models import StudyRunStatus

router = APIRouter()


@router.get("/api/studies/run", response_model=StudyRunStatus)
def study_status() -> dict:
    """The study started from the app: which one, its status and log lines (the command's own progress)."""
    return studyrun.STUDY_JOB.state


@router.post("/api/studies/run/{key}", response_model=StudyRunStatus)
def start_study(key: str) -> dict:
    """Start the study `key` (an Evidence head's `run_key`) in the background: 404 for an unknown study, 409
    while a study (in the app or a terminal), an update or a rebuild of the readings runs."""
    studyrun.STUDY_JOB.start(key)
    return studyrun.STUDY_JOB.state


@router.delete("/api/studies/run", response_model=StudyRunStatus)
def cancel_study() -> dict:
    """Stop the running study; its report keeps the last finished run's numbers. 409 if none runs."""
    if not studyrun.STUDY_JOB.cancel():
        raise HTTPException(409, "No study is running.")
    return studyrun.STUDY_JOB.state
