"""Virtual portfolios for A/B tests and simulations.

- **fork**: copy a portfolio as it stood at the close of a day into a new virtual one (one deposit, one buy per
  holding at that day's traded close and DKK rate), so the two can be compared from there on equal terms
  (/api/portfolios/compare with start = that day). The copy holds the same shares and cash; dividends the
  original earned before that day stay with the original, so its value can be a little higher. The copy's buys
  pay no fee (they copy holdings, not trades); the fork takes over the source's broker fee schedule, so the trades
  you make in it later pay what the source's broker would charge (fees.SimFees; without one, `backtest.fee_bps`),
  and its params record which (`fee_model`).
- **simulations**: a `Strategy` turns prices into rows (trades and cash) for a period; `write_run` checks the
  whole ledger and stores it as one run in a virtual portfolio made for it, replacing the previous run. The
  same inputs give the same rows, so a rerun is idempotent. The strategies themselves (rule engines, e.g.
  backtest/exits.py) live elsewhere; this is the interface they write through.

Simulated trades never count as yours: they only go into virtual portfolios.
"""
from __future__ import annotations

from typing import Protocol

import pandas as pd

from . import money, performance, universe, userstore
from .config import settings
from .fees import SimFees

SIM_TYPES = ("BUY", "SELL", "DEPOSIT", "WITHDRAW", "FEE", "INTEREST")


def _close(market, sym: str, day: pd.Timestamp) -> tuple[pd.Timestamp, float] | None:
    """The traded close on `day`, or the last one before it."""
    from .portfolio import session_close

    return session_close(market, sym, day)


def fork(src_id: int, name: str, at, market, extra_cash_dkk: float = 0.0, tags=()) -> int:
    """A virtual copy of portfolio `src_id` as it stood at the close of `at`: one deposit of its value then (plus
    `extra_cash_dkk`), and a buy of each holding at that day's traded close and DKK rate. Refused (ValueError)
    when a holding has no price or rate that day."""
    src = userstore.get_portfolio(src_id)
    if not src:
        raise ValueError(f"no portfolio {src_id}")
    if userstore.portfolio_by_name(name):
        raise ValueError(f"there is already a portfolio called {name}")
    cal = performance.benchmark_sessions(market)
    day = cal[cal <= pd.Timestamp(at)]
    if day.empty:
        raise ValueError(f"no prices on or before {at}")
    day = day[-1]
    rows = [r for r in userstore.transactions(portfolios=[src_id]) if str(r["date"])[:10] <= day.date().isoformat()]
    pos, _ = universe.positions(pd.DataFrame(rows, columns=universe.TX_COLS + ["id"]).assign(
        date=lambda d: pd.to_datetime(d["date"])) if rows else pd.DataFrame(columns=universe.TX_COLS))
    buys, problems, total = [], [], 0.0
    for _, p in pos[pos["status"] == "holding"].iterrows():
        sym, qty = p["symbol"], float(p["quantity"])
        found = _close(market, sym, day)
        fx = performance.fx_series(market, sym)
        rate = money.rate_on(fx, day)
        if found is None or rate is None:
            problems.append(f"{sym}: no {'price' if found is None else 'DKK rate'} on {day:%Y-%m-%d}")
            continue
        buys.append({"symbol": sym, "date": day.date().isoformat(), "type": "BUY", "quantity": qty, "price": found[1],
                     "fee": 0.0, "fx_rate": rate, "ext_ref": f"fork:{src_id}:{sym}"})
        total += qty * found[1] * float(rate)
    if problems:
        raise ValueError("can't value the portfolio that day: " + "; ".join(problems))
    if performance.has_ledger(rows):
        bal, cash_problems = performance.cash_balance(rows, market, src["dividends"])
        if cash_problems:
            raise ValueError("its cash that day is unknown: " + "; ".join(cash_problems))
        total += float(bal.iloc[-1]) if len(bal) else 0.0
    total += float(extra_cash_dkk or 0)
    if total <= 0:
        raise ValueError(f"{src['name']} held nothing on {day:%Y-%m-%d}")
    deposit = {"date": day.date().isoformat(), "type": "DEPOSIT", "amount": total, "currency": "DKK",
               "note": f"forked from {src['name']} at the close of {day:%Y-%m-%d}"}
    fees = SimFees.for_portfolio(src, money.fee_bps(settings().get("backtest")))
    return userstore.create_with_rows(
        {"name": name, "mode": "virtual", "kind": src["kind"], "dividends": src["dividends"], "origin": "fork",
         "parent_id": src_id, "forked_at": day.date().isoformat(), "tags": list(tags),
         "fee_schedule": fees.schedule, "params": {"fee_model": fees.describe()},
         "note": f"A copy of {src['name']} at the close of {day:%Y-%m-%d}"}, [deposit, *buys], "fork")


# ---------------- simulations ----------------

class Strategy(Protocol):
    """A rule set that turns prices into rows for a period: trades (BUY/SELL with symbol, quantity, price, fee
    and optionally fx_rate) and cash (DEPOSIT/WITHDRAW/FEE with an amount in DKK), each with a date. It must
    start with a deposit of `capital_dkk` and only use prices known on each row's date."""
    key: str

    def rows(self, market, start: pd.Timestamp, end: pd.Timestamp, capital_dkk: float, params: dict) -> list[dict]: ...


