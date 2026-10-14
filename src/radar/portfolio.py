"""Checks and derived views for the portfolio editor and the importers: is a transaction plausible, what does it
do to the position, and what are the positions per account. Python decides; the UI only shows the verdicts.

Nothing is "fixed" silently. Errors block a save; warnings (an unusual price, a likely duplicate) are shown and
must be confirmed.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from . import universe, userstore

ERROR, WARNING = "error", "warning"


def _text(v) -> str | None:
    """A text cell from pandas, with empty and missing (NaN) both as None."""
    return None if v is None or (isinstance(v, float) and pd.isna(v)) or v == "" else str(v)


def _issue(level: str, field: str, message: str) -> dict:
    return {"level": level, "field": field, "message": message}


def _session(market, symbol: str, day: pd.Timestamp) -> tuple[pd.Timestamp, float] | None:
    """The traded close on `day`, or the last session before it (weekends, holidays)."""
    if symbol not in market.closes.columns:
        return None
    bars = market.bars(symbol)
    col = "raw_close" if "raw_close" in bars else "close"
    s = bars[col].dropna()[:day]
    if s.empty:
        return None
    return s.index[-1], float(s.iloc[-1])


def price_check(market, symbol: str, day, price: float | None = None) -> dict:
    """The traded close on that day (to prefill a price) and, given a price, whether it looks plausible: about
    100× off is the classic pence/pound (GBp/GBP) or cents mix-up; far from the day's close is worth a second
    look. Prices are per share in the instrument's quote currency."""
    from . import universe as u

    day = pd.Timestamp(day)
    ccy = u.currencies([symbol]).get(symbol) if symbol in market.closes.columns else None
    found = _session(market, symbol, day)
    out = {"symbol": symbol, "currency": ccy, "close": None, "close_date": None, "verdict": "no_data", "message": None}
    if not found:
        out["message"] = "No price history for this date, so the price can't be checked."
        return out
    d, close = found
    out |= {"close": close, "close_date": d.date().isoformat(), "verdict": "ok"}
    if price is None or price <= 0:
        return out
    r = price / close
    if 80 <= r <= 125:
        out |= {"verdict": "x100", "message": f"{price:g} is about 100× the close of {close:g} {ccy or ''}: "
                                              "pence vs pounds (GBp/GBP), or øre vs kroner?"}
    elif 0.008 <= r <= 0.0125:
        out |= {"verdict": "div100", "message": f"{price:g} is about 1/100 of the close of {close:g} {ccy or ''}: "
                                                "pounds vs pence (GBp/GBP)?"}
    elif abs(r - 1) > 0.25:
        out |= {"verdict": "far", "message": f"{price:g} is {r - 1:+.0%} from that day's close of {close:g} "
                                             f"{ccy or ''}. Right currency and date?"}
    return out


