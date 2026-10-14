"""Where the discovery universe comes from: Yahoo's equity screener (Nordic, European and US listings), index
members from iShares holdings files (STOXX Europe 600 via EXSA, S&P 500 via CSPX) and SKAT's positive list mapped
from ISIN to Yahoo ETF symbols.

Every source checks that it parsed a plausible number of names and raises otherwise, so a changed layout fails
loudly and the cached universe is kept (scan.py)."""
from __future__ import annotations

import csv
import io
import re
from typing import Callable

import pandas as pd

from .. import net

# Yahoo exchange code -> (symbol suffix, country, the currency a home listing reports in)
EXCHANGES = {
    "CPH": (".CO", "Denmark", {"DKK", "EUR"}), "STO": (".ST", "Sweden", {"SEK", "EUR"}),
    "OSL": (".OL", "Norway", {"NOK", "USD", "EUR"}), "HEL": (".HE", "Finland", {"EUR"}),
    "GER": (".DE", "Germany", {"EUR"}), "PAR": (".PA", "France", {"EUR"}), "AMS": (".AS", "Netherlands", {"EUR"}),
    "MIL": (".MI", "Italy", {"EUR"}), "MCE": (".MC", "Spain", {"EUR"}), "EBS": (".SW", "Switzerland", {"CHF", "EUR"}),
    "LSE": (".L", "United Kingdom", {"GBP", "GBp"}), "BRU": (".BR", "Belgium", {"EUR"}),
    "VIE": (".VI", "Austria", {"EUR"}), "LIS": (".LS", "Portugal", {"EUR"}), "ISE": (".IR", "Ireland", {"EUR"}),
    "WSE": (".WA", "Poland", {"PLN"}), "ATH": (".AT", "Greece", {"EUR"}),
    "NMS": ("", "United States", {"USD"}), "NYQ": ("", "United States", {"USD"}),
    "BTS": ("", "United States", {"USD"}),
}
SUFFIX_EXCHANGE = {v[0]: k for k, v in EXCHANGES.items() if v[0]}
EUROPEAN_CCY = {"EUR", "GBP", "CHF", "SEK", "NOK", "DKK", "PLN"}
# a company reporting in one of these currencies is at home only on these exchanges; elsewhere it is a cross-listing
CCY_HOME = {"DKK": {"CPH"}, "SEK": {"STO"}, "NOK": {"OSL"}, "CHF": {"EBS"}, "GBP": {"LSE"}, "PLN": {"WSE"}}


# ---------------- Yahoo screener ----------------

SECTORS = ["Basic Materials", "Communication Services", "Consumer Cyclical", "Consumer Defensive", "Energy",
           "Financial Services", "Healthcare", "Industrials", "Real Estate", "Technology", "Utilities"]


def screen_exchange(code: str, min_cap: float = 5e7, page: int = 250, limit: int = 4000,
                    sector: str | None = None) -> list[dict]:
    """Every equity Yahoo lists on one exchange above `min_cap` (in its own reporting units), all pages;
    optionally only one sector."""
    yf = net.yf()
    Q = yf.EquityQuery

    parts = [Q("eq", ["exchange", code]), Q("gt", ["intradaymarketcap", min_cap])]
    if sector:
        parts.append(Q("eq", ["sector", sector]))
    query = Q("and", parts)
    out, offset = [], 0
    while offset < limit:
        res = retry(lambda: yf.screen(query, size=page, offset=offset, sortField="intradaymarketcap", sortAsc=False))
        quotes = res.get("quotes", [])
        out += quotes
        offset += page
        if len(quotes) < page or offset >= res.get("total", 0):
            break
    return out


def screen_sectors(codes: list[str], min_cap: float = 5e7) -> dict[str, str]:
    """Symbol -> Yahoo sector, from one screener query per exchange and sector (a few hundred calls at most,
    instead of one profile lookup per company)."""
    out = {}
    for code in codes:
        for sec in SECTORS:
            for q in screen_exchange(code, min_cap, sector=sec):
                out[q["symbol"]] = sec
    return out


def throttled(e: Exception) -> bool:
    """Yahoo's answers to too many requests: 429, or a 401 "Invalid Crumb" once its session cookie is refused.
    A host we have paused (net.Throttled) is not worth waiting for here: its cooldown is much longer."""
    if isinstance(e, net.Throttled):
        return False
    msg = str(e).lower()
    return any(s in msg for s in ("rate limit", "too many", "429", "invalid crumb", "401"))


