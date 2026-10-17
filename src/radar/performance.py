"""Portfolio returns over time, in DKK, against ACWI: a value series per portfolio, its time-weighted (TWR) and
money-weighted (MWR / XIRR) return, and ACWI with the same cash flows, for real and virtual portfolios (A/B tests)
alike.

The method: guide/laerebog/twr-og-mwr.md; the conventions (calendar, funding, dividends, gaps):
docs/data-conventions.md, *Returns over time*.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import fxrates, money, tracked
from .signals.risk import annualised_vol, deepest_drawdown
from .userstore import TRADE_TYPES

EXTERNAL = {"DEPOSIT": 1.0, "WITHDRAW": -1.0}
INCOME = {"DIVIDEND": 1.0, "INTEREST": 1.0, "FEE": -1.0}
EPS = 1e-6
PERIODS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252}
MIN_MWR_DAYS = 365         # an annual rate from a few weeks is mostly noise


# ---------------- cash ----------------

def fx_series(market, symbol: str | None) -> pd.Series | None:
    """DKK per unit of the symbol's quoted price (None when the currency or its rate is unknown)."""
    if not symbol:
        return None
    return fxrates.fx_to_dkk(market.closes, fxrates.currencies([symbol]).get(symbol))


def trade_fx(row: dict, fx: pd.Series | None) -> float | None:
    """The DKK rate a trade was booked at: its own fx_rate, else Yahoo's rate that day (last one before)."""
    if row.get("fx_rate"):
        return float(row["fx_rate"])
    return money.rate_on(fx, row["date"])


def trade_cash_dkk(row: dict, fx: pd.Series | None) -> float | None:
    """A trade's effect on cash, in DKK: a buy pays price × quantity + fee, a sale receives it minus the fee."""
    rate = trade_fx(row, fx)
    if rate is None:
        return None
    gross, fee = float(row["quantity"]) * float(row["price"]), float(row.get("fee") or 0)
    return -(gross + fee) * rate if row["type"] == "BUY" else (gross - fee) * rate


def has_ledger(rows: list[dict]) -> bool:
    """Does this portfolio keep a cash ledger (any deposit or withdrawal)?"""
    return any(r["type"] in EXTERNAL for r in rows)


def cash_moves(rows: list[dict], market, dividends: str = "reinvested") -> tuple[list[dict], list[dict]]:
    """Each row's effect on cash (DKK) and whether it is an external flow, oldest first; plus problems (a trade
    whose DKK rate is unknown: {date, message}). DIVIDEND rows only move cash under the `cash` dividend policy."""
    fx_cache: dict[str, pd.Series | None] = {}
    out, problems = [], []
    for r in sorted(rows, key=lambda r: (str(r["date"])[:10], r.get("id") or 0)):
        t, day = r["type"], pd.Timestamp(str(r["date"])[:10])
        if t in EXTERNAL:
            out.append({"date": day, "cash": EXTERNAL[t] * float(r["amount"]), "external": True, "row": r})
        elif t in INCOME:
            if t == "DIVIDEND" and dividends != "cash":
                continue
            out.append({"date": day, "cash": INCOME[t] * float(r["amount"]), "external": False, "row": r})
        elif t in TRADE_TYPES:
            sym = r["symbol"]
            if sym not in fx_cache:
                fx_cache[sym] = fx_series(market, sym)
            c = trade_cash_dkk(r, fx_cache[sym])
            if c is None:
                problems.append({"date": day, "message": f"{sym} on {day:%Y-%m-%d}: no DKK rate for its currency"})
                continue
            out.append({"date": day, "cash": c, "external": False, "row": r})
    return out, problems


def cash_balance(rows: list[dict], market, dividends: str = "reinvested") -> tuple[pd.Series, list[str]]:
    """Cash in DKK at the end of each day with a cash row (cumulative), and problems (unknown DKK rates)."""
    moves, problems = cash_moves(rows, market, dividends)
    messages = [p["message"] for p in problems]
    if not moves:
        return pd.Series(dtype=float), messages
    s = pd.Series([m["cash"] for m in moves], index=[m["date"] for m in moves]).groupby(level=0).sum().cumsum()
    return s, messages


