"""Everything the radar tracks: ETFs, stock lists, macro tickers, holdings."""
from __future__ import annotations

import io
import re
import time
from dataclasses import dataclass

import pandas as pd
import requests

from .config import DATA, HOLDINGS_FILE, POSITIVE_LIST_FILE, TRANSACTIONS_FILE, settings, universe_config

UA = {"User-Agent": "Mozilla/5.0 (market-radar personal research script)"}
# State Street publishes SPY's full holdings daily – an official S&P 500 constituent list.
SPY_HOLDINGS = ("https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/"
                "etfs/us/holdings-daily-us-en-spy.xlsx")


@dataclass(frozen=True)
class Instrument:
    ticker: str
    name: str
    group: str
    region: str
    ucits: str | None = None
    isin: str | None = None
    ucits_name: str | None = None


def benchmark() -> str:
    return universe_config()["benchmark"]["ticker"]


def etfs() -> list[Instrument]:
    out = []
    for key, g in universe_config()["etf_groups"].items():
        for it in g["items"]:
            out.append(Instrument(it["ticker"], it["name"], key, g["region"], it.get("ucits"), it.get("isin"),
                                  it.get("ucits_name")))
    return out


def group_benchmarks() -> dict[str, dict]:
    """ETF groups with a home-market benchmark (key -> {ticker, name}), used for an extra RRG."""
    return {k: g["benchmark"] for k, g in universe_config()["etf_groups"].items() if g.get("benchmark")}


SPY_MIN_HOLDINGS = 450  # fewer means the file layout changed; the cached list is kept instead


def _spy_holdings() -> pd.DataFrame:
    resp = requests.get(SPY_HOLDINGS, headers=UA, timeout=60)
    resp.raise_for_status()
    return parse_spy_holdings(resp.content)


def parse_spy_holdings(content: bytes, min_holdings: int = SPY_MIN_HOLDINGS) -> pd.DataFrame:
    """SSGA's daily SPY holdings xlsx → ticker, name (US stocks only; cash and futures rows dropped)."""
    df = pd.read_excel(io.BytesIO(content), skiprows=4)
    missing = {"Ticker", "Name", "Weight", "Local Currency"} - set(df.columns)
    if missing:
        raise ValueError(f"SPY holdings file has no {', '.join(sorted(missing))} column: has the layout changed?")
    df = df[pd.to_numeric(df["Weight"], errors="coerce").notna() & (df["Local Currency"] == "USD")]
    df = df.dropna(subset=["Ticker"])
    df["ticker"] = df["Ticker"].astype(str).str.strip().str.replace(".", "-", regex=False)
    df = df[df["ticker"].str.replace("-", "").str.isalpha()]
    df = df[["ticker", "Name"]].rename(columns={"Name": "name"}).drop_duplicates("ticker").sort_values("ticker")
    if len(df) < min_holdings:
        raise ValueError(f"only {len(df)} stocks in the SPY holdings file (expected ≥ {min_holdings})")
    return df


def us_constituents(refresh: bool = False, offline: bool = False) -> list[str]:
    """S&P 500 constituents (from SPY holdings), cached for `constituents_max_age_days`.

    A failed download falls back to the cached list (logged in data/sources.json); `offline` never fetches.
    """
    from . import coverage

    cache_file = DATA / "constituents_us.csv"
    cached = pd.read_csv(cache_file)["ticker"].tolist() if cache_file.exists() else []
    max_age = settings()["constituents_max_age_days"] * 86400
    if offline or (not refresh and cached and time.time() - cache_file.stat().st_mtime < max_age):
        return cached
    try:
        df = _spy_holdings()
    except Exception as e:
        if not cached:
            raise
        coverage.record("constituents", False, error=f"{type(e).__name__}: {e}; using the cached list")
        return cached
    DATA.mkdir(exist_ok=True)
    df.to_csv(cache_file, index=False)
    coverage.record("constituents", True, f"{len(df)} stocks")
    return df["ticker"].tolist()


