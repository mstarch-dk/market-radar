"""A job's live progress: the tracker (steps, phases, issues), the update's steps reporting to it, its state in the
operations log while it runs, and another process (the app, the MCP server) following it from there."""
import threading
import time
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from fakes import LOCAL
from radar import api, ops, sourcelog, updater
from radar.api_models import OpsJobDetail, OpsRunningJob, UpdateStatus
from radar.progress import ISSUES_MAX, Progress, issue, labelled, tick


def _wait(job):
    for _ in range(500):
        if job.state["status"] != "running":
            break
        time.sleep(0.01)
    return job.state


# ---------------- the tracker ----------------

def test_steps_are_counted_from_the_plan_and_an_unplanned_one_is_added():
    p = Progress()
    p.plan([("a", "A"), ("b", "B")])
    p.step("b", "B")
    assert p.state["step"] == {"i": 2, "n": 2, "key": "b", "label": "B"}
    p.finish("b", False, "boom")
    p.step("c", "C")
    s = p.snapshot()
    assert s["step"]["i"] == 3 and s["step"]["n"] == 3
    assert [(r["key"], r["status"], r["message"]) for r in s["steps"]] == [
        ("a", "pending", None), ("b", "failed", "boom"), ("c", "running", None)]


def test_a_new_step_starts_its_phase_over_and_a_plain_tick_keeps_the_phase_name():
    p = Progress("Working")
    p.step("prices", "Prices")
    labelled(p, "Known tickers")(40, 80)
    assert p.state["phase"] == {"done": 40, "total": 80, "label": "Known tickers"}
    p(80, 80)                                                       # a plain callback, same phase
    assert p.state["phase"]["label"] == "Known tickers"
    p.step("fred", "Macro (FRED)")
    assert p.state["phase"] is None


def test_issues_name_the_running_step_and_only_the_newest_are_kept():
    p = Progress()
    p.step("prices", "Prices")
    for i in range(ISSUES_MAX + 5):
        p.issue("warn", f"no data for T{i}")
    s = p.snapshot()
    assert s["issues_total"] == ISSUES_MAX + 5 and len(s["issues"]) == ISSUES_MAX
    assert s["issues"][-1] == {"level": "warn", "source": "prices", "message": f"no data for T{ISSUES_MAX + 4}"}


def test_a_plain_callback_or_none_still_works_and_hears_no_issues():
    seen = []
    tick(lambda d, t: seen.append((d, t)), 1, 2, "ignored")
    issue(lambda d, t: seen.append("issue"), "warn", "x")
    tick(None, 1, 2)
    issue(None, "warn", "x")
    assert seen == [(1, 2)]


def test_a_follower_hears_steps_and_issues_as_urgent_and_ticks_as_not():
    heard = []
    p = Progress(on_change=lambda s, urgent: heard.append(urgent))
    p.step("a", "A")
    p.phase(1, 2)
    p.issue("error", "A failed")
    assert heard == [True, False, True]


# ---------------- the update's steps ----------------

def test_run_steps_reports_each_step_and_a_failure_as_an_issue(monkeypatch):
    monkeypatch.setattr(sourcelog, "record", lambda *a, **k: None)
    p = Progress()
    updater.plan(p, [("ok", "Fine source"), ("bad", "Broken source")])

    def bad():
        raise ValueError("layout changed")
    updater.run_steps({"ok": ("Fine source", lambda: "3 rows"), "bad": ("Broken source", bad)}, lambda line: None, p)
    s = p.snapshot()
    assert [(r["key"], r["status"]) for r in s["steps"]] == [("ok", "ok"), ("bad", "failed")]
    assert s["steps"][0]["message"] == "3 rows"
    (i,) = s["issues"]
    assert i["level"] == "error" and i["source"] == "bad" and "layout changed" in i["message"]


def test_the_refresh_plans_every_step_and_the_report_last():
    p = Progress()
    updater.plan(p, [*updater.STEPS, updater.REPORT_STEP])
    keys = [s["key"] for s in p.state["steps"]]
    assert keys[:3] == ["prices", "reference", "fred"] and keys[-1] == "report"
    assert len(keys) == len(set(keys)) == 3 + len(updater.EXTERNAL) + 1


def test_an_app_job_keeps_its_steps_and_issues_after_it_ends():
    def work(log, progress):
        updater.plan(progress, [("a", "A")])
        progress.step("a", "A")
        progress(5, 10)
        progress.issue("warn", "no data for XYZ")
        progress.finish("a", True, "done")
    job = updater.UpdateJob(work)
    job.start()
    st = UpdateStatus.model_validate(_wait(job))
    assert st.status == "done" and st.progress is None and st.step is None
    assert [s.status for s in st.steps] == ["ok"] and st.issues[0].message == "no data for XYZ"
    (j,) = ops.jobs()
    d = OpsJobDetail.model_validate(ops.job_detail(j["id"]))
    assert d.progress is not None and d.progress.issues_total == 1 and d.heartbeat


# ---------------- the operations log, while it runs ----------------