def retry(fn, tries: int = 4, wait: float = 20.0, sleep=None):
    """Yahoo answers bursts with "Too Many Requests": wait and try again (longer each time)."""
    import time

    sleep = sleep or time.sleep
    for n in range(tries):
        try:
            return fn()
        except Exception as e:
            if not throttled(e) or n == tries - 1:
                raise
            sleep(wait * (n + 1))


def _norm_name(name: str | None) -> str:
    n = (name or "").lower()
    n = re.sub(r"\b(ag|sa|s\.a\.|plc|nv|n\.v\.|se|asa|ab|a/s|as|spa|s\.p\.a\.|oyj|abp|ltd|limited|holding|holdings|"
               r"group|inc|corp|corporation|class [ab]|ser\. [ab]|publ|\(publ\))\b", " ", n)
    return re.sub(r"[^a-z0-9]", "", n)


def quote_row(q: dict, code: str, fx: dict[str, float]) -> dict:
    """One screener quote as a universe row (market cap converted to DKK; GBp quotes have caps in GBP)."""
    ccy = q.get("currency")
    cap = q.get("marketCap")
    rate = fx.get("GBP" if ccy == "GBp" else ccy)
    return {"ticker": q["symbol"], "name": q.get("longName") or q.get("shortName") or q["symbol"],
            "exchange": code, "country": EXCHANGES[code][1], "currency": ccy,
            "financial_currency": q.get("financialCurrency"),
            "market_cap_dkk": float(cap) * rate if cap and rate else None,
            "quote_type": q.get("quoteType")}


def home_listings(quotes: dict[str, list[dict]], fx: dict[str, float], min_cap_dkk: float,
                  keep: set[str] = frozenset()) -> pd.DataFrame:
    """Screener quotes per exchange -> one row per company, on its home exchange.

    Cross-listings are dropped: a quote must be in its exchange's currency and report in a European currency,
    and a company found on several exchanges is kept where its reporting currency is at home (else the first
    exchange in the order given). Tickers in `keep` (e.g. STOXX 600 members) skip the currency and size tests."""
    rows = []
    for order, (code, qs) in enumerate(quotes.items()):
        home_ccy = EXCHANGES[code][2]
        for q in qs:
            if q.get("quoteType") != "EQUITY" or not q.get("symbol"):
                continue
            r = quote_row(q, code, fx) | {"_order": order}
            kept = r["ticker"] in keep
            if not kept:
                fin = r["financial_currency"]
                if r["currency"] not in home_ccy or fin not in EUROPEAN_CCY or code not in CCY_HOME.get(fin, {code}):
                    continue
                if r["market_cap_dkk"] is None or r["market_cap_dkk"] < min_cap_dkk:
                    continue
            r["_home"] = r["financial_currency"] in home_ccy
            r["_kept"] = kept
            rows.append(r)
    if not rows:
        return pd.DataFrame(columns=["ticker", "name", "exchange", "country", "currency", "market_cap_dkk"])
    df = pd.DataFrame(rows)
    df["_key"] = df["name"].map(_norm_name)
    df = df.sort_values(["_kept", "_home", "market_cap_dkk", "_order"], ascending=[False, False, False, True])
    df = pd.concat([df[df["_key"] == ""], df[df["_key"] != ""].drop_duplicates("_key")])
    df = df.drop_duplicates("ticker")
    return df.drop(columns=[c for c in df.columns if c.startswith("_")] + ["financial_currency", "quote_type"])


def drop_known_names(df: pd.DataFrame, names: list[str], keep: set[str] = frozenset()) -> pd.DataFrame:
    """Rows whose company (by normalised name) is already elsewhere in the universe are dropped: a Nordic
    company's German listing doesn't belong in the Europe market. Tickers in `keep` stay."""
    known = {k for k in map(_norm_name, names) if k}
    key = df["name"].map(_norm_name)
    return df[~key.isin(known) | df["ticker"].isin(keep)]


def check_counts(df: pd.DataFrame, min_count: dict[str, int], what: str) -> None:
    """Raise when an exchange has fewer names than expected (the screener changed or returned too little)."""
    have = df["exchange"].value_counts() if not df.empty else pd.Series(dtype=int)
    short = {k: int(have.get(k, 0)) for k, n in (min_count or {}).items() if have.get(k, 0) < n}
    if short:
        raise ValueError(f"{what}: too few names from Yahoo's screener ("
                         + ", ".join(f"{k} {n} < {min_count[k]}" for k, n in short.items()) + ")")


# ---------------- index members (iShares holdings: EXSA for the STOXX Europe 600, CSPX for the S&P 500) ----------------