# ---------------- value and flows ----------------

@dataclass
class Book:
    """One portfolio's (or a pool's) daily series on the benchmark calendar."""
    dates: pd.DatetimeIndex
    value: pd.Series                # DKK at each close; NaN = unknown (gap)
    holdings: pd.Series
    cash: pd.Series
    inflow: pd.Series               # external money in, at the start of each day
    outflow: pd.Series              # external money out, at the end of each day
    breaks: pd.Series               # the chain restarts here: an opening, or a flow whose DKK value is unknown
    funding: str                    # ledger | implicit | mixed
    dividends: str
    missing: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _session(idx: pd.DatetimeIndex, day: pd.Timestamp) -> int | None:
    i = int(idx.searchsorted(day))
    return i if i < len(idx) else None


def benchmark_sessions(market) -> pd.DatetimeIndex:
    """The trading days: the sessions the benchmark has a close on."""
    return market.closes[tracked.benchmark()].dropna().index


def book(rows: list[dict], market, dividends: str = "reinvested") -> Book | None:
    """The daily value of one portfolio's rows in DKK, with its external flows. None without any rows.

    Rows from before the price history (settings: history_years) can't be valued on their dates: the series then
    opens on the first day the whole portfolio can be valued, from what was held then (as money put in that
    day). Without a cash ledger, a trade whose DKK rate is unknown breaks the chain on its day (that day's
    return is left out, and said so); with a ledger the cash, and so the value, stays unknown from then on."""
    rows = [r for r in rows if r["type"] in TRADE_TYPES or r["type"] in EXTERNAL or r["type"] in INCOME]
    if not rows:
        return None
    cal = benchmark_sessions(market)
    first_row = pd.Timestamp(min(str(r["date"])[:10] for r in rows))
    idx = cal[cal >= first_row]
    if idx.empty:
        return None
    pre = first_row < cal[0]                      # some rows are older than the price history
    notes, missing = [], []
    funding = "ledger" if has_ledger(rows) else "implicit"

    # holdings: shares (dividend-scaled under `reinvested`) per symbol, valued at each close in DKK
    closes, raw = market.closes, market.raw_closes()
    holdings = pd.Series(0.0, index=idx)
    unknown = pd.Series(False, index=idx)
    late = 0
    by_symbol: dict[str, list[dict]] = {}
    for r in rows:
        if r["type"] in TRADE_TYPES:
            by_symbol.setdefault(r["symbol"], []).append(r)
    for sym, lots in sorted(by_symbol.items()):
        px = closes[sym] if sym in closes else None
        rpx = raw[sym] if raw is not None and sym in raw else None
        fx = fx_series(market, sym)
        if dividends == "cash" and rpx is not None:
            px = rpx
        factor = (closes[sym] / rpx).dropna() if dividends != "cash" and px is not None and rpx is not None else None
        units = pd.Series(0.0, index=idx)
        qty = u = 0.0
        for r in sorted(lots, key=lambda r: (str(r["date"])[:10], r.get("id") or 0)):
            i = _session(idx, pd.Timestamp(str(r["date"])[:10]))
            if i is None:
                late += 1
                continue
            q = float(r["quantity"])
            if r["type"] == "SELL":
                if qty <= EPS:
                    continue
                keep = 1 - min(q, qty) / qty
                qty, u = qty * keep, u * keep
            else:
                f = factor.asof(pd.Timestamp(str(r["date"])[:10])) if factor is not None and not factor.empty else np.nan
                if not (np.isfinite(f) and f > 0):      # before the price history: from its first factor
                    f = factor.iloc[0] if factor is not None and not factor.empty else 1.0
                qty, u = qty + q, u + q / f
            units.iloc[i:] = u if qty > EPS else 0.0
        held = units > EPS
        if not held.any():
            continue
        if px is None or fx is None:
            missing.append(f"{sym}: " + ("no prices" if px is None else "no DKK rate for its currency"))
            unknown |= held
            continue
        val = units * px.reindex(idx) * fx.reindex(idx)
        unknown |= held & val.isna()
        holdings = holdings + val.fillna(0.0)
    if late:
        notes.append(f"{late} row(s) after the last price date are not counted yet")

    # cash and external flows
    moves, problems = cash_moves(rows, market, dividends)
    cash_change = pd.Series(0.0, index=idx)
    ext_in = pd.Series(0.0, index=idx)
    ext_out = pd.Series(0.0, index=idx)
    breaks = pd.Series(False, index=idx)
    for m in moves:
        i = _session(idx, m["date"])
        if i is None:
            continue
        cash_change.iloc[i] += m["cash"]
        if m["external"]:
            (ext_in if m["cash"] > 0 else ext_out).iloc[i] += abs(m["cash"])
    if funding == "ledger":
        if problems:                              # the cash, and so the value, is unknown from then on
            missing += [p["message"] for p in problems]
            unknown.iloc[min(_session(idx, p["date"]) or 0 for p in problems):] = True
        cash = cash_change.cumsum()
        inflow, outflow = ext_in, ext_out
    else:                                         # every buy is new money, every sale or income taken out
        cash = pd.Series(0.0, index=idx)
        inflow, outflow = (-cash_change).clip(lower=0), cash_change.clip(lower=0)
        later = [p for p in problems if not pre or p["date"] >= cal[0]]
        missing += [p["message"] for p in later]
        for p in later:                           # that day's flow is unknown: its return is left out
            if (i := _session(idx, p["date"])) is not None:
                breaks.iloc[i] = True
        if later:
            notes.append(f"{len(later)} day(s) with a trade whose DKK value is unknown are left out of the "
                         "time-weighted return")
    value = (holdings + cash).where(~unknown)
    if pre:                                       # open on the first day everything can be valued
        known = value.dropna()
        k = idx.get_loc(known.index[0]) if len(known) else len(idx)
        inflow.iloc[:k], outflow.iloc[:k] = 0.0, 0.0
        if k < len(idx):
            inflow.iloc[k], outflow.iloc[k], breaks.iloc[k] = float(value.iloc[k]), 0.0, True
            notes.append(f"Prices start on {cal[0]:%Y-%m-%d}: returns are measured from {idx[k]:%Y-%m-%d}, "
                         "starting from what was held then")
    if dividends == "reinvested" and any(r["type"] == "DIVIDEND" for r in rows):
        notes.append("Dividend rows are kept for the record but not counted: adjusted prices already include dividends")
    return Book(idx, value, holdings.where(~unknown), cash, inflow, outflow, breaks, funding, dividends, missing, notes)