def names(tickers: list[str]) -> dict[str, str]:
    """Display names: config ETFs, SPY holdings file, then a cached Yahoo lookup for the rest."""
    out = {e.ticker: e.name for e in etfs()}
    us_file = DATA / "constituents_us.csv"
    if us_file.exists():
        us = pd.read_csv(us_file)
        if "name" in us:
            out |= {t: str(n).title() for t, n in zip(us["ticker"], us["name"])}
    cache_file = DATA / "names.csv"
    cached = dict(pd.read_csv(cache_file).values) if cache_file.exists() else {}
    missing = [t for t in tickers if t not in out and t not in cached]
    if missing:
        import yfinance as yf
        from concurrent.futures import ThreadPoolExecutor

        def lookup(t):
            try:
                info = yf.Ticker(t).info
                return t, info.get("longName") or info.get("shortName") or t
            except Exception:
                return t, t
        with ThreadPoolExecutor(8) as ex:
            cached |= dict(ex.map(lookup, missing))
        pd.DataFrame(list(cached.items()), columns=["ticker", "name"]).to_csv(cache_file, index=False)
    return {t: out.get(t) or cached.get(t, t) for t in tickers}


def sectors(tickers: list[str]) -> pd.DataFrame:
    """Yahoo sector and industry per stock (cached in data/sectors.csv; ETFs and unknowns stay blank)."""
    cache_file = DATA / "sectors.csv"
    cached = pd.read_csv(cache_file, keep_default_na=False) if cache_file.exists()         else pd.DataFrame(columns=["ticker", "sector", "industry"])
    missing = sorted(set(tickers) - set(cached["ticker"]))
    if missing:
        import yfinance as yf
        from concurrent.futures import ThreadPoolExecutor

        def lookup(t):
            try:
                info = yf.Ticker(t).info
                return {"ticker": t, "sector": info.get("sector") or "", "industry": info.get("industry") or ""}
            except Exception:
                return None  # not cached, so it is retried next run
        with ThreadPoolExecutor(8) as ex:
            found = [r for r in ex.map(lookup, missing) if r]
        cached = pd.concat([cached, pd.DataFrame(found)], ignore_index=True)
        DATA.mkdir(exist_ok=True)
        cached.to_csv(cache_file, index=False)
    return cached.set_index("ticker").reindex(tickers).fillna("")


FX_DKK = {"DKK": None, "USD": "USDDKK=X", "EUR": "EURDKK=X", "GBP": "GBPDKK=X", "GBp": "GBPDKK=X",
          "SEK": "SEKDKK=X", "NOK": "NOKDKK=X", "CHF": "CHFDKK=X",
          "JPY": "JPYDKK=X", "HKD": "HKDDKK=X"}


def currencies(tickers: list[str]) -> dict[str, str | None]:
    """Quote currency per ticker (cached Yahoo lookup). GBp = pence."""
    cache_file = DATA / "currencies.csv"
    cached = dict(pd.read_csv(cache_file).values) if cache_file.exists() else {}
    missing = [t for t in tickers if t not in cached]
    if missing:
        import yfinance as yf
        from concurrent.futures import ThreadPoolExecutor

        def lookup(t):
            try:
                return t, yf.Ticker(t).fast_info.get("currency")
            except Exception:
                return t, None
        with ThreadPoolExecutor(8) as ex:
            cached |= {t: c for t, c in ex.map(lookup, missing) if c}
        DATA.mkdir(exist_ok=True)
        pd.DataFrame(list(cached.items()), columns=["ticker", "currency"]).to_csv(cache_file, index=False)
    return {t: cached.get(t) for t in tickers}


def stock_groups(refresh: bool = False, offline: bool = False) -> dict[str, list[str]]:
    groups = {}
    for key, g in universe_config()["stock_groups"].items():
        groups[key] = us_constituents(refresh, offline) if g.get("source") == "spy_holdings" else list(g["tickers"])
    return groups


def stock_group_labels() -> dict[str, str]:
    return {k: g["label"] for k, g in universe_config()["stock_groups"].items()}


def macro_yahoo() -> dict[str, str]:
    return universe_config()["macro"]["yahoo"]


