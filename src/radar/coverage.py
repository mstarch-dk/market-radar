"""What the radar knows: freshness and coverage per data source, the update log, and the blind spots.

Each source row says where the data comes from, what it feeds, how much of the configured universe it
covers, how old it is and whether its last update worked. Ages are counted from the report's as-of date
(the benchmark's last trading day), so a weekend doesn't make everything look stale; prices are also
checked against today, since an update that keeps failing makes the whole report old.
"""
from __future__ import annotations

import json
from datetime import date, datetime

import pandas as pd

from .config import DATA, HOLDINGS_FILE, POSITIVE_LIST_FILE, TRANSACTIONS_FILE

LOG_FILE = DATA / "sources.json"

OK, STALE, MISSING, INFO = "ok", "stale", "missing", "info"

# key -> display name, provider, official source?, cadence, what it feeds
SOURCES = {
    "prices": ("Prices (ETFs, stocks, macro, FX)", "Yahoo Finance via yfinance", False, "daily",
               "Regime, Rotation, Momentum, Levels, Holdings"),
    "fred": ("US macro series", "FRED (St. Louis Fed)", True, "daily–weekly", "Regime"),
    "cftc": ("Futures positioning", "CFTC Commitments of Traders", True, "weekly", "Positioning"),
    "oecd": ("Leading indicators", "OECD Composite Leading Indicators", True, "monthly", "Regime, Positioning"),
    "factset": ("S&P 500 earnings revisions", "FactSet Earnings Insight (PDF)", True, "weekly", "Regime, Positioning"),
    "analyst": ("Analyst consensus", "Yahoo Finance", False, "weekly re-fetch", "Levels (take-profit)"),
    "constituents": ("S&P 500 constituents", "SSGA SPY holdings", True, "monthly re-fetch",
                     "Momentum, breadth"),
    "reference": ("Names, sectors, currencies", "Yahoo Finance (cached)", False, "on first use",
                  "Momentum clusters, Holdings (DKK)"),
    "positive_list": ("Positive list (aktiebaserede inv.selskaber)", "SKAT (manual download)", True, "yearly",
                      "Themes (UCITS check)"),
    "holdings": ("Holdings & transactions", "Yahoo portfolio export (manual)", False, "manual",
                 "Holdings, Levels"),
}


# ---------------- update log ----------------