def _frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=universe.TX_COLS + ["id"])
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def validate(row: dict, market, others: list[dict] | None = None, exclude_id: int | None = None,
             check_symbol: bool = True) -> list[dict]:
    """Issues with one transaction, in the context of the stored ones (`others`, default: the store), leaving
    out `exclude_id` (the row being edited)."""
    issues = []
    sym = (row.get("symbol") or "").strip().upper()
    if not sym:
        issues.append(_issue(ERROR, "symbol", "Choose a ticker."))
    elif check_symbol and sym not in market.closes.columns:
        issues.append(_issue(ERROR, "symbol", f"No Yahoo price data for {sym}: check the symbol (e.g. NOVO-B.CO)."))
    try:
        day = pd.Timestamp(row.get("date"))
    except (TypeError, ValueError):
        day = None
    if day is None or pd.isna(day):
        issues.append(_issue(ERROR, "date", "Enter the trade date."))
    elif day.date() > date.today():
        issues.append(_issue(ERROR, "date", "The date is in the future."))
    if row.get("type") not in ("BUY", "SELL"):
        issues.append(_issue(ERROR, "type", "Choose buy or sell."))
    for f, label in (("quantity", "Quantity"), ("price", "Price")):
        v = row.get(f)
        if v is None or not isinstance(v, (int, float)) or v <= 0:
            issues.append(_issue(ERROR, f, f"{label} must be more than 0."))
    fee = row.get("fee") or 0
    if not isinstance(fee, (int, float)) or fee < 0:
        issues.append(_issue(ERROR, "fee", "The fee can't be negative."))
    acct = row.get("account")
    if acct and acct not in {a["name"] for a in userstore.accounts()}:
        issues.append(_issue(ERROR, "account", f"Unknown account \"{acct}\": add it under Accounts first."))
    if any(i["level"] == ERROR for i in issues):
        return issues

    stored = userstore.transactions() if others is None else others
    rest = [t for t in stored if t.get("id") != exclude_id]
    same = [t for t in rest if t["symbol"] == sym and (t.get("account") or None) == (acct or None)]
    candidate = dict(row, symbol=sym, fee=fee, account=acct or None)
    _, warn = universe.positions(_frame(same + [candidate]))
    if warn.get(sym):
        issues.append(_issue(ERROR, "quantity", "This would sell more than was held at that date "
                             f"({warn[sym][0]}). Add the missing buy first, or check the quantity."))
    if any(userstore._key(t) == userstore._key(candidate) for t in rest):
        issues.append(_issue(WARNING, "date", "The same trade (ticker, date, type, quantity, price) is already stored."))
    pc = price_check(market, sym, day, row["price"])
    if pc["verdict"] in ("x100", "div100", "far"):
        issues.append(_issue(WARNING, "price", pc["message"]))
    return issues


def effect(row: dict, others: list[dict] | None = None, exclude_id: int | None = None) -> dict:
    """The position before and after this transaction (quantity and average cost), for the editor's preview."""
    sym = (row.get("symbol") or "").strip().upper()
    stored = userstore.transactions() if others is None else others
    rest = [t for t in stored if t.get("id") != exclude_id and t["symbol"] == sym]
    before, _ = universe.positions(_frame(rest))
    after, _ = universe.positions(_frame(rest + [dict(row, symbol=sym, fee=row.get("fee") or 0)]))

    def pick(df):
        if df.empty or df.iloc[0]["status"] != "holding":
            return {"quantity": 0.0, "avg_price": None}
        return {"quantity": float(df.iloc[0]["quantity"]), "avg_price": float(df.iloc[0]["avg_price"])}
    return {"symbol": sym, "before": pick(before), "after": pick(after)}


def positions_view(market) -> dict:
    """Open positions per account and in total, valued at the last traded close (in the quote currency)."""
    tx = universe.transactions()
    total, warn = universe.positions(tx)
    per, _ = universe.positions(tx, by_account=True)

    def rows(df, by_account):
        out = []
        for _, p in df[df["status"] == "holding"].iterrows():
            found = _session(market, p["symbol"], pd.Timestamp.today())
            last = found[1] if found else None
            out.append({"symbol": p["symbol"], "account": _text(p.get("account")) if by_account else None,
                        "accounts": _text(p.get("accounts")), "quantity": float(p["quantity"]), "avg_price": float(p["avg_price"]),
                        "first_trade": p["first_trade"], "last": last,
                        "value": last * float(p["quantity"]) if last is not None else None,
                        "unrealized": last / float(p["avg_price"]) - 1 if last is not None and p["avg_price"] else None})
        return out
    names = universe.names(sorted(total["symbol"])) if not total.empty else {}
    ccy = universe.currencies(sorted(total["symbol"])) if not total.empty else {}
    add = lambda r: r | {"name": names.get(r["symbol"]), "currency": ccy.get(r["symbol"])}  # noqa: E731
    return {"total": [add(r) for r in rows(total, False)], "by_account": [add(r) for r in rows(per, True)],
            "warnings": warn, "transactions": len(tx)}
