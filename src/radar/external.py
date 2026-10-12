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
import requests

from .config import DATA, universe_config

UA = {"User-Agent": "Mozilla/5.0 (market-radar personal research script)"}
COT_FILE = DATA / "cot.parquet"
CLI_FILE = DATA / "oecd_cli.parquet"
FACTSET_FILE = DATA / "factset.parquet"
FACTSET_TEXT = DATA / "factset_latest.txt"


def _cfg() -> dict:
    return universe_config().get("external", {})


# ---------------- CFTC Commitments of Traders ----------------

COT_DATASETS = {  # Socrata dataset id, and which trader groups to keep (CFTC column prefix -> label)
    "tff": ("gpe5-46if", {"asset_mgr_positions": "Asset managers", "lev_money_positions": "Leveraged funds"}),
    "disagg": ("72hh-3qpy", {"m_money_positions": "Managed money"}),
}
COT_HISTORY_YEARS = 4


def _cot_fetch(dataset: str, codes: list[str], since: date) -> list[dict]:
    where = (f"cftc_contract_market_code in({','.join(repr(c) for c in codes)}) "
             f"AND report_date_as_yyyy_mm_dd > '{since.isoformat()}'")
    resp = requests.get(f"https://publicreporting.cftc.gov/resource/{dataset}.json",
                        params={"$where": where, "$limit": 50000}, headers=UA, timeout=60)
    resp.raise_for_status()
    return resp.json()


def cot_rows(raw: list[dict], groups: dict[str, str], names: dict[str, str]) -> pd.DataFrame:
    """Long table: date, market, trader group, net position as % of open interest."""
    rows = []
    for r in raw:
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


def update_cot() -> int:
    contracts = _cfg().get("cot", {})
    existing = load_cot()
    full = date.today() - timedelta(days=int(365.25 * COT_HISTORY_YEARS))
    last = existing.groupby("market")["date"].max() if not existing.empty else pd.Series(dtype="datetime64[ns]")
    frames = [existing]
    for report, (dataset, groups) in COT_DATASETS.items():
        names = {str(code): name for name, code in contracts.get(report, {}).items()}
        # markets already stored only need new weeks; newly configured ones get the full history
        known = {c: n for c, n in names.items() if n in last.index}
        new = {c: n for c, n in names.items() if n not in last.index}
        if known:
            since = min(last[n] for n in known.values()).date()
            frames.append(cot_rows(_cot_fetch(dataset, list(known), since), groups, names))
        if new:
            frames.append(cot_rows(_cot_fetch(dataset, list(new), full), groups, names))
    df = pd.concat([f for f in frames if not f.empty], ignore_index=True) if any(not f.empty for f in frames) \
        else pd.DataFrame(columns=["date", "market", "group", "net", "net_pct_oi"])
    df = df.drop_duplicates(["date", "market", "group"], keep="last").sort_values(["market", "group", "date"])
    DATA.mkdir(exist_ok=True)
    df.to_parquet(COT_FILE, index=False)
    return len(df) - len(existing)


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
    df = csv.pivot_table(index="TIME_PERIOD", columns="REF_AREA", values="OBS_VALUE")
    df.index = pd.PeriodIndex(df.index, freq="M").to_timestamp()
    return df.sort_index()


def update_oecd_cli() -> str:
    areas = _cfg().get("oecd_cli", {})
    start = (date.today() - timedelta(days=365 * 6)).strftime("%Y-%m")
    resp = requests.get(OECD_CLI_URL.format(areas="+".join(areas), start=start), headers=UA, timeout=60)
    resp.raise_for_status()
    df = parse_oecd_cli(resp.text)
    DATA.mkdir(exist_ok=True)
    df.to_parquet(CLI_FILE)
    missing = [a for a in areas if a not in df.columns]
    return f"latest {df.index[-1]:%b %Y}" + (f"; no data for {', '.join(missing)}" if missing else "")


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


# ---------------- FactSet Earnings Insight ----------------

FACTSET_URL = ("https://advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/"
               "Earnings%20Insight/EarningsInsight_{d:%m%d%y}.pdf")
FACTSET_LOOKBACK_DAYS = 14
# the chart pages are images, so only the prose is parsed; these pages are kept as text for the brief
FACTSET_TEXT_PAGES = ("Key Metrics", "Earnings Revisions", "Forward Estimates & Valuation")

_NUM = r"(-?\d+(?:\.\d+)?)"
FACTSET_PATTERNS = {
    "quarter": r"For (Q\d \d{4}), the estimated \(year-over-year\) earnings growth rate",
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


def _factset_pages(pdf: bytes) -> list[str]:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf)) as p:
        return [pg.extract_text() or "" for pg in p.pages]


def update_factset() -> str | None:
    """Fetch the newest Earnings Insight PDF not seen yet; returns its date or None."""
    existing = load_factset()
    seen = set(existing["report_date"].dt.date) if not existing.empty else set()
    for back in range(FACTSET_LOOKBACK_DAYS + 1):
        d = date.today() - timedelta(days=back)
        if d in seen:
            return None  # newest report already stored
        resp = requests.get(FACTSET_URL.format(d=d), headers=UA, timeout=60)
        if resp.status_code != 200 or not resp.content.startswith(b"%PDF"):
            continue
        pages = _factset_pages(resp.content)
        row = parse_factset(pages) | {"report_date": pd.Timestamp(d)}
        df = pd.concat([existing, pd.DataFrame([row])], ignore_index=True).sort_values("report_date")
        DATA.mkdir(exist_ok=True)
        df.to_parquet(FACTSET_FILE, index=False)
        keep = [p for p in pages if any(h in p[:200] for h in FACTSET_TEXT_PAGES)]
        FACTSET_TEXT.write_text(f"FactSet Earnings Insight {d.isoformat()}\n{FACTSET_URL.format(d=d)}\n\n"
                                + "\n\n".join(keep), encoding="utf-8")
        return d.isoformat()
    return None


def load_factset() -> pd.DataFrame:
    return pd.read_parquet(FACTSET_FILE) if FACTSET_FILE.exists() else pd.DataFrame()


# ---------------- Analyst consensus (Yahoo) ----------------

ANALYST_FILE = DATA / "analyst.parquet"
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


def update_analyst(tickers: list[str], max_age_days: int = 7) -> str:
    """Append a dated consensus row per ticker whose last fetch is older than `max_age_days`.

    The history is kept so the levels can tell whether targets are being raised or cut.
    """
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor

    existing = load_analyst()
    today = pd.Timestamp(date.today())
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

    with ThreadPoolExecutor(8) as ex:
        rows = [r for r in ex.map(fetch, due) if r]
    if not rows:
        raise RuntimeError(f"no data for {len(due)} tickers")
    new = pd.DataFrame(rows)
    for col in ("current_price", "target_mean", "target_median", "target_high", "target_low", "n_analysts", "rec_mean"):
        new[col] = pd.to_numeric(new[col], errors="coerce")
    df = pd.concat([existing, new], ignore_index=True).drop_duplicates(["ticker", "fetched"], keep="last")
    DATA.mkdir(exist_ok=True)
    df.sort_values(["ticker", "fetched"]).to_parquet(ANALYST_FILE, index=False)
    return f"{len(rows)} of {len(due)} tickers refreshed"


def load_analyst() -> pd.DataFrame:
    return pd.read_parquet(ANALYST_FILE) if ANALYST_FILE.exists() else pd.DataFrame()
