"""Valuation data: weekly snapshots of P/E and EPS estimates per stock (Yahoo's screener) and per ETF (Yahoo
fund data), and the market's valuation (Shiller CAPE via multpl.com, Damodaran's implied equity risk premium).

Snapshots are kept, one per week, so the history builds up: EPS revisions and an ETF's P/E against its own past
need it (signals/valuation.py). Yahoo mixes currencies within one quote when a company reports in another
currency than it trades in (Shell trades in pence and reports in dollars): the trailing and next-year EPS come
converted into the trading currency, this year's EPS in the reporting currency. P/E is worked out here on each
EPS's own currency (Yahoo's own this-year ratio is wrong for those names); a value that can't be right is
dropped with a note, never shown.
"""
from __future__ import annotations

import io
import math
import re
from datetime import date, datetime

import pandas as pd

from . import guard, money, net
from .config import discovery_config, typed, write_parquet
from .config_schema import Valuation as ValuationSettings
from .paths import CACHE, HISTORY
from .values import num

STOCKS_FILE = HISTORY / "valuation" / "stocks.parquet"     # weekly snapshots: history
ETFS_FILE = HISTORY / "valuation" / "etfs.parquet"
MARKET_FILE = CACHE / "valuation" / "market.parquet"        # each series replaced from its source: cache

STOCK_COLS = ["date", "ticker", "quote_type", "currency", "financial_currency", "cross_ccy", "price", "eps_ttm", "eps_cy",
              "eps_fy1", "pe_ttm", "pe_cy", "pe_fy1", "pb", "div_yield", "earnings_date", "market_cap", "note"]
ETF_COLS = ["date", "ticker", "pe", "pb", "ps", "pcf", "note"]


def _cfg() -> ValuationSettings:
    return typed().valuation


# ---------------- stocks: one row per screener quote ----------------

def price_in(price: float | None, ccy: str | None, fin: str | None, fx: dict[str, float]) -> float | None:
    """A quoted price in the company's reporting currency (`fx`: DKK per unit; GBp is pence). None when a rate
    is missing: a P/E across two currencies without the rate would be wrong by the exchange rate."""
    if price is None or not ccy:
        return None
    fin = fin or ccy
    if ccy == fin:
        return price
    base, scale = (money.main_unit(ccy), 0.01) if money.is_pence(ccy) else (ccy, 1.0)
    if base == fin:
        return price * scale
    if base not in fx or fin not in fx or not fx[fin]:
        return None
    return price * scale * fx[base] / fx[fin]


def _local_day(ts: float, zone: str | None) -> str:
    """The day a Unix timestamp falls on at the exchange (an evening report in New York is the next morning in
    Tokyo); UTC's day when the exchange's time zone isn't given or isn't known."""
    t = pd.Timestamp(ts, unit="s", tz="UTC")
    try:
        return (t.tz_convert(zone) if zone else t).date().isoformat()
    except Exception:  # an unknown zone name
        return t.date().isoformat()