def pool(maybe: list[Book | None]) -> Book | None:
    """Several portfolios as one (a tag group): values and flows add up; a gap in any is a gap in the pool."""
    books = [b for b in maybe if b is not None]
    if not books:
        return None
    idx = books[0].dates
    for b in books[1:]:
        idx = idx.union(b.dates)

    def total(attr, fill):
        return sum((getattr(b, attr).reindex(idx).fillna(fill) if fill is not None else
                    getattr(b, attr).reindex(idx)) for b in books)

    value = sum(b.value.reindex(idx).where(idx >= b.dates[0], 0.0) for b in books)
    breaks = sum(b.breaks.reindex(idx).fillna(False).astype(int) for b in books) > 0
    fundings = {b.funding for b in books}
    return Book(idx, value, total("holdings", None), total("cash", 0.0), total("inflow", 0.0), total("outflow", 0.0),
                breaks, fundings.pop() if len(fundings) == 1 else "mixed",
                books[0].dividends if len({b.dividends for b in books}) == 1 else "mixed",
                [m for b in books for m in b.missing], [n for b in books for n in b.notes])


# ---------------- returns ----------------

def twr(value: pd.Series, inflow: pd.Series, outflow: pd.Series, opening: bool = False,
        breaks: pd.Series | None = None) -> pd.Series:
    """The time-weighted index: 100 before the first day, or (`opening`) 100 at the first day's close, starting
    from the value held then. None on gap days and days without capital. On a break the chain restarts from
    that close (100 if nothing came before; else that day's return is left out and shown as None)."""
    level, prev, acc_in, acc_out = 100.0, 0.0, 0.0, 0.0
    started, pending = False, opening
    brk = breaks.to_numpy() if breaks is not None else np.zeros(len(value), dtype=bool)
    out = []
    for v, i, o, b in zip(value.to_numpy(), inflow.to_numpy(), outflow.to_numpy(), brk):
        acc_in, acc_out = acc_in + i, acc_out + o
        pending = pending or bool(b)
        if not np.isfinite(v):
            out.append(np.nan)
            continue
        base = prev + acc_in
        if pending or (base <= EPS and v > EPS):  # restart the chain from this close
            out.append(np.nan if started else level)
            started, pending = True, False
        elif base > EPS:
            level *= (v + acc_out) / base
            out.append(level)
            started = True
        else:                                     # no capital: no return
            out.append(np.nan)
        prev, acc_in, acc_out = v, 0.0, 0.0
    return pd.Series(out, index=value.index)


