"""Refreshing the data: the steps behind `radar update` / `radar run`, and a background job so the web app can
run them with a button and show progress (for people who don't use a terminal).

Each source is a step; a failing step is logged (data/sources.json) and keeps its cached data, so one broken
source never blocks the rest.
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable

from . import coverage, external, ingest, report, sentiment, universe, valuation
from .config import settings

Log = Callable[[str], None]


def _steps(steps: dict, log: Log) -> None:
    """Run update steps {source key: (label, fn)}; a failure is logged and the cached data is kept."""
    for key, (label, step) in steps.items():
        try:
            msg = step()
            log(f"{label}: {msg}.")
            coverage.record(key, True, msg)
        except Exception as e:  # network/format problems shouldn't block the rest of the radar
            log(f"{label}: FAILED ({type(e).__name__}: {e}); using cached data.")
            coverage.record(key, False, error=f"{type(e).__name__}: {e}")


def update(log: Log = print, refresh_constituents: bool = False, progress: Callable[[int, int], None] | None = None) -> None:
    """Download new prices (incremental) and macro and non-price series."""
    tickers = universe.all_price_tickers(refresh_constituents)
    log(f"Updating {len(tickers)} tickers…")

    def prices():
        res = ingest.update_prices(tickers, progress)
        msg = f"{res['rows']:,} rows, {res['new']} new tickers"
        if res["rebased"]:
            msg += f"; re-downloaded after a dividend/split re-based the history: {', '.join(res['rebased'])}"
        if res["missing"]:
            msg += f"; no data for {len(res['missing'])}: {', '.join(res['missing'])}"
        return msg

    def fred():
        series = list(universe.macro_fred()) + list(universe.macro_fred_views())
        failed = ingest.update_fred(series)
        if failed:
            raise RuntimeError(f"failed: {', '.join(failed)}; those series keep their cached values")
        return f"{len(series)} series"

    _steps({"prices": ("Prices", prices)}, log)
    log("Looking up names and sectors (the first time this takes a few minutes)…")
    universe.names(tickers)  # warm the name cache
    universe.sectors(sorted({t for g in universe.stock_groups().values() for t in g}))  # warm the sector cache
    _steps({"fred": ("Macro (FRED)", fred)}, log)
    update_external(log)


def update_external(log: Log = print) -> None:
    """Non-price sources. A failure keeps the previous cached file, so the report still builds."""
    h = universe.holdings()
    mine = sorted(h.loc[h["status"].isin(["holding", "watch"]), "symbol"].dropna()) if not h.empty else []
    _steps({
        "cftc": ("CFTC positioning", lambda: f"{external.update_cot()} new rows"),
        "oecd": ("OECD leading indicators", external.update_oecd_cli),
        "factset": ("FactSet earnings insight",
                    lambda: f"report {d}" if (d := external.update_factset()) else "no new report"),
        "analyst": ("Analyst targets", lambda: external.update_analyst(mine, settings()["analyst"]["max_age_days"])),
        "ecb": ("ECB euro-area rates", external.update_ecb),
        "cape": ("Shiller CAPE (multpl.com)", valuation.update_cape),
        "erp": ("Equity risk premium (Damodaran)", valuation.update_erp),
        "putcall": ("CBOE put/call ratios", sentiment.update_putcall),
        "aaii": ("AAII sentiment survey", sentiment.update_aaii),
        "valuation_etfs": ("ETF valuation (Yahoo fund data)", valuation.update_etfs),
        "valuation_stocks": ("Stock valuation (Yahoo screener, weekly; a few minutes)", valuation.update_stocks),
    }, log)


def build_report(log: Log = print) -> dict:
    res = report.build()
    log(f"Regime: {res['regime']} (data as of {res['asof']}). Stale tickers: {res['stale']}")
    return res


# ---------------- background job for the web app ----------------

class UpdateJob:
    """One data refresh at a time, run in a thread; its log and progress can be polled."""

    def __init__(self, work: Callable[[Log, Callable[[int, int], None]], None] | None = None,
                 label: str = "Downloading prices"):
        self._lock = threading.Lock()
        self._label = label
        self._work = work or (lambda log, progress: (update(log, progress=progress), build_report(log)))
        self.state = {"status": "idle", "started": None, "finished": None, "log": [], "progress": None, "error": None}

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
        threading.Thread(target=self._run, name="radar-update", daemon=True).start()
        return True

    def _run(self) -> None:
        try:
            self._work(self._log, self._progress)
            self.state["status"] = "done"
        except BaseException as e:   # SystemExit from report.build (no prices) included: report it, don't die
            self.state["error"] = f"{type(e).__name__}: {e}"
            self._log(f"Stopped: {self.state['error']}")
            self.state["status"] = "failed"
        finally:
            self.state["finished"] = datetime.now().isoformat(timespec="seconds")
            self.state["progress"] = None


def _discover(log: Log, progress: Callable[[int, int], None]) -> None:
    from .discovery import scan

    scan.run(log, progress)


JOB = UpdateJob()
DISCOVER_JOB = UpdateJob(_discover, "Scanning")  # the separate discovery scan (Discover page)
