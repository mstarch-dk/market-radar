"""What the radar knows: freshness and coverage per data source, the update log, and the blind spots.

Each source row says where the data comes from, what it feeds, how much of the configured universe it
covers, how old it is and whether its last update worked. Ages are counted from the report's as-of date
(the benchmark's last trading day), so a weekend doesn't make everything look stale; prices are also
checked against today, since an update that keeps failing makes the whole report old.
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from . import sourcelog, trades
from .config import POSITIVE_LIST_FILE
from .paths import CACHE

OK, STALE, MISSING, INFO = "ok", "stale", "missing", "info"
NOT_REGIME = {"valuation_stocks", "valuation_etfs", "ecb", "putcall", "aaii",   # never "the regime's oldest input"
              "fundamentals_edgar", "fundamentals_yahoo", "factors"}

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
    "acwi_holdings": ("MSCI ACWI weights", "iShares MSCI ACWI UCITS holdings", True, "monthly re-fetch, on use",
                      "Portfolio proposals (sector, region and currency vs ACWI)"),
    "reference": ("Names, sectors, currencies", "Yahoo Finance (cached)", False, "on first use",
                  "Momentum clusters, Holdings (DKK)"),
    "positive_list": ("Positive list (aktiebaserede inv.selskaber)", "SKAT (manual download)", True, "yearly",
                      "Themes (UCITS check)"),
    "holdings": ("Holdings & transactions", "your portfolios (entered or imported in the app)", False, "manual",
                 "Holdings, Levels"),
    "discovery_universe": ("Discovery universe", "Yahoo screener, iShares STOXX 600 holdings, positive list → Yahoo",
                           False, "monthly re-build", "Discover"),
    "discovery_prices": ("Discovery prices", "Yahoo Finance via yfinance", False, "each discovery scan", "Discover"),
    "valuation_stocks": ("Stock valuation & EPS estimates", "Yahoo screener (consensus estimates)", False, "weekly snapshot",
                         "P/E vs sector, EPS revisions (Momentum, Discover, holdings, ticker pages)"),
    "valuation_etfs": ("ETF valuation", "Yahoo fund data", False, "weekly snapshot", "Rotation, Themes (P/E vs ACWI)"),
    "cape": ("Shiller CAPE (US)", "multpl.com (Shiller's method; unofficial)", False, "monthly + current estimate",
             "Positioning (valuation), Regime (if switched on)"),
    "erp": ("Implied equity risk premium", "Aswath Damodaran, NYU Stern", True, "monthly",
            "Positioning (valuation), Regime (if switched on)"),
    "ecb": ("Euro-area rates", "ECB Data Portal", True, "daily", "Positioning"),
    "putcall": ("Put/call ratios", "CBOE daily market statistics", True, "daily", "Positioning (sentiment)"),
    "aaii": ("Investor sentiment survey", "AAII (weekly)", False, "weekly", "Positioning (sentiment)"),
    "fundamentals_edgar": ("Financial statements (US)", "SEC EDGAR company facts (10-K, 10-Q)", True,
                           "per company, as reports come out", "Statement facts (radar fundamentals)"),
    "fundamentals_yahoo": ("Financial statements", "Yahoo Finance via yfinance", False,
                           "per company, as reports come out", "Statement facts (radar fundamentals)"),
    "factors": ("Long factor and industry histories", "Kenneth R. French Data Library; JKP Global Factor Data", True,
                "monthly re-fetch", "The long-history score test (radar study longrun)"),
}


def live(view: dict, log: dict | None = None) -> dict:
    """A built coverage section with each source's last attempt, success and error from the update log as it is
    now, and `failing` worked out again from them."""
    log = sourcelog.load_log() if log is None else log
    rows = []
    for r in view["sources"]:
        entry = log.get(r["key"])
        rows.append(r if entry is None else r | {"last_attempt": entry.get("last_attempt"),
                                                  "last_success": entry.get("last_success"),
                                                  "error": entry.get("error")})
    return view | {"sources": rows, "failing": [r["name"] for r in rows if r["error"]]}


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
    log = sourcelog.load_log() if log is None else log
    today = today or date.today()
    rows = []

    # prices: coverage of the configured universe; age vs today (a failing update makes the whole report old)
    last = prices.groupby("ticker")["date"].max() if not prices.empty else pd.Series(dtype="datetime64[ns]")
    missing = sorted(set(configured) - set(last.index))
    stale = sorted(t for t, d in last.items() if t in set(configured) and (pd.Timestamp(ref) - d).days > max_age["prices"])
    # without the as-of session but not yet stale: an exchange holiday, or a bar Yahoo hasn't delivered
    behind = sorted(t for t, d in last.items() if t in set(configured) and t not in stale and d < pd.Timestamp(ref))
    have = len(set(configured) & set(last.index))
    span = f"history from {_d(prices['date'].min())}" if not prices.empty else ""
    rows.append(_row("prices", pd.Timestamp(ref) if not prices.empty else None, today, max_age["prices"],
                     f"{have} of {len(configured)} configured tickers" + (f"; {len(stale)} stale" if stale else "")
                     + (f"; {len(behind)} without a bar for {_d(ref)}" if behind else ""),
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
    cons = CACHE / "constituents_us.csv"
    n_cons = len(pd.read_csv(cons)) if cons.exists() else 0
    rows.append(_row("constituents", _mtime(cons), today, cfg["constituents_max_age_days"] + 14,
                     f"{n_cons} US stocks", "Today's members only: no history of index changes", log))

    # ACWI's weights (fetched when a proposal needs them)
    aw = CACHE / "acwi_holdings.csv"
    n_aw = len(pd.read_csv(aw)) if aw.exists() else 0
    rows.append(_row("acwi_holdings", _mtime(aw), today, cfg["constituents_max_age_days"] + 14,
                     f"{n_aw} stocks", "Fetched by `radar propose` when older than a month", log,
                     state=None if aw.exists() else INFO))

    # reference caches: how many stocks have a sector (used by the momentum clusters)
    sec_file = CACHE / "sectors.csv"
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
        from . import userstore

        counts = holdings["status"].value_counts()
        tx = trades.transactions()
        latest_tx = f"{len(tx)} transactions, latest {_d(tx['date'].max())}" if not tx.empty else ""
        rows.append(_row("holdings", _mtime(userstore.USERDATA / userstore.DB_NAME), ref, None,
                         f"{counts.get('holding', 0)} holdings, {counts.get('watch', 0)} watchlist, "
                         f"{counts.get('sold', 0)} sold", latest_tx, log, state=INFO))
    else:
        rows.append(_row("holdings", None, ref, None, "no import", "", log, state=MISSING))

    rows += _discovery_rows(today, max_age, log)
    rows += _valuation_rows(ref, max_age, log, stock_tickers)
    rows += _fundamentals_rows(ref, max_age, log, stock_tickers)
    rows += _factors_rows(ref, max_age, log)

    reg = regime_counts(indicators)
    dated = [r for r in rows if r["age_days"] is not None and r["status"] in (OK, STALE) and r["key"] != "prices"
             and r["max_age"] is not None and not r["key"].startswith("discovery") and r["key"] not in NOT_REGIME]
    oldest = max(dated, key=lambda r: r["age_days"], default=None)
    return {
        "sources": rows, "regime": reg,
        "oldest": {"name": oldest["name"], "asof": oldest["asof"], "age_days": oldest["age_days"]} if oldest else None,
        "failing": [r["name"] for r in rows if r["error"]],
        "stale_sources": [r["name"] for r in rows if r["status"] == STALE and not r["key"].startswith("discovery")],
        "missing_tickers": missing, "stale_tickers": stale, "behind_tickers": behind,
        "blind_spots": cfg["coverage"].get("blind_spots") or [],
    }


def _discovery_rows(today: date, max_age: dict, log: dict) -> list[dict]:
    """The separate discovery scan: how many names, and how old its universe and prices are (missing until the
    first `radar discover`)."""
    from .discovery import scan

    uni = scan.load_universe()
    by_market = ", ".join(f"{n} {m}" for m, n in uni["market"].value_counts().items()) if not uni.empty else ""
    rows = [_row("discovery_universe", _mtime(scan.UNIVERSE_FILE), today, max_age.get("discovery_universe"),
                 f"{len(uni)} names" if not uni.empty else "not built yet", by_market, log)]
    last = None
    if scan.PRICES_FILE.exists():
        d = pd.read_parquet(scan.PRICES_FILE, columns=["date"])["date"]
        last = pd.Timestamp(d.max()) if len(d) else None
    rows.append(_row("discovery_prices", last, today, max_age.get("discovery_prices"),
                     "separate from the daily update", "Run it from the Discover page or `radar discover`", log))
    return rows


def _valuation_rows(ref: date, max_age: dict, log: dict, stock_tickers: list[str]) -> list[dict]:
    """The valuation snapshots, the market's valuation (CAPE, ERP), euro-area rates and the sentiment series."""
    from . import external, sentiment, valuation

    rows = []
    st = valuation.load_stocks()
    now = valuation.latest(st)
    weeks = len(valuation.snapshot_dates(st))
    have = now.reindex([t for t in stock_tickers if t in now.index])
    rows.append(_row("valuation_stocks", pd.to_datetime(st["date"]).max() if not st.empty else None, ref,
                     max_age.get("valuation_stocks"),
                     f"{int(have['pe_fy1'].notna().sum())} of {len(stock_tickers)} tracked stocks with a forward P/E; "
                     f"{len(now):,} names in all" if not now.empty else "no snapshot yet",
                     f"{weeks} weekly snapshot{'s' if weeks != 1 else ''}; EPS revisions need 4 and 12 weeks", log))
    et = valuation.load_etfs()
    enow = valuation.latest(et)
    rows.append(_row("valuation_etfs", pd.to_datetime(et["date"]).max() if not et.empty else None, ref,
                     max_age.get("valuation_etfs"),
                     f"{int(enow['pe'].notna().sum())} ETFs with a P/E" if not enow.empty else "no snapshot yet",
                     "Yahoo stores fund multiples inverted (earnings yield); turned around here", log))
    mk = valuation.load_market()
    for key, series, detail in (("cape", "cape", "monthly since 1871"), ("erp", "erp", "monthly since 2008")):
        s = valuation.market_series(series, mk)
        rows.append(_row(key, s.index.max() if len(s) else None, ref, max_age.get(key),
                         f"{len(s):,} months" if len(s) else "not loaded", detail, log))
    ecb = external.load_ecb()
    rows.append(_row("ecb", ecb.dropna(how="all").index.max() if not ecb.empty else None, ref, max_age.get("ecb"),
                     f"{len(ecb.columns)} series" if not ecb.empty else "not loaded", "Euro area AAA 10Y yield", log))
    pc = sentiment.load_putcall()
    rows.append(_row("putcall", pd.to_datetime(pc["date"]).max() if not pc.empty else None, ref, max_age.get("putcall"),
                     f"{len(pc)} trading days" if not pc.empty else "not loaded", "Total, equity and index ratios", log))
    aa = sentiment.load_aaii()
    rows.append(_row("aaii", pd.to_datetime(aa["date"]).max() if not aa.empty else None, ref, max_age.get("aaii"),
                     f"{len(aa):,} weeks" if not aa.empty else "not loaded", "Bullish / neutral / bearish members", log))
    return rows


