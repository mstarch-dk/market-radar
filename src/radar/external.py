"""Free non-price data: CFTC positioning, OECD leading indicators, FactSet earnings revisions,
analyst consensus targets (Yahoo).

Each `update_*` is incremental and writes a parquet file in data/. Fetch failures are the caller's
to soften (see cli.update): the last cached file stays in place and the report keeps using it.
"""
from __future__ import annotations

import io
import re
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import guard, net
from .config import universe_config, write_parquet, write_text
from .jsonsafe import clean
from .paths import CACHE, HISTORY

COT_FILE = CACHE / "cot.parquet"
CLI_FILE = CACHE / "oecd_cli.parquet"
FACTSET_FILE = HISTORY / "factset.parquet"      # one row per weekly report; the source only looks 14 days back
FACTSET_TEXT = CACHE / "factset_latest.txt"


def cfg() -> dict:
    return universe_config().get("external", {})


# ---------------- CFTC Commitments of Traders ----------------

COT_DATASETS = {  # Socrata dataset id, and which trader groups to keep (CFTC column prefix -> label)
    "tff": ("gpe5-46if", {"asset_mgr_positions": "Asset managers", "lev_money_positions": "Leveraged funds"}),
    "disagg": ("72hh-3qpy", {"m_money_positions": "Managed money"}),
}
COT_HISTORY_YEARS = 4


def cot_fetch(dataset: str, codes: list[str], since: date) -> list[dict]:
    where = (f"cftc_contract_market_code in({','.join(repr(c) for c in codes)}) "
             f"AND report_date_as_yyyy_mm_dd > '{since.isoformat()}'")
    resp = net.get(f"https://publicreporting.cftc.gov/resource/{dataset}.json",
                   params={"$where": where, "$limit": 50000}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def cot_rows(raw: list[dict], groups: dict[str, str], names: dict[str, str]) -> pd.DataFrame:
    """Long table: date, market, trader group, net position as % of open interest."""
    rows = []
    for r in raw:
        if r.get("futonly_or_combined", "FutOnly") != "FutOnly":  # futures+options rows would mix two bases
            continue
        oi = float(r["open_interest_all"])
        for prefix, label in groups.items():
            # the disaggregated report suffixes its position columns with "_all"; TFF mostly doesn't
            long_ = r.get(f"{prefix}_long") or r.get(f"{prefix}_long_all")
            short = r.get(f"{prefix}_short") or r.get(f"{prefix}_short_all")
            if long_ is None or short is None or not oi:
                continue
            rows.append({"date": pd.Timestamp(r["report_date_as_yyyy_mm_dd"][:10]),
                         "market": names[r["cftc_contract_market_code"]], "group": label,
                         "net": float(long_) - float(short), "net_pct_oi": 100 * (float(long_) - float(short)) / oi})
    return pd.DataFrame(rows, columns=["date", "market", "group", "net", "net_pct_oi"])


def update_cot(today: date | None = None) -> int:
    contracts = cfg().get("cot", {})
    existing = load_cot()
    full = (today or date.today()) - timedelta(days=int(365.25 * COT_HISTORY_YEARS))
    last = existing.groupby("market")["date"].max() if not existing.empty else pd.Series(dtype="datetime64[ns]")
    frames = [existing]
    for report, (dataset, groups) in COT_DATASETS.items():
        names = {str(code): name for name, code in contracts.get(report, {}).items()}
        # markets already stored only need new weeks; newly configured ones get the full history
        known = {c: n for c, n in names.items() if n in last.index}
        new = {c: n for c, n in names.items() if n not in last.index}
        if known:
            since = min(last[n] for n in known.values()).date()
            frames.append(cot_parse(cot_fetch(dataset, list(known), since), groups, names, report))
        if new:
            frames.append(cot_parse(cot_fetch(dataset, list(new), full), groups, names, report))
    df = pd.concat([f for f in frames if not f.empty], ignore_index=True) if any(not f.empty for f in frames) \
        else pd.DataFrame(columns=["date", "market", "group", "net", "net_pct_oi"])
    df = df.drop_duplicates(["date", "market", "group"], keep="last").sort_values(["market", "group", "date"])
    write_parquet(df, COT_FILE, index=False)
    return len(df) - len(existing)


def cot_parse(raw: list[dict], groups: dict[str, str], names: dict[str, str], report: str) -> pd.DataFrame:
    """`cot_rows`, but records that yield nothing mean the CFTC renamed its columns: fail rather than store nothing."""
    rows = cot_rows(raw, groups, names)
    if raw and rows.empty:
        raise ValueError(f"{len(raw)} {report} records but no {', '.join(groups)} columns: has the CFTC format changed?")
    return rows


def load_cot() -> pd.DataFrame:
    return pd.read_parquet(COT_FILE) if COT_FILE.exists() else pd.DataFrame()


def cot_table(cot: pd.DataFrame, lookback_weeks: int = 156, extreme: float = 10) -> pd.DataFrame:
    """Latest net positioning per market/group, its percentile over `lookback_weeks` and the 4-week change."""
    rows = []
    for (market, group), g in cot.groupby(["market", "group"], sort=False):
        s = g.set_index("date")["net_pct_oi"].sort_index().iloc[-lookback_weeks:]
        if len(s) < 52:
            continue
        pct = 100 * (s < s.iloc[-1]).mean()
        # relative to its own history: a "3y low" can still be net long
        flag = "3y high" if pct >= 100 - extreme else "3y low" if pct <= extreme else None
        rows.append({"market": market, "group": group, "asof": s.index[-1], "net_pct_oi": s.iloc[-1],
                     "chg_4w": s.iloc[-1] - s.iloc[-5] if len(s) > 4 else np.nan, "percentile": pct, "flag": flag})
    return pd.DataFrame(rows)


# ---------------- OECD Composite Leading Indicators ----------------

OECD_CLI_URL = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI,/"
                "{areas}.M.LI...AA...H?startPeriod={start}&format=csvfilewithlabels")


