"""Rebuilding the readings without downloading: a dashboard knows what it was built from (`dashboard.outdated`),
the app can rebuild it (`/api/report`), does so by itself after an upgrade changed its shape, and one build runs
at a time across the app and a terminal."""
import os
import time

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

import world
from radar import api, cli, dashboard, ingest, locks, report, updater
from radar.fundamentals.store import YAHOO_FILE  # the synthetic world keeps its prices in memory; this one is on disk
from test_updater import held  # noqa: F401 - the fixture


@pytest.fixture
def client(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers: {})
    api.reset()
    dashboard.reset()
    monkeypatch.setattr(updater, "REPORT_JOB", updater.UpdateJob(updater.rebuild_readings, "Building the readings", "report"))
    monkeypatch.setattr(updater, "JOB", updater.UpdateJob(lambda log, progress: None))
    report.build()
    return TestClient(api.app)


def _touch(f) -> None:
    t = f.stat().st_mtime + 10
    os.utime(f, (t, t))


def _wait(job) -> dict:
    for _ in range(600):
        if job.state["status"] != "running":
            return job.state
        time.sleep(0.1)
    raise AssertionError("the rebuild did not finish")


def test_a_fresh_build_is_not_outdated_and_a_changed_input_is(client):
    d = dashboard.load()
    assert d["build"]["format"] == dashboard.FORMAT and d["build"]["inputs"]["fundamentals_yahoo"] is not None
    assert dashboard.outdated(d) is None
    _touch(YAHOO_FILE)
    assert dashboard.outdated(d) == {"reason": "inputs", "changed": ["fundamentals_yahoo"]}


def test_an_older_shape_is_outdated_whatever_its_inputs(client, monkeypatch):
    d = dashboard.load()
    monkeypatch.setattr(dashboard, "FORMAT", dashboard.FORMAT + 1)
    assert dashboard.outdated(d) == {"reason": "format", "changed": []}
    assert dashboard.outdated({k: v for k, v in d.items() if k != "build"})["reason"] == "format"   # before builds were recorded


def test_the_pages_say_so_and_the_app_rebuilds_it(client):
    assert client.get("/api/momentum").json()["outdated"] is None
    _touch(YAHOO_FILE)
    o = client.get("/api/momentum").json()["outdated"]
    assert o == {"reason": "inputs", "changed": ["fundamentals_yahoo"], "rebuilding": False}
    r = client.post("/api/report")
    assert r.status_code == 200 and r.json()["status"] == "running"
    st = _wait(updater.REPORT_JOB)
    assert st["status"] == "done", st
    assert any("Regime:" in line for line in st["log"])
    assert client.get("/api/momentum").json()["outdated"] is None


def test_no_rebuild_while_an_update_runs_or_another_rebuild(client, monkeypatch):
    monkeypatch.setitem(updater.JOB.state, "status", "running")
    _touch(YAHOO_FILE)
    assert client.get("/api/regime").json()["outdated"] is None      # the update rebuilds them when it finishes
    r = client.post("/api/report")
    assert r.status_code == 409 and "update is running" in r.json()["detail"]["message"]
    monkeypatch.setitem(updater.JOB.state, "status", "idle")
    monkeypatch.setitem(updater.REPORT_JOB.state, "status", "running")
    assert client.get("/api/regime").json()["outdated"]["rebuilding"] is True
    assert client.post("/api/report").status_code == 409


def test_the_app_rebuilds_an_older_shape_at_start(client, monkeypatch):
    api.rebuild_if_older(("ok", None))                                # same shape: nothing to do
    assert updater.REPORT_JOB.state["status"] == "idle"
    monkeypatch.setattr(dashboard, "FORMAT", dashboard.FORMAT + 1)
    api.rebuild_if_older(("ok", None))
    assert _wait(updater.REPORT_JOB)["status"] == "done"
    assert dashboard.outdated(dashboard.load()) is None


def test_one_build_at_a_time(client, held):  # noqa: F811
    held(updater.REPORT_LOCK)
    with pytest.raises(locks.Busy, match="already being built"):
        updater.build_report(lambda m: None, wait=0)
    res = CliRunner().invoke(cli.app, ["report"])
    assert res.exit_code == 1 and "already being built" in res.output
    updater.REPORT_JOB._run()
    assert updater.REPORT_JOB.state["status"] == "failed" and "already being built" in updater.REPORT_JOB.state["error"]