def _fundamentals_rows(ref: date, max_age: dict, log: dict, stock_tickers: list[str]) -> list[dict]:
    """Financial statements: how many companies have them and when they were fetched. Each company is fetched on
    its own schedule, so the source's age is its newest fetch; the oldest fetch is in the detail."""
    from . import universe, userstore
    from .fundamentals import edgar, schedule, yahoo

    rows = []
    for key, path, names, label in (("fundamentals_edgar", edgar.LOG_FILE, edgar.us_tickers(universe.tracked_stocks()), "US stocks"),
                                    ("fundamentals_yahoo", yahoo.LOG_FILE, stock_tickers, "tracked stocks")):
        d = schedule.load_log(path)
        good = d[d["ok"] & d["last_end"].notna() & d["ticker"].isin(set(names))]
        detail = (f"oldest fetch {_d(good['fetched'].min())}; latest periods from {_d(good['last_end'].min())} "
                  f"to {_d(good['last_end'].max())}" if not good.empty else "not fetched yet")
        if key == "fundamentals_edgar" and not userstore.sec_contact():
            detail = "needs a contact e-mail for SEC (Data page, or radar fundamentals contact EMAIL)"
        rows.append(_row(key, d["fetched"].max() if not d.empty else None, ref, max_age.get(key),
                         f"{len(good)} of {len(names)} {label}", detail, log))
    return rows


def _factors_rows(ref: date, max_age: dict, log: dict) -> list[dict]:
    """The long histories: when they were fetched (the sources themselves lag months: French about two, JKP up to a
    year), and the last month in each."""
    from . import factors

    d = factors.load()
    last = factors.asof(d)
    want = factors.datasets()
    detail = ", ".join(f"{k} to {m}" for k, m in last.items()) if last else "not fetched yet"
    return [_row("factors", d["fetched"].max() if not d.empty else None, ref, max_age.get("factors"),
                 f"{len(set(last) & set(want))} of {len(want)} datasets", detail, log)]


def regime_counts(indicators: list[dict]) -> dict:
    """How many regime indicators have current data, and which don't. Context rows (never in the vote) are left out."""
    indicators = [i for i in indicators if i.get("group") != "context"]
    na = [i["name"] for i in indicators if i["status"] == "n/a"]
    stale = [i["name"] for i in indicators if i["status"] == "stale"]
    return {"total": len(indicators), "current": len(indicators) - len(na) - len(stale), "na": na, "stale": stale}