def parse_oecd_cli(text: str) -> pd.DataFrame:
    csv = pd.read_csv(io.StringIO(text))
    dupes = csv.duplicated(["REF_AREA", "TIME_PERIOD"])
    if dupes.any():  # pivot_table would silently average two different series
        raise ValueError(f"{dupes.sum()} duplicate area/month observations: the query matches more than one series")
    df = csv.pivot_table(index="TIME_PERIOD", columns="REF_AREA", values="OBS_VALUE")
    if df.empty:
        raise ValueError("no observations in the OECD's answer: has the query or the format changed?")
    df.index = pd.PeriodIndex(df.index, freq="M").to_timestamp()
    return df.sort_index()


def update_oecd_cli(today: date | None = None) -> str:
    """The CLI for the configured areas over a rolling six-year window. The answer is checked against what is
    stored before anything is written (guard): an area missing from it keeps its stored values (and says so); an
    area that ends earlier than stored, or has markedly fewer months, keeps the stored file."""
    areas = cfg().get("oecd_cli", {})
    start = ((today or date.today()) - timedelta(days=365 * 6)).strftime("%Y-%m")
    resp = net.get(OECD_CLI_URL.format(areas="+".join(areas), start=start), timeout=60)
    resp.raise_for_status()
    df = parse_oecd_cli(resp.text)
    notes = guard.replace(CLI_FILE, load_oecd_cli(), df, what="OECD CLI", key=None, date=None,
                          expected_keys=list(areas), carry=True,
                          start_tol=timedelta(days=62), row_tol=0.05)   # the window rolls a month at a time
    missing = [a for a in areas if a not in df.columns and not any(a in n for n in notes)]
    return (f"latest {df.index[-1]:%b %Y}" + (f"; no data for {', '.join(missing)}" if missing else "")
            + "".join(f"; {n}" for n in notes))