def macro_fred() -> dict[str, str]:
    return universe_config()["macro"]["fred"]


# ---------- holdings / watchlist ----------

HOLDING_COLS = ["symbol", "status", "quantity", "avg_price", "first_trade", "last_sell_date", "last_sell_price"]


def _is_market_symbol(sym: str) -> bool:
    """Indices, futures, FX and Yahoo's cash rows – not positions."""
    return sym.startswith(("^", "$$")) or "=" in sym


def _replay(lots: pd.DataFrame) -> tuple[dict, list[str]]:
    """Replay BUY/SELL transactions with the average-cost method (gennemsnitsmetoden)."""
    qty = cost = 0.0
    opened = last_sell_date = last_sell_price = None
    warnings = []
    for _, t in lots.sort_values("Trade Date", kind="stable").iterrows():
        q, px, kind = t["Quantity"], t["Purchase Price"], t["Transaction Type"]
        if pd.isna(q) or pd.isna(px):
            continue
        if kind not in ("BUY", "SELL"):
            warnings.append(f"skipped a {kind} transaction on {t['Trade Date']:%Y-%m-%d}: only BUY/SELL are replayed")
            continue
        if kind == "SELL":
            if q > qty + 1e-9:
                warnings.append(f"sold {q:g} on {t['Trade Date']:%Y-%m-%d} but held {qty:g} (split or missing buy?)")
                q = qty
            cost -= cost / qty * q if qty else 0
            qty -= q
            last_sell_date, last_sell_price = t["Trade Date"], px
        else:
            if qty <= 1e-9:
                opened = t["Trade Date"]
            qty += q
            cost += q * px
    held = qty > 1e-9
    return {
        "status": "holding" if held else "sold",
        "quantity": round(qty, 6) if held else None,
        "avg_price": cost / qty if held else None,
        "first_trade": opened.date().isoformat() if held and pd.notna(opened) else None,
        "last_sell_date": last_sell_date.date().isoformat() if last_sell_date is not None and pd.notna(last_sell_date) else None,
        "last_sell_price": last_sell_price,
    }, warnings


