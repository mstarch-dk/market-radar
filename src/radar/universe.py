"""Everything the radar tracks: ETFs, stock lists, macro tickers, holdings."""
from __future__ import annotations

import io
import pathlib
import re
import time
from dataclasses import dataclass
from datetime import date

import pandas as pd

from . import net
from .config import POSITIVE_LIST_FILE, settings, universe_config
from .paths import CACHE, HOLDINGS_FILE, TRANSACTIONS_FILE

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
    resp = net.get(SPY_HOLDINGS, timeout=60)
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

    A failed download falls back to the cached list (logged in sources.json); `offline` never fetches.
    """
    from . import coverage

    cache_file = CACHE / "constituents_us.csv"
    cached = pd.read_csv(cache_file)["ticker"].tolist() if cache_file.exists() else []
    max_age = settings()["constituents_max_age_days"] * 86400
    if offline or (not refresh and cached and time.time() - cache_file.stat().st_mtime < max_age):
        return cached
    try:
        from . import ops

        with ops.context(source="constituents"):
            df = _spy_holdings()
    except Exception as e:
        if not cached:
            raise
        coverage.record("constituents", False, error=f"{type(e).__name__}: {e}; using the cached list", exc=e)
        return cached
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_file, index=False)
    coverage.record("constituents", True, f"{len(df)} stocks")
    return df["ticker"].tolist()


def names(tickers: list[str]) -> dict[str, str]:
    """Display names: config ETFs, SPY holdings file, then a cached Yahoo lookup for the rest."""
    out = {e.ticker: e.name for e in etfs()}
    us_file = CACHE / "constituents_us.csv"
    if us_file.exists():
        us = pd.read_csv(us_file)
        if "name" in us:
            out |= {t: str(n).title() for t, n in zip(us["ticker"], us["name"])}
    cache_file = CACHE / "names.csv"
    cached = dict(pd.read_csv(cache_file).values) if cache_file.exists() else {}
    missing = [t for t in tickers if t not in out and t not in cached]
    if missing:
        yf = net.yf()

        def lookup(t):
            try:
                info = yf.Ticker(t).info
                return t, info.get("longName") or info.get("shortName") or t
            except Exception:
                return t, t
        with net.pool(8) as ex:
            cached |= dict(ex.map(lookup, missing))
        pd.DataFrame(list(cached.items()), columns=["ticker", "name"]).to_csv(cache_file, index=False)
    return {t: out.get(t) or cached.get(t, t) for t in tickers}


def sectors(tickers: list[str]) -> pd.DataFrame:
    """Yahoo sector and industry per stock (cached in data/sectors.csv; ETFs and unknowns stay blank)."""
    cache_file = CACHE / "sectors.csv"
    cached = pd.read_csv(cache_file, keep_default_na=False) if cache_file.exists()         else pd.DataFrame(columns=["ticker", "sector", "industry"])
    missing = sorted(set(tickers) - set(cached["ticker"]))
    if missing:
        yf = net.yf()

        def lookup(t):
            try:
                info = yf.Ticker(t).info
                return {"ticker": t, "sector": info.get("sector") or "", "industry": info.get("industry") or ""}
            except Exception:
                return None  # not cached, so it is retried next run
        with net.pool(8) as ex:
            found = [r for r in ex.map(lookup, missing) if r]
        cached = pd.concat([cached, pd.DataFrame(found)], ignore_index=True)
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.to_csv(cache_file, index=False)
    return cached.set_index("ticker").reindex(tickers).fillna("")


# CAD: for the P/E of US listings that report in it (valuation.price_in); Yahoo has no CNY/DKK quote
FX_DKK = {"DKK": None, "USD": "USDDKK=X", "EUR": "EURDKK=X", "GBP": "GBPDKK=X", "GBp": "GBPDKK=X",
          "SEK": "SEKDKK=X", "NOK": "NOKDKK=X", "CHF": "CHFDKK=X", "PLN": "PLNDKK=X",
          "JPY": "JPYDKK=X", "HKD": "HKDDKK=X", "CAD": "CADDKK=X"}
# Yahoo has no KRW/DKK or TWD/DKK quote either: those go through USD (DKK per unit = USDDKK=X / USDxxx=X)
FX_VIA_USD = {"KRW": "USDKRW=X", "TWD": "USDTWD=X"}
FX_TICKERS = sorted({t for t in FX_DKK.values() if t} | set(FX_VIA_USD.values()))


def dkk_rates(last: dict[str, float]) -> dict[str, float]:
    """Latest DKK per unit of each currency from the latest close per FX ticker; a currency whose
    pair(s) are missing is left out. GBp is left out too (callers use GBP and divide by 100)."""
    out = {"DKK": 1.0} | {c: last[t] for c, t in FX_DKK.items() if t and c != "GBp" and t in last}
    usd = last.get(FX_DKK["USD"])
    out |= {c: usd / last[t] for c, t in FX_VIA_USD.items() if usd and last.get(t)}
    return out


def fx_to_dkk(closes: pd.DataFrame, ccy: str | None) -> pd.Series | None:
    """DKK per unit of quoted price (pence-quoted GBp includes the /100)."""
    if ccy in FX_VIA_USD:
        usd, per_usd = FX_DKK["USD"], FX_VIA_USD[ccy]
        if usd not in closes or per_usd not in closes:
            return None
        return closes[usd].ffill() / closes[per_usd].ffill()
    if ccy not in FX_DKK:
        return None
    fx = FX_DKK[ccy]
    if fx is None:
        return pd.Series(1.0, index=closes.index)
    if fx not in closes:
        return None
    return closes[fx].ffill() * (0.01 if ccy == "GBp" else 1.0)


def currencies(tickers: list[str]) -> dict[str, str | None]:
    """Quote currency per ticker (cached Yahoo lookup). GBp = pence."""
    cache_file = CACHE / "currencies.csv"
    cached = dict(pd.read_csv(cache_file).values) if cache_file.exists() else {}
    missing = [t for t in tickers if t not in cached]
    if missing:
        yf = net.yf()

        def lookup(t):
            try:
                return t, yf.Ticker(t).fast_info.get("currency")
            except Exception:
                return t, None
        with net.pool(8) as ex:
            cached |= {t: c for t, c in ex.map(lookup, missing) if c}
        CACHE.mkdir(parents=True, exist_ok=True)
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


def macro_fred_views() -> dict[str, str]:
    """FRED series only the market-views evidence check reads (kept out of the regime's freshness check)."""
    return universe_config()["macro"].get("fred_views") or {}


# ---------- holdings / watchlist ----------

HOLDING_COLS = ["symbol", "status", "quantity", "avg_price", "first_trade", "last_sell_date", "last_sell_price"]


def _is_market_symbol(sym: str) -> bool:
    """Indices, futures, FX and Yahoo's cash rows – not positions."""
    return sym.startswith(("^", "$$")) or "=" in sym


CASH_TYPES = ("DEPOSIT", "WITHDRAW", "DIVIDEND", "FEE", "INTEREST")
TX_COLS = ["symbol", "date", "type", "quantity", "price", "fee", "fx_rate", "portfolio_id", "portfolio"]


def replay(tx: pd.DataFrame) -> tuple[dict, list[str]]:
    """Replay one symbol's BUY/SELL transactions with the average-cost method (gennemsnitsmetoden).

    `tx` has the columns date, type, quantity, price and fee. Fees are part of the acquisition cost; a sale
    removes cost in proportion and doesn't change the average. A sale larger than the position is capped and
    reported, never silently accepted. Cash rows (deposits, dividends, …) don't change a position and are
    passed over."""
    qty = cost = 0.0
    opened = last_sell_date = last_sell_price = None
    warnings = []
    for _, t in tx.sort_values("date", kind="stable").iterrows():
        q, px, kind = t["quantity"], t["price"], t["type"]
        if kind in CASH_TYPES:
            continue
        fee = t.get("fee", 0)
        fee = 0.0 if pd.isna(fee) else float(fee)
        if pd.isna(q) or pd.isna(px):
            continue
        day = pd.Timestamp(t["date"])
        if kind not in ("BUY", "SELL"):
            warnings.append(f"skipped a {kind} transaction on {day:%Y-%m-%d}: only BUY/SELL are replayed")
            continue
        if kind == "SELL":
            if q > qty + 1e-9:
                warnings.append(f"sold {q:g} on {day:%Y-%m-%d} but held {qty:g} (split or missing buy?)")
                q = qty
            cost -= cost / qty * q if qty else 0
            qty -= q
            last_sell_date, last_sell_price = day, px
        else:
            if qty <= 1e-9:
                opened = day
            qty += q
            cost += q * px + fee
    held = qty > 1e-9
    return {
        "status": "holding" if held else "sold",
        "quantity": round(qty, 6) if held else None,
        "avg_price": cost / qty if held else None,
        "first_trade": opened.date().isoformat() if held and opened is not None else None,
        "last_sell_date": last_sell_date.date().isoformat() if last_sell_date is not None else None,
        "last_sell_price": last_sell_price,
    }, warnings


def positions(tx: pd.DataFrame, by_portfolio: bool = False) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Positions (holding or sold) derived from transactions, per symbol or per (symbol, portfolio).
    `portfolios` lists the portfolios a symbol was traded in."""
    cols = HOLDING_COLS + ["portfolios"] + (["portfolio_id", "portfolio"] if by_portfolio else [])
    tx = tx[tx["type"].isin(["BUY", "SELL"])] if not tx.empty else tx
    if tx.empty:
        return pd.DataFrame(columns=cols), {}
    keys = ["symbol", "portfolio"] if by_portfolio else ["symbol"]
    tx = tx.assign(portfolio=tx["portfolio"].fillna("") if "portfolio" in tx else "",
                   portfolio_id=tx["portfolio_id"] if "portfolio_id" in tx else None)
    rows, warnings = [], {}
    for key, lots in tx.groupby(keys, sort=True):
        sym = key[0] if isinstance(key, tuple) else key
        row, warn = replay(lots)
        names = sorted(a for a in lots["portfolio"].unique() if a)
        extra = {"portfolio_id": _int(lots["portfolio_id"].iloc[0]), "portfolio": key[1] or None} if by_portfolio else {}
        rows.append({"symbol": sym, **row, "portfolios": ", ".join(names) or None, **extra})
        if warn:
            label = f"{sym} in {key[1]}" if by_portfolio and key[1] else sym
            warnings.setdefault(sym, []).extend(warn if label == sym else [f"{label}: {w}" for w in warn])
    return pd.DataFrame(rows, columns=cols), warnings


def _int(v) -> int | None:
    return None if v is None or pd.isna(v) else int(v)


def _yahoo_rows(path: str) -> tuple[list[dict], list[str], dict[str, list[str]]]:
    """A Yahoo Finance portfolio export as transaction rows, the symbols without transactions (its watchlist),
    and a note per symbol for rows that were skipped (types other than BUY/SELL). Indices, futures, FX and cash
    rows are left out."""
    raw = pd.read_csv(path)
    raw.columns = [c.strip() for c in raw.columns]
    raw["Quantity"] = pd.to_numeric(raw.get("Quantity"), errors="coerce")
    raw["Purchase Price"] = pd.to_numeric(raw.get("Purchase Price"), errors="coerce")
    raw["Commission"] = pd.to_numeric(raw.get("Commission"), errors="coerce")
    trade = pd.to_numeric(raw.get("Trade Date"), errors="coerce").astype("Int64").astype("string")
    raw["Trade Date"] = pd.to_datetime(trade, format="%Y%m%d", errors="coerce")
    # older exports have no type: their lots are buys
    kind = raw.get("Transaction Type", pd.Series("", index=raw.index)).fillna("").astype(str).str.strip().str.upper()
    raw["Transaction Type"] = kind.replace("", "BUY")
    raw = raw[~raw["Symbol"].map(_is_market_symbol)]
    watch = sorted(s for s, lots in raw.groupby("Symbol") if lots["Quantity"].isna().all())
    skipped: dict[str, list[str]] = {}
    for _, r in raw[~raw["Transaction Type"].isin(["BUY", "SELL"]) & raw["Quantity"].notna()].iterrows():
        day = f" on {r['Trade Date']:%Y-%m-%d}" if pd.notna(r["Trade Date"]) else ""
        skipped.setdefault(r["Symbol"], []).append(
            f"skipped a {r['Transaction Type']} transaction{day}: only BUY/SELL are replayed")
    tx = raw[raw["Transaction Type"].isin(["BUY", "SELL"])].dropna(subset=["Quantity", "Purchase Price", "Trade Date"])
    rows = [{"symbol": r["Symbol"], "date": r["Trade Date"].date().isoformat(), "type": r["Transaction Type"],
             "quantity": float(r["Quantity"]), "price": float(r["Purchase Price"]),
             "fee": 0.0 if pd.isna(r["Commission"]) else float(r["Commission"])} for _, r in tx.iterrows()]
    return rows, watch, skipped


def import_yahoo_csv(path: str) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Import a Yahoo Finance portfolio export into the transaction store.

    The export is a full snapshot of that Yahoo portfolio, so it replaces the default portfolio's rows from the
    previous Yahoo import (manual entries, other brokers' imports and trades moved to another portfolio are
    kept) and its watchlist. Returns the positions
    of the exported symbols and the replay warnings."""
    from . import userstore

    ensure_migrated()
    rows, watch, skipped = _yahoo_rows(path)          # into the default portfolio         # read everything before writing anything
    userstore.add_import(rows, "yahoo", pathlib.Path(path).name, replace_source=True)
    userstore.meta_set("yahoo_watch", watch)
    exported = {r["symbol"] for r in rows} | set(watch)
    pos, warnings = positions(transactions())
    pos = pos[pos["symbol"].isin(exported)]
    watch_rows = pd.DataFrame({"symbol": [w for w in watch if w not in set(pos["symbol"])], "status": "watch"})
    df = pd.concat([pos, watch_rows], ignore_index=True)[HOLDING_COLS]
    notes = {k: skipped.get(k, []) + warnings.get(k, []) for k in exported if skipped.get(k) or warnings.get(k)}
    return df.sort_values("symbol").reset_index(drop=True), notes


# ---------- the store, and moving the old CSV files into it ----------

def _legacy_files() -> bool:
    return HOLDINGS_FILE.exists() or TRANSACTIONS_FILE.exists()


def ensure_migrated() -> None:
    """Move the old Yahoo-import CSVs (imports/holdings.csv + transactions.csv) into the store, once.

    The positions are rebuilt from the stored transactions and compared with the old holdings.csv; any
    difference undoes the migration and keeps the CSVs in use (radar doctor reports it). On success the CSVs
    are renamed to *.migrated.csv, never deleted."""
    from . import userstore

    if not _legacy_files() or userstore.meta_get("legacy_csv"):
        return
    old = pd.read_csv(HOLDINGS_FILE) if HOLDINGS_FILE.exists() else pd.DataFrame(columns=HOLDING_COLS)
    tx = pd.read_csv(TRANSACTIONS_FILE) if TRANSACTIONS_FILE.exists() else pd.DataFrame(columns=TX_COLS)
    rows = [{"symbol": r["symbol"], "date": str(r["date"])[:10], "type": r["type"], "quantity": float(r["quantity"]),
             "price": float(r["price"]), "fee": 0.0} for _, r in tx.iterrows()]
    imp = userstore.add_import(rows, "yahoo", "imports/transactions.csv (moved into the store)")
    new, _ = positions(_store_frame())
    problems = []
    for _, o in old[old["status"].isin(["holding", "sold"])].iterrows():
        n = new[new["symbol"] == o["symbol"]]
        if n.empty or n.iloc[0]["status"] != o["status"]:
            problems.append(f"{o['symbol']}: {o['status']} before, {n.iloc[0]['status'] if len(n) else 'missing'} after")
        elif o["status"] == "holding" and not (abs(n.iloc[0]["quantity"] - o["quantity"]) < 1e-6
                                                and abs(n.iloc[0]["avg_price"] - o["avg_price"]) <= 1e-6 * abs(o["avg_price"])):
            problems.append(f"{o['symbol']}: {o['quantity']} @ {o['avg_price']} before, "
                            f"{n.iloc[0]['quantity']} @ {n.iloc[0]['avg_price']} after")
    if problems:
        userstore.undo_import(imp["id"])
        userstore.meta_set("legacy_csv", {"status": "failed", "problems": problems})
        return
    userstore.meta_set("yahoo_watch", sorted(old.loc[old["status"] == "watch", "symbol"].dropna()))
    for f in (HOLDINGS_FILE, TRANSACTIONS_FILE):
        if f.exists():
            f.replace(f.with_name(f.stem + ".migrated.csv"))
    userstore.meta_set("legacy_csv", {"status": "migrated", "at": date.today().isoformat(), "transactions": len(rows)})


def _store_frame(portfolios: list[int] | None = None, types=("BUY", "SELL")) -> pd.DataFrame:
    """Stored rows as a frame (`portfolios`: ids, None = every portfolio; `types`: None = every type)."""
    from . import userstore

    cols = TX_COLS + (["amount", "currency"] if types is None else [])
    tx = pd.DataFrame(userstore.transactions(portfolios=portfolios, types=types), columns=cols + ["id", "source"])
    if tx.empty:
        return pd.DataFrame(columns=cols)
    tx["date"] = pd.to_datetime(tx["date"])
    return tx[cols]


def _legacy_mode() -> bool:
    from . import userstore

    m = userstore.meta_get("legacy_csv") or {}
    return m.get("status") == "failed" and _legacy_files()


def _selection(portfolios: list[int] | None) -> list[int]:
    """None means yours: the real portfolios that aren't archived (virtual ones only when chosen)."""
    from . import userstore

    return userstore.portfolio_ids() if portfolios is None else list(portfolios)


def transactions(portfolios: list[int] | None = None) -> pd.DataFrame:
    """Every BUY/SELL (symbol, date, type, quantity, price, fee, fx_rate, portfolio_id, portfolio) in these
    portfolios (ids; default: your real ones). Cash rows are left out: see ledger()."""
    ensure_migrated()
    if _legacy_mode():
        tx = pd.read_csv(TRANSACTIONS_FILE, parse_dates=["date"]) if TRANSACTIONS_FILE.exists() else pd.DataFrame(columns=TX_COLS)
        return tx.assign(fee=0.0, fx_rate=None, portfolio_id=None, portfolio=None)
    return _store_frame(_selection(portfolios))


def ledger(portfolios: list[int] | None = None) -> pd.DataFrame:
    """Every row of these portfolios (default: your real ones), cash rows included, with amount and currency."""
    ensure_migrated()
    return _store_frame(_selection(portfolios), types=None)


def holdings(portfolios: list[int] | None = None) -> pd.DataFrame:
    """Holdings and sold positions derived from the transactions of these portfolios (ids; default: your real
    ones), plus the watchlist (shared by all portfolios): the last Yahoo import's,
    `watchlist:` in universe.yaml, and the edits made in the web app (userstore) on top. An add puts a symbol on
    the watchlist (a sold one too), a remove takes a watchlist symbol off. Holdings are never changed by the
    overlay."""
    from . import userstore

    ensure_migrated()
    if _legacy_mode():
        df = pd.read_csv(HOLDINGS_FILE) if HOLDINGS_FILE.exists() else pd.DataFrame(columns=HOLDING_COLS)
    else:
        pos, _ = positions(transactions(portfolios))
        watch = [w for w in userstore.meta_get("yahoo_watch", []) if w not in set(pos["symbol"])]
        df = pd.concat([pos, pd.DataFrame({"symbol": watch, "status": "watch"})], ignore_index=True)
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


def _every_portfolio_symbol() -> set[str]:
    from . import userstore

    if _legacy_mode():
        return set()
    return {t["symbol"] for t in userstore.transactions() if t["symbol"]}


def history_start(today: date | None = None) -> date:
    """Where the stored price history starts: `history_years` back, or earlier when your first trade needs it
    (that day minus backtest.warmup_days, for the 200-day average and 12-month momentum on the day you bought),
    but never more than backtest.max_years back."""
    from datetime import timedelta

    from . import userstore

    today = today or date.today()
    cfg, bt = settings(), settings().get("backtest") or {}
    start = today - timedelta(days=int(365.25 * cfg["history_years"]))
    dates = [str(t["date"])[:10] for t in userstore.transactions()]
    if dates:
        start = min(start, date.fromisoformat(min(dates)) - timedelta(days=int(bt.get("warmup_days", 0))))
    return max(start, today - timedelta(days=int(365.25 * bt.get("max_years", 10))))


def all_price_tickers(refresh: bool = False, offline: bool = False) -> list[str]:
    """Every ticker the radar downloads prices for; `offline` uses the cached constituent list as is."""
    tickers = {benchmark()}
    tickers |= {e.ticker for e in etfs()}
    tickers |= {b["ticker"] for b in group_benchmarks().values()}
    for g in stock_groups(refresh, offline).values():
        tickers |= set(g)
    tickers |= set(macro_yahoo().values())
    tickers |= set(holdings()["symbol"].dropna())
    tickers |= _every_portfolio_symbol()                  # virtual portfolios need prices too
    tickers |= set(FX_TICKERS)
    return sorted(tickers)
