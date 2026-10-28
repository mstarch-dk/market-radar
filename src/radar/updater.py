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

from . import locks, ops, sourcelog, universe, userstore
from .config import typed
from .fundamentals import edgar, yahoo
from .market import Market
from .paths import CACHE
from .progress import Progress
from .reporting import report
from .sources import constituents, external, factors, ingest, sentiment, tracked, valuation

UPDATE_LOCK = CACHE / "update.lock"   # one update at a time: the app's job, `radar update` / `run` in a terminal
BUSY = "an update is already running (in the app or in a terminal): wait for it to finish"
REPORT_LOCK = CACHE / "report.lock"   # one report build at a time: it saves the rank snapshots and runs the A/B test
REPORT_BUSY = "the readings are already being built (in the app or in a terminal): wait for it to finish"

Log = Callable[[str], None]
Prog = Progress | Callable[[int, int], None] | None   # who follows the work: a tracker, a plain callback or nobody

# the non-price sources in the order they run, as {source key: label}
EXTERNAL = {
    "cftc": "CFTC positioning",
    "oecd": "OECD leading indicators",
    "factset": "FactSet earnings insight",
    "analyst": "Analyst targets",
    "ecb": "ECB euro-area rates",
    "cape": "Shiller CAPE (multpl.com)",
    "erp": "Equity risk premium (Damodaran)",
    "putcall": "CBOE put/call ratios",
    "aaii": "AAII sentiment survey",
    "factors": "Factor histories (French, JKP; monthly, and daily developed factors)",
    "acwi_segments": "MSCI ACWI weights (iShares; weekly snapshot)",
    "valuation_etfs": "ETF valuation (Yahoo fund data)",
    "valuation_stocks": "Stock valuation (Yahoo screener, weekly; a few minutes)",
    "calendar": "Earnings calendar (holdings and watchlist)",
    # after the valuation snapshot: it names each stock's reporting currency and next earnings date
    "fundamentals_edgar": "Financial statements (SEC EDGAR, US)",
    "fundamentals_yahoo": "Financial statements (Yahoo)",
}
# the update's steps as (key, label), planned up front so a follower sees "step 4 of 20"
STEPS = [("prices", "Prices"), ("reference", "Names and sectors"), ("fred", "Macro (FRED)"), *EXTERNAL.items()]
REPORT_STEP = ("report", "Building the readings")


def _tracker(progress: Prog) -> Progress | None:
    return progress if isinstance(progress, Progress) else None


def plan(progress: Prog, steps: list[tuple[str, str]]) -> None:
    """Tell a tracker which steps are coming (a plain callback has no use for it)."""
    if (p := _tracker(progress)):
        p.plan(steps)


def run_steps(steps: dict, log: Log, progress: Prog = None) -> None:
    """Run update steps {source key: (label, fn)}; a failure is logged and the cached data is kept. A tracker hears
    each step start and end, and a failure as an issue at once."""
    p = _tracker(progress)
    for key, (label, step) in steps.items():
        if p:
            p.step(key, label)
        try:
            with ops.context(source=key):   # the step's requests are attributed to it
                msg = step()
            log(f"{label}: {msg}.")
            sourcelog.record(key, True, msg)
            if p:
                p.finish(key, True, msg)
        except Exception as e:  # network/format problems shouldn't block the rest of the radar
            err = f"{type(e).__name__}: {e}"
            log(f"{label}: FAILED ({err}); using cached data.")
            sourcelog.record(key, False, error=err, exc=e)
            if p:
                p.issue("error", f"{label} failed ({err}); using cached data", key)
                p.finish(key, False, err)


def update(log: Log = print, refresh_constituents: bool = False, progress: Prog = None) -> None:
    """Download new prices (incremental) and macro and non-price series. One at a time: while another update runs
    (the app's, or one in a terminal) this raises `locks.Busy` before asking anything."""
    with locks.file_lock(UPDATE_LOCK, timeout=0, what=BUSY):
        _update(log, refresh_constituents, progress)


def _names(tickers: list[str]) -> str:
    return ", ".join(tickers[:12]) + (f" and {len(tickers) - 12} more" if len(tickers) > 12 else "")


