"""The shared write rules: a fresh download never shrinks what is stored (guard), one writer at a time
(locks), and a reader never sees half a file (config.write_atomic)."""
import threading
from datetime import timedelta

import pandas as pd
import pytest

from radar import config, guard, locks


def _long(keys: dict[str, tuple[str, int]]) -> pd.DataFrame:
    """{key: (first date, sessions)} → a long frame with ticker/date/close."""
    return pd.concat([pd.DataFrame({"ticker": k, "date": pd.bdate_range(start, periods=n), "close": 1.0})
                      for k, (start, n) in keys.items()], ignore_index=True)


def test_a_complete_answer_passes():
    old = _long({"A": ("2026-01-05", 20), "B": ("2026-01-05", 20)})
    new = _long({"A": ("2026-01-05", 21), "B": ("2026-01-05", 21)})
    out, notes = guard.check(old, new, what="t", key="ticker")
    assert out is new and notes == []


@pytest.mark.parametrize("new, problem", [
    (_long({"A": ("2026-01-05", 20)}), "B missing"),
    (_long({"A": ("2026-01-05", 20), "B": ("2026-01-12", 15)}), "B starts 2026-01-12"),
    (_long({"A": ("2026-01-05", 20), "B": ("2026-01-05", 18)}), "B ends"),
])
def test_less_than_stored_is_refused(new, problem):
    old = _long({"A": ("2026-01-05", 20), "B": ("2026-01-05", 20)})
    with pytest.raises(guard.Shrunk, match=problem):
        guard.check(old, new, what="t", key="ticker")


def test_tolerances_and_keys_no_longer_configured():
    old = _long({"A": ("2026-01-05", 20), "GONE": ("2026-01-05", 20)})
    new = _long({"A": ("2026-01-06", 18)})          # a day later, a session short, GONE dropped from config
    guard.check(old, new, what="t", key="ticker", expected_keys=["A"], start_tol=timedelta(days=1),
                end_tol=timedelta(days=1), row_tol=0.1)


def test_carry_keeps_a_missing_series_and_says_so():
    old = _long({"A": ("2026-01-05", 20), "B": ("2026-01-05", 20)})
    out, notes = guard.check(old, _long({"A": ("2026-01-05", 21)}), what="t", key="ticker", carry=True)
    assert set(out["ticker"]) == {"A", "B"} and len(out) == 41
    assert notes == ["kept the stored B (to 2026-01-30): not in the answer"]


def test_wide_frames_are_checked_per_column_and_carried(tmp_path):
    idx = pd.period_range("2020-01", periods=24, freq="M").to_timestamp()
    old = pd.DataFrame({"USA": range(24), "DEU": range(24)}, index=idx, dtype=float)
    with pytest.raises(guard.Shrunk, match="USA ends"):
        guard.check(old, old.iloc[:-2], what="cli", key=None, date=None)
    path = tmp_path / "cli.parquet"
    notes = guard.replace(path, old, old[["USA"]], what="cli", key=None, date=None, carry=True)
    back = pd.read_parquet(path)
    assert list(back.columns) == ["USA", "DEU"] and len(back) == 24 and notes


def test_empty_or_too_short_answers_are_refused_and_nothing_is_written(tmp_path):
    path = tmp_path / "x.parquet"
    old = _long({"A": ("2026-01-05", 20)})
    config.write_parquet(old, path, index=False)
    before = path.read_bytes()
    for bad in (old.iloc[0:0], None):
        with pytest.raises(guard.Shrunk):
            guard.replace(path, old, bad, what="x", key="ticker")
    with pytest.raises(guard.Shrunk, match="need 100"):
        guard.check(None, old, what="x", key="ticker", min_rows=100)
    assert path.read_bytes() == before


def test_a_single_long_series():
    old = pd.DataFrame({"date": pd.bdate_range("2026-01-05", periods=20), "v": 1.0})
    with pytest.raises(guard.Shrunk, match="ends"):
        guard.check(old, old.iloc[:-1], what="aaii", key=None, date="date")
    guard.check(old, old, what="aaii", key=None, date="date")


# ---------------- locks ----------------

def test_a_lock_makes_the_other_writer_wait_and_times_out(tmp_path):
    path = tmp_path / "prices.parquet"
    order, inside = [], threading.Event()

    def other():
        with locks.file_lock(path, timeout=5):
            order.append("other")

    with locks.file_lock(path):
        t = threading.Thread(target=other)
        t.start()
        t.join(0.3)
        assert t.is_alive() and order == []        # waits while held
        with locks.file_lock(path):                # the same thread again: no self-deadlock
            order.append("me")
    t.join(5)
    assert order == ["me", "other"]

    def holder():
        with locks.file_lock(path):
            inside.set()
            done.wait(5)
    done = threading.Event()
    h = threading.Thread(target=holder)
    h.start()
    inside.wait(5)
    with pytest.raises(locks.Busy, match="busy"), locks.file_lock(path, timeout=0):
        pass
    done.set()
    h.join(5)