def load_oecd_cli() -> pd.DataFrame:
    return pd.read_parquet(CLI_FILE) if CLI_FILE.exists() else pd.DataFrame()


def cli_table(cli: pd.DataFrame, labels: dict[str, str]) -> pd.DataFrame:
    """Per area: latest CLI, 3-month change, and the cycle phase (above/below 100 x rising/falling)."""
    rows = []
    for area in [a for a in labels if a in cli.columns] or list(cli.columns):  # config order: first area votes
        s = cli[area].dropna()
        if len(s) < 4:
            continue
        chg = s.iloc[-1] - s.iloc[-4]
        above, rising = s.iloc[-1] >= 100, chg > 0
        phase = {(True, True): "Expansion", (True, False): "Slowdown",
                 (False, False): "Contraction", (False, True): "Recovery"}[(above, rising)]
        rows.append({"area": area, "label": labels.get(area, area), "asof": s.index[-1], "cli": s.iloc[-1],
                     "chg_3m": chg, "phase": phase})
    return pd.DataFrame(rows)


# ---------------- ECB Data Portal (euro-area rates) ----------------

ECB_FILE = CACHE / "ecb.parquet"
ECB_URL = "https://data-api.ecb.europa.eu/service/data/{key}?startPeriod={start}&format=csvdata"


def parse_ecb(text: str) -> pd.Series:
    """One ECB SDMX series as CSV (`format=csvdata`) → a dated series."""
    csv = pd.read_csv(io.StringIO(text))
    if not {"TIME_PERIOD", "OBS_VALUE"} <= set(csv.columns) or csv.empty:
        raise ValueError("no TIME_PERIOD / OBS_VALUE in the ECB's answer: has the format changed?")
    if csv["KEY"].nunique() > 1:
        raise ValueError(f"{csv['KEY'].nunique()} series in one answer: the key matches more than one series")
    freq = str(csv["FREQ"].iloc[0]) if "FREQ" in csv else ("D" if len(str(csv["TIME_PERIOD"].iloc[0])) == 10 else "M")
    s = pd.Series(pd.to_numeric(csv["OBS_VALUE"], errors="coerce").values,
                  index=pd.PeriodIndex(csv["TIME_PERIOD"], freq="M" if freq == "M" else "D").to_timestamp())
    s = s.dropna().sort_index()
    if s.empty:
        raise ValueError("the ECB's answer has no values: kept the stored series")
    return s


def update_ecb(today: date | None = None) -> str:
    series = cfg().get("ecb", {})
    start = ((today or date.today()) - timedelta(days=365 * 6)).isoformat()
    out = {}
    for key, (sid, _label) in series.items():
        resp = net.get(ECB_URL.format(key=sid, start=start), timeout=60)
        resp.raise_for_status()
        out[key] = parse_ecb(resp.text)
    df = pd.DataFrame(out).sort_index()
    # a six-year window that rolls with today: the start may move later, the end may not move back
    guard.replace(ECB_FILE, load_ecb(), df, what="ECB", key=None, date=None, expected_keys=list(series),
                  start_tol=timedelta(days=62), row_tol=0.05)
    return ", ".join(f"{k} {s.index[-1]:%d %b}" for k, s in out.items())


def load_ecb() -> pd.DataFrame:
    return pd.read_parquet(ECB_FILE) if ECB_FILE.exists() else pd.DataFrame()


# ---------------- FactSet Earnings Insight ----------------

FACTSET_URL = ("https://advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/"
               "Earnings%20Insight/EarningsInsight_{d:%m%d%y}.pdf")
FACTSET_LOOKBACK_DAYS = 14
# the chart pages are images, so only the prose is parsed; these pages are kept as text for the brief
FACTSET_TEXT_PAGES = ("Key Metrics", "Earnings Revisions", "Forward Estimates & Valuation")

