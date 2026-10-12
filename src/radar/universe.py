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


def _spy_holdings() -> pd.DataFrame:
    resp = requests.get(SPY_HOLDINGS, headers=UA, timeout=60)
    resp.raise_for_status()
    df = pd.read_excel(io.BytesIO(resp.content), skiprows=4)
    df = df[pd.to_numeric(df["Weight"], errors="coerce").notna() & (df["Local Currency"] == "USD")]
    df = df.dropna(subset=["Ticker"])
    df["ticker"] = df["Ticker"].astype(str).str.strip().str.replace(".", "-", regex=False)
    df = df[df["ticker"].str.replace("-", "").str.isalpha()]
    return df[["ticker", "Name"]].rename(columns={"Name": "name"}).drop_duplicates("ticker").sort_values("ticker")


def us_constituents(refresh: bool = False) -> list[str]:
    """S&P 500 constituents (from SPY holdings), cached for `constituents_max_age_days`."""
    cache_file = DATA / "constituents_us.csv"
    max_age = settings()["constituents_max_age_days"] * 86400
    if not refresh and cache_file.exists() and time.time() - cache_file.stat().st_mtime < max_age:
        return pd.read_csv(cache_file)["ticker"].tolist()
    df = _spy_holdings()
    DATA.mkdir(exist_ok=True)
    df.to_csv(cache_file, index=False)
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


FX_DKK = {"DKK": None, "USD": "USDDKK=X", "EUR": "EURDKK=X", "GBP": "GBPDKK=X", "GBp": "GBPDKK=X",
          "SEK": "SEKDKK=X", "NOK": "NOKDKK=X", "CHF": "CHFDKK=X"}


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


def stock_groups(refresh: bool = False) -> dict[str, list[str]]:
    groups = {}
    for key, g in universe_config()["stock_groups"].items():
        groups[key] = us_constituents(refresh) if g.get("source") == "spy_holdings" else list(g["tickers"])
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
        if kind == "SELL":
            if q > qty + 1e-9:
                warnings.append(f"sold {q:g} on {t['Trade Date']:%Y-%m-%d} but held {qty:g} (split or missing buy?)")
                q = qty
            cost -= cost / qty * q if qty else 0
            qty -= q
            last_sell_date, last_sell_price = t["Trade Date"], px
        else:  # BUY (older exports have no type column: treat lots as buys)
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
    raw["Transaction Type"] = raw.get("Transaction Type", pd.Series("BUY", index=raw.index)).fillna("").str.upper()

    tx_all = raw[~raw["Symbol"].map(_is_market_symbol)].dropna(subset=["Quantity", "Purchase Price", "Trade Date"])
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
    """Holdings + watchlist from the Yahoo import plus `watchlist:` in universe.yaml."""
    df = pd.read_csv(HOLDINGS_FILE) if HOLDINGS_FILE.exists() else pd.DataFrame(columns=HOLDING_COLS)
    extra = [t for t in universe_config().get("watchlist") or [] if t not in set(df["symbol"])]
    if extra:
        df = pd.concat([df, pd.DataFrame({"symbol": extra, "status": "watch"})], ignore_index=True)
    return df


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
    df.columns = ["residence", "isin", "share_class", "lei", "tin", "sub_fund", "tin2", "name", "registered", "deregistered"][:len(df.columns)]
    df["isin"] = df["isin"].str.strip().str.upper()
    df = df[df["isin"].str.match(ISIN_RE.pattern, na=False)]
    df.attrs["year"] = year
    return df


def positive_list_isins() -> set[str] | None:
    df = positive_list()
    return None if df is None else set(df["isin"])


def positive_list_flag(isin: str | None, isins: set[str] | None) -> str:
    if not isinstance(isin, str) or not isin or isins is None:
        return "?"
    return "yes" if isin.upper() in isins else "no"


def all_price_tickers(refresh: bool = False) -> list[str]:
    tickers = {benchmark()}
    tickers |= {e.ticker for e in etfs()}
    for g in stock_groups(refresh).values():
        tickers |= set(g)
    tickers |= set(macro_yahoo().values())
    tickers |= set(holdings()["symbol"].dropna())
    tickers |= {fx for fx in FX_DKK.values() if fx}
    return sorted(tickers)