def new_sim_portfolio(name: str, strategy: str, params: dict | None = None, tags=(), kind: str = "other",
                      parent_id: int | None = None) -> int:
    """An empty virtual portfolio for a strategy's runs; `parent_id` is the real portfolio it replays, if any."""
    p = {"name": name, "mode": "virtual", "origin": "sim", "kind": kind, "strategy": strategy, "params": params or {},
         "tags": list(tags)}
    return userstore.save_portfolio(p | ({"parent_id": parent_id} if parent_id is not None else {}))


def find_sim(parent_id: int, strategy: str) -> dict | None:
    """The simulated portfolio that replays `parent_id` with `strategy` (found by those, so a rename keeps it)."""
    return next((p for p in userstore.portfolios() if p["origin"] == "sim" and p.get("parent_id") == parent_id
                 and p.get("strategy") == strategy), None)


def check_rows(rows: list[dict], market, dividends: str = "reinvested") -> list[str]:
    """Everything wrong with a run's rows taken together: unknown types or fields, sales beyond what was held,
    cash going negative, trades without a DKK rate."""
    problems = []
    for i, r in enumerate(rows):
        if r.get("type") not in SIM_TYPES:
            problems.append(f"row {i}: type {r.get('type')!r} (allowed: {', '.join(SIM_TYPES)})")
        elif r["type"] in ("BUY", "SELL") and not (r.get("symbol") and (r.get("quantity") or 0) > 0 and (r.get("price") or 0) > 0):
            problems.append(f"row {i}: a trade needs symbol, quantity and price")
        elif r["type"] not in ("BUY", "SELL") and not (r.get("amount") or 0) > 0:
            problems.append(f"row {i}: a cash row needs an amount")
        if r.get("id") is not None:
            problems.append(f"row {i}: has an id (rows are stored new)")
    if problems:
        return problems
    trades = pd.DataFrame([r for r in rows if r["type"] in ("BUY", "SELL")], columns=universe.TX_COLS)
    if not trades.empty:
        trades["date"] = pd.to_datetime(trades["date"])
        _, warn = universe.positions(trades.assign(fee=trades["fee"].fillna(0)))
        problems += [f"{s}: {w}" for s, ws in warn.items() for w in ws]
    bal, fx_problems = performance.cash_balance(rows, market, dividends)
    problems += fx_problems
    if len(bal) and bal.min() < -0.5:
        problems.append(f"cash goes negative: {bal.min():,.0f} DKK on {bal.idxmin():%Y-%m-%d}")
    return problems


def write_run(pid: int, strategy: str, params: dict, start, end, rows: list[dict], market, message: str | None = None) -> dict:
    """Check a run's rows and store them in simulated portfolio `pid`, replacing its previous run. Raises
    ValueError (nothing stored) when the portfolio isn't a simulation or the rows don't add up."""
    p = userstore.get_portfolio(pid)
    if not p or p["mode"] != "virtual" or p["origin"] != "sim":
        raise ValueError("simulated runs go only into a virtual portfolio made for simulations (new_sim_portfolio)")
    rows = [dict(r, fee=r.get("fee") or 0.0, currency="DKK" if r["type"] not in ("BUY", "SELL") else None)
            for r in sorted(rows, key=lambda r: str(r["date"])[:10])]
    problems = check_rows(rows, market, p["dividends"])
    if problems:
        raise ValueError("; ".join(problems[:5]))
    asof = performance.benchmark_sessions(market)[-1].date().isoformat()
    run_id = userstore.replace_sim_run(pid, {"strategy": strategy, "params": params, "start": start, "end": end,
                                             "data_asof": asof, "message": message}, rows)
    perf = performance.portfolio_performance(pid, market)
    return {"run_id": run_id, "rows": len(rows), "stats": perf["stats"] if perf else None}


def run(strategy: Strategy, pid: int, start, end, capital_dkk: float, market, params: dict | None = None) -> dict:
    """Let `strategy` produce its rows for the period and store them as a run of portfolio `pid`."""
    params = params or {}
    rows = strategy.rows(market, pd.Timestamp(start), pd.Timestamp(end), capital_dkk, params)
    return write_run(pid, strategy.key, params, start, end, rows, market)


def basket_rows(market, weights: dict[str, float], day: pd.Timestamp, capital: float, fee_bps: float) -> tuple[list[dict], list[str]]:
    """A deposit of `capital` DKK and a buy of each name for its weight at `day`'s traded close (or the last one
    in the 7 days before), paying the fee. Names without a price or DKK rate are left out (listed); the rest keep
    their weights, so some cash stays uninvested."""
    ds = day.date().isoformat()
    rows = [{"date": ds, "type": "DEPOSIT", "amount": float(capital), "currency": "DKK", "note": "basket capital"}]
    problems = []
    for t, w in weights.items():
        b = market.bars(t) if t in market.closes.columns else pd.DataFrame()
        col = "raw_close" if "raw_close" in b else "close"
        s = b[col].dropna()[:day] if len(b) else pd.Series(dtype=float)
        fx = performance.fx_series(market, t)
        rate = money.rate_on(fx, day)
        if not len(s) or (day - s.index[-1]).days > 7:
            problems.append(f"{t}: no traded price by {ds}")
            continue
        if rate is None:
            problems.append(f"{t}: no DKK rate on {ds}")
            continue
        px = float(s.iloc[-1])
        qty = w * capital / (px * rate * (1 + money.bps(fee_bps)))
        rows.append({"symbol": t, "date": ds, "type": "BUY", "quantity": qty, "price": px,
                     "fee": qty * px * money.bps(fee_bps), "fx_rate": rate, "note": f"basket: {w:.1%}"})
    return (rows if len(rows) > 1 else []), problems
