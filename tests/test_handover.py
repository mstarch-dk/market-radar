"""What a non-technical user does without a terminal: refresh data and import a portfolio from the app, and
`radar doctor` explaining what's missing."""
import threading
import time

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

import world
from radar import api, cli, dashboard, updater
from radar.sources import ingest
from test_holdings_import import HEADER, _row


@pytest.fixture
def client(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers, progress=None: {})
    api.reset()
    dashboard.reset()
    return TestClient(api.app)


def _wait(job, timeout=5):
    end = time.time() + timeout
    while job.state["status"] == "running" and time.time() < end:
        time.sleep(0.01)
    return job.state


def test_one_update_at_a_time_with_log_and_progress():
    gate = threading.Event()

    def work(log, progress):
        log("Prices: 10 rows.")
        progress(80, 700)
        gate.wait(5)
    job = updater.UpdateJob(work)
    assert job.start() is True
    time.sleep(0.05)
    assert job.state["status"] == "running" and job.state["progress"] == {"done": 80, "total": 700, "label": "Downloading prices"}
    assert job.start() is False                                              # refused while running
    gate.set()
    st = _wait(job)
    assert st["status"] == "done" and st["log"][0].endswith("Prices: 10 rows.") and st["finished"] and st["progress"] is None


def test_a_failing_update_is_reported_not_raised():
    def work(log, progress):
        raise SystemExit("No price data yet – run `radar update` first.")
    job = updater.UpdateJob(work)
    job.start()
    st = _wait(job)
    assert st["status"] == "failed" and "No price data yet" in st["error"] and "Stopped" in st["log"][-1]


def test_update_endpoints(client, monkeypatch):
    calls = []
    monkeypatch.setattr(updater, "JOB", updater.UpdateJob(lambda log, progress: calls.append(1)))
    assert client.get("/api/update").json()["status"] == "idle"
    assert client.post("/api/update").status_code == 200
    _wait(updater.JOB)
    assert client.get("/api/update").json()["status"] == "done" and calls == [1]


def test_update_refused_while_running(client, monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(updater, "JOB", updater.UpdateJob(lambda log, progress: gate.wait(5)))
    client.post("/api/update")
    r = client.post("/api/update")
    gate.set()
    assert r.status_code == 409 and "already running" in r.json()["detail"]["message"]


def test_import_from_the_app(client, tmp_data):
    csv = "\n".join([HEADER, _row("S3", 20260105, 100, 10, "BUY"), _row("E3")]) + "\n"
    r = client.post("/api/import", content=csv.encode(), headers={"Content-Type": "text/csv"})
    assert r.status_code == 200 and r.json() | {"warnings": {}} == {"holdings": 1, "sold": 0, "watch": 1, "warnings": {}}
    statuses = {t["symbol"]: t["status"] for t in client.get("/api/context").json()["tickers"]}
    assert statuses == {"S3": "holding", "E3": "watch"}                     # replaces the previous import


def test_import_rejects_other_files_and_keeps_the_previous_import(client, tmp_data):
    before = (tmp_data / "holdings.csv").read_text(encoding="utf-8")
    assert client.post("/api/import", content=b"").status_code == 400
    r = client.post("/api/import", content=b"Date,Open,Close\n2026-01-01,1,2\n")
    assert r.status_code == 400 and "Yahoo Finance portfolio export" in r.json()["detail"]["message"]
    assert (tmp_data / "holdings.csv").read_text(encoding="utf-8") == before


def test_doctor_explains_what_is_missing(tmp_data, monkeypatch):

    res = CliRunner().invoke(cli.app, ["doctor", "--offline"])
    assert "[WARN] Market data: not downloaded yet" in res.output
    assert "Download market data" in res.output                              # the fix, in plain words
    assert "Internet" not in res.output                                      # --offline skips the network


def test_doctor_names_a_bad_setting(monkeypatch):
    from radar import config_schema, health

    def broken():
        raise config_schema.SettingsError("config/settings.yaml is invalid: backtest.fee_bps: missing")
    monkeypatch.setattr(health, "settings", broken)
    got = {c["name"]: c for c in health.checks(offline=True)}["Settings"]
    assert got["status"] == "fail" and "backtest.fee_bps: missing" in got["detail"]


def test_doctor_tells_a_server_error_from_no_connection_and_a_paused_site(tmp_data, monkeypatch):
    from datetime import datetime, timedelta

    from fakes import Resp, serve
    from radar import health, net, ops

    serve(monkeypatch, {"yahoo": Resp(200), "stlouisfed": Resp(503), "cftc": ConnectionError("refused")},
          default=Resp(404))                                  # a 4xx means the site answers: fine for this check
    ops.set_cooldown("sdmx.oecd.org", datetime.now() + timedelta(hours=1), "429s", strikes=1)
    net.reset()
    got = {c["name"].removeprefix("Internet: "): c for c in health.checks() if c["name"].startswith("Internet")}
    assert got["Yahoo Finance (prices)"]["status"] == "ok" and got["iShares (STOXX 600 holdings)"]["status"] == "ok"
    assert (got["FRED (US macro)"]["status"], got["FRED (US macro)"]["detail"]) == ("warn", "HTTP 503")
    assert got["CFTC (futures positioning)"]["status"] == "fail"
    assert "no connection (ConnectionError)" in got["CFTC (futures positioning)"]["detail"]
    oecd = got["OECD (leading indicators)"]
    assert oecd["status"] == "warn" and "paused" in oecd["detail"] and "Operations page" in oecd["fix"]
