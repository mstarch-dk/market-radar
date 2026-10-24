"""Refreshing the data: the steps behind `radar update` / `radar run`, and a background job so the web app can
run them with a button and show progress (for people who don't use a terminal).

Each source is a step; a failing step is logged (sources.json in the cache) and keeps its cached data, so one broken
source never blocks the rest.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

from . import locks, ops, report, sourcelog, universe, userstore
from .config import typed
from .fundamentals import edgar, yahoo
from .market import Market
from .paths import CACHE
from .sources import external, factors, ingest, sentiment, tracked, valuation

UPDATE_LOCK = CACHE / "update.lock"   # one update at a time: the app's job, `radar update` / `run` in a terminal
BUSY = "an update is already running (in the app or in a terminal): wait for it to finish"
REPORT_LOCK = CACHE / "report.lock"   # one report build at a time: it saves the rank snapshots and runs the A/B test
REPORT_BUSY = "the readings are already being built (in the app or in a terminal): wait for it to finish"

Log = Callable[[str], None]


def run_steps(steps: dict, log: Log) -> None:
    """Run update steps {source key: (label, fn)}; a failure is logged and the cached data is kept."""
    for key, (label, step) in steps.items():
        try:
            with ops.context(source=key):   # the step's requests are attributed to it
                msg = step()
            log(f"{label}: {msg}.")
            sourcelog.record(key, True, msg)
        except Exception as e:  # network/format problems shouldn't block the rest of the radar
            log(f"{label}: FAILED ({type(e).__name__}: {e}); using cached data.")
            sourcelog.record(key, False, error=f"{type(e).__name__}: {e}", exc=e)


def update(log: Log = print, refresh_constituents: bool = False, progress: Callable[[int, int], None] | None = None) -> None:
    """Download new prices (incremental) and macro and non-price series. One at a time: while another update runs
    (the app's, or one in a terminal) this raises `locks.Busy` before asking anything."""
    with locks.file_lock(UPDATE_LOCK, timeout=0, what=BUSY):
        _update(log, refresh_constituents, progress)


def _update(log: Log, refresh_constituents: bool, progress) -> None:
    tickers = universe.all_price_tickers(refresh_constituents)
    log(f"Updating {len(tickers)} tickers…")

    def prices():
        res = ingest.update_prices(tickers, progress, start=universe.history_start(), bench=tracked.benchmark())
        msg = f"{res['rows']:,} rows, {res['new']} new tickers"
        if res["behind"]:
            names = sorted(res["behind"])
            late = (f"{len(names)} without a bar for {res['asof']} (exchange holiday, or not on Yahoo yet): "
                    + ", ".join(names[:12]) + (f" and {len(names) - 12} more" if len(names) > 12 else ""))
            ops.event("warn", "source", f"prices: {late}", detail=", ".join(names))
            msg += f"; {late}"
        if res.get("short"):
            names = sorted(res["short"])
            short = (f"{len(names)} with a Yahoo history shorter than the one stored (kept the stored bars; "
                     f"asked again next time): " + ", ".join(names[:12])
                     + (f" and {len(names) - 12} more" if len(names) > 12 else ""))
            ops.event("warn", "source", f"prices: {short}", detail=", ".join(names))
            msg += f"; {short}"
        if res.get("deepened"):
            msg += f"; {res['deepened']} downloaded again further back (to your first trade)"
        if res["rebased"]:
            msg += f"; re-downloaded after a dividend/split re-based the history: {', '.join(res['rebased'])}"
        if res["missing"]:
            msg += f"; no data for {len(res['missing'])}: {', '.join(res['missing'])}"
        return msg

    def fred():
        series = list(tracked.macro_fred()) + list(tracked.macro_fred_views()) + list(tracked.macro_fred_study())
        failed = ingest.update_fred(series)
        if failed:
            raise RuntimeError(f"failed: {', '.join(failed)}; those series keep their cached values")
        return f"{len(series)} series"

    run_steps({"prices": ("Prices", prices)}, log)
    log("Looking up names and sectors (the first time this takes a few minutes)…")
    try:   # a cache, not a source: a failure is logged and the remaining steps still run
        with ops.context(source="reference"):
            universe.names(tickers)  # warm the name cache
            universe.sectors(sorted({t for g in tracked.stock_groups().values() for t in g}))  # warm the sector cache
    except Exception as e:
        log(f"Names and sectors: FAILED ({type(e).__name__}: {e}); using the cached ones.")
        ops.event("error", "source", f"names and sectors: {type(e).__name__}: {e}", source="reference", exc=e)
    run_steps({"fred": ("Macro (FRED)", fred)}, log)
    update_external(log)


def update_external(log: Log = print) -> None:
    """Non-price sources. A failure keeps the previous cached file, so the report still builds."""
    mine = universe.held_or_watched()
    stocks = universe.tracked_stocks()
    run_steps({
        "cftc": ("CFTC positioning", lambda: f"{external.update_cot()} new rows"),
        "oecd": ("OECD leading indicators", external.update_oecd_cli),
        "factset": ("FactSet earnings insight",
                    lambda: f"report {d}" if (d := external.update_factset()) else "no new report"),
        "analyst": ("Analyst targets", lambda: external.update_analyst(mine, typed().analyst.max_age_days)),
        "ecb": ("ECB euro-area rates", external.update_ecb),
        "cape": ("Shiller CAPE (multpl.com)", valuation.update_cape),
        "erp": ("Equity risk premium (Damodaran)", valuation.update_erp),
        "putcall": ("CBOE put/call ratios", sentiment.update_putcall),
        "aaii": ("AAII sentiment survey", sentiment.update_aaii),
        "factors": ("Long factor histories (French, JKP; monthly)", factors.update_factors),
        "valuation_etfs": ("ETF valuation (Yahoo fund data)", lambda: valuation.update_etfs(universe.etf_tickers())),
        "valuation_stocks": ("Stock valuation (Yahoo screener, weekly; a few minutes)",
                             lambda: valuation.update_stocks(stocks)),
        # after the valuation snapshot: it names each stock's reporting currency and next earnings date
        "fundamentals_edgar": ("Financial statements (SEC EDGAR, US)",
                               lambda: edgar.update_edgar(stocks, userstore.sec_contact())),
        "fundamentals_yahoo": ("Financial statements (Yahoo)", lambda: yahoo.update_yahoo(stocks)),
    }, log)


def build_report(log: Log = print, wait: float = 600) -> dict:
    """Build dashboard.json and summary.json from the local data (no downloads), one build at a time. After an
    update it waits for a build already running (`wait` seconds); a build on its own (`radar report`, the app's
    *Rebuild* button) passes 0 and is refused with `locks.Busy`."""
    with locks.file_lock(REPORT_LOCK, timeout=wait, what=REPORT_BUSY):
        return _build_report(log)


def _build_report(log: Log) -> dict:
    res = report.build()
    log(f"Regime: {res['regime']} (data as of {res['asof']}). Stale tickers: {res['stale']}"
        + (f"; without the last session: {res['behind']}" if res.get("behind") else ""))
    _abtest(log)
    return res


def _abtest(log: Log) -> None:
    """The forward A/B test, when one is running: this month's picks (once a month) and the replayed portfolios.
    A failure is logged and never stops the report."""
    from . import abtest

    if not abtest.portfolios():
        return
    try:
        with ops.context(source="abtest"):
            m = Market.load()
            abtest.refresh(m, log=log)
            from . import report

            report.add_abtest(m)
    except Exception as e:  # noqa: BLE001
        log(f"A/B test: FAILED ({type(e).__name__}: {e}); the portfolios keep their last run.")
        ops.event("error", "job", f"abtest: {type(e).__name__}: {e}", source="abtest", exc=e)


# ---------------- background job for the web app ----------------

def _refresh(log: Log, progress: Callable[[int, int], None]) -> None:
    """The web app's refresh: the daily backup, the update, the report."""
    _daily_backup(log)
    update(log, progress=progress)
    build_report(log)


class UpdateJob:
    """One data refresh at a time, run in a thread; its log and progress can be polled."""

    def __init__(self, work: Callable[[Log, Callable[[int, int], None]], None] | None = None,
                 label: str = "Downloading prices", kind: str = "update"):
        self._lock = threading.Lock()
        self._label = label
        self._kind = kind     # the job's kind in the operations log
        self._work = work or _refresh
        self.state: dict[str, Any] = {"status": "idle", "started": None, "finished": None, "log": [], "progress": None, "error": None}

    def _log(self, line: str) -> None:
        self.state["log"] = [*self.state["log"], f"{datetime.now():%H:%M:%S} {line}"][-200:]

    def _progress(self, done: int, total: int) -> None:
        self.state["progress"] = {"done": done, "total": total, "label": self._label}

    def start(self) -> bool:
        """Start a refresh; False if one is already running."""
        with self._lock:
            if self.state["status"] == "running":
                return False
            self.state = {"status": "running", "started": datetime.now().isoformat(timespec="seconds"), "finished": None,
                          "log": [], "progress": None, "error": None}
        jid = ops.job_start(self._kind)
        threading.Thread(target=self._run, args=(jid,), name="radar-update", daemon=True).start()
        return True

    def _run(self, jid: int | None = None) -> None:
        status, error = "done", None
        try:
            with ops.context(job=jid):
                self._work(self._log, self._progress)
        except BaseException as e:   # SystemExit from report.build (no prices) included: report it, don't die
            status, error = "failed", f"{type(e).__name__}: {e}"
            self._log(f"Stopped: {error}")
            ops.event("error", "job", f"{self._kind} stopped: {error}", exc=e)
        finally:
            ops.job_finish(jid, status, error, self.state["log"])
            ops.prune()
            # the status changes last, so whoever waits for it sees the operations log complete
            self.state.update(error=error, finished=datetime.now().isoformat(timespec="seconds"), progress=None,
                              status=status)


def _daily_backup(log: Log) -> None:
    """Today's backup, if the app has been open since before today (it is also taken at start)."""
    from . import backup

    try:
        if (b := backup.daily()):
            log(f"Backup: {b.name}")
    except Exception as e:                        # never stops the update; the Data page shows the backups' age
        log(f"Backup failed: {type(e).__name__}: {e}")
        ops.event("error", "job", f"backup: {type(e).__name__}: {e}", source="backup", exc=e)


def discover(log: Log, progress: Callable[[int, int], None], refresh_universe: bool = False) -> None:
    """The discovery scan, told which names the radar already tracks."""
    from .discovery import scan

    scan.run(set(universe.all_price_tickers(offline=True)), log, progress, refresh_universe)


def rebuild_readings(log: Log, progress: Callable[[int, int], None]) -> None:
    """The readings rebuilt from the data already downloaded: after an upgrade, an edited settings.yaml or a
    terminal update without a report. The config files are read again, as a new `radar report` would."""
    from .config import reload, universe_config

    reload()

    universe_config.cache_clear()
    build_report(log, wait=0)


JOB = UpdateJob()
DISCOVER_JOB = UpdateJob(discover, "Scanning", "discover")  # the separate discovery scan (Discover page)
REPORT_JOB = UpdateJob(rebuild_readings, "Building the readings", "report")  # no downloads (the Rebuild button)