def _update(log: Log, refresh_constituents: bool, progress: Prog) -> None:
    plan(progress, STEPS)
    p = _tracker(progress)
    tickers = universe.all_price_tickers(refresh_constituents)
    log(f"Updating {len(tickers)} tickers…")

    def warn(text: str) -> None:   # a ticker finding the follower should see now, not only in the step's line
        if p:
            p.issue("warn", text, "prices")

    def prices():
        res = ingest.update_prices(tickers, progress, start=universe.history_start(), bench=tracked.benchmark())
        msg = f"{res['rows']:,} rows, {res['new']} new tickers"
        if res["behind"]:
            names = sorted(res["behind"])
            late = (f"{len(names)} without a bar for {res['asof']} (exchange holiday, or not on Yahoo yet): "
                    + _names(names))
            ops.event("warn", "source", f"prices: {late}", detail=", ".join(names))
            warn(late)
            msg += f"; {late}"
        if res.get("short"):
            names = sorted(res["short"])
            short = (f"{len(names)} with a Yahoo history shorter than the one stored (kept the stored bars; "
                     f"asked again next time): " + _names(names))
            ops.event("warn", "source", f"prices: {short}", detail=", ".join(names))
            warn(short)
            msg += f"; {short}"
        if res.get("deepened"):
            msg += f"; {res['deepened']} downloaded again further back (to your first trade)"
        if res["rebased"]:
            msg += f"; re-downloaded after a dividend/split re-based the history: {', '.join(res['rebased'])}"
        if res["missing"]:
            warn(f"no data for {len(res['missing'])}: {_names(res['missing'])}")
            msg += f"; no data for {len(res['missing'])}: {', '.join(res['missing'])}"
        return msg

    def fred():
        series = list(tracked.macro_fred()) + list(tracked.macro_fred_views()) + list(tracked.macro_fred_study())
        failed = ingest.update_fred(series)
        if failed:
            raise RuntimeError(f"failed: {', '.join(failed)}; those series keep their cached values")
        return f"{len(series)} series"

    run_steps({"prices": ("Prices", prices)}, log, progress)
    log("Looking up names and sectors (the first time this takes a few minutes)…")
    if p:
        p.step("reference", "Names and sectors")
    try:   # a cache, not a source: a failure is logged and the remaining steps still run
        with ops.context(source="reference"):
            universe.names(tickers, progress)  # warm the name cache
            universe.sectors(sorted({t for g in tracked.stock_groups().values() for t in g}), progress)  # and sectors
        if p:
            p.finish("reference", True)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        log(f"Names and sectors: FAILED ({err}); using the cached ones.")
        ops.event("error", "source", f"names and sectors: {err}", source="reference", exc=e)
        if p:
            p.issue("error", f"Names and sectors failed ({err}); using the cached ones", "reference")
            p.finish("reference", False, err)
    run_steps({"fred": ("Macro (FRED)", fred)}, log, progress)
    update_external(log, progress)


def update_external(log: Log = print, progress: Prog = None) -> None:
    """Non-price sources. A failure keeps the previous cached file, so the report still builds."""
    mine = universe.held_or_watched()
    stocks = universe.tracked_stocks()
    work: dict[str, Callable[[], str]] = {
        "cftc": lambda: f"{external.update_cot()} new rows",
        "oecd": external.update_oecd_cli,
        "factset": lambda: f"report {d}" if (d := external.update_factset()) else "no new report",
        "analyst": lambda: external.update_analyst(mine, typed().analyst.max_age_days),
        "ecb": external.update_ecb,
        "cape": valuation.update_cape,
        "erp": valuation.update_erp,
        "putcall": sentiment.update_putcall,
        "aaii": sentiment.update_aaii,
        "factors": factors.update_factors,
        "acwi_segments": constituents.update_acwi_segments,
        "valuation_etfs": lambda: valuation.update_etfs(universe.etf_tickers()),
        "valuation_stocks": lambda: valuation.update_stocks(stocks, progress=progress),
        "calendar": lambda: external.update_calendar(mine, **typed().calendar.refresh.model_dump()),
        "fundamentals_edgar": lambda: edgar.update_edgar(stocks, userstore.sec_contact(), progress=progress),
        "fundamentals_yahoo": lambda: yahoo.update_yahoo(stocks, progress=progress),
    }
    run_steps({key: (label, work[key]) for key, label in EXTERNAL.items()}, log, progress)


def build_report(log: Log = print, wait: float = 600, progress: Prog = None) -> dict:
    """Build dashboard.json and summary.json from the local data (no downloads), one build at a time. After an
    update it waits for a build already running (`wait` seconds); a build on its own (`radar report`, the app's
    *Rebuild* button) passes 0 and is refused with `locks.Busy`. A tracker sees it as the step `report`."""
    p = _tracker(progress)
    if p:
        p.step(*REPORT_STEP)
    try:
        with locks.file_lock(REPORT_LOCK, timeout=wait, what=REPORT_BUSY):
            res = _build_report(log)
    except BaseException as e:
        if p:
            p.finish(REPORT_STEP[0], False, f"{type(e).__name__}: {e}")
        raise
    if p:
        p.finish(REPORT_STEP[0], True, f"regime {res['regime']}, data as of {res['asof']}")
    return res


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
            from .reporting import report

            report.add_abtest(m)
    except Exception as e:  # noqa: BLE001
        log(f"A/B test: FAILED ({type(e).__name__}: {e}); the portfolios keep their last run.")
        ops.event("error", "job", f"abtest: {type(e).__name__}: {e}", source="abtest", exc=e)