def quote_valuation(q: dict, fx: dict[str, float], pe_range: tuple[float, float] = (1, 300),
                    check_estimates: bool = False) -> dict:
    """One screener quote (or a yfinance .info dict mapped to the same keys) as a snapshot row.

    Trailing and next-year EPS are taken in the trading currency (pence quotes: pounds), as Yahoo's own trailing
    and forward P/E are; this year's EPS in the reporting currency. `check_estimates` drops a next-year EPS more
    than 3× or under ⅓ of the trailing one: Yahoo's single-ticker data for some markets (Japan) mixes bases; the
    screener's doesn't, and a recovery from a small trailing EPS is real there."""
    notes: list[str] = []
    ccy = q.get("currency")
    fin = q.get("financialCurrency") or ccy
    raw = num(q.get("regularMarketPrice"))
    base = money.main_unit(ccy)
    px_trade = raw / 100 if raw is not None and money.is_pence(ccy) else raw       # in the trading currency's main unit
    px_fin = price_in(raw, ccy, fin, fx)                                      # in the reporting currency
    if raw is not None and px_fin is None:
        notes.append(f"no {ccy}→{fin} rate: this year's P/E left out")
    eps = {"ttm": num(q.get("epsTrailingTwelveMonths")), "cy": num(q.get("epsCurrentYear")),
           "fy1": num(q.get("epsForward"))}

    def pe(key: str, price: float | None) -> float | None:
        e = eps[key]
        if price is None or e is None:
            return None
        if e <= 0:
            notes.append(f"EPS {key} {e:g}: negative or zero earnings, no P/E")
            return None
        v = price / e
        if not pe_range[0] <= v <= pe_range[1]:
            notes.append(f"P/E {key} {v:.3g} outside {pe_range[0]}–{pe_range[1]}: left out")
            return None
        return v

    ttm, fy1 = eps["ttm"], eps["fy1"]
    ratio = fy1 / ttm if ttm and fy1 and ttm > 0 and fy1 > 0 else None
    inconsistent = bool(check_estimates and ratio is not None and not 1 / 3 <= ratio <= 3)
    if inconsistent:
        notes.append(f"next-year EPS is {ratio:.2g}× trailing: an inconsistent estimate, left out")
    pe_fy1 = None if inconsistent else pe("fy1", px_trade)
    pe_cy = pe("cy", px_fin)
    if pe_cy and pe_fy1 and not 1 / 3 <= pe_cy / pe_fy1 <= 3:
        notes.append(f"this year's P/E {pe_cy:.3g} vs next year's {pe_fy1:.3g}: inconsistent, left out")
        pe_cy = None
    book = num(q.get("bookValue"))                                          # reporting currency
    pb = px_fin / book if px_fin is not None and book and book > 0 else None
    if pb is not None and not 0.05 <= pb <= 100:
        notes.append(f"P/B {pb:.3g} out of range: left out")
        pb = None
    dy = num(q.get("trailingAnnualDividendYield"))       # a fraction; screener `dividendYield` is in percent
    if dy is not None and not 0 <= dy <= 0.25:
        notes.append(f"dividend yield {dy:.3g} out of range: left out")
        dy = None
    ts = num(q.get("earningsTimestamp"))
    out = {"ticker": q.get("symbol"), "quote_type": q.get("quoteType"), "currency": ccy, "financial_currency": fin,
           "cross_ccy": bool(base and fin and base != fin), "price": px_trade,
           "eps_ttm": eps["ttm"], "eps_cy": eps["cy"], "eps_fy1": eps["fy1"],
           "pe_ttm": pe("ttm", px_trade), "pe_cy": pe_cy, "pe_fy1": pe_fy1, "pb": pb, "div_yield": dy,
           "earnings_date": _local_day(ts, q.get("exchangeTimezoneName")) if ts else None,
           "market_cap": num(q.get("marketCap"))}       # Yahoo's, in the trading currency (a check on ours)
    yahoo = num(q.get("forwardPE"))
    if pe_fy1 and yahoo and abs(yahoo / pe_fy1 - 1) > 0.05:
        notes.append(f"Yahoo's own forward P/E is {yahoo:.1f}")
    return out | {"note": "; ".join(notes) or None}


def info_as_quote(symbol: str, info: dict) -> dict:
    """yfinance .info → the screener's key names (for the stocks the screens miss)."""
    return {"symbol": symbol, "quoteType": info.get("quoteType"), "currency": info.get("currency"),
            "financialCurrency": info.get("financialCurrency"),
            "regularMarketPrice": info.get("regularMarketPrice") or info.get("currentPrice"),
            "epsTrailingTwelveMonths": info.get("trailingEps"), "epsCurrentYear": info.get("epsCurrentYear"),
            "epsForward": info.get("forwardEps"), "bookValue": info.get("bookValue"),
            "trailingAnnualDividendYield": info.get("trailingAnnualDividendYield"),
            "earningsTimestamp": info.get("earningsTimestamp"), "forwardPE": info.get("forwardPE"),
            "exchangeTimezoneName": info.get("exchangeTimezoneName"), "marketCap": info.get("marketCap")}


def screen_codes() -> dict[str, dict]:
    """Exchange code → min_cap and min_count, from discovery.yaml (markets + valuation.us)."""
    dc = discovery_config()
    out = {}
    for mk in dc["markets"].values():
        for code in mk.get("exchanges", []):
            out[code] = {"min_cap": 5e7, "min_count": max(10, int((mk.get("min_count") or {}).get(code, 10)))}
    us = dc["valuation"]["us"]
    for code in us["exchanges"]:
        out[code] = {"min_cap": us["min_cap"], "min_count": us["min_count"].get(code, 10)}
    return out


def snapshot_due(path, days: int, today: date | None = None) -> tuple[bool, pd.DataFrame]:
    old = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    if old.empty:
        return True, old
    last = pd.to_datetime(old["date"]).max().date()
    return ((today or date.today()) - last).days >= days, old


