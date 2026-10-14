"""`radar doctor`: is everything Market Radar needs in place? Each check says what it found and, when something
is wrong, what to do about it in plain words. Used by the start scripts when something fails."""
from __future__ import annotations

import sys
from datetime import date, datetime

from .config import POSITIVE_LIST_FILE, PRICES_FILE, REPORTS, ROOT, settings

# the services `radar update` and the discovery scan read from (no API keys needed); any answer below 500 is "up"
SERVICES = {
    "Yahoo Finance (prices)": "https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=1d",
    "FRED (US macro)": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
    "CFTC (futures positioning)": "https://publicreporting.cftc.gov/",
    "OECD (leading indicators)": "https://sdmx.oecd.org/public/rest/",
    "FactSet (earnings insight)": "https://advantage.factset.com/",
    "ECB (euro-area rates)": "https://data-api.ecb.europa.eu/service/",
    "SSGA (S&P 500 constituents)": "https://www.ssga.com/",
    "iShares (STOXX 600 holdings)": "https://www.ishares.com/",
    "multpl.com (Shiller CAPE)": "https://www.multpl.com/",
    "Damodaran (equity risk premium)": "https://pages.stern.nyu.edu/~adamodar/",
    "CBOE (put/call ratios)": "https://www.cboe.com/",
    "AAII (sentiment survey)": "https://www.aaii.com/",
}


def _check(name: str, status: str, detail: str, fix: str | None = None) -> dict:
    return {"name": name, "status": status, "detail": detail, "fix": fix}


def _age_days(path) -> int | None:
    return (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).days if path.exists() else None


def checks(offline: bool = False) -> list[dict]:
    out = []
    v = sys.version_info
    out.append(_check("Python", "ok" if v >= (3, 11) else "fail", f"{v.major}.{v.minor}.{v.micro}",
                      "Start Market Radar with the start script (it installs the right Python through uv)."))

    dist = ROOT / "web" / "dist" / "index.html"
    out.append(_check("Web app", "ok" if dist.exists() else "fail",
                      "built" if dist.exists() else "web/dist is missing",
                      "Download the release zip (it includes the built app), or build it: pnpm -C web install && pnpm -C web build."))

    age = _age_days(PRICES_FILE)
    if age is None:
        out.append(_check("Market data", "warn", "not downloaded yet",
                          "Open the app and click \"Download market data\" (the first time takes a few minutes), or run: uv run radar run"))
    else:
        out.append(_check("Market data", "ok" if age <= 7 else "warn", f"last downloaded {age} day(s) ago",
                          "Click \"Update data\" in the app, or run: uv run radar run"))

    dash = REPORTS / "dashboard.json"
    dage = _age_days(dash)
    out.append(_check("Dashboard", "ok" if dage is not None and dage <= 7 else "warn",
                      "not built yet" if dage is None else f"built {dage} day(s) ago",
                      "It is built at the end of every update (\"Update data\" in the app, or uv run radar run)."))

    if POSITIVE_LIST_FILE.exists():
        import pandas as pd

        try:
            years = [n for n in pd.ExcelFile(POSITIVE_LIST_FILE).sheet_names if n.strip().isdigit()]
            latest = max(years) if years else None
        except Exception as e:  # a broken file is worth knowing about
            latest = None
            out.append(_check("SKAT positive list", "warn", f"can't read imports/positivliste.xlsx ({type(e).__name__})",
                              "Download the current list from skat.dk and save it as imports/positivliste.xlsx."))
        else:
            current = latest is not None and int(latest) >= date.today().year
            out.append(_check("SKAT positive list", "ok" if current else "warn", f"latest sheet: {latest}",
                              "SKAT publishes a new list each year: download it from skat.dk and replace imports/positivliste.xlsx."))
    else:
        out.append(_check("SKAT positive list", "warn", "imports/positivliste.xlsx is missing",
                          "Download it from skat.dk; without it the positive-list column shows \"?\"."))

    from . import universe, userstore

    legacy = userstore.meta_get("legacy_csv") or {}
    if legacy.get("status") == "failed":
        out.append(_check("Your portfolio", "warn",
                          "the old imports/*.csv files could not be moved into the store unchanged: "
                          + "; ".join(legacy.get("problems", [])[:3]),
                          "The old files are still used. Re-import from Yahoo Finance or enter the trades on the "
                          "Portfolio page; nothing was lost."))
    else:
        n = len(universe.transactions())
        out.append(_check("Your portfolio", "info", f"{n} transactions" if n else "no transactions yet (optional)",
                          None if n else "In the app: Portfolio → add a trade, or import from your broker or Yahoo Finance."))
    profile = ROOT / "notes" / "investor.md"
    out.append(_check("Investor profile for Claude", "info",
                      "notes/investor.md found" if profile.exists() else "not set up (optional, for the Claude Code skills)",
                      None if profile.exists() else "Copy investor.example.md to notes/investor.md and fill it in."))

    if not offline:
        from . import net

        for name, url in SERVICES.items():
            try:
                r = net.get(url, source="doctor", timeout=8, retries=0, expected=tuple(range(400, 500)))
                ok = r.status_code < 500
                out.append(_check(f"Internet: {name}", "ok" if ok else "warn", f"HTTP {r.status_code}",
                                  "The service may be down for a moment; updates keep the last data and retry next time."))
            except net.Throttled as e:
                out.append(_check(f"Internet: {name}", "warn", str(e),
                                  "Market Radar paused this site after it asked us to slow down; it resumes by itself "
                                  "(or clear the pause on the Operations page)."))
            except Exception as e:
                out.append(_check(f"Internet: {name}", "fail", f"no connection ({type(e).__name__})",
                                  "Check the internet connection, or whether a firewall or VPN blocks Python."))
    _ = settings()  # config files parse (raises with the file name if not)
    return out