def import_yahoo_csv(path: str) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Normalise a Yahoo Finance portfolio export into imports/holdings.csv.

    Symbols with transactions become holdings (net quantity > 0) or sold positions; symbols without
    transactions become watchlist. Indices, futures, FX and cash rows are skipped.
    """
    raw = pd.read_csv(path)
    raw.columns = [c.strip() for c in raw.columns]
    raw["Quantity"] = pd.to_numeric(raw.get("Quantity"), errors="coerce")
    raw["Purchase Price"] = pd.to_numeric(raw.get("Purchase Price"), errors="coerce")
    trade = pd.to_numeric(raw.get("Trade Date"), errors="coerce").astype("Int64").astype("string")
    raw["Trade Date"] = pd.to_datetime(trade, format="%Y%m%d", errors="coerce")
    # older exports have no type: their lots are buys
    kind = raw.get("Transaction Type", pd.Series("", index=raw.index)).fillna("").astype(str).str.strip().str.upper()
    raw["Transaction Type"] = kind.replace("", "BUY")

    tx_all = raw[~raw["Symbol"].map(_is_market_symbol) & raw["Transaction Type"].isin(["BUY", "SELL"])]
    tx_all = tx_all.dropna(subset=["Quantity", "Purchase Price", "Trade Date"])
    tx_all = tx_all.rename(columns={"Symbol": "symbol", "Trade Date": "date", "Transaction Type": "type",
                                    "Quantity": "quantity", "Purchase Price": "price"})
    TRANSACTIONS_FILE.parent.mkdir(exist_ok=True)
    tx_all[["symbol", "date", "type", "quantity", "price"]].sort_values(["symbol", "date"], kind="stable").to_csv(
        TRANSACTIONS_FILE, index=False)

    rows, warnings = [], {}
    for sym, lots in raw.groupby("Symbol", sort=True):
        if _is_market_symbol(sym):
            continue
        tx = lots.dropna(subset=["Quantity"])
        if tx.empty:
            rows.append({"symbol": sym, "status": "watch"})
            continue
        row, warn = _replay(tx)
        rows.append({"symbol": sym, **row})
        if warn:
            warnings[sym] = warn
    df = pd.DataFrame(rows, columns=HOLDING_COLS)
    HOLDINGS_FILE.parent.mkdir(exist_ok=True)
    df.to_csv(HOLDINGS_FILE, index=False)
    return df, warnings


def transactions() -> pd.DataFrame:
    if not TRANSACTIONS_FILE.exists():
        return pd.DataFrame(columns=["symbol", "date", "type", "quantity", "price"])
    return pd.read_csv(TRANSACTIONS_FILE, parse_dates=["date"])


def holdings() -> pd.DataFrame:
    """Holdings + watchlist from the Yahoo import plus `watchlist:` in universe.yaml, with the watchlist edits
    made in the web app (userstore) on top: an add puts a symbol on the watchlist (a sold one too), a remove
    takes a watchlist symbol off. Holdings are never changed by the overlay."""
    from . import userstore

    df = pd.read_csv(HOLDINGS_FILE) if HOLDINGS_FILE.exists() else pd.DataFrame(columns=HOLDING_COLS)
    extra = [t for t in universe_config().get("watchlist") or [] if t not in set(df["symbol"])]
    if extra:
        df = pd.concat([df, pd.DataFrame({"symbol": extra, "status": "watch"})], ignore_index=True)
    overlay = userstore.watchlist_overlay()
    if overlay:
        add = {s for s, a in overlay.items() if a == "add"}
        drop = {s for s, a in overlay.items() if a == "remove"}
        df = df[~(df["symbol"].isin(drop) & (df["status"] == "watch"))].copy()
        df.loc[df["symbol"].isin(add) & (df["status"] == "sold"), "status"] = "watch"
        new = sorted(add - set(df["symbol"]))
        if new:
            df = pd.concat([df, pd.DataFrame({"symbol": new, "status": "watch"})], ignore_index=True)
    return df.reset_index(drop=True)


# ---------- Danish positive list ----------

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def positive_list() -> pd.DataFrame | None:
    """SKAT's list of aktiebaserede investeringsselskaber – the latest year's sheet only.

    Older sheets are history; a fund deregistered this year must not count as listed.
    """
    if not POSITIVE_LIST_FILE.exists():
        return None
    sheets = pd.read_excel(POSITIVE_LIST_FILE, sheet_name=None, dtype=str)
    year = max(n for n in sheets if n.strip().isdigit())
    df = sheets[year]
    isin_col = next((c for c in df.columns if "isin" in str(c).lower()), None)  # by header: SKAT reorders columns
    if isin_col is None:
        raise ValueError(f"no ISIN column in the {year} sheet of {POSITIVE_LIST_FILE.name}")
    df = df.rename(columns={isin_col: "isin"})
    df["isin"] = df["isin"].str.strip().str.upper()
    df = df[df["isin"].str.match(ISIN_RE.pattern, na=False)]
    if df.empty:
        raise ValueError(f"no valid ISINs in the {year} sheet of {POSITIVE_LIST_FILE.name}")
    df.attrs["year"] = year
    return df


def positive_list_isins() -> set[str] | None:
    df = positive_list()
    return None if df is None else set(df["isin"])


def positive_list_flag(isin: str | None, isins: set[str] | None) -> str:
    if not isinstance(isin, str) or not isin or isins is None:
        return "?"
    return "yes" if isin.upper() in isins else "no"


def all_price_tickers(refresh: bool = False, offline: bool = False) -> list[str]:
    """Every ticker the radar downloads prices for; `offline` uses the cached constituent list as is."""
    tickers = {benchmark()}
    tickers |= {e.ticker for e in etfs()}
    tickers |= {b["ticker"] for b in group_benchmarks().values()}
    for g in stock_groups(refresh, offline).values():
        tickers |= set(g)
    tickers |= set(macro_yahoo().values())
    tickers |= set(holdings()["symbol"].dropna())
    tickers |= {fx for fx in FX_DKK.values() if fx}
    return sorted(tickers)