def store_snapshot(path, old: pd.DataFrame, new: pd.DataFrame, today: date | None = None) -> int:
    """Add today's snapshot; one per ISO week (a second run in the same week replaces it). Names the replaced
    run had and this one missed are carried into it, with a note, rather than dropped from the week. Returns how
    many were carried."""
    today = pd.Timestamp(today or date.today())
    new = new.assign(date=today)
    carried = pd.DataFrame()
    if not old.empty:
        d = pd.to_datetime(old["date"])
        week = lambda s: s.dt.isocalendar().year * 100 + s.dt.isocalendar().week  # noqa: E731
        same = week(d) == (today.isocalendar().year * 100 + today.isocalendar().week)
        replaced = old[same]
        carried = replaced[~replaced["ticker"].isin(set(new["ticker"]))].drop_duplicates("ticker", keep="last")
        if not carried.empty:
            note = "carried from " + pd.to_datetime(carried["date"]).dt.strftime("%d %b")
            carried = carried.assign(date=today, note=[f"{n}; {c}" if isinstance(n, str) and n else c
                                                       for n, c in zip(carried["note"], note)])
        old = old[~same]
    parts = [x for x in (old, new, carried) if not x.empty]
    write_parquet(pd.concat(parts, ignore_index=True), path, index=False)
    return len(carried)


def update_stocks(stocks: list[str], force: bool = False, today: date | None = None) -> str:
    """The weekly stock snapshot: Yahoo's screener per exchange, then one-by-one lookups for the tracked `stocks`
    it missed. An exchange returning fewer names than expected raises (the last snapshot stays)."""
    from .discovery import scan, sources

    cfg = _cfg()
    due, old = snapshot_due(STOCKS_FILE, cfg.snapshot_days, today)
    if not due and not force:
        return f"up to date (snapshot of {pd.to_datetime(old['date']).max():%d %b})"
    fx = scan.fx_rates()
    rng = cfg.pe_range
    rows: dict = {}
    short: list = []
    for code, c in screen_codes().items():
        qs = [q for q in sources.screen_exchange(code, min_cap=c["min_cap"]) if q.get("quoteType") == "EQUITY"]
        if len(qs) < c["min_count"]:
            short.append(f"{code} {len(qs)} < {c['min_count']}")
        for q in qs:
            rows.setdefault(q["symbol"], quote_valuation(q, fx, rng))
    if short:
        raise ValueError("too few names from Yahoo's screener (" + ", ".join(short) + "): keeping the last snapshot")
    missing = [t for t in stocks if t not in rows][: cfg.fallback_max]
    looked, failed = look_up(missing, fx, rng, rows)
    df = pd.DataFrame(list(rows.values())).reindex(columns=STOCK_COLS)
    carried = store_snapshot(STOCKS_FILE, old, df, today)
    have = sum(t in rows for t in stocks)
    with_pe = df["pe_fy1"].notna().sum()
    return (f"{len(df):,} names, {with_pe:,} with a forward P/E; {have} of {len(stocks)} tracked stocks"
            f" ({looked} looked up one by one" + (f", {len(failed)} lookups failed" if failed else "") + ")"
            + (f"; {carried} carried from this week's earlier snapshot" if carried else ""))


def look_up(tickers: list[str], fx: dict, rng: tuple, rows: dict) -> tuple[int, list[str]]:
    """Look up names the screener missed, one by one: (how many were added, the ones whose lookup failed)."""
    import logging

    yf = net.yf()

    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    n, failed = 0, []
    for t in tickers:
        try:
            info = yf.Ticker(t).info or {}
        except Exception:
            failed.append(t)
            continue
        if info.get("quoteType") == "EQUITY":
            rows[t] = quote_valuation(info_as_quote(t, info), fx, rng, check_estimates=True)
            n += 1
    return n, failed


# ---------------- ETFs: Yahoo fund data ----------------

FUND_KEYS = {"Price/Earnings": "pe", "Price/Book": "pb", "Price/Sales": "ps", "Price/Cashflow": "pcf"}


