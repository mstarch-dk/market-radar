"""The update itself: one at a time across the app and a terminal, and one failing step never stops the rest."""
import threading

import pytest
from typer.testing import CliRunner

from radar import cli, coverage, external, ingest, locks, updater, universe
from radar.discovery import scan


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