_NUM = r"(-?\d+(?:\.\d+)?)"
FACTSET_REQUIRED = ("growth_now", "growth_start")  # the regime vote; without them the report is useless
FACTSET_PATTERNS = {
    # "estimated" before the season, "blended" (actuals + estimates) once companies report
    "quarter": r"For (Q\d \d{4}), the (?:estimated|blended) \(year-over-year\) earnings growth rate",
    "growth_now": r"earnings growth rate for the S&P 500 is " + _NUM + "%",
    "growth_start": r"On \w+ \d+, the estimated \(year-over-year\) earnings growth rate for the S&P 500 for Q\d\s+\d{4}\s+was "
                    + _NUM + "%",
    "guidance_neg": r"(\d+) S&P 500 companies have issued negative EPS guidance",
    "guidance_pos": r"(\d+) S&P 500\s+companies have issued positive EPS guidance",
    "fwd_pe": r"forward 12-month P/E ratio for the S&P 500 is " + _NUM,
    "fwd_pe_5y": r"5-year average(?: of)? \(?" + _NUM,
    "fwd_pe_10y": r"10-year average(?: of)? \(?" + _NUM,
    "cy_next_growth": r"For CY \d{4}, analysts are projecting earnings growth of " + _NUM + r"%(?![\s\S]*For CY)",
    "rev_up_sectors": r"upward\s+revisions to earnings estimates, led by the ([A-Za-z ,]+?) sectors",
    "rev_down_sectors": r"downward revisions to earnings estimates, led by\s+the ([A-Za-z ,]+?) sectors",
}


def parse_factset(pages: list[str]) -> dict:
    text = "\n".join(pages)
    flat = re.sub(r"\s+", " ", text)
    out: dict = {}
    for key, pat in FACTSET_PATTERNS.items():
        m = re.search(pat, flat)
        if not m:
            out[key] = None
        elif key.endswith("_sectors"):
            out[key] = ", ".join(s.strip() for s in re.split(r",\s*(?:and\s+)?|\s+and\s+", m.group(1)) if s.strip())
        elif key == "quarter":
            out[key] = m.group(1)
        else:
            out[key] = float(m.group(1))
    return out


def factset_pages(pdf: bytes) -> list[str]:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf)) as p:
        return [pg.extract_text() or "" for pg in p.pages]


def update_factset(today: date | None = None) -> str | None:
    """Fetch the newest Earnings Insight PDF not seen yet; returns its date or None."""
    existing = load_factset()
    seen = set(existing["report_date"].dt.date) if not existing.empty else set()
    for back in range(FACTSET_LOOKBACK_DAYS + 1):
        d = (today or date.today()) - timedelta(days=back)
        if d in seen:
            return None  # newest report already stored
        resp = net.get(FACTSET_URL.format(d=d), timeout=60, expected=(403, 404))
        if resp.status_code != 200 or not resp.content.startswith(b"%PDF"):
            continue
        pages = factset_pages(resp.content)
        row = parse_factset(pages) | {"report_date": pd.Timestamp(d)}
        missing = [k for k in FACTSET_REQUIRED if row[k] is None]
        if missing:  # not stored, so the next run retries; the wording has probably changed
            raise ValueError(f"report {d} parsed without {', '.join(missing)}: has the FactSet wording changed?")
        df = pd.concat([existing, pd.DataFrame([row])], ignore_index=True).sort_values("report_date")
        write_parquet(df, FACTSET_FILE, index=False)
        FACTSET_TEXT.parent.mkdir(parents=True, exist_ok=True)
        keep = [p for p in pages if any(h in p[:200] for h in FACTSET_TEXT_PAGES)]
        write_text(FACTSET_TEXT, f"FactSet Earnings Insight {d.isoformat()}\n{FACTSET_URL.format(d=d)}\n\n"
                   + "\n\n".join(keep))
        return d.isoformat()
    return None