def test_a_running_job_is_readable_from_the_log_as_it_goes():
    jid = ops.job_start("cli_run")
    live = ops.Live(jid, every=0)
    p = Progress(on_change=lambda s, urgent: live.update(progress=s, urgent=urgent))
    p.plan([("prices", "Prices")])
    p.step("prices", "Prices")
    labelled(p, "Known tickers")(80, 560)
    live.update(lines=["12:00:00 Updating 560 tickers…"])
    ops.record_request("query1.finance.yahoo.com", "/v8", "GET", 429, False, 5)
    with ops.context(job=jid):
        ops.record_request("query1.finance.yahoo.com", "/v8", "GET", 200, True, 5)
    (r,) = ops.running_jobs()
    row = OpsRunningJob.model_validate(r)
    assert row.kind == "cli_run" and not row.stale and row.requests == 1
    assert row.progress and row.progress.step and row.progress.step.label == "Prices"
    assert row.progress.phase and row.progress.phase.model_dump() == {"done": 80, "total": 560, "label": "Known tickers"}
    assert row.log == ["12:00:00 Updating 560 tickers…"]
    assert OpsJobDetail.model_validate(ops.job_detail(jid)).log == ["12:00:00 Updating 560 tickers…"]
    live.close()
    ops.job_finish(jid, "done", None, ["12:00:00 Updating 560 tickers…", "12:05:00 Prices: 9 rows."])
    assert ops.running_jobs() == []
    assert ops.job_detail(jid)["log"][-1].endswith("Prices: 9 rows.")      # the final log wins once it is written


def test_a_job_silent_for_minutes_is_stale_and_one_without_live_state_too(monkeypatch):
    old = ops.job_start("cli_run")                                       # an older version: no live row
    jid = ops.job_start("update")
    ops.Live(jid).close()
    real = ops.now
    monkeypatch.setattr(ops, "now", lambda: real() + timedelta(seconds=ops.STALE_S + 1))
    rows = {r["id"]: r for r in ops.running_jobs()}
    assert rows[old]["stale"] and rows[old]["quiet_s"] is None and rows[jid]["stale"]
    assert updater.elsewhere() is None


def test_a_new_server_leaves_a_job_with_a_recent_sign_of_life_running():
    mcp = ops.job_start("update")                                        # the MCP server's, alive
    ops.Live(mcp).close()
    dead = ops.job_start("update")                                       # an earlier server's
    ops.mark_interrupted()
    st = {j["id"]: j["status"] for j in ops.jobs()}
    assert st[mcp] == "running" and st[dead] == "interrupted"


def test_the_live_thread_keeps_a_quiet_job_alive():
    jid = ops.job_start("update")
    live = ops.Live(jid, beat=0.05)
    first = ops.running_jobs()[0]["heartbeat"]
    time.sleep(0.2)
    assert ops.running_jobs()[0]["heartbeat"] > first
    live.close()


# ---------------- another process following it ----------------

@pytest.fixture
def client(tmp_data):
    return TestClient(api.app, base_url=LOCAL)


def _terminal_run():
    """An update a terminal runs: in the operations log only, with live progress."""
    jid = ops.job_start("cli_run")
    live = ops.Live(jid)
    p = Progress()
    p.plan([("prices", "Prices"), ("fred", "Macro (FRED)")])
    p.step("prices", "Prices")
    p.issue("warn", "no data for 1: XYZ")
    live.close(p.snapshot(), ["12:00:00 Updating 3 tickers…"])
    return jid


def test_the_app_shows_an_update_a_terminal_runs_and_wont_start_another(client, monkeypatch):
    monkeypatch.setattr(updater, "JOB", updater.UpdateJob(lambda log, progress: None))
    assert client.get("/api/update").json()["status"] == "idle"
    jid = _terminal_run()
    st = client.get("/api/update").json()
    assert st["status"] == "running" and st["elsewhere"] == "cli_run" and st["step"]["label"] == "Prices"
    assert st["issues"][0]["message"] == "no data for 1: XYZ" and st["log"] == ["12:00:00 Updating 3 tickers…"]
    r = client.post("/api/update")
    assert r.status_code == 409 and "already running" in r.json()["detail"]["message"]
    (run,) = client.get("/api/ops/running").json()
    assert run["id"] == jid and run["progress"]["steps"][0]["status"] == "running"
    ops.job_finish(jid, "done")
    assert client.get("/api/update").json()["status"] == "idle" and client.get("/api/ops/running").json() == []


def test_the_terminal_prints_steps_phases_and_issues(capsys):
    from radar.cli.common import tracked_job

    with tracked_job("cli_update") as (log, progress):
        updater.plan(progress, [("prices", "Prices"), ("fred", "Macro (FRED)")])
        progress.step("prices", "Prices")
        labelled(progress, "Known tickers")(560, 560)
        progress.issue("warn", "no data for 1: XYZ")
        log("Prices: 9 rows.")
    err = capsys.readouterr().err
    assert "[1/2] Prices…" in err and "Known tickers: 560 of 560" in err and "! no data for 1: XYZ" in err
    (j,) = ops.jobs()
    d = ops.job_detail(j["id"])
    assert j["status"] == "done" and d["progress"]["issues_total"] == 1 and d["log"][-1].endswith("Prices: 9 rows.")


def test_an_app_job_is_written_live_for_other_processes():
    gate = threading.Event()

    def work(log, progress):
        progress.step("prices", "Prices")
        progress.issue("warn", "no data for XYZ")
        gate.wait(5)
    job = updater.UpdateJob(work)
    job.start()
    time.sleep(0.1)
    (r,) = ops.running_jobs()
    assert r["kind"] == "update" and r["progress"]["issues"][0]["message"] == "no data for XYZ"
    gate.set()
    _wait(job)
