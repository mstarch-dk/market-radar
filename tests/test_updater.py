"""The update itself: one at a time across the app and a terminal, and one failing step never stops the rest."""
import threading

import pandas as pd
import pytest
from typer.testing import CliRunner

from radar import cli, locks, sourcelog, universe, updater
from radar.discovery import scan
from radar.fundamentals import edgar, yahoo
from radar.portfolios import trades
from radar.sources import constituents, external, factors, ingest, sentiment, valuation


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
        scan.run(set(), lambda m: None)


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


def test_the_prices_step_says_which_tickers_are_late_short_or_missing(tmp_data, monkeypatch):
    from radar import ops
    from radar.sources import tracked

    late = [f"L{i:02}" for i in range(14)]
    monkeypatch.setattr(universe, "all_price_tickers", lambda *a, **k: ["A"])
    monkeypatch.setattr(ingest, "update_prices", lambda *a, **k: {
        "rows": 1234, "new": 1, "asof": "2026-10-16", "behind": set(late), "short": {"S1"}, "deepened": 2,
        "rebased": ["R1"], "missing": ["M1", "M2"]})
    monkeypatch.setattr(universe, "names", lambda t: None)
    monkeypatch.setattr(universe, "sectors", lambda t: None)
    monkeypatch.setattr(tracked, "stock_groups", lambda: {})
    monkeypatch.setattr(ingest, "update_fred", lambda series: ["DGS10"])
    monkeypatch.setattr(updater, "update_external", lambda log: None)
    updater.update(lambda m: None)
    log = sourcelog.load_log()
    msg = log["prices"]["detail"]
    assert msg.startswith("1,234 rows, 1 new tickers; 14 without a bar for 2026-10-16")
    assert "L11 and 2 more" in msg and "L12" not in msg                      # twelve named, the rest counted
    assert "1 with a Yahoo history shorter than the one stored" in msg and "S1" in msg
    assert "2 downloaded again further back" in msg and "re-based the history: R1" in msg
    assert msg.endswith("no data for 2: M1, M2")
    warns = [e["message"] for e in ops.events() if e["kind"] == "source" and e["level"] == "warn"]
    assert any("14 without a bar" in w for w in warns) and any("shorter than the one stored" in w for w in warns)
    assert log["fred"]["error"] == "RuntimeError: failed: DGS10; those series keep their cached values"


# ---------------- updater: one failing step never stops the rest ----------------

def test_a_failing_step_is_recorded_and_the_next_steps_still_run(tmp_data):
    ran, lines = [], []

    def boom():
        ran.append("b")
        raise RuntimeError("source down")
    updater.run_steps({"a": ("Step A", lambda: ran.append("a") or "3 rows"),
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
    updater.run_steps({"a": ("A", lambda: "ok")}, lambda m: None)
    first = sourcelog.load_log()["a"]["last_success"]
    updater.run_steps({"a": ("A", lambda: (_ for _ in ()).throw(ValueError("bad shape")))}, lambda m: None)
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
    monkeypatch.setattr(constituents, "update_acwi_segments", ok("acwi_segments"))
    monkeypatch.setattr(valuation, "update_etfs", ok("valuation_etfs"))
    monkeypatch.setattr(valuation, "update_stocks", ok("valuation_stocks"))
    calendar_args = {}
    monkeypatch.setattr(external, "update_calendar",
                        lambda tickers, **k: calendar_args.update(k) or ran.append("calendar") or "up to date")
    monkeypatch.setattr(edgar, "update_edgar", ok("fundamentals_edgar"))
    monkeypatch.setattr(yahoo, "update_yahoo", ok("fundamentals_yahoo"))
    lines = []
    updater.update_external(lines.append)
    assert ran == ["cftc", "oecd", "factset", "analyst", "ecb", "cape", "erp", "putcall", "aaii", "factors",
                   "acwi_segments", "valuation_etfs", "valuation_stocks", "calendar", "fundamentals_edgar", "fundamentals_yahoo"]
    assert set(calendar_args) == {"max_age_days", "near_days", "near_max_age_hours"}   # calendar.refresh
    log = sourcelog.load_log()
    assert log["ecb"]["error"] == "ValueError: ECB changed its format"
    assert log["cftc"]["detail"] == "5 new rows" and log["factset"]["detail"] == "no new report"
    assert all(log[k]["error"] is None for k in log if k != "ecb")
    assert any("ECB euro-area rates: FAILED" in line and "using cached data" in line for line in lines)
