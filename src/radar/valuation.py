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
from datetime import date, datetime, timezone

import pandas as pd

from . import net
from .config import DATA, discovery_config, settings, write_parquet

DIR = DATA / "valuation"
STOCKS_FILE = DIR / "stocks.parquet"
ETFS_FILE = DIR / "etfs.parquet"
MARKET_FILE = DIR / "market.parquet"

STOCK_COLS = ["date", "ticker", "quote_type", "currency", "financial_currency", "cross_ccy", "price", "eps_ttm", "eps_cy",
              "eps_fy1", "pe_ttm", "pe_cy", "pe_fy1", "pb", "div_yield", "earnings_date", "note"]
ETF_COLS = ["date", "ticker", "pe", "pb", "ps", "pcf", "note"]


def _cfg() -> dict:
    return settings()["valuation"]


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


# ---------------- stocks: one row per screener quote ----------------

def price_in(price: float | None, ccy: str | None, fin: str | None, fx: dict[str, float]) -> float | None:
    """A quoted price in the company's reporting currency (`fx`: DKK per unit; GBp is pence). None when a rate
    is missing: a P/E across two currencies without the rate would be wrong by the exchange rate."""
    if price is None or not ccy:
        return None
    fin = fin or ccy
    if ccy == fin:
        return price
    base, scale = ("GBP", 0.01) if ccy == "GBp" else (ccy, 1.0)
    if base == fin:
        return price * scale
    if base not in fx or fin not in fx or not fx[fin]:
        return None
    return price * scale * fx[base] / fx[fin]


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
    raw = _num(q.get("regularMarketPrice"))
    base = "GBP" if ccy == "GBp" else ccy
    px_trade = raw / 100 if raw is not None and ccy == "GBp" else raw       # in the trading currency's main unit
    px_fin = price_in(raw, ccy, fin, fx)                                      # in the reporting currency
    if raw is not None and px_fin is None:
        notes.append(f"no {ccy}→{fin} rate: this year's P/E left out")
    eps = {"ttm": _num(q.get("epsTrailingTwelveMonths")), "cy": _num(q.get("epsCurrentYear")),
           "fy1": _num(q.get("epsForward"))}

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
    inconsistent = bool(check_estimates and ttm and fy1 and ttm > 0 and fy1 > 0 and not 1 / 3 <= fy1 / ttm <= 3)
    if inconsistent:
        notes.append(f"next-year EPS is {fy1 / ttm:.2g}× trailing: an inconsistent estimate, left out")
    pe_fy1 = None if inconsistent else pe("fy1", px_trade)
    pe_cy = pe("cy", px_fin)
    if pe_cy and pe_fy1 and not 1 / 3 <= pe_cy / pe_fy1 <= 3:
        notes.append(f"this year's P/E {pe_cy:.3g} vs next year's {pe_fy1:.3g}: inconsistent, left out")
        pe_cy = None
    book = _num(q.get("bookValue"))                                          # reporting currency
    pb = px_fin / book if px_fin is not None and book and book > 0 else None
    if pb is not None and not 0.05 <= pb <= 100:
        notes.append(f"P/B {pb:.3g} out of range: left out")
        pb = None
    dy = _num(q.get("trailingAnnualDividendYield"))       # a fraction; screener `dividendYield` is in percent
    if dy is not None and not 0 <= dy <= 0.25:
        notes.append(f"dividend yield {dy:.3g} out of range: left out")
        dy = None
    ts = _num(q.get("earningsTimestamp"))
    out = {"ticker": q.get("symbol"), "quote_type": q.get("quoteType"), "currency": ccy, "financial_currency": fin,
           "cross_ccy": bool(base and fin and base != fin), "price": px_trade,
           "eps_ttm": eps["ttm"], "eps_cy": eps["cy"], "eps_fy1": eps["fy1"],
           "pe_ttm": pe("ttm", px_trade), "pe_cy": pe_cy, "pe_fy1": pe_fy1, "pb": pb, "div_yield": dy,
           "earnings_date": datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat() if ts else None}
    yahoo = _num(q.get("forwardPE"))
    if out["pe_fy1"] and yahoo and abs(yahoo / out["pe_fy1"] - 1) > 0.05:
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
            "earningsTimestamp": info.get("earningsTimestamp"), "forwardPE": info.get("forwardPE")}


def _screen_codes() -> dict[str, dict]:
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


def _snapshot_due(path, days: int) -> tuple[bool, pd.DataFrame]:
    old = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    if old.empty:
        return True, old
    last = pd.to_datetime(old["date"]).max().date()
    return (date.today() - last).days >= days, old


def _store(path, old: pd.DataFrame, new: pd.DataFrame) -> None:
    """Add today's snapshot; one per ISO week (a second run in the same week replaces it)."""
    today = pd.Timestamp(date.today())
    if not old.empty:
        d = pd.to_datetime(old["date"])
        week = lambda s: s.dt.isocalendar().year * 100 + s.dt.isocalendar().week  # noqa: E731
        old = old[week(d) != (today.isocalendar().year * 100 + today.isocalendar().week)]
    new = new.assign(date=today)
    DIR.mkdir(parents=True, exist_ok=True)
    write_parquet(pd.concat([old, new], ignore_index=True) if not old.empty else new, path, index=False)