def xirr(dates: list[pd.Timestamp], amounts: list[float]) -> float | None:
    """The annual rate r with Σ amount / (1+r)^(days/365) = 0 (amounts from the investor's side: money in
    negative, money out and the final value positive). None when it can't be pinned down."""
    if len(amounts) < 2 or not any(a < 0 for a in amounts) or not any(a > 0 for a in amounts):
        return None
    t0 = min(dates)
    years = np.array([(d - t0).days / 365.0 for d in dates])
    a = np.array(amounts, dtype=float)
    npv = lambda r: float(np.sum(a / (1 + r) ** years))  # noqa: E731
    lo, hi = -0.9999, 1.0
    while npv(hi) > 0 and hi < 1e6:
        hi *= 2
    f_lo, f_hi = npv(lo), npv(hi)
    if not (np.isfinite(f_lo) and np.isfinite(f_hi)) or f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f = npv(mid)
        if abs(f) < 1e-9 * np.abs(a).sum():
            break
        lo, hi = (mid, hi) if f * f_lo > 0 else (lo, mid)
    return mid


def _mwr(dates: pd.DatetimeIndex, inflow: pd.Series, outflow: pd.Series, final_value: float | None) -> float | None:
    if final_value is None or not np.isfinite(final_value) or (dates[-1] - dates[0]).days < MIN_MWR_DAYS:
        return None
    flows = (outflow - inflow)
    ds, am = [d for d, f in flows.items() if abs(f) > EPS], [f for f in flows if abs(f) > EPS]
    return xirr(ds + [dates[-1]], am + [final_value])


def bench_dkk(market) -> pd.Series:
    b = tracked.benchmark()
    px = market.closes[b].dropna()
    fx = fxrates.fx_to_dkk(market.closes, fxrates.currencies([b])[b])
    return (px * fx.reindex(px.index).ffill()).dropna() if fx is not None else pd.Series(dtype=float)


def same_flows(inflow: pd.Series, outflow: pd.Series, bench: pd.Series) -> tuple[pd.Series, str | None]:
    """The value of putting the same external flows into ACWI at each day's close; stops (NaN) if a withdrawal
    is larger than the ACWI holding at that point."""
    b = bench.reindex(inflow.index).ffill()
    units, out, note = 0.0, [], None
    for d, i, o in zip(inflow.index, inflow.to_numpy(), outflow.to_numpy()):
        if note or not np.isfinite(b[d]):
            out.append(np.nan)
            continue
        units += (i - o) / b[d]
        if units < -EPS:
            note = f"ACWI with the same cash flows stops on {d:%Y-%m-%d}: a withdrawal larger than its value"
            out.append(np.nan)
            continue
        out.append(max(units, 0.0) * b[d])
    return pd.Series(out, index=inflow.index), note


def _last(s: pd.Series) -> float | None:
    s = s.dropna()
    return float(s.iloc[-1]) if len(s) else None