STOXX600_URL = ("https://www.ishares.com/de/privatanleger/de/produkte/251931/"
                "ishares-stoxx-europe-600-ucits-etf-de/latest-holdings.csv")
STOXX600_MIN = 550
SP500_URL = ("https://www.ishares.com/de/privatanleger/de/produkte/253743/"
             "ishares-core-sp-500-ucits-etf/latest-holdings.csv")
SP500_MIN = 490
# index key (discovery.yaml `index:`) -> (holdings file, fewest stocks it may hold, display name)
INDEXES = {"stoxx600": (STOXX600_URL, STOXX600_MIN, "STOXX 600"), "sp500": (SP500_URL, SP500_MIN, "S&P 500")}

# iShares' exchange names (German site) -> Yahoo exchange code
ISHARES_EXCHANGES = {
    "xetra": "GER", "deutsche börse ag": "GER", "london stock exchange": "LSE", "six swiss exchange": "EBS",
    "nyse euronext - euronext paris": "PAR", "euronext paris": "PAR", "euronext amsterdam": "AMS",
    "nyse euronext - euronext amsterdam": "AMS", "borsa italiana": "MIL", "bolsa de madrid": "MCE",
    "nyse euronext - euronext brussels": "BRU", "euronext brussels": "BRU", "wiener boerse ag": "VIE",
    "nyse euronext - euronext lisbon": "LIS", "euronext lisbon": "LIS", "irish stock exchange - all market": "ISE",
    "warsaw stock exchange/equities/main market": "WSE", "athens exchange s.a. cash market": "ATH",
    "omx nordic exchange copenhagen a/s": "CPH", "oslo bors asa": "OSL", "nasdaq omx helsinki ltd.": "HEL",
    "nasdaq omx nordic": "STO",
    "new york stock exchange inc.": "NYQ", "nasdaq": "NMS", "cboe bzx": "BTS",
}
# iShares' German GICS sector names -> Yahoo's sector names (used when Yahoo has no sector for a name)
ISHARES_SECTORS = {
    "IT": "Technology", "Finanzwesen": "Financial Services", "Gesundheitsversorgung": "Healthcare",
    "Nichtzyklische Konsumgüter": "Consumer Defensive", "Zyklische Konsumgüter": "Consumer Cyclical",
    "Industrie": "Industrials", "Energie": "Energy", "Materialien": "Basic Materials", "Versorger": "Utilities",
    "Kommunikation": "Communication Services", "Immobilien": "Real Estate",
}


def parse_holdings(text: str, min_rows: int, what: str) -> pd.DataFrame:
    """An iShares holdings CSV (German locale) -> ticker (Yahoo symbol), name, exchange, country, sector hint.
    Cash, futures and unlisted lines are skipped."""
    rows = list(csv.reader(io.StringIO(text)))
    head = next((i for i, r in enumerate(rows) if r and r[0].strip() == "Emittententicker"), None)
    if head is None:
        raise ValueError("no 'Emittententicker' header in the iShares holdings file: has the layout changed?")
    hdr = [h.strip() for h in rows[head]]
    need = {"Emittententicker", "Name", "Sektor", "Anlageklasse", "Börse"}
    if need - set(hdr):
        raise ValueError(f"iShares holdings file has no {', '.join(sorted(need - set(hdr)))} column")
    out = []
    for r in rows[head + 1:]:
        if len(r) != len(hdr):
            continue
        d = dict(zip(hdr, r))
        if d["Anlageklasse"].strip() != "Aktien":
            continue
        code = ISHARES_EXCHANGES.get(d["Börse"].strip().lower())
        if not code:
            continue
        sym = re.sub(r"[ ./]+", "-", d["Emittententicker"].strip().rstrip("."))   # "BT.A" / "INVE B" -> BT-A, INVE-B
        out.append({"ticker": sym + EXCHANGES[code][0], "name": d["Name"].strip().title(), "exchange": code,
                    "country": EXCHANGES[code][1], "sector_hint": ISHARES_SECTORS.get(d["Sektor"].strip(), "")})
    if len(out) < min_rows:
        raise ValueError(f"only {len(out)} stocks in the {what} holdings file (expected ≥ {min_rows})")
    return pd.DataFrame(out).drop_duplicates("ticker")


def parse_stoxx600(text: str, min_rows: int = STOXX600_MIN) -> pd.DataFrame:
    return parse_holdings(text, min_rows, "STOXX 600")


def parse_sp500(text: str, min_rows: int = SP500_MIN) -> pd.DataFrame:
    return parse_holdings(text, min_rows, "S&P 500")