def load_factset() -> pd.DataFrame:
    return pd.read_parquet(FACTSET_FILE) if FACTSET_FILE.exists() else pd.DataFrame()


# ---------------- Analyst consensus (Yahoo) ----------------

ANALYST_FILE = HISTORY / "analyst.parquet"   # kept as fetched: history
ANALYST_FIELDS = {  # Yahoo .info key -> column
    "currentPrice": "current_price", "currency": "currency", "targetMeanPrice": "target_mean",
    "targetMedianPrice": "target_median", "targetHighPrice": "target_high", "targetLowPrice": "target_low",
    "numberOfAnalystOpinions": "n_analysts", "recommendationKey": "rec_key", "recommendationMean": "rec_mean",
    "sector": "sector",  # empty for funds, which Yahoo sometimes labels EQUITY too
}


def parse_analyst(info: dict | None) -> dict | None:
    """Consensus fields from a Yahoo `.info` dict. Funds have no targets: only quote_type is set."""
    if not info or not info.get("quoteType"):
        return None
    row = {"quote_type": info["quoteType"]}
    for key, col in ANALYST_FIELDS.items():
        v = info.get(key)
        row[col] = None if v in ("", "none") else v
    return row


def update_analyst(tickers: list[str], max_age_days: int = 7, today: date | None = None) -> str:
    """Append a dated consensus row per ticker whose last fetch is older than `max_age_days`.

    The history is kept so the levels can tell whether targets are being raised or cut.
    """
    yf = net.yf()

    existing = load_analyst()
    today = pd.Timestamp(today or date.today())
    last = existing.groupby("ticker")["fetched"].max() if not existing.empty else pd.Series(dtype="datetime64[ns]")
    due = [t for t in tickers if t not in last or (today - last[t]).days >= max_age_days]
    if not due:
        return "up to date"

    def fetch(t):
        try:
            row = parse_analyst(yf.Ticker(t).info)
        except Exception:
            return None
        return row | {"ticker": t, "fetched": today} if row else None

    with net.pool(8) as ex:
        rows = [r for r in ex.map(fetch, due) if r]
    if not rows:
        raise RuntimeError(f"no data for {len(due)} tickers")
    new = pd.DataFrame(rows)
    for col in ("current_price", "target_mean", "target_median", "target_high", "target_low", "n_analysts", "rec_mean"):
        new[col] = pd.to_numeric(new[col], errors="coerce")
    df = pd.concat([existing, new], ignore_index=True).drop_duplicates(["ticker", "fetched"], keep="last")
    write_parquet(df.sort_values(["ticker", "fetched"]), ANALYST_FILE, index=False)
    return f"{len(rows)} of {len(due)} tickers refreshed"


def load_analyst() -> pd.DataFrame:
    return pd.read_parquet(ANALYST_FILE) if ANALYST_FILE.exists() else pd.DataFrame()


# ---------------- Ticker detail (Yahoo): fundamentals, estimates, fund look-through ----------------
# `fetch_detail` turns yfinance's objects into plain JSON (the cache file and the test fixtures share that
# shape); the `parse_*` functions read only that JSON. Yahoo mixes units between fields (dividendYield and
# netExpenseRatio in percent, margins and growth as fractions), so every ratio is normalised to a fraction
# and range-checked: a value that can't be right is dropped with a note, never shown.

PROFILE_DIR = CACHE / "profiles"
DETAIL_INFO_KEYS = (
    "quoteType", "longName", "shortName", "currency", "financialCurrency", "exchange", "fullExchangeName",
    "sector", "industry", "country", "website", "longBusinessSummary", "fullTimeEmployees", "marketCap",
    "enterpriseValue", "trailingPE", "forwardPE", "trailingPegRatio", "pegRatio", "priceToBook",
    "enterpriseToEbitda", "enterpriseToRevenue", "grossMargins", "operatingMargins", "profitMargins",
    "revenueGrowth", "earningsGrowth", "returnOnEquity", "debtToEquity", "dividendYield",
    "trailingAnnualDividendYield", "payoutRatio", "beta", "shortPercentOfFloat", "currentPrice",
    "regularMarketPrice", "targetMeanPrice", "targetHighPrice", "targetLowPrice", "targetMedianPrice",
    "numberOfAnalystOpinions", "recommendationKey", "recommendationMean", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
    "totalAssets", "netExpenseRatio", "fundFamily", "legalType", "category",
)