# ---------------- atomic writes ----------------

def test_concurrent_writers_never_leave_a_broken_file(tmp_path):
    path = tmp_path / "x.parquet"
    errors = []

    def write(n):
        try:
            for _ in range(25):
                config.write_parquet(pd.DataFrame({"n": [n] * 50}), path, index=False)
        except Exception as e:  # noqa: BLE001
            errors.append(e)
    ts = [threading.Thread(target=write, args=(n,)) for n in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors
    assert len(pd.read_parquet(path)) == 50
    assert not list(tmp_path.glob("*.tmp"))


def test_a_failed_write_leaves_the_old_file_and_no_temp(tmp_path):
    path = tmp_path / "x.csv"
    config.write_text(path, "old")

    def boom(tmp):
        tmp.write_text("half")
        raise RuntimeError("disk full")
    with pytest.raises(RuntimeError):
        config.write_atomic(path, boom)
    assert path.read_text() == "old" and not list(tmp_path.glob("*.tmp"))


def test_replace_waits_for_a_windows_reader(tmp_path, monkeypatch):
    path = tmp_path / "x.txt"
    config.write_text(path, "old")
    real, calls = type(path).replace, []

    def flaky(self, target):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError("in use")
        return real(self, target)
    monkeypatch.setattr(type(path), "replace", flaky)
    monkeypatch.setattr(config.time, "sleep", lambda s: None)
    config.write_text(path, "new")
    assert path.read_text() == "new" and len(calls) == 3


@pytest.mark.skipif(__import__("os").name != "nt", reason="only Windows refuses to replace an open file")
def test_replace_succeeds_once_a_real_reader_lets_go(tmp_path):
    path = tmp_path / "x.txt"
    config.write_text(path, "old")
    f = open(path, "rb")  # noqa: SIM115                    # a reader (the app loading prices) holds it open
    t = threading.Timer(0.3, f.close)
    t.start()
    config.write_text(path, "new")                          # retries until the reader is done
    t.join()
    assert path.read_text() == "new"


def test_a_lock_held_by_another_process_is_respected(tmp_path):
    import subprocess
    import sys
    import time
    path = tmp_path / "prices.parquet"
    flag = tmp_path / "held"
    code = ("import sys, time, pathlib; from radar import locks\n"
            "with locks.file_lock(pathlib.Path(sys.argv[1])):\n"
            "    pathlib.Path(sys.argv[2]).write_text('1'); time.sleep(3)\n")
    proc = subprocess.Popen([sys.executable, "-c", code, str(path), str(flag)])
    try:
        deadline = time.monotonic() + 20
        while not flag.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert flag.exists()
        with pytest.raises(locks.Busy), locks.file_lock(path, timeout=0):
            pass
        with locks.file_lock(path, timeout=10):     # free once the other process is done
            pass
    finally:
        proc.wait(10)


def test_data_files_are_written_through_the_atomic_helpers():
    """A cache, history or report file written with to_csv/to_parquet/write_text directly can be read half-written
    by the running app, or collide with another writer's temp file. Use config.write_parquet / write_csv /
    write_text. The exceptions write a file the user named (--out), a zip with its own temp file, or the
    pointer file at setup."""
    import re
    from pathlib import Path

    import radar
    allowed = {"cli.py", "backup.py", "export.py", "paths.py", "config.py", "api.py", "home.py"}
    raw = re.compile(r"\.(to_csv|to_parquet|write_text|write_bytes)\(")
    bad = []
    for f in Path(radar.__file__).parent.rglob("*.py"):
        if f.name in allowed:
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if raw.search(line) and "tmp" not in line.split("(")[0]:
                bad.append(f"{f.relative_to(Path(radar.__file__).parent)}:{i}: {line.strip()}")
    assert not bad, "write through config.write_*:\n" + "\n".join(bad)


def test_two_processes_logging_sources_keep_each_others_entries(tmp_path):
    """sources.json is read, changed and written by the app and a terminal update alike."""
    import json
    import os
    import subprocess
    import sys
    env = os.environ | {"MARKET_RADAR_HOME": str(tmp_path / "home"), "MARKET_RADAR_CACHE": str(tmp_path / "cache"),
                        "MARKET_RADAR_CONFIG": str(tmp_path / "config")}
    code = ("import sys; from radar import coverage, paths\n"
            "for i in range(40): coverage.record(f'{sys.argv[1]}{i}', True, 'ok')\n")
    procs = [subprocess.Popen([sys.executable, "-c", code, p], env=env) for p in ("a", "b")]
    assert [p.wait(120) for p in procs] == [0, 0]
    log = json.loads((tmp_path / "cache" / "sources.json").read_text(encoding="utf-8"))
    assert len(log) == 80