def fetch_index(key: str) -> pd.DataFrame:
    """The members of one index in INDEXES, from its iShares holdings file."""
    url, n, what = INDEXES[key]
    resp = net.get(url, timeout=60)
    resp.raise_for_status()
    return parse_holdings(resp.content.decode("utf-8-sig", errors="replace"), n, what)


# ---------------- UCITS ETFs: SKAT's positive list -> Yahoo symbols ----------------

def positive_list_funds(pl: pd.DataFrame) -> pd.DataFrame:
    """The positive list's share classes: isin, share class name, sub-fund name (columns found by header)."""
    def col(*words):
        return next((c for c in pl.columns if any(w in str(c).lower() for w in words)), None)
    share, sub = col("andelsklasse", "shareclass"), col("afdeling", "sub-fund")
    if share is None or sub is None:
        raise ValueError("the positive list has no share-class / sub-fund name columns: has the layout changed?")
    df = pl.rename(columns={share: "share_class", sub: "sub_fund"})[["isin", "share_class", "sub_fund"]]
    return df.dropna(subset=["isin"]).drop_duplicates("isin")


def search_isin(isin: str) -> list[dict]:
    yf = net.yf()

    return yf.Search(isin, max_results=10, news_count=0).quotes


def map_isins(isins: list[str], cached: pd.DataFrame, exchanges: list[str],
              search: Callable[[str], list[dict]] = search_isin, workers: int = 2,
              progress: Callable[[int, int], None] | None = None, budget: int | None = None) -> pd.DataFrame:
    """ISIN -> best Yahoo ETF listing (exchange preference order). Looked-up ISINs are cached, unresolved ones
    too (symbol empty), so each ISIN is searched once; a failed search is not cached and retried next time.
    At most `budget` new ISINs are searched per call, so Yahoo isn't flooded; the rest follow on later scans."""
    done = set(cached["isin"]) if not cached.empty else set()
    todo = [i for i in isins if i not in done][:budget]
    rank = {e: n for n, e in enumerate(exchanges)}
    failures = [0]                    # consecutive failed searches: Yahoo is throttling, so stop for this scan

    def one(isin: str) -> dict | None:
        if failures[0] >= MAX_FAILURES:
            return None
        try:
            quotes = search(isin)
            failures[0] = 0
        except Exception:
            failures[0] += 1
            return None
        etfs = [q for q in quotes if q.get("quoteType") == "ETF" and q.get("symbol")]
        etfs.sort(key=lambda q: rank.get(q.get("exchange"), len(rank)))
        q = etfs[0] if etfs else {}
        return {"isin": isin, "symbol": q.get("symbol", ""), "exchange": q.get("exchange", ""),
                "yahoo_name": q.get("longname") or q.get("shortname") or "",
                "quote_type": "ETF" if etfs else (quotes[0].get("quoteType", "") if quotes else "")}
    found = []
    with net.pool(workers) as ex:
        for n, r in enumerate(ex.map(one, todo)):
            if r:
                found.append(r)
            if progress and n % 100 == 0:
                progress(n, len(todo))
    return pd.concat([cached, pd.DataFrame(found)], ignore_index=True) if found else cached


MAX_FAILURES = 15


HEDGED = re.compile(r"hedg|hdg|\bh\b", re.I)


def pick_share_classes(funds: pd.DataFrame, isin_map: pd.DataFrame, exchanges: list[str]) -> pd.DataFrame:
    """One ETF listing per sub-fund: unhedged before hedged, accumulating before distributing, then the
    preferred exchange."""
    rank = {e: n for n, e in enumerate(exchanges)}
    df = funds.merge(isin_map, on="isin")
    df = df[(df["quote_type"] == "ETF") & (df["symbol"].fillna("") != "")].copy()
    if df.empty:
        return df.assign(hedged=[], acc=[])
    df["hedged"] = df["share_class"].fillna("").map(lambda s: bool(HEDGED.search(s)))
    df["acc"] = df["share_class"].fillna("").str.contains(r"\bacc", case=False)
    df["_ex"] = df["exchange"].map(lambda e: rank.get(e, len(rank)))
    df = df.sort_values(["sub_fund", "hedged", "acc", "_ex"], ascending=[True, True, False, True])
    return df.drop_duplicates("sub_fund").drop_duplicates("symbol").drop(columns="_ex")


def etf_category(name: str, table: list) -> str:
    n = f" {(name or '').upper()} "
    for category, words in table:
        if any(str(w).upper() in n for w in words):
            return category
    return "Other"