def _frame(df) -> dict:
    """{row: {column: value}} for a yfinance table; empty for None/empty."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return {}
    return clean({str(i): row for i, row in df.to_dict(orient="index").items()})


def fetch_detail(ticker: str) -> dict:
    """Everything Yahoo has on one ticker beyond prices, as plain JSON. A failing block is recorded in
    `errors` and left empty; the others still arrive."""
    import logging
    from datetime import datetime

    yf = net.yf()

    logging.getLogger("yfinance").setLevel(logging.CRITICAL)  # 404s for funds are expected, not news
    t = yf.Ticker(ticker)
    raw: dict = {"symbol": ticker, "fetched": datetime.now().isoformat(timespec="seconds"), "errors": {}}

    def block(name, fn, default):
        try:
            raw[name] = fn()
        except Exception as e:
            raw[name] = default
            raw["errors"][name] = f"{type(e).__name__}: {e}"[:300]

    def recommendations():
        df = t.recommendations
        return clean(df.to_dict(orient="records")) if isinstance(df, pd.DataFrame) else []

    def fund():
        fd = t.funds_data
        top, ops = fd.top_holdings, fd.fund_operations
        return clean({
            "top_holdings": [{"symbol": s, "name": r.get("Name"), "weight": r.get("Holding Percent")}
                             for s, r in top.to_dict(orient="index").items()] if isinstance(top, pd.DataFrame) else [],
            "sector_weightings": fd.sector_weightings or {}, "asset_classes": fd.asset_classes or {},
            "operations": ops.iloc[:, 0].to_dict() if isinstance(ops, pd.DataFrame) and not ops.empty else {},
            "overview": fd.fund_overview or {},
        })

    block("info", lambda: clean({k: (t.info or {}).get(k) for k in DETAIL_INFO_KEYS}), {})
    block("recommendations", recommendations, [])
    block("eps_trend", lambda: _frame(t.eps_trend), {})
    block("eps_revisions", lambda: _frame(t.eps_revisions), {})
    block("growth_estimates", lambda: _frame(t.growth_estimates), {})
    block("calendar", lambda: clean(t.calendar or {}), {})
    if raw["info"].get("quoteType") in ("ETF", "MUTUALFUND"):
        block("fund", fund, {})
    return raw


def detail(ticker: str, max_age_hours: float = 24, refresh: bool = False) -> tuple[dict | None, str]:
    """Cached `fetch_detail`: (raw, status), status ok | stale (fetch failed, older copy used) | missing."""
    import json
    from datetime import datetime

    path = PROFILE_DIR / f"{ticker}.json"
    cached = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if cached and not refresh:
        age = (datetime.now() - datetime.fromisoformat(cached["fetched"])).total_seconds() / 3600
        if age < max_age_hours:
            return cached, "ok"
    try:
        raw = fetch_detail(ticker)
    except Exception:
        return cached, "stale" if cached else "missing"
    if not any(raw.get(k) for k in ("info", "recommendations", "eps_trend", "calendar")):
        return (cached, "stale") if cached else (None, "missing")  # Yahoo answered with nothing
    if cached:   # a block that failed this time keeps its cached copy (noted in `kept`, not shown as an error)
        raw["kept"] = {}
        for name in list(raw.get("errors") or {}):
            if cached.get(name):
                raw[name] = cached[name]
                raw["kept"][name] = cached.get("kept", {}).get(name) or cached["fetched"]
                del raw["errors"][name]
        if "fund" not in raw and cached.get("fund") and raw.get("info", {}).get("quoteType") in ("ETF", "MUTUALFUND"):
            raw["fund"] = cached["fund"]
            raw["kept"]["fund"] = cached.get("kept", {}).get("fund") or cached["fetched"]
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    write_text(path, json.dumps(raw, indent=1))
    return raw, "ok"


def _ratio(v, lo: float, hi: float, name: str, notes: list[str], scale: float = 1.0) -> float | None:
    """A ratio from Yahoo (divided by `scale` first), or None with a note when it is outside [lo, hi]."""
    try:
        v = float(v) / scale
    except (TypeError, ValueError):
        return None
    if np.isnan(v):
        return None
    if not lo <= v <= hi:
        notes.append(f"{name} {v:g} is outside the plausible range [{lo:g}, {hi:g}]: not shown")
        return None
    return v


def dividend_yield(info: dict, notes: list[str]) -> float | None:
    """Yahoo's `dividendYield` moved from a fraction to percent; `trailingAnnualDividendYield` is still a
    fraction, so it decides which reading is right. Without it, the current convention (percent) applies."""
    dy, trailing = info.get("dividendYield"), info.get("trailingAnnualDividendYield")
    if dy is None:
        return None
    dy = float(dy)
    frac = dy / 100
    if trailing:
        frac = min((dy, dy / 100), key=lambda c: abs(c - float(trailing)))
    return _ratio(frac, 0, 0.25, "dividend yield", notes)


def parse_fundamentals(info: dict) -> dict:
    notes: list[str] = []

    def multiple(key, hi, label):
        v = info.get(key)
        if v is None:
            return None
        if float(v) <= 0:
            notes.append(f"{label} {float(v):g} is not meaningful (negative earnings or book value)")
            return None
        return _ratio(v, 0, hi, label, notes)

    peg_key = "trailingPegRatio" if info.get("trailingPegRatio") is not None else "pegRatio"
    out = {
        "market_cap": info.get("marketCap"), "enterprise_value": info.get("enterpriseValue"),
        "currency": info.get("currency"), "financial_currency": info.get("financialCurrency"),
        "trailing_pe": multiple("trailingPE", 1000, "trailing P/E"), "forward_pe": multiple("forwardPE", 1000, "forward P/E"),
        "peg": multiple(peg_key, 50, "PEG"), "price_to_book": multiple("priceToBook", 500, "price/book"),
        "ev_ebitda": multiple("enterpriseToEbitda", 500, "EV/EBITDA"),
        "ev_revenue": multiple("enterpriseToRevenue", 500, "EV/revenue"),
        "gross_margin": _ratio(info.get("grossMargins"), -5, 1, "gross margin", notes),
        "operating_margin": _ratio(info.get("operatingMargins"), -5, 1, "operating margin", notes),
        "profit_margin": _ratio(info.get("profitMargins"), -5, 1, "profit margin", notes),
        "revenue_growth": _ratio(info.get("revenueGrowth"), -1, 20, "revenue growth", notes),
        "earnings_growth": _ratio(info.get("earningsGrowth"), -50, 50, "earnings growth", notes),
        "return_on_equity": _ratio(info.get("returnOnEquity"), -5, 5, "return on equity", notes),
        "debt_to_equity": _ratio(info.get("debtToEquity"), 0, 50, "debt/equity", notes, scale=100),  # Yahoo: %
        "dividend_yield": dividend_yield(info, notes),
        "payout_ratio": _ratio(info.get("payoutRatio"), 0, 10, "payout ratio", notes),
        "beta": _ratio(info.get("beta"), -5, 10, "beta", notes),
        "short_pct_float": _ratio(info.get("shortPercentOfFloat"), 0, 1, "short interest", notes),
        "employees": info.get("fullTimeEmployees"),
    }
    return out | {"notes": notes}


def parse_recommendations(rows: list[dict]) -> list[dict]:
    """Monthly buy/hold/sell counts, newest first, with the mean on Yahoo's 1 (strong buy) – 5 scale."""
    out = []
    for r in rows:
        counts = [int(r.get(k) or 0) for k in ("strongBuy", "buy", "hold", "sell", "strongSell")]
        n = sum(counts)
        out.append({"period": r.get("period"), "strong_buy": counts[0], "buy": counts[1], "hold": counts[2],
                    "sell": counts[3], "strong_sell": counts[4], "n": n,
                    "mean": round(sum((i + 1) * c for i, c in enumerate(counts)) / n, 2) if n else None})
    return out