def tracked_stocks() -> list[str]:
    from . import universe

    names = {t for g in universe.stock_groups(offline=True).values() for t in g}
    h = universe.holdings()
    if not h.empty:
        names |= set(h.loc[h["status"].isin(["holding", "watch"]), "symbol"].dropna())
    etfs = {i.ticker for i in universe.etfs()} | {universe.benchmark()}
    return sorted(names - etfs)


def update_stocks(force: bool = False) -> str:
    """The weekly stock snapshot: Yahoo's screener per exchange, then one-by-one lookups for tracked names it
    missed. An exchange returning fewer names than expected raises (the last snapshot stays)."""
    from .discovery import scan, sources

    cfg = _cfg()
    due, old = _snapshot_due(STOCKS_FILE, cfg["snapshot_days"])
    if not due and not force:
        return f"up to date (snapshot of {pd.to_datetime(old['date']).max():%d %b})"
    fx = scan.fx_rates()
    rng = tuple(cfg["pe_range"])
    rows, short = {}, []
    for code, c in _screen_codes().items():
        qs = [q for q in sources.screen_exchange(code, min_cap=c["min_cap"]) if q.get("quoteType") == "EQUITY"]
        if len(qs) < c["min_count"]:
            short.append(f"{code} {len(qs)} < {c['min_count']}")
        for q in qs:
            rows.setdefault(q["symbol"], quote_valuation(q, fx, rng))
    if short:
        raise ValueError("too few names from Yahoo's screener (" + ", ".join(short) + "): keeping the last snapshot")
    missing = [t for t in tracked_stocks() if t not in rows][: cfg["fallback_max"]]
    looked = _lookups(missing, fx, rng, rows)
    df = pd.DataFrame(list(rows.values())).reindex(columns=STOCK_COLS)
    _store(STOCKS_FILE, old, df)
    have = sum(t in rows for t in tracked_stocks())
    with_pe = df["pe_fy1"].notna().sum()
    return (f"{len(df):,} names, {with_pe:,} with a forward P/E; {have} of {len(tracked_stocks())} tracked stocks"
            f" ({looked} looked up one by one)")


def _lookups(tickers: list[str], fx: dict, rng: tuple, rows: dict) -> int:
    import logging

    yf = net.yf()

    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    n = 0
    for t in tickers:
        try:
            info = yf.Ticker(t).info or {}
        except Exception:
            continue
        if info.get("quoteType") == "EQUITY":
            rows[t] = quote_valuation(info_as_quote(t, info), fx, rng, check_estimates=True)
            n += 1
    return n


# ---------------- ETFs: Yahoo fund data ----------------

FUND_KEYS = {"Price/Earnings": "pe", "Price/Book": "pb", "Price/Sales": "ps", "Price/Cashflow": "pcf"}


def fund_valuation(holdings: dict, pe_range: tuple[float, float] = (3, 150)) -> dict:
    """yfinance funds_data.equity_holdings → multiples. Yahoo stores them inverted (earnings yield, book yield
    …: 0.0313 for a fund on 32× earnings), so each is turned around; 0 or out of range means unknown."""
    ranges = {"pe": pe_range, "pb": (0.2, 50), "ps": (0.1, 50), "pcf": (1, 200)}
    out, notes = {}, []
    for label, key in FUND_KEYS.items():
        v = _num(holdings.get(label))
        if v is None or v <= 0:
            out[key] = None
            continue
        m = 1 / v
        lo, hi = ranges[key]
        if not lo <= m <= hi:
            notes.append(f"{label} {m:.3g} outside {lo}–{hi}: left out")
            m = None
        out[key] = m
    return out | {"note": "; ".join(notes) or None}


def etf_tickers() -> list[str]:
    from . import universe

    out = {i.ticker for i in universe.etfs()} | {universe.benchmark()}
    out |= {b["ticker"] for b in universe.group_benchmarks().values()}
    h = universe.holdings()
    stocks = {t for g in universe.stock_groups(offline=True).values() for t in g}
    if not h.empty:  # held or watched funds; stocks among them are skipped by the lookup
        out |= set(h.loc[h["status"].isin(["holding", "watch"]), "symbol"].dropna()) - stocks
    return sorted(out)


