"""Your positions from the transaction store: the average-cost replay (gennemsnitsmetoden), positions per symbol
or portfolio, the trades and the whole ledger of a portfolio selection, holdings with the watchlist overlay, and
the one-time move of the old imports/*.csv files into the store."""
from __future__ import annotations

from datetime import date

import pandas as pd

from ..config import universe_config
from ..paths import HOLDINGS_FILE, TRANSACTIONS_FILE
from ..userstore import CASH_TYPES
from ..values import whole

HOLDING_COLS = ["symbol", "status", "quantity", "avg_price", "first_trade", "last_sell_date", "last_sell_price"]


def is_market_symbol(sym: str) -> bool:
    """Indices, futures, FX and Yahoo's cash rows – not positions."""
    return sym.startswith(("^", "$$")) or "=" in sym


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
    rows: list[dict] = []
    warnings: dict[str, list[str]] = {}
    for key, lots in tx.groupby(keys, sort=True):
        sym = key[0] if isinstance(key, tuple) else key
        row, warn = replay(lots)
        names = sorted(a for a in lots["portfolio"].unique() if a)
        extra = {"portfolio_id": whole(lots["portfolio_id"].iloc[0]), "portfolio": key[1] or None} if by_portfolio else {}
        rows.append({"symbol": sym, **row, "portfolios": ", ".join(names) or None, **extra})
        if warn:
            label = f"{sym} in {key[1]}" if by_portfolio and key[1] else sym
            warnings.setdefault(sym, []).extend(warn if label == sym else [f"{label}: {w}" for w in warn])
    return pd.DataFrame(rows, columns=cols), warnings


def _legacy_files() -> bool:
    return HOLDINGS_FILE.exists() or TRANSACTIONS_FILE.exists()


def ensure_migrated() -> None:
    """Move the old Yahoo-import CSVs (imports/holdings.csv + transactions.csv) into the store, once.

    The positions are rebuilt from the stored transactions and compared with the old holdings.csv; any
    difference undoes the migration and keeps the CSVs in use (radar doctor reports it). On success the CSVs
    are renamed to *.migrated.csv, never deleted."""
    from .. import userstore

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
    from .. import userstore

    cols = TX_COLS + (["amount", "currency"] if types is None else [])
    tx = pd.DataFrame(userstore.transactions(portfolios=portfolios, types=types), columns=cols + ["id", "source"])
    if tx.empty:
        return pd.DataFrame(columns=cols)
    tx["date"] = pd.to_datetime(tx["date"])
    return tx[cols]


def _legacy_mode() -> bool:
    from .. import userstore

    m = userstore.meta_get("legacy_csv") or {}
    return m.get("status") == "failed" and _legacy_files()


def _selection(portfolios: list[int] | None) -> list[int]:
    """None means yours: the real portfolios that aren't archived (virtual ones only when chosen)."""
    from .. import userstore

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
    from .. import userstore

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


def portfolio_symbols() -> set[str]:
    from .. import userstore

    if _legacy_mode():
        return set()
    return {t["symbol"] for t in userstore.transactions() if t["symbol"]}
