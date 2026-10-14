"""Checks and derived views for the portfolio editor and the importers: is a transaction plausible, what does it
do to the position, and what are the positions per portfolio. Python decides; the UI only shows the verdicts.

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
    out = {"symbol": symbol, "currency": ccy, "close": None, "close_date": None, "verdict": "no_data", "message": None,
           "fx": None}
    if not found:
        out["message"] = "No price history for this date, so the price can't be checked."
        return out
    d, close = found
    fx = u.fx_to_dkk(market.closes, ccy)
    rate = fx.dropna().asof(d) if fx is not None else None
    out |= {"close": close, "close_date": d.date().isoformat(), "verdict": "ok",
            "fx": float(rate) if rate is not None and pd.notna(rate) else None}
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


TYPE_WORDS = {"BUY": "buy", "SELL": "sale", "DEPOSIT": "deposit", "WITHDRAW": "withdrawal", "DIVIDEND": "dividend",
              "FEE": "fee", "INTEREST": "interest payment"}
CASH_SLACK = 0.5                       # DKK: rounding, not a missing deposit


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v


def validate(row: dict, market, others: list[dict] | None = None, exclude_id: int | None = None,
             check_symbol: bool = True) -> list[dict]:
    """Issues with one row (a trade or a cash row), in the context of its portfolio's stored rows (`others`,
    default: the store), leaving out `exclude_id` (the row being edited)."""
    from . import performance

    issues = []
    kind = row.get("type")
    trade, cash_row = kind in userstore.TRADE_TYPES, kind in userstore.CASH_TYPES
    sym = (row.get("symbol") or "").strip().upper()
    if not (trade or cash_row):
        issues.append(_issue(ERROR, "type", "Choose a type: buy, sell, deposit, withdrawal, dividend, fee or interest."))
    if trade or kind == "DIVIDEND":
        if not sym:
            issues.append(_issue(ERROR, "symbol", "Choose a ticker."))
        elif check_symbol and sym not in market.closes.columns:
            issues.append(_issue(ERROR, "symbol", f"No Yahoo price data for {sym}: check the symbol (e.g. NOVO-B.CO)."))
    elif cash_row and sym:
        issues.append(_issue(ERROR, "symbol", f"A {TYPE_WORDS[kind]} has no ticker."))
    try:
        day = pd.Timestamp(row.get("date"))
    except (TypeError, ValueError):
        day = None
    if day is None or pd.isna(day):
        issues.append(_issue(ERROR, "date", "Enter the date."))
    elif day.date() > date.today():
        issues.append(_issue(ERROR, "date", "The date is in the future."))
    fee = row.get("fee") or 0
    if trade:
        for f, label in (("quantity", "Quantity"), ("price", "Price")):
            v = row.get(f)
            if not _num(v) or v <= 0:
                issues.append(_issue(ERROR, f, f"{label} must be more than 0."))
        if not _num(fee) or fee < 0:
            issues.append(_issue(ERROR, "fee", "The fee can't be negative."))
        if row.get("fx_rate") is not None and (not _num(row["fx_rate"]) or row["fx_rate"] <= 0):
            issues.append(_issue(ERROR, "fx_rate", "The exchange rate must be more than 0 (DKK per unit of price)."))
    elif cash_row:
        v = row.get("amount")
        if not _num(v) or v <= 0:
            issues.append(_issue(ERROR, "amount", "The amount must be more than 0."))
        if (row.get("currency") or "DKK").upper() != "DKK":
            issues.append(_issue(ERROR, "currency", "Cash rows are entered in DKK (convert at the rate your broker used)."))
        if fee:
            issues.append(_issue(ERROR, "fee", "Enter a fee as a row of its own (type Fee)."))
    pid, problem = target_portfolio(row)
    if problem:
        issues.append(_issue(ERROR, "portfolio", problem))
    if any(i["level"] == ERROR for i in issues):
        return issues

    stored = userstore.transactions() if others is None else others
    rest = [t for t in stored if t.get("id") != exclude_id and t.get("portfolio_id") == pid]
    candidate = dict(row, symbol=sym or None, fee=fee if trade else 0, portfolio_id=pid, date=day.date().isoformat())
    if cash_row:
        candidate |= {"quantity": None, "price": None, "currency": "DKK"}
    else:
        candidate |= {"amount": None, "currency": None}
    if any(userstore._key(t) == userstore._key(candidate) for t in rest):
        issues.append(_issue(WARNING, "date", f"The same {TYPE_WORDS[kind]} is already stored in this portfolio."))
    if trade:
        same = [t for t in rest if t["symbol"] == sym]
        _, warn = universe.positions(_frame(same + [candidate]))
        if warn.get(sym):
            issues.append(_issue(ERROR, "quantity", "This would sell more than was held in this portfolio at that date "
                                 f"({warn[sym][0]}). Add the missing buy first, or check the quantity."))
        pc = price_check(market, sym, day, row["price"])
        if pc["verdict"] in ("x100", "div100", "far"):
            issues.append(_issue(WARNING, "price", pc["message"]))
    p = userstore.get_portfolio(pid) if pid is not None and pid > 0 else None
    if kind == "DIVIDEND":
        held, _ = universe.positions(_frame([t for t in rest if t["symbol"] == sym and str(t["date"])[:10] <= candidate["date"]]))
        if held.empty or held.iloc[0]["status"] != "holding":
            issues.append(_issue(WARNING, "symbol", f"{sym} wasn't held in this portfolio on that date."))
        if (p or {}).get("dividends", "reinvested") == "reinvested":
            issues.append(_issue(WARNING, "type", "This portfolio counts dividends as reinvested (adjusted prices), so "
                                 "the row is kept for the record but not counted. Switch it to cash dividends to count them."))
    issues += _cash_issues(rest + [candidate], market, p, candidate, performance)
    return issues


def _cash_issues(rows: list[dict], market, p: dict | None, candidate: dict, performance) -> list[dict]:
    """Would cash go negative? An error in a virtual portfolio (it can only spend what was put in), a warning in
    a real one that keeps a cash ledger (a missing deposit?); real portfolios without cash rows aren't checked."""
    virtual = (p or {}).get("mode") == "virtual"
    if not virtual and not performance.has_ledger(rows):
        return []
    out = []
    bal, problems = performance.cash_balance(rows, market, (p or {}).get("dividends", "reinvested"))
    own = [m for m in problems if candidate.get("symbol") and m.startswith(f"{candidate['symbol']} on {candidate['date']}")]
    if own:
        out.append(_issue(ERROR if virtual else WARNING, "fx_rate",
                          f"No DKK exchange rate for {candidate['symbol']} on that date: enter the rate you traded at."))
    if len(bal) and bal.min() < -CASH_SLACK:
        d = bal.idxmin()
        msg = f"Cash would go negative: {bal.min():,.0f} DKK on {d:%Y-%m-%d}."
        out.append(_issue(ERROR, "amount", msg + " A virtual portfolio can only spend what was deposited: add a "
                          "deposit first.") if virtual else
                   _issue(WARNING, "amount", msg + " Is a deposit missing?"))
    return out