def update_etfs(force: bool = False) -> str:
    import logging

    yf = net.yf()

    cfg = _cfg()
    due, old = _snapshot_due(ETFS_FILE, cfg["snapshot_days"])
    if not due and not force:
        return f"up to date (snapshot of {pd.to_datetime(old['date']).max():%d %b})"
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    tickers = etf_tickers()
    rows = []
    for t in tickers:
        try:
            eh = yf.Ticker(t).funds_data.equity_holdings
        except Exception:
            continue  # not a fund, or Yahoo has no fund data for it
        if eh is None or eh.empty:
            continue
        rows.append({"ticker": t} | fund_valuation(eh.iloc[:, 0].to_dict(), tuple(cfg["fund_pe_range"])))
    if not rows:
        raise ValueError(f"no fund data for any of {len(tickers)} ETFs: has Yahoo changed?")
    df = pd.DataFrame(rows).reindex(columns=ETF_COLS)
    _store(ETFS_FILE, old, df)
    return f"{len(df)} of {len(tickers)} ETFs, {df['pe'].notna().sum()} with a P/E"


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
    need = {"Start of month": None, "ERP (T12m)": None, "T.Bond Rate": None}
    for k in need:
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


def _market_merge(name: str, s: pd.Series) -> None:
    old = load_market()
    new = pd.DataFrame({"date": s.index, "series": name, "value": s.values})
    df = pd.concat([old[old["series"] != name], new], ignore_index=True) if not old.empty else new
    DIR.mkdir(parents=True, exist_ok=True)
    write_parquet(df.sort_values(["series", "date"]), MARKET_FILE, index=False)


def update_cape() -> str:
    resp = net.get(MULTPL_URL, timeout=60)
    resp.raise_for_status()
    s = parse_multpl(resp.text)
    _market_merge("cape", s)
    return f"{len(s):,} months since {s.index[0]:%Y}; {s.iloc[-1]:.1f} on {s.index[-1]:%d %b %Y}"


def update_erp() -> str:
    resp = net.get(DAMODARAN_URL, timeout=60)
    resp.raise_for_status()
    df = parse_damodaran(resp.content)
    _market_merge("erp", df.set_index("date")["erp"])
    _market_merge("tbond", df.set_index("date")["tbond"])
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
        from . import universe
        from .discovery import scan
        from .signals import valuation as sv

        cfg = _cfg()
        hist = load_stocks() if hist is None else hist
        etf_hist = load_etfs() if etf_hist is None else etf_hist
        self.weeks = sv.history_weeks(hist)
        self.asof = pd.to_datetime(hist["date"]).max().date().isoformat() if not hist.empty else None
        self.now = latest(hist)
        sec_file = DATA / "sectors.csv"
        sectors = (pd.read_csv(sec_file, keep_default_na=False).set_index("ticker")["sector"].to_dict()
                   if sec_file.exists() else {})
        self.radar_group = {t: g for g, ts in universe.stock_groups(offline=True).items() for t in ts}
        disc = scan.load_universe()
        disc = disc[disc["kind"] == "stock"] if not disc.empty else disc
        self.disc_group = dict(zip(disc["ticker"], disc["market"])) if not disc.empty else {}
        disc_sector = {t: s for t, s in zip(disc["ticker"], disc["sector"]) if s} if not disc.empty else {}
        self.sector = disc_sector | {t: s for t, s in sectors.items() if s}
        mp = cfg["min_peers"]
        self.rel = {"radar": sv.vs_sector(self.now, self.radar_group, self.sector, mp) if not self.now.empty else pd.Series(dtype=object),
                    "disc": sv.vs_sector(self.now, self.disc_group, self.sector, mp) if not self.now.empty else pd.Series(dtype=object)}
        self.rev, self.rev_base = {}, {}
        for w in REVISION_WEEKS:
            self.rev[w], self.rev_base[w] = sv.revisions(hist, w)
        self.etf = sv.etf_rows(etf_hist, universe.benchmark(), cfg["etf_history_weeks"])
        self.etf_asof = pd.to_datetime(etf_hist["date"]).max().date().isoformat() if not etf_hist.empty else None
        self.band = cfg["revision_band"]

    def stock(self, t: str, peers: str = "radar") -> dict:
        """The valuation fields of one stock (all None when it isn't in the snapshot)."""
        from .signals import gauges as gz

        r = self.now.loc[t] if t in self.now.index else None
        get = (lambda k: _num(r[k]) if r is not None else None)
        rel = self.rel[peers].get(t)
        rel = _num(rel)
        out = {"pe_fy1": get("pe_fy1"), "pe_cy": get("pe_cy"), "pe_ttm": get("pe_ttm"), "pb": get("pb"),
               "div_yield": get("div_yield"), "pe_vs_sector": rel,
               "eps_rev_4w": _num(self.rev[4].get(t)), "eps_rev_12w": _num(self.rev[12].get(t)),
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
        from . import universe
        from .signals import valuation as sv

        labels = universe.stock_group_labels()
        dmarkets = {k: m["label"] for k, m in discovery_config()["markets"].items()}
        out = {"weeks_stored": self.weeks, "asof": self.asof, "windows": []}
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


def context() -> Context:
    """A Context, rebuilt when a snapshot or the Discover universe changes (for the API)."""
    global _ctx
    from .discovery import scan

    key = tuple(f.stat().st_mtime if f.exists() else 0 for f in (STOCKS_FILE, ETFS_FILE, scan.UNIVERSE_FILE))
    if _ctx is None or _ctx[0] != key:
        _ctx = (key, Context())
    return _ctx[1]
