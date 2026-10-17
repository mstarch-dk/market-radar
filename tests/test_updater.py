"""The update itself: one at a time across the app and a terminal, and one failing step never stops the rest."""
import threading

import pandas as pd
import pytest
from typer.testing import CliRunner

from radar import cli, external, factors, ingest, locks, sentiment, sourcelog, trades, universe, updater, valuation
from radar.discovery import scan
from radar.fundamentals import edgar, yahoo


@pytest.fixture
def held():
    """Hold a lock from another thread (as another process would) until the test ends."""
    stop, threads = threading.Event(), []

    def hold(path):
        ready = threading.Event()

        def run():
            with locks.file_lock(path):
                ready.set()
                stop.wait(10)
        t = threading.Thread(target=run)
        t.start()
        ready.wait(5)
        threads.append(t)
    yield hold
    stop.set()
    [t.join(5) for t in threads]


def test_a_second_update_is_refused_while_one_runs(tmp_data, monkeypatch, held):
    asked = []
    monkeypatch.setattr(universe, "all_price_tickers", lambda *a, **k: asked.append(1) or [])
    held(updater.UPDATE_LOCK)
    with pytest.raises(locks.Busy, match="already running"):
        updater.update(lambda m: None)
    assert asked == []                                  # refused before anything was asked for


def test_the_app_job_reports_it_and_the_terminal_exits_with_an_error(tmp_data, monkeypatch, held):
    held(updater.UPDATE_LOCK)
    job = updater.UpdateJob(lambda log, progress: updater.update(log))
    job._run()
    assert job.state["status"] == "failed" and "already running" in job.state["error"]
    res = CliRunner().invoke(cli.app, ["update"])
    assert res.exit_code == 1 and "already running" in res.output


def test_a_discovery_scan_is_one_at_a_time_too(tmp_data, held):
    held(scan.SCAN_LOCK)
    with pytest.raises(locks.Busy, match="already running"):
        scan.run(lambda m: None)


def test_a_failing_name_lookup_does_not_stop_the_other_sources(tmp_data, monkeypatch):
    ran = []
    monkeypatch.setattr(universe, "all_price_tickers", lambda *a, **k: ["A"])
    monkeypatch.setattr(ingest, "update_prices", lambda *a, **k: {"rows": 0, "new": 0, "rebased": [], "missing": [],
                                                                   "behind": {}, "short": {}})
    monkeypatch.setattr(universe, "names", lambda t: (_ for _ in ()).throw(ValueError("names.csv is broken")))
    monkeypatch.setattr(ingest, "update_fred", lambda series: ran.append("fred") or [])
    monkeypatch.setattr(updater, "update_external", lambda log: ran.append("external"))
    lines = []
    updater.update(lines.append)
    assert ran == ["fred", "external"]
    assert any("names.csv is broken" in line for line in lines)


# ---------------- updater: one failing step never stops the rest ----------------

def test_a_failing_step_is_recorded_and_the_next_steps_still_run(tmp_data):
    ran, lines = [], []

    def boom():
        ran.append("b")
        raise RuntimeError("source down")
    updater._steps({"a": ("Step A", lambda: ran.append("a") or "3 rows"),
                    "b": ("Step B", boom),
                    "c": ("Step C", lambda: ran.append("c") or "fine")}, lines.append)
    assert ran == ["a", "b", "c"]
    log = sourcelog.load_log()
    assert log["a"]["detail"] == "3 rows" and log["a"]["error"] is None and "last_success" in log["a"]
    assert log["b"]["error"] == "RuntimeError: source down" and "last_success" not in log["b"]
    assert log["c"]["detail"] == "fine" and log["c"]["error"] is None
    assert "Step A: 3 rows." in lines
    assert "Step B: FAILED (RuntimeError: source down); using cached data." in lines


def test_a_failure_keeps_the_last_success_time_of_the_source(tmp_data):
    updater._steps({"a": ("A", lambda: "ok")}, lambda m: None)
    first = sourcelog.load_log()["a"]["last_success"]
    updater._steps({"a": ("A", lambda: (_ for _ in ()).throw(ValueError("bad shape")))}, lambda m: None)
    entry = sourcelog.load_log()["a"]
    assert entry["last_success"] == first and entry["error"] == "ValueError: bad shape"


def test_every_external_source_is_tried_even_when_one_raises(tmp_data, monkeypatch):
    ran = []

    def ok(name, value="done"):
        return lambda *a, **k: ran.append(name) or value

    def fails(*a, **k):
        ran.append("ecb")
        raise ValueError("ECB changed its format")
    monkeypatch.setattr(trades, "holdings", lambda: pd.DataFrame())
    monkeypatch.setattr(external, "update_cot", ok("cftc", 5))
    monkeypatch.setattr(external, "update_oecd_cli", ok("oecd"))
    monkeypatch.setattr(external, "update_factset", ok("factset", None))
    monkeypatch.setattr(external, "update_analyst", ok("analyst"))
    monkeypatch.setattr(external, "update_ecb", fails)
    monkeypatch.setattr(valuation, "update_cape", ok("cape"))
    monkeypatch.setattr(valuation, "update_erp", ok("erp"))
    monkeypatch.setattr(sentiment, "update_putcall", ok("putcall"))
    monkeypatch.setattr(sentiment, "update_aaii", ok("aaii"))
    monkeypatch.setattr(factors, "update_factors", ok("factors"))
    monkeypatch.setattr(valuation, "update_etfs", ok("valuation_etfs"))
    monkeypatch.setattr(valuation, "update_stocks", ok("valuation_stocks"))
    monkeypatch.setattr(edgar, "update_edgar", ok("fundamentals_edgar"))
    monkeypatch.setattr(yahoo, "update_yahoo", ok("fundamentals_yahoo"))
    lines = []
    updater.update_external(lines.append)
    assert ran == ["cftc", "oecd", "factset", "analyst", "ecb", "cape", "erp", "putcall", "aaii", "factors",
                   "valuation_etfs", "valuation_stocks", "fundamentals_edgar", "fundamentals_yahoo"]
    log = sourcelog.load_log()
    assert log["ecb"]["error"] == "ValueError: ECB changed its format"
    assert log["cftc"]["detail"] == "5 new rows" and log["factset"]["detail"] == "no new report"
    assert all(log[k]["error"] is None for k in log if k != "ecb")
    assert any("ECB euro-area rates: FAILED" in line and "using cached data" in line for line in lines)