# ---------------- background job for the web app ----------------

def _refresh(log: Log, progress: Prog) -> None:
    """The web app's refresh: the daily backup, the update, the report."""
    plan(progress, [*STEPS, REPORT_STEP])
    _daily_backup(log)
    update(log, progress=progress)
    build_report(log, progress=progress)


def fresh_state(status: str = "idle", started: str | None = None) -> dict[str, Any]:
    """A job's state as the app and the MCP tools show it: `progress` is the running phase (done of total),
    `step` the step running (i of n), `steps` every step with how it ended, `issues` the newest problems so far
    (`issues_total` counts them all)."""
    return {"status": status, "started": started, "finished": None, "log": [], "progress": None, "error": None,
            "step": None, "steps": [], "issues": [], "issues_total": 0}


class UpdateJob:
    """One data refresh at a time, run in a thread; its log and progress can be polled here, and other processes
    (the app, the MCP server) read them from the operations log while it runs (`ops.Live`)."""

    def __init__(self, work: Callable[[Log, Progress], None] | None = None,
                 label: str = "Downloading prices", kind: str = "update"):
        self._lock = threading.Lock()
        self._label = label
        self._kind = kind     # the job's kind in the operations log
        self._work = work or _refresh
        self._live: ops.Live | None = None
        self.state: dict[str, Any] = fresh_state()

    def _log(self, line: str) -> None:
        self.state["log"] = [*self.state["log"], f"{datetime.now():%H:%M:%S} {line}"][-200:]
        if self._live:
            self._live.update(lines=self.state["log"])

    def _changed(self, snap: dict, urgent: bool) -> None:
        self.state.update(progress=snap["phase"], step=snap["step"], steps=snap["steps"], issues=snap["issues"],
                          issues_total=snap["issues_total"])
        if self._live:
            self._live.update(progress=snap, urgent=urgent)

    def start(self) -> bool:
        """Start a refresh; False if one is already running."""
        with self._lock:
            if self.state["status"] == "running":
                return False
            self.state = fresh_state("running", datetime.now().isoformat(timespec="seconds"))
        jid = ops.job_start(self._kind)
        self._live = ops.Live(jid)
        threading.Thread(target=self._run, args=(jid,), name="radar-update", daemon=True).start()
        return True

    def _run(self, jid: int | None = None) -> None:
        status, error = "done", None
        progress = Progress(self._label, self._changed)
        try:
            with ops.context(job=jid):
                self._work(self._log, progress)
        except BaseException as e:   # SystemExit from report.build (no prices) included: report it, don't die
            status, error = "failed", f"{type(e).__name__}: {e}"
            self._log(f"Stopped: {error}")
            ops.event("error", "job", f"{self._kind} stopped: {error}", exc=e)
        finally:
            if self._live:   # the steps and issues stay with the job; the phase ended with it
                self._live.close(progress.snapshot() | {"phase": None, "step": None}, self.state["log"])
                self._live = None
            ops.job_finish(jid, status, error, self.state["log"])
            ops.prune()
            # the status changes last, so whoever waits for it sees the operations log complete
            self.state.update(error=error, finished=datetime.now().isoformat(timespec="seconds"), progress=None,
                              step=None, status=status)


UPDATE_KINDS = ("update", "cli_run", "cli_update")   # the operations log's kinds for a data update


def elsewhere(kinds: tuple[str, ...] = UPDATE_KINDS) -> dict[str, Any] | None:
    """A job of `kinds` that another process is running (a terminal, the MCP server, the app), as this process's
    own job state shows one, read from the operations log; None when none has shown a sign of life lately.
    `elsewhere` is its kind (cli_run = a terminal)."""
    for j in ops.running_jobs():
        if j["kind"] in kinds and not j["stale"]:
            prog = j["progress"] or {}
            return fresh_state("running", j["started"]) | {
                "log": j["log"], "progress": prog.get("phase"), "step": prog.get("step"),
                "steps": prog.get("steps", []), "issues": prog.get("issues", []),
                "issues_total": prog.get("issues_total", 0), "elsewhere": j["kind"]}
    return None


def _daily_backup(log: Log) -> None:
    """Today's backup, if the app has been open since before today (it is also taken at start)."""
    from .datahome import backup

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