def fund_valuation(holdings: dict, pe_range: tuple[float, float] = (3, 150)) -> dict:
    """yfinance funds_data.equity_holdings → multiples. Yahoo stores them inverted (earnings yield, book yield
    …: 0.0313 for a fund on 32× earnings), so each is turned around; 0 or out of range means unknown."""
    ranges = {"pe": pe_range, "pb": (0.2, 50), "ps": (0.1, 50), "pcf": (1, 200)}
    out: dict[str, float | None] = {}
    notes: list[str] = []
    for label, key in FUND_KEYS.items():
        v = num(holdings.get(label))
        if v is None or v <= 0:
            out[key] = None
            continue
        m = 1 / v
        lo, hi = ranges[key]
        if not lo <= m <= hi:
            notes.append(f"{label} {m:.3g} outside {lo}–{hi}: left out")
            out[key] = None
            continue
        out[key] = m
    return out | {"note": "; ".join(notes) or None}


def update_etfs(tickers: list[str], force: bool = False, today: date | None = None) -> str:
    """The weekly fund snapshot (Yahoo fund data) for `tickers`; stocks among them are skipped."""
    import logging

    yf = net.yf()

    cfg = _cfg()
    due, old = snapshot_due(ETFS_FILE, cfg.snapshot_days, today)
    if not due and not force:
        return f"up to date (snapshot of {pd.to_datetime(old['date']).max():%d %b})"
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    rows = []
    for t in tickers:
        try:
            eh = yf.Ticker(t).funds_data.equity_holdings
        except Exception:
            continue  # not a fund, or Yahoo has no fund data for it
        if eh is None or eh.empty:
            continue
        rows.append({"ticker": t} | fund_valuation(eh.iloc[:, 0].to_dict(), cfg.fund_pe_range))
    if not rows:
        raise ValueError(f"no fund data for any of {len(tickers)} ETFs: has Yahoo changed?")
    prev = set(latest(old).index) & set(tickers) if not old.empty else set()
    need = math.ceil(cfg.etf_min_share * len(prev))
    if len(rows) < need:   # a thin answer (throttled, Yahoo trouble) would replace a fuller snapshot
        raise ValueError(f"fund data for only {len(rows)} of {len(tickers)} ETFs (the last snapshot had {len(prev)}): "
                         "keeping the last snapshot")
    df = pd.DataFrame(rows).reindex(columns=ETF_COLS)
    carried = store_snapshot(ETFS_FILE, old, df, today)
    return (f"{len(df)} of {len(tickers)} ETFs, {df['pe'].notna().sum()} with a P/E"
            + (f"; {carried} carried from this week's earlier snapshot" if carried else ""))


# ---------------- the market: CAPE and the equity risk premium ----------------

MULTPL_URL = "https://www.multpl.com/shiller-pe/table/by-month"
DAMODARAN_URL = "https://pages.stern.nyu.edu/~adamodar/pc/implprem/ERPbymonth.xlsx"


def parse_multpl(html: str, min_rows: int = 1000) -> pd.Series:
    """multpl.com's monthly Shiller CAPE table (newest first; the first row is today's estimate)."""
    rows = re.findall(r"<td>\s*([A-Z][a-z]{2} \d{1,2}, \d{4})\s*</td>\s*<td>\s*(?:&#x2002;|&ensp;)?\s*([\d.]+)", html)
    if len(rows) < min_rows:
        raise ValueError(f"only {len(rows)} CAPE rows on multpl.com: has the page changed?")
    s = pd.Series({pd.Timestamp(datetime.strptime(d, "%b %d, %Y")): float(v) for d, v in rows}).sort_index()
    return s[~s.index.duplicated(keep="last")]


def parse_damodaran(content: bytes, min_rows: int = 100) -> pd.DataFrame:
    """Damodaran's ERPbymonth.xlsx, sheet "Historical ERP": the implied ERP on trailing-12-month cash flows (his
    headline number) and the T-bond rate, monthly."""
    raw = pd.read_excel(io.BytesIO(content), sheet_name="Historical ERP", header=None)
    head = [str(v).strip() for v in raw.iloc[0]]
    need: dict[str, int] = {}
    for k in ("Start of month", "ERP (T12m)", "T.Bond Rate"):
        if k not in head:
            raise ValueError(f"Damodaran's sheet has no {k!r} column: has the file changed?")
        need[k] = head.index(k)
    df = pd.DataFrame({"date": pd.to_datetime(raw.iloc[1:, need["Start of month"]], errors="coerce"),
                       "erp": pd.to_numeric(raw.iloc[1:, need["ERP (T12m)"]], errors="coerce"),
                       "tbond": pd.to_numeric(raw.iloc[1:, need["T.Bond Rate"]], errors="coerce")}).dropna(subset=["date", "erp"])
    if len(df) < min_rows:
        raise ValueError(f"only {len(df)} monthly ERP rows: has the file changed?")
    if not df["erp"].between(-0.05, 0.2).all():
        raise ValueError("ERP values outside -5%…20%: a unit change in the file?")
    return df.sort_values("date").reset_index(drop=True)