def load_log() -> dict:
    try:
        return json.loads(LOG_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def record(source: str, ok: bool, detail: str | None = None, error: str | None = None) -> None:
    """Log one update attempt. A failure keeps the last success, so the page can say how old the data is."""
    log = load_log()
    now = datetime.now().isoformat(timespec="seconds")
    entry = log.get(source, {}) | {"last_attempt": now, "detail": detail, "error": None if ok else error}
    if ok:
        entry["last_success"] = now
    log[source] = entry
    DATA.mkdir(exist_ok=True)
    LOG_FILE.write_text(json.dumps(log, indent=1), encoding="utf-8")


# ---------------- freshness ----------------

def status(asof, ref, max_age: int | None) -> tuple[str, int | None]:
    """(ok | stale | missing, age in days) of data last dated `asof`, seen from `ref`."""
    if asof is None or pd.isna(asof):
        return MISSING, None
    age = (pd.Timestamp(ref).normalize() - pd.Timestamp(asof).normalize()).days
    return (STALE if max_age is not None and age > max_age else OK), age


def _mtime(path) -> pd.Timestamp | None:
    return pd.Timestamp(datetime.fromtimestamp(path.stat().st_mtime)) if path.exists() else None


def _d(ts) -> str:
    return pd.Timestamp(ts).strftime("%d %b %Y")


def _row(key: str, asof, ref, max_age: int | None, coverage: str, detail: str = "", log: dict | None = None,
         state: str | None = None) -> dict:
    name, provider, official, cadence, feeds = SOURCES[key]
    st, age = status(asof, ref, max_age)
    entry = (log or {}).get(key, {})
    return {"key": key, "name": name, "provider": provider, "official": official, "cadence": cadence,
            "feeds": feeds, "coverage": coverage, "detail": detail,
            "asof": None if asof is None or pd.isna(asof) else pd.Timestamp(asof).date().isoformat(),
            "age_days": age, "max_age": max_age, "status": state or st,
            "last_attempt": entry.get("last_attempt"), "last_success": entry.get("last_success"),
            "error": entry.get("error")}


def build(ref: date, prices: pd.DataFrame, configured: list[str], fred: pd.DataFrame, fred_series: dict,
          cot: pd.DataFrame, cot_markets: list[str], cli: pd.DataFrame, cli_areas: dict, factset: pd.DataFrame,
          analyst: pd.DataFrame, analyst_tickers: list[str], stock_tickers: list[str],
          holdings: pd.DataFrame, positive_list_year: str | None, indicators: list[dict], cfg: dict,
          today: date | None = None, log: dict | None = None) -> dict:
    """Everything the "Data & coverage" tab and summary.json show. `cfg` is settings()."""
    max_age = cfg["coverage"]["max_age"]
    log = load_log() if log is None else log
    today = today or date.today()
    rows = []

    # prices: coverage of the configured universe; age vs today (a failing update makes the whole report old)
    last = prices.groupby("ticker")["date"].max() if not prices.empty else pd.Series(dtype="datetime64[ns]")
    missing = sorted(set(configured) - set(last.index))
    stale = sorted(t for t, d in last.items() if t in set(configured) and (pd.Timestamp(ref) - d).days > max_age["prices"])
    have = len(set(configured) & set(last.index))
    span = f"history from {_d(prices['date'].min())}" if not prices.empty else ""
    rows.append(_row("prices", pd.Timestamp(ref) if not prices.empty else None, today, max_age["prices"],
                     f"{have} of {len(configured)} configured tickers" + (f"; {len(stale)} stale" if stale else ""),
                     span, log))

    # FRED: the oldest series decides
    lasts = {s: fred[s].dropna().index.max() for s in fred_series if s in fred and not fred[s].dropna().empty}
    rows.append(_row("fred", min(lasts.values()) if lasts else None, ref, max_age["fred"],
                     f"{len(lasts)} of {len(fred_series)} series",
                     ", ".join(f"{fred_series[s]} {pd.Timestamp(d):%d %b}" for s, d in lasts.items()), log))

    # CFTC
    cot_last = cot.groupby("market")["date"].max() if not cot.empty else pd.Series(dtype="datetime64[ns]")
    rows.append(_row("cftc", cot_last.max() if not cot_last.empty else None, ref, max_age["cftc"],
                     f"{len(set(cot_last.index) & set(cot_markets))} of {len(cot_markets)} markets",
                     "Positions as of Tuesday, published Friday", log))

    # OECD CLI: the voting area (first configured) decides
    areas = [a for a in cli_areas if a in cli.columns] if not cli.empty else []
    lead = cli[areas[0]].dropna().index.max() if areas else None
    rows.append(_row("oecd", lead, ref, max_age["oecd"], f"{len(areas)} of {len(cli_areas)} areas",
                     f"Latest month {pd.Timestamp(lead):%b %Y}; published with a ~2-month lag" if lead is not None else "",
                     log))

    # FactSet
    fs_last = factset["report_date"].max() if not factset.empty else None
    quarter = factset.sort_values("report_date").iloc[-1].get("quarter") if not factset.empty else None
    rows.append(_row("factset", fs_last, ref, max_age["factset"], "S&P 500 aggregate only",
                     f"Report for {quarter}" if quarter else "", log))

    # analyst consensus for holdings/watchlist: the oldest fetch decides
    if not analyst.empty and analyst_tickers:
        a = analyst[analyst["ticker"].isin(analyst_tickers)].sort_values("fetched").groupby("ticker").last()
        enough = int((pd.to_numeric(a.get("n_analysts"), errors="coerce") >= cfg["stops"]["min_analysts"]).sum())
        rows.append(_row("analyst", a["fetched"].min() if not a.empty else None, ref, max_age["analyst"],
                         f"{len(a)} of {len(analyst_tickers)} holdings/watchlist names; {enough} with ≥ "
                         f"{cfg['stops']['min_analysts']} analysts", "Funds have no targets", log))
    else:
        rows.append(_row("analyst", None, ref, max_age["analyst"],
                         f"0 of {len(analyst_tickers)} holdings/watchlist names", "", log))

    # constituents list (file date)
    cons = DATA / "constituents_us.csv"
    n_cons = len(pd.read_csv(cons)) if cons.exists() else 0
    rows.append(_row("constituents", _mtime(cons), today, cfg["constituents_max_age_days"] + 14,
                     f"{n_cons} US stocks", "Today's members only: no history of index changes", log))

    # reference caches: how many stocks have a sector (used by the momentum clusters)
    sec_file = DATA / "sectors.csv"
    sectors = pd.read_csv(sec_file, keep_default_na=False).set_index("ticker") if sec_file.exists() else None
    known = int((sectors.reindex(stock_tickers)["sector"].fillna("") != "").sum()) if sectors is not None else 0
    rows.append(_row("reference", None, ref, None, f"sector known for {known} of {len(stock_tickers)} stocks",
                     "Names and currencies are fetched once and cached", log, state=INFO))

    # positive list: the year's sheet; a new calendar year without its sheet is stale
    pl_state = (MISSING if positive_list_year is None
                else STALE if int(positive_list_year) < ref.year else OK)
    rows.append(_row("positive_list", _mtime(POSITIVE_LIST_FILE), ref, None,
                     f"{positive_list_year} sheet" if positive_list_year else "not loaded",
                     "imports/positivliste.xlsx", log, state=pl_state))

    # your portfolio (the transaction store)
    if not holdings.empty:
        from . import universe, userstore

        counts = holdings["status"].value_counts()
        tx = universe.transactions()
        latest_tx = f"{len(tx)} transactions, latest {_d(tx['date'].max())}" if not tx.empty else ""
        rows.append(_row("holdings", _mtime(userstore.USERDATA / userstore.DB_NAME), ref, None,
                         f"{counts.get('holding', 0)} holdings, {counts.get('watch', 0)} watchlist, "
                         f"{counts.get('sold', 0)} sold", latest_tx, log, state=INFO))
    else:
        rows.append(_row("holdings", None, ref, None, "no import", "", log, state=MISSING))

    reg = regime_counts(indicators)
    dated = [r for r in rows if r["age_days"] is not None and r["status"] in (OK, STALE) and r["key"] != "prices"
             and r["max_age"] is not None]
    oldest = max(dated, key=lambda r: r["age_days"], default=None)
    return {
        "sources": rows, "regime": reg,
        "oldest": {"name": oldest["name"], "asof": oldest["asof"], "age_days": oldest["age_days"]} if oldest else None,
        "failing": [r["name"] for r in rows if r["error"]],
        "stale_sources": [r["name"] for r in rows if r["status"] == STALE],
        "missing_tickers": missing, "stale_tickers": stale,
        "blind_spots": cfg["coverage"].get("blind_spots") or [],
    }


def regime_counts(indicators: list[dict]) -> dict:
    """How many regime indicators have current data, and which don't."""
    na = [i["name"] for i in indicators if i["status"] == "n/a"]
    stale = [i["name"] for i in indicators if i["status"] == "stale"]
    return {"total": len(indicators), "current": len(indicators) - len(na) - len(stale), "na": na, "stale": stale}