def target_portfolio(row: dict) -> tuple[int | None, str | None]:
    """The portfolio id a row goes into (its portfolio_id, or `portfolio` / older `account` by name, else the
    default; None when there is no default yet: "Main" is created on save) and a problem if it can't. A
    negative id stands for a portfolio an import will create (named in the file)."""
    pid, name = row.get("portfolio_id"), (row.get("portfolio") or row.get("account") or "").strip()
    if pid is not None and int(pid) < 0:
        return int(pid), None
    if pid is not None:
        p = userstore.get_portfolio(int(pid))
        return (int(pid), None) if p else (None, f"No portfolio {pid}.")
    if name:
        p = userstore.portfolio_by_name(name)
        return (p["id"], None) if p else (None, f"Unknown portfolio \"{name}\": add it under Portfolios first.")
    return userstore.default_portfolio(), None


def effect(row: dict, others: list[dict] | None = None, exclude_id: int | None = None) -> dict:
    """The position in its portfolio before and after this transaction (quantity and average cost), for the
    editor's preview."""
    sym = (row.get("symbol") or "").strip().upper()
    pid, _ = target_portfolio(row)
    stored = userstore.transactions() if others is None else others
    rest = [t for t in stored if t.get("id") != exclude_id and t["symbol"] == sym and t.get("portfolio_id") == pid
            and t["type"] in userstore.TRADE_TYPES]
    before, _ = universe.positions(_frame(rest))
    after, _ = universe.positions(_frame(rest + [dict(row, symbol=sym, fee=row.get("fee") or 0, portfolio_id=pid)]))

    def pick(df):
        if df.empty or df.iloc[0]["status"] != "holding":
            return {"quantity": 0.0, "avg_price": None}
        return {"quantity": float(df.iloc[0]["quantity"]), "avg_price": float(df.iloc[0]["avg_price"])}
    return {"symbol": sym, "before": pick(before), "after": pick(after)}