def market_merge(series: dict[str, pd.Series]) -> None:
    """Replace these series in the market file, each checked against its stored copy first (guard: not ending
    earlier, starting later or markedly shorter); nothing is written unless all pass."""
    old = load_market()
    df = old
    for name, s in series.items():
        new = pd.DataFrame({"date": s.index, "series": name, "value": s.values})
        stored = old[old["series"] == name][["date", "value"]] if not old.empty else None
        guard.check(stored, new[["date", "value"]], what=name.upper(), key=None, date="date", row_tol=0.02)
        df = pd.concat([df[df["series"] != name], new], ignore_index=True) if not df.empty else new
    write_parquet(df.sort_values(["series", "date"]), MARKET_FILE, index=False)


def update_cape() -> str:
    resp = net.get(MULTPL_URL, timeout=60)
    resp.raise_for_status()
    s = parse_multpl(resp.text)
    market_merge({"cape": s})
    return f"{len(s):,} months since {s.index[0]:%Y}; {s.iloc[-1]:.1f} on {s.index[-1]:%d %b %Y}"


def update_erp() -> str:
    resp = net.get(DAMODARAN_URL, timeout=60)
    resp.raise_for_status()
    df = parse_damodaran(resp.content)
    market_merge({"erp": df.set_index("date")["erp"], "tbond": df.set_index("date")["tbond"]})
    last = df.iloc[-1]
    return f"{len(df)} months; {last['erp']:.2%} on {last['date']:%b %Y}"


# ---------------- reading ----------------

def load_stocks() -> pd.DataFrame:
    return pd.read_parquet(STOCKS_FILE) if STOCKS_FILE.exists() else pd.DataFrame(columns=STOCK_COLS)


def load_etfs() -> pd.DataFrame:
    return pd.read_parquet(ETFS_FILE) if ETFS_FILE.exists() else pd.DataFrame(columns=ETF_COLS)


def load_market() -> pd.DataFrame:
    return pd.read_parquet(MARKET_FILE) if MARKET_FILE.exists() else pd.DataFrame(columns=["date", "series", "value"])


def market_series(name: str, df: pd.DataFrame | None = None) -> pd.Series:
    df = load_market() if df is None else df
    s = df[df["series"] == name]
    return pd.Series(s["value"].values, index=pd.to_datetime(s["date"])).sort_index() if not s.empty else pd.Series(dtype=float)


def latest(df: pd.DataFrame) -> pd.DataFrame:
    """The newest snapshot's rows, indexed by ticker."""
    if df.empty:
        return df.set_index("ticker") if "ticker" in df else df
    d = pd.to_datetime(df["date"])
    return df[d == d.max()].drop_duplicates("ticker", keep="last").set_index("ticker")


def snapshot_dates(df: pd.DataFrame) -> list[pd.Timestamp]:
    return sorted(pd.to_datetime(df["date"]).unique()) if not df.empty else []



# ---------------- the readings per ticker, for every table ----------------

REVISION_WEEKS = (4, 12)  # the windows behind eps_rev_4w / eps_rev_12w