def _period(index: pd.Series, n: int | None = None, since: pd.Timestamp | None = None,
            value: pd.Series | None = None) -> float | None:
    """The index's return over the last `n` sessions, or since a date. None when either end is unknown (a gap,
    or not that much history): a lookback never skips across a gap. A day without capital (value 0) is known
    and flat: it starts from the level before it."""
    if index.empty or not np.isfinite(index.iloc[-1]):
        return None
    if since is not None:
        pos = int(index.index.searchsorted(since)) - 1
        if pos < 0:
            return float(index.iloc[-1] / 100 - 1) if index.dropna().index[0] >= since else None
    else:
        assert n is not None, "a period needs n or since"
        pos = len(index) - 1 - n
        if pos < 0:
            return None
    start = index.iloc[pos]
    if not np.isfinite(start) and value is not None and np.isfinite(value.iloc[pos]) and abs(value.iloc[pos]) <= EPS:
        before = index.iloc[:pos].dropna()
        start = before.iloc[-1] if len(before) else 100.0
    return float(index.iloc[-1] / start - 1) if np.isfinite(start) and start > 0 else None


def _max_drawdown(index: pd.Series) -> float | None:
    s = index.dropna()
    return deepest_drawdown(s) if len(s) else None


def _vol(index: pd.Series) -> float | None:
    r = index.pct_change(fill_method=None).dropna()
    return annualised_vol(r) if len(r) > 20 else None


def analyze(b: Book, market, start=None, end=None) -> dict:
    """Series and statistics for one book, optionally over a window (`start` rebases the index to 100)."""
    bench = bench_dkk(market)
    end = pd.Timestamp(end) if end else None
    sl = slice(pd.Timestamp(start) if start else None, end)
    value, inflow, outflow = b.value.loc[sl], b.inflow.loc[sl].copy(), b.outflow.loc[sl].copy()
    notes = list(b.notes)
    opening = False
    if start and b.value.loc[:pd.Timestamp(start)].notna().any():    # a window on a portfolio that already
        s0 = b.value.index[b.value.index >= pd.Timestamp(start)]     # existed: it starts from its value at
        s0 = s0[0] if len(s0) else b.value.index[-1]                 # that close, as if put in then
        known = b.value.loc[s0:].dropna()
        if len(known) and known.iloc[0] > EPS:
            if known.index[0] > s0:
                notes.append(f"No complete value on {s0:%Y-%m-%d} (a price missing): measured from "
                             f"{known.index[0]:%Y-%m-%d}")
            sl = slice(known.index[0], end)
            value, inflow, outflow = b.value.loc[sl], b.inflow.loc[sl].copy(), b.outflow.loc[sl].copy()
            inflow.iloc[0], outflow.iloc[0], opening = float(known.iloc[0]), 0.0, True
            notes = [n for n in notes if not n.startswith("Prices start")]  # the window opens later anyway
    brk = b.breaks.reindex(value.index).fillna(False).astype(bool)
    index = twr(value, inflow, outflow, opening, brk)
    known = index.dropna()
    mid = brk[known.index[0]:].iloc[1:] if len(known) else brk.iloc[0:0]
    unknown_flow = mid[mid].index[0] if mid.any() else None   # a flow of unknown size: no money-weighted figures
    sf, sf_note = same_flows(inflow, outflow, bench)
    if unknown_flow is not None:
        sf = sf.where(sf.index < unknown_flow)
        sf_note = sf_note or f"ACWI with the same cash flows stops on {unknown_flow:%Y-%m-%d}: a flow's DKK value is unknown"
    if sf_note:
        notes.append(sf_note)
    first = index.dropna().index[0] if index.notna().any() else None
    b_index = (100 * bench / bench.asof(first)).reindex(value.index) if first is not None else pd.Series(np.nan, index=value.index)
    final = _last(value)
    days = (value.index[-1] - first).days if first is not None else 0
    tot = float(index.dropna().iloc[-1] / 100 - 1) if index.notna().any() else None
    btot = float(b_index.dropna().iloc[-1] / 100 - 1) if b_index.notna().any() else None
    ann = lambda r: ((1 + r) ** (365 / days) - 1) if r is not None and days >= 365 else None  # noqa: E731
    ytd = pd.Timestamp(year=value.index[-1].year, month=1, day=1) if len(value) else None
    periods = {}
    for k, n in PERIODS.items():
        periods[k] = {"portfolio": _period(index, n, value=value), "acwi": _period(b_index, n)}
    periods["ytd"] = {"portfolio": _period(index, since=ytd, value=value), "acwi": _period(b_index, since=ytd)}
    periods["since_start"] = {"portfolio": tot, "acwi": btot}
    stats = {
        "start": first.date().isoformat() if first is not None else None,
        "days": days, "value_dkk": final, "invested_dkk": float((inflow - outflow).sum()),
        "twr_total": tot, "twr_ann": ann(tot), "mwr_ann": None if unknown_flow is not None else _mwr(value.index, inflow, outflow, final),
        "acwi_twr_total": btot, "acwi_twr_ann": ann(btot),
        "acwi_mwr_ann": None if unknown_flow is not None else _mwr(value.index, inflow, outflow, _last(sf)),
        "excess_twr": tot - btot if tot is not None and btot is not None else None,
        "max_drawdown": _max_drawdown(index), "vol_ann": _vol(index), "periods": periods,
    }
    nan = lambda s: [None if not np.isfinite(x) else round(float(x), 6) for x in s.to_numpy()]  # noqa: E731
    gaps = int((value.isna() & (value.index >= first)).sum()) if first is not None else 0
    if gaps:
        notes.append(f"{gaps} day(s) without a complete value (a price or DKK rate missing) are left as gaps")
    if b.funding == "implicit":
        notes.append("No cash ledger: every buy counts as new money and every sale as money taken out")
    return {
        "funding": b.funding, "dividends": b.dividends, "missing": b.missing, "notes": notes, "stats": stats,
        "series": {"dates": [d.date().isoformat() for d in value.index], "value_dkk": nan(value),
                   "cash_dkk": nan(b.cash.loc[sl]), "invested_dkk": nan((inflow - outflow).cumsum()),
                   "index": nan(index), "acwi_index": nan(b_index), "acwi_same_flows_dkk": nan(sf)},
    }