def positions_view(market, portfolios: list[int] | None = None) -> dict:
    """Open positions per portfolio and in total over these portfolios (ids; default: your real ones), valued at
    the last traded close (in the quote currency)."""
    tx = universe.transactions(portfolios)
    total, warn = universe.positions(tx)
    per, _ = universe.positions(tx, by_portfolio=True)

    def rows(df, by_portfolio):
        out = []
        for _, p in df[df["status"] == "holding"].iterrows():
            found = _session(market, p["symbol"], pd.Timestamp.today())
            last = found[1] if found else None
            out.append({"symbol": p["symbol"],
                        "portfolio_id": universe._int(p.get("portfolio_id")) if by_portfolio else None,
                        "portfolio": _text(p.get("portfolio")) if by_portfolio else None,
                        "portfolios": _text(p.get("portfolios")), "quantity": float(p["quantity"]),
                        "avg_price": float(p["avg_price"]), "first_trade": p["first_trade"], "last": last,
                        "value": last * float(p["quantity"]) if last is not None else None,
                        "unrealized": last / float(p["avg_price"]) - 1 if last is not None and p["avg_price"] else None})
        return out
    names = universe.names(sorted(total["symbol"])) if not total.empty else {}
    ccy = universe.currencies(sorted(total["symbol"])) if not total.empty else {}
    add = lambda r: r | {"name": names.get(r["symbol"]), "currency": ccy.get(r["symbol"])}  # noqa: E731
    return {"total": [add(r) for r in rows(total, False)], "by_portfolio": [add(r) for r in rows(per, True)],
            "warnings": warn, "transactions": len(tx), "cash": cash_view(market, portfolios)}


def cash_view(market, portfolios: list[int] | None = None) -> list[dict]:
    """Cash per portfolio, in DKK, for those that keep a cash ledger (deposits/withdrawals)."""
    from . import performance

    ids = userstore.portfolio_ids() if portfolios is None else portfolios
    out = []
    for p in userstore.portfolios():
        if p["id"] not in ids:
            continue
        rows = userstore.transactions(portfolios=[p["id"]])
        if not performance.has_ledger(rows):
            out.append({"portfolio_id": p["id"], "portfolio": p["name"], "funding": "implicit", "cash_dkk": None})
            continue
        bal, problems = performance.cash_balance(rows, market, p["dividends"])
        out.append({"portfolio_id": p["id"], "portfolio": p["name"], "funding": "ledger",
                    "cash_dkk": None if problems else (float(bal.iloc[-1]) if len(bal) else 0.0), "problems": problems})
    return out


def check_move(from_id: int, to_id: int, ids=None, symbols=None) -> list[str]:
    """What moving these rows to another portfolio would break: a sale left without its buy, in either one."""
    rows = userstore.transactions(portfolios=[from_id, to_id])
    moving = lambda t: (t["portfolio_id"] == from_id and (not ids or t["id"] in ids)  # noqa: E731
                        and (not symbols or t["symbol"] in symbols))
    after = [dict(t, portfolio_id=to_id) if moving(t) else t for t in rows]
    problems = []
    for pid in (from_id, to_id):
        _, before = universe.positions(_frame([t for t in rows if t["portfolio_id"] == pid]))
        _, now = universe.positions(_frame([t for t in after if t["portfolio_id"] == pid]))
        problems += [f"{sym}: {w}" for sym, ws in now.items() for w in ws if w not in before.get(sym, [])]
    return problems