class Context:
    """The latest snapshot with each stock's P/E against its sector and its EPS revisions, built once per report
    or request. Peers are the stock's radar group (Momentum, holdings) or its Discover market; sectors come from
    the cached lookups only (no network)."""

    def __init__(self, hist: pd.DataFrame | None = None, etf_hist: pd.DataFrame | None = None):
        from . import tracked
        from .discovery import scan
        from .signals import valuation as sv

        cfg = _cfg()
        hist = load_stocks() if hist is None else hist
        etf_hist = load_etfs() if etf_hist is None else etf_hist
        self.weeks = sv.history_weeks(hist)
        self.asof = pd.to_datetime(hist["date"]).max().date().isoformat() if not hist.empty else None
        self.now = latest(hist)
        sec_file = CACHE / "sectors.csv"
        sectors = (pd.read_csv(sec_file, keep_default_na=False).set_index("ticker")["sector"].to_dict()
                   if sec_file.exists() else {})
        self.radar_group = {t: g for g, ts in tracked.stock_groups(offline=True).items() for t in ts}
        disc = scan.load_universe()
        disc = disc[disc["kind"] == "stock"] if not disc.empty else disc
        self.disc_group = dict(zip(disc["ticker"], disc["market"])) if not disc.empty else {}
        disc_sector = {t: s for t, s in zip(disc["ticker"], disc["sector"]) if s} if not disc.empty else {}
        self.sector = disc_sector | {t: s for t, s in sectors.items() if s}
        mp = cfg.min_peers
        self.rel = {"radar": sv.vs_sector(self.now, self.radar_group, self.sector, mp) if not self.now.empty else pd.Series(dtype=object),
                    "disc": sv.vs_sector(self.now, self.disc_group, self.sector, mp) if not self.now.empty else pd.Series(dtype=object)}
        self.rev, self.rev_base = {}, {}
        for w in REVISION_WEEKS:
            self.rev[w], self.rev_base[w] = sv.revisions(hist, w)
        self.etf = sv.etf_rows(etf_hist, tracked.benchmark(), cfg.etf_history_weeks)
        self.etf_asof = pd.to_datetime(etf_hist["date"]).max().date().isoformat() if not etf_hist.empty else None
        self.band = cfg.revision_band

    def stock(self, t: str, peers: str = "radar") -> dict:
        """The valuation fields of one stock (all None when it isn't in the snapshot)."""
        from .signals import gauges as gz

        r = self.now.loc[t] if t in self.now.index else None
        get = (lambda k: num(r[k]) if r is not None else None)
        rel = self.rel[peers].get(t)
        rel = num(rel)
        out = {"pe_fy1": get("pe_fy1"), "pe_cy": get("pe_cy"), "pe_ttm": get("pe_ttm"), "pb": get("pb"),
               "div_yield": get("div_yield"), "pe_vs_sector": rel,
               "eps_rev_4w": num(self.rev[4].get(t)), "eps_rev_12w": num(self.rev[12].get(t)),
               "earnings_date": (r["earnings_date"] if r is not None and isinstance(r["earnings_date"], str) else None)}
        gauges = {"pe_vs_sector": gz.gauge("pe_vs_sector", rel), "eps_rev": gz.gauge("eps_rev", out["eps_rev_4w"])}
        return out | {"val_gauges": {k: g for k, g in gauges.items() if g}}

    def fund(self, t: str) -> dict:
        from .signals import gauges as gz

        e = self.etf.get(t) or {}
        g = {"pe_vs_acwi": gz.gauge("pe_vs_acwi", e.get("pe_vs_acwi")), "pe_pct": gz.gauge("pe_pct", e.get("pe_pct"))}
        return {"pe": e.get("pe"), "pe_vs_acwi": e.get("pe_vs_acwi"), "pe_pct": e.get("pe_pct"),
                "val_gauges": {k: v for k, v in g.items() if v}}

    def breadth(self) -> dict:
        """EPS-revision breadth per radar region and per Discover market, for each comparison window."""
        from . import tracked
        from .signals import valuation as sv

        labels = tracked.stock_group_labels()
        dmarkets = {k: m["label"] for k, m in discovery_config()["markets"].items()}
        out: dict = {"weeks_stored": self.weeks, "asof": self.asof, "windows": []}
        for w, rev in self.rev.items():
            if rev.empty:
                out["windows"].append({"weeks": w, "base": None, "rows": []})
                continue
            rows = [r | {"scope": "radar", "label": labels.get(r["group"], r["group"])}
                    for r in sv.breadth(rev, self.radar_group, self.band)]
            rows += [r | {"scope": "discover", "label": f"{dmarkets.get(r['group'], r['group'])} (Discover)"}
                     for r in sv.breadth(rev, self.disc_group, self.band)]
            base = self.rev_base[w]
            out["windows"].append({"weeks": w, "base": base.date().isoformat() if base is not None else None, "rows": rows})
        return out


_ctx: tuple[tuple, Context] | None = None


def reset() -> None:
    """Forget the cached valuation context (context() builds it again)."""
    global _ctx
    _ctx = None


def context() -> Context:
    """A Context, rebuilt when a snapshot or the Discover universe changes (for the API)."""
    global _ctx
    from .discovery import scan

    key = tuple(f.stat().st_mtime if f.exists() else 0 for f in (STOCKS_FILE, ETFS_FILE, scan.UNIVERSE_FILE))
    if _ctx is None or _ctx[0] != key:
        _ctx = (key, Context())
    return _ctx[1]