# ---------------- per portfolio, and comparisons (A/B) ----------------

_cache: dict = {}


def reset() -> None:
    """Forget the cached portfolio books."""
    _cache.clear()


def portfolio_book(p: dict, market) -> Book | None:
    """The book (daily DKK value, flows) of one portfolio from the store, with its dividend policy."""
    from . import userstore

    return book(userstore.transactions(portfolios=[p["id"]]), market, p["dividends"])


def _cached(key, fn):
    if key not in _cache:
        if len(_cache) > 64:
            _cache.clear()
        _cache[key] = fn()
    return _cache[key]


def _identity(p: dict) -> dict:
    return {k: p[k] for k in ("id", "name", "mode", "kind", "tags", "archived")}


def portfolio_performance(pid: int, market, start=None, end=None) -> dict | None:
    """One portfolio's value, TWR/MWR and the same for ACWI (None if there is no such portfolio)."""
    from . import userstore

    p = userstore.get_portfolio(pid)
    if not p:
        return None

    def run():
        b = portfolio_book(p, market)
        out = analyze(b, market, start, end) if b is not None else _empty()
        return out | {"portfolio": _identity(p), "asof": _asof(market)}
    return _cached(("one", pid, start, end, market.mtime, userstore.transactions_version()), run)


def _asof(market) -> str:
    return market.closes[tracked.benchmark()].dropna().index[-1].date().isoformat()


def _empty() -> dict:
    return {"funding": "implicit", "dividends": "reinvested", "missing": [], "notes": ["No rows yet."], "stats": None,
            "series": {k: [] for k in ("dates", "value_dkk", "cash_dkk", "invested_dkk", "index", "acwi_index",
                                       "acwi_same_flows_dkk")}}


