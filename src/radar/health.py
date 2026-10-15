"""`radar doctor`: is everything Market Radar needs in place? Each check says what it found and, when something
is wrong, what to do about it in plain words. Used by the start scripts when something fails."""
from __future__ import annotations

import sys
from datetime import date, datetime

from .config import POSITIVE_LIST_FILE, ROOT, settings
from .paths import NOTES, PRICES_FILE, REPORTS

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

    from . import home

    st = home.status()
    if st["state"] == "unset":
        out.append(_check("Data folder", "warn", "not chosen yet (first start of this version)",
                          "Start the app: it finds your data from an earlier version, or starts an empty folder. "
                          "Or run: uv run radar setup"))
    elif st["state"] == "missing":
        out.append(_check("Data folder", "fail", f"{st['home']} can't be found",
                          "Connect the drive it is on, or if you moved it: uv run radar setup --use NEW_PATH"))
    else:
        out.append(_check("Data folder", "fail" if st["read_only"] else "warn" if st["warning"] else "ok",
                          st["read_only"] or st["warning"] or st["home"],
                          "Start the newest Market Radar you have." if st["read_only"] else None))
    if st["state"] in ("ok", "newer"):
        out += _data_checks()
    else:
        out += _positive_list()
    if not offline:
        out += _internet()
    _ = settings()  # config files parse (raises with the file name if not)
    return out


def _data_checks() -> list[dict]:
    out = []
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
    out += _positive_list()
    out += _portfolio()
    return out


def _positive_list() -> list[dict]:
    out = []
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
    return out


def _portfolio() -> list[dict]:
    from . import universe, userstore

    out = []
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
    profile = NOTES / "investor.md"
    out.append(_check("Investor profile for Claude", "info",
                      f"{profile} found" if profile.exists() else "not set up (optional, for the Claude Code skills)",
                      None if profile.exists() else f"Copy investor.example.md to {profile} and fill it in."))
    return out


def _internet() -> list[dict]:
    from . import net

    out = []
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
    return out
