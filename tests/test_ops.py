"""The operations log (ops.db): recording, housekeeping, the summary, jobs, and the Operations endpoints."""
import threading
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from radar import api, coverage, net, ops, updater
from radar.api_models import OpsJobDetail, OpsSummary


def test_summary_per_host_and_source_with_percentiles():
    for ms in (10, 20, 30, 40, 1000):
        with ops.context(source="fred"):
            ops.record_request("fred.stlouisfed.org", "/x", "GET", 200, True, ms)
    with ops.context(source="fred"):
        ops.record_request("fred.stlouisfed.org", "/x", "GET", 503, False, 5, error=None)
    s = OpsSummary.model_validate(ops.summary(7, net.limits)).model_dump()
    (row,) = s["rows"]
    assert row["source"] == "fred" and row["requests"] == 6 and row["errors"] == 1 and row["error_pct"] == 16.7
    assert row["p50_ms"] == 25 and row["p95_ms"] > 500 and row["last_error"] == "HTTP 503"
    assert sum(row["daily"]) == 6 and len(row["daily"]) == 7 and s["requests_24h"] == 6 and s["errors_24h"] == 1


def test_an_empty_log_says_so():
    s = ops.summary(7)
    assert s["rows"] == [] and s["last_update"] is None and s["requests_24h"] == 0


def test_prune_keeps_recent_rows_only(monkeypatch):
    old = datetime(2026, 1, 1)
    monkeypatch.setattr(ops, "now", lambda: old)
    ops.record_request("a.org", "/", "GET", 200, True, 1)
    ops.event("info", "source", "old")
    jid = ops.job_start("update")
    ops.job_finish(jid, "done")
    monkeypatch.setattr(ops, "now", lambda: old + timedelta(days=60))
    ops.record_request("a.org", "/", "GET", 200, True, 1)
    ops.prune()
    assert len(ops.requests()) == 1            # requests kept 30 days
    assert len(ops.events()) == 1 and len(ops.jobs()) == 1   # events and jobs 180


def test_job_context_records_status_log_and_attribution():
    lines = []
    with ops.job("cli_run", lines) as jid:
        lines.append("12:00:00 Prices: 10 rows.")
        ops.record_request("a.org", "/", "GET", 200, True, 1)
    with pytest.raises(RuntimeError), ops.job("cli_run"):
        raise RuntimeError("boom")
    jobs = ops.jobs()
    assert [j["status"] for j in jobs] == ["failed", "done"] and "boom" in jobs[0]["error"]
    d = OpsJobDetail.model_validate(ops.job_detail(jid))
    assert d.log == ["12:00:00 Prices: 10 rows."] and d.requests == 1 and d.errors == 0


def test_update_job_is_recorded(monkeypatch):
    def work(log, progress):
        log("Prices: 1 row.")
        ops.record_request("a.org", "/", "GET", 200, True, 1)
    job = updater.UpdateJob(work)
    job.start()
    for _ in range(500):
        if job.state["status"] != "running":
            break
        threading.Event().wait(0.01)
    (j,) = ops.jobs()
    assert j["kind"] == "update" and j["status"] == "done"
    d = ops.job_detail(j["id"])
    assert d["requests"] == 1 and d["log"][0].endswith("Prices: 1 row.")


def test_interrupted_jobs_are_marked():
    ops.job_start("update")
    ops.mark_interrupted()
    assert ops.jobs()[0]["status"] == "interrupted"


def test_source_records_are_atomic_and_become_events(tmp_data):
    def rec(i):
        coverage.record(f"s{i}", True, f"{i} rows")
    threads = [threading.Thread(target=rec, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert set(coverage.load_log()) == {f"s{i}" for i in range(20)}   # no write lost
    coverage.record("cftc", False, error="ValueError: bad layout", exc=ValueError("bad layout"))
    ev = ops.events(level="error")[0]
    assert ev["kind"] == "parse" and ev["source"] == "cftc" and "ValueError" in ev["detail"]


def test_live_coverage_overlays_the_current_log(tmp_data):
    view = {"sources": [{"key": "cftc", "name": "Futures positioning", "error": None, "last_attempt": "old",
                         "last_success": "old"}], "failing": []}
    coverage.record("cftc", False, error="HTTPError: 503")
    out = coverage.live(view)
    assert out["sources"][0]["error"] == "HTTPError: 503" and out["failing"] == ["Futures positioning"]
    assert out["sources"][0]["last_success"] is None


# ---------------- endpoints ----------------

@pytest.fixture
def client(tmp_data):
    return TestClient(api.app)


def test_ops_endpoints(client):
    with ops.context(source="cftc"):
        ops.record_request("publicreporting.cftc.gov", "/resource", "GET", 200, True, 12.5)
    ops.event("error", "source", "it broke", source="cftc")
    assert client.get("/api/ops/summary?days=3").json()["rows"][0]["host"] == "publicreporting.cftc.gov"
    assert client.get("/api/ops/events?level=error").json()[0]["message"] == "it broke"
    assert client.get("/api/ops/events?level=info").json() == []
    assert client.get("/api/ops/requests?source=cftc").json()[0]["duration_ms"] == 12.5
    assert client.get("/api/ops/jobs").json() == []
    assert client.get("/api/ops/jobs/99").status_code == 404
    checks = client.get("/api/ops/doctor").json()       # offline: no network
    assert all(not c["name"].startswith("Internet") for c in checks)


def test_cooldown_can_be_cleared_from_the_app(client):
    assert client.delete("/api/ops/cooldown/x.org").status_code == 404
    ops.set_cooldown("x.org", ops.now() + timedelta(minutes=15), "3 × HTTP 429", 1)
    assert [c["host"] for c in client.get("/api/ops/summary").json()["cooldowns"]] == ["x.org"]
    assert client.delete("/api/ops/cooldown/x.org").json() is True
    assert client.get("/api/ops/summary").json()["cooldowns"] == []


def test_server_errors_are_recorded_but_not_user_errors(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kaput")
    monkeypatch.setattr(api.ops, "jobs", boom)
    c = TestClient(api.app, raise_server_exceptions=False)
    assert c.get("/api/ops/jobs").status_code == 500
    assert client.get("/api/ops/jobs/99").status_code == 404
    (ev,) = ops.events(kind="api")
    assert "kaput" in ev["message"] and ev["source"] == "app:ops" and "RuntimeError" in ev["detail"]