def compare(market, ids: list[int] | None = None, tags: list[str] | None = None, start=None) -> dict:
    """Portfolios (by id) and tag groups (each pooled into one line) side by side from a common start (the
    latest first day among them, or `start`), every index rebased to 100 there, with ACWI as the yardstick."""
    from . import userstore

    def run() -> dict:
        lines: list[tuple[dict, Book | None]] = []
        for pid in ids or []:
            p = userstore.get_portfolio(pid)
            if p:
                lines.append(({"kind": "portfolio", "label": p["name"], "portfolio": _identity(p)}, portfolio_book(p, market)))
        for tag in tags or []:
            t = userstore.norm_tag(tag)
            members = [p for p in userstore.portfolios() if t in p["tags"]]
            lines.append(({"kind": "tag", "label": f"#{t}", "tag": t, "members": [m["name"] for m in members]},
                          pool([portfolio_book(m, market) for m in members])))
        firsts = []
        for _, b in lines:
            if b is not None:
                idx = twr(b.value, b.inflow, b.outflow).dropna()
                if len(idx):
                    firsts.append(idx.index[0])
        common = pd.Timestamp(start) if start else (max(firsts) if firsts else None)
        rows, series = [], []
        for meta, b in lines:
            res = analyze(b, market, common) if b is not None else _empty()
            rows.append(meta | {"funding": res["funding"], "stats": res["stats"], "notes": res["notes"],
                                "missing": res["missing"]})
            s = res["series"]
            series.append({"name": meta["label"], "dates": s["dates"], "values": s["index"]})
        bench = bench_dkk(market)
        if common is not None and len(bench.loc[common:]):
            b = bench.loc[common:]
            series.append({"name": "ACWI (DKK)", "dates": [d.date().isoformat() for d in b.index],
                           "values": [round(float(x), 6) for x in 100 * b / b.iloc[0]]})
        return {"asof": _asof(market), "start": common.date().isoformat() if common is not None else None,
                "rows": rows, "chart": {"title": "Growth of 100 (time-weighted, DKK)", "decimals": 1, "hlines": [100.0],
                                        "series": series}}
    return _cached(("cmp", tuple(ids or ()), tuple(tags or ()), start, market.mtime, userstore.transactions_version()), run)


SUMMARY_PERIODS = ("1m", "3m", "ytd", "1y")


def summary(market) -> list[dict]:
    """Your real portfolios' returns for summary.json (the skills read it): per portfolio its tax kind, tags,
    funding, value and time-weighted returns over 1m/3m/YTD/1y and since its start, each next to ACWI's."""
    from . import userstore

    out = []
    for p in userstore.portfolios(include_archived=False):
        if p["mode"] != "real" or not p["n_tx"]:
            continue
        res = portfolio_performance(p["id"], market)
        if res is None:
            continue
        st = res["stats"] or {}
        per = st.get("periods") or {}
        row = {"name": p["name"], "kind": p["kind"], "tags": p["tags"], "funding": res["funding"],
               "start": st.get("start"), "value_dkk": st.get("value_dkk"),
               "twr_total": st.get("twr_total"), "acwi_twr_total": st.get("acwi_twr_total"), "mwr_ann": st.get("mwr_ann")}
        for k in SUMMARY_PERIODS:
            row[f"twr_{k}"] = (per.get(k) or {}).get("portfolio")
            row[f"acwi_{k}"] = (per.get(k) or {}).get("acwi")
        row["notes"] = res["notes"] + res["missing"]
        out.append(row)
    return out


def return_on_paid_in(rows: list[dict], market, end: pd.Timestamp) -> float | None:
    """The return of trade rows on the money paid in, valued at `end`; None when their book doesn't reach `end` or
    nothing went in."""
    rows = [dict(r, fee=r.get("fee") or 0.0, currency="DKK" if r["type"] not in ("BUY", "SELL") else None) for r in rows]
    b = book(rows, market)
    if b is None:
        return None
    v = b.value.loc[:end].dropna()
    if not len(v) or v.index[-1] != end:
        return None
    ext = float((b.inflow - b.outflow).loc[:end].sum())
    return float(v.iloc[-1] / ext - 1) if ext > 0 else None
