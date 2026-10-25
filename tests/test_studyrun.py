"""Running a study from the app (studyrun.py, /api/studies/run): only the studies the Evidence page knows, as a
child process of the study's own command, one at a time with an update, a rebuild or a terminal run, its log
kept and cancellable; and a changing request from another site gets 403."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from datetime import date

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from fakes import LOCAL
from radar import api, cli, errors, evidence, locks, ops, studyrun, updater
from radar.model import artifacts as art


def child(code: str):
    """A stand-in for `python -m radar study …`: this interpreter running `code`, whatever the study."""
    return lambda command: [sys.executable, "-c", code]


@contextmanager
def held_elsewhere():
    """The study lock held by someone else (another thread: a holder's own thread may take it again)."""
    taken, done = threading.Event(), threading.Event()

    def hold():
        with locks.file_lock(studyrun.LOCK, timeout=0):
            taken.set()
            done.wait(30)
    t = threading.Thread(target=hold)
    t.start()
    taken.wait(10)
    try:
        yield
    finally:
        done.set()
        t.join()


def wait(job: studyrun.StudyJob) -> dict:
    for _ in range(300):
        if not job.running:
            return job.state
        time.sleep(0.05)
    raise AssertionError("the study did not finish")


@pytest.fixture
def jobs(monkeypatch):
    """Idle update and rebuild jobs, so a test can mark one running."""
    monkeypatch.setattr(updater, "JOB", updater.UpdateJob(lambda log, progress: None))
    monkeypatch.setattr(updater, "REPORT_JOB", updater.UpdateJob(lambda log, progress: None, kind="report"))


def test_every_study_on_the_evidence_page_can_be_run_and_nothing_else():
    known = studyrun.commands()
    assert known["score-study:momentum"] == "radar study score"
    assert known["score-study:qv"] == "radar study score --signal qv"
    assert {"longrun-study", "exit-study", "redeploy-study", "propose-study"} <= set(known)
    assert "score-study" not in known
    head = evidence.head(art.Loaded("exit-study", "missing"), "Stop rule", "radar study exits", None, 30, date(2026, 1, 2))
    assert head["run_key"] in known
    assert studyrun.argv("radar study score --signal qv")[1:] == ["-m", "radar", "study", "score", "--signal", "qv"]
    with pytest.raises(errors.NotFound):
        studyrun.StudyJob().start("rm -rf")


def test_python_dash_m_radar_is_the_command_line():
    out = subprocess.run([sys.executable, "-m", "radar", "--help"], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0 and "study" in out.stdout


def test_a_run_keeps_the_child_log_and_its_end(jobs):
    job = studyrun.StudyJob(launch=child("import sys; print('Panels built', file=sys.stderr); print('quiet')"))
    job.start("exit-study")
    st = wait(job)
    assert st["status"] == "done" and st["study"] == "exit-study" and st["error"] is None
    assert any(line.endswith("Panels built") for line in st["log"]) and not any("quiet" in x for x in st["log"])
    bad = studyrun.StudyJob(launch=child("raise SystemExit('Not studied: no prices')"))
    bad.start("exit-study")
    st = wait(bad)
    assert st["status"] == "failed" and st["error"] == "Not studied: no prices"


def test_a_running_study_can_be_cancelled_and_its_job_is_closed(jobs):
    job = studyrun.StudyJob(launch=child("import sys, time; print('started', file=sys.stderr, flush=True); "
                                         "time.sleep(60)"))
    assert not job.cancel()
    job.start("exit-study")
    for _ in range(200):                     # the child is up
        if any("started" in x for x in job.state["log"]):
            break
        time.sleep(0.05)
    jid = ops.job_start(studyrun.KIND)       # what the child's cli/common.job would have recorded
    assert job.cancel()
    st = wait(job)
    assert st["status"] == "failed" and st["error"] == "Cancelled"
    assert ops.job_detail(jid)["status"] == "interrupted"


def test_cancel_ends_the_whole_process_tree(tmp_path):
    """A child that starts its own child (as a venv's python.exe launcher does on Windows): both end."""
    pid_file = tmp_path / "grandchild.pid"
    code = ("import subprocess, sys, time; "
            "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
            f"open(r'{pid_file}', 'w').write(str(p.pid)); time.sleep(60)")
    proc = subprocess.Popen([sys.executable, "-c", code])
    for _ in range(200):
        if pid_file.exists() and pid_file.read_text():
            break
        time.sleep(0.05)
    grandchild = int(pid_file.read_text())
    studyrun.kill(proc)
    proc.wait(10)
    for _ in range(100):
        if not alive(grandchild):
            break
        time.sleep(0.05)
    assert not alive(grandchild)


def alive(pid: int) -> bool:
    if sys.platform == "win32":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_one_at_a_time_with_updates_rebuilds_and_terminals(jobs, monkeypatch):
    job = studyrun.StudyJob(launch=child("import time; time.sleep(60)"))
    monkeypatch.setitem(updater.JOB.state, "status", "running")
    with pytest.raises(errors.Conflict, match="update is running"):
        job.start("exit-study")
    monkeypatch.setitem(updater.JOB.state, "status", "idle")
    monkeypatch.setitem(updater.REPORT_JOB.state, "status", "running")
    with pytest.raises(errors.Conflict, match="rebuilt"):
        job.start("exit-study")
    monkeypatch.setitem(updater.REPORT_JOB.state, "status", "idle")
    with held_elsewhere(), pytest.raises(errors.Conflict, match="Not started"):
        job.start("exit-study")             # a study in a terminal holds the lock
    job.start("exit-study")
    try:
        with pytest.raises(errors.Conflict, match="already running"):
            job.start("redeploy-study")
    finally:
        job.cancel()
        wait(job)


def test_a_study_in_a_terminal_waits_for_the_one_running():
    with held_elsewhere():
        res = CliRunner().invoke(cli.app, ["study", "exits"])
    assert res.exit_code == 1 and "Not started: a study is already running" in res.output


@pytest.fixture
def client(tmp_data, jobs, monkeypatch):
    monkeypatch.setattr(studyrun, "STUDY_JOB", studyrun.StudyJob(launch=child("import time; time.sleep(60)")))
    api.reset()
    return TestClient(api.app, base_url=LOCAL)


def test_the_api_starts_reports_and_cancels_a_study(client):
    assert client.get("/api/studies/run").json()["status"] == "idle"
    assert client.post("/api/studies/run/no-such-study").status_code == 404
    r = client.post("/api/studies/run/score-study:quality")
    assert r.status_code == 200 and r.json()["status"] == "running" and r.json()["study"] == "score-study:quality"
    assert client.post("/api/studies/run/exit-study").status_code == 409
    assert client.post("/api/update").status_code == 409 and client.post("/api/report").status_code == 409
    assert client.delete("/api/studies/run").status_code == 200
    assert wait(studyrun.STUDY_JOB)["error"] == "Cancelled"
    assert client.delete("/api/studies/run").status_code == 409


def test_a_changing_request_from_another_site_is_refused(client):
    evil = client.post("/api/studies/run/exit-study", headers={"origin": "https://example.com"})
    assert evil.status_code == 403 and studyrun.STUDY_JOB.state["status"] == "idle"
    rebound = TestClient(api.app, base_url="http://attacker.example").post("/api/report")
    assert rebound.status_code == 403
    assert client.get("/api/studies/run", headers={"origin": "https://example.com"}).status_code == 200   # reads pass
    ok = client.post("/api/studies/run/exit-study", headers={"origin": "http://localhost:5173"})
    assert ok.status_code == 200
    client.delete("/api/studies/run")
    wait(studyrun.STUDY_JOB)