EPS_PERIODS = {"0q": "Current quarter", "+1q": "Next quarter", "0y": "Current year", "+1y": "Next year"}


def parse_eps_trend(trend: dict, revisions: dict, growth: dict) -> list[dict]:
    """Per period: consensus EPS now vs 7/30/90 days ago (the revision trend), revision counts and growth."""
    out = []
    for p, label in EPS_PERIODS.items():
        t, r, g = trend.get(p) or {}, revisions.get(p) or {}, growth.get(p) or {}
        if not t and not r:
            continue
        now = t.get("current")

        def chg(col, t=t, now=now):
            old = t.get(col)
            # only meaningful between two positive estimates (a sign flip has no percent change)
            return now / old - 1 if now is not None and old is not None and old > 0 and now > 0 else None
        out.append({"period": p, "label": label, "eps": now, "currency": t.get("currency"),
                    "chg_7d": chg("7daysAgo"), "chg_30d": chg("30daysAgo"), "chg_90d": chg("90daysAgo"),
                    "up_30d": r.get("upLast30days"), "down_30d": r.get("downLast30days"),
                    "growth": g.get("stockTrend"), "index_growth": g.get("indexTrend")})
    return out


def parse_calendar(cal: dict, today: date | None = None) -> dict:
    """Next earnings date (the first one not in the past), its consensus, and dividend dates."""
    today = today or date.today()
    dates = cal.get("Earnings Date") or []
    dates = sorted(date.fromisoformat(d) for d in (dates if isinstance(dates, list) else [dates]) if d)
    upcoming = [d for d in dates if d >= today]
    return {"next_earnings": upcoming[0].isoformat() if upcoming else None,
            "eps_estimate": cal.get("Earnings Average"), "revenue_estimate": cal.get("Revenue Average"),
            "ex_dividend": cal.get("Ex-Dividend Date"), "dividend_date": cal.get("Dividend Date")}


FUND_SECTORS = {"realestate": "Real Estate"}  # funds_data keys → the sector names Yahoo uses for stocks


def parse_fund(fund: dict, info: dict) -> dict:
    """ETF look-through: top holdings, sector weights (largest first), expense ratio and size."""
    notes: list[str] = []
    ops = fund.get("operations") or {}
    ter = _ratio(ops.get("Annual Report Expense Ratio"), 0, 0.03, "expense ratio", notes)
    if ter is None and info.get("netExpenseRatio") is not None:
        ter = _ratio(info["netExpenseRatio"], 0, 0.03, "expense ratio", notes, scale=100)  # Yahoo: percent
    sectors = sorted(((k, v) for k, v in (fund.get("sector_weightings") or {}).items() if v), key=lambda x: -x[1])
    overview = fund.get("overview") or {}
    return {"top_holdings": fund.get("top_holdings") or [],
            "sector_weights": [{"sector": FUND_SECTORS.get(k, k.replace("_", " ").title()), "weight": v}
                               for k, v in sectors],
            "asset_classes": {k: v for k, v in (fund.get("asset_classes") or {}).items() if v},
            "expense_ratio": ter, "total_assets": info.get("totalAssets"),
            "family": overview.get("family") or info.get("fundFamily"),
            "legal_type": overview.get("legalType") or info.get("legalType"), "notes": notes}
