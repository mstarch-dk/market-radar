"""Attribution vs ACWI: why a selection of portfolios beat or lagged ACWI over a period, in DKK, and whether what's
left looks like skill.

It assembles: the portfolios' daily books (portfolios/performance.py, the same as *Returns*), each holding's class
and segment (portfolios/exposure.py, the same as the X-ray), ACWI's segment weights and the proxies' returns
(portfolios/segments.py), and the math in model/attribution.py: Brinson–Fachler per day by sector and by region on
local returns, the currency effect in DKK and the cross term, Carino's linking to months and to the period, and the
factor regression on French's developed factors. No math of its own. Computed live, nothing written.

Every figure says what it rests on: benchmark segments are proxy ETFs, past weights before the first weekly snapshot
are back-drifted, today's classification is used for past days, and a day with a missing price, proxy or weight is
left out (counted, never a 0 % return). The method: plans/F4-attribution.md. Analysis, not advice."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from . import userstore
from .config import typed
from .model import attribution as at
from .model import stats
from .portfolios import exposure, performance, segments
from .portfolios.prices import Prices
from .signals.risk import weekly
from .sources import constituents, factors, fxrates, tracked
from .values import num

if TYPE_CHECKING:
    from .market import Market

CASH = "cash"
UNCLASSIFIED = "unclassified"
UNKNOWN_CCY = "unknown"      # value whose currency isn't known: its whole return counts as local
EFFECTS = (*at.EFFECTS, "currency", "cross")
DAYS_PER_MONTH = 365.25 / 12
_cache: dict[tuple, dict] = {}


# ---------------- inputs ----------------

def _returns(prices: Prices, tickers, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Daily DKK returns of `tickers` on `dates` (NaN where a close is unknown)."""
    return pd.DataFrame({t: segments.daily_returns(prices, t, dates) for t in tickers}, index=dates)


def _fx(market: Market, currencies, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Each currency's daily return against DKK (DKK itself: 0; no rate: NaN, and the currency is missing)."""
    cols = {}
    for c in currencies:
        if c == UNKNOWN_CCY:
            cols[c] = pd.Series(0.0, index=dates)   # by definition: unknown currency, whole return local
            continue
        fx = fxrates.fx_to_dkk(market.closes, c)
        px = fx.reindex(dates) if fx is not None else pd.Series(np.nan, index=dates)
        cols[c] = px / px.shift(1) - 1
    return pd.DataFrame(cols, index=dates)


def _key(meta: pd.DataFrame, t: str, dim: str) -> str:
    """A holding's segment in `dim` when it has one of its own (a stock, a sector fund's sector), else unclassified."""
    k = meta.at[t, dim] if t in meta.index else None
    return k if isinstance(k, str) and k and k not in exposure.UNCOVERED and k != exposure.WORLD else UNCLASSIFIED


def _portfolio_segments(dim: str, w: pd.DataFrame, r: pd.DataFrame, meta: pd.DataFrame, wb: pd.DataFrame,
                        rb: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The portfolio's segment weights and returns per day from its holdings' weights `w` (at the previous close)
    and returns `r`. A world fund is spread with ACWI's weights `wb`, an index fund with its index's weights, a fund
    with sector weights by them (sector only); each slice gets the segment's benchmark return `rb` plus the fund's
    own difference to that mix, so the slices add up to the fund's return. Everything else sits in its own segment
    or in `unclassified`."""
    wseg: dict[str, pd.Series] = {}
    contrib: dict[str, pd.Series] = {}
    big_rb = (wb * rb).sum(axis=1, min_count=1)

    def add(seg: str, weight: pd.Series, ret: pd.Series) -> None:
        held = weight > 0
        wseg[seg] = wseg.get(seg, 0.0) + weight
        contrib[seg] = contrib.get(seg, 0.0) + (weight * ret).where(held, 0.0)   # zero: not held that day

    for t in w.columns:
        cls = meta.at[t, "class"] if t in meta.index else "unknown"
        spread = meta.at[t, f"{dim}_weights"] if t in meta.index else None
        if cls == "world":
            shares = wb
        elif cls in ("fund_sectors", "index_fund") and isinstance(spread, dict) and spread:
            shares = pd.DataFrame({k: v for k, v in spread.items()}, index=w.index)
            rest = 1 - sum(spread.values())
            if rest > 1e-9:
                shares[UNCLASSIFIED] = rest
        else:
            add(_key(meta, t, dim), w[t], r[t])
            continue
        base = pd.DataFrame({k: rb[k] if k in rb else big_rb for k in shares.columns}, index=w.index)
        gap = r[t] - (shares * base).sum(axis=1, min_count=1)
        for k in shares.columns:
            add(k, w[t] * shares[k], base[k] + gap)
    wp = pd.DataFrame(wseg, index=w.index).fillna(0.0)   # zero: a segment nobody holds that day
    rp = pd.DataFrame({k: contrib[k] / wseg[k] for k in wseg}, index=w.index).where(wp > 0)
    return wp, rp


def _currency_weights(w: pd.DataFrame, cash_w: pd.Series, meta: pd.DataFrame, acwi_ccy: pd.DataFrame
                      ) -> pd.DataFrame:
    """The portfolio's value shares by currency per day: a stock its quote currency, a world fund ACWI's currency
    mix, an index fund its index's mix (or its hedge currency), a US sector fund USD, cash DKK; a fund not looked
    through `unknown`."""
    out: dict[str, pd.Series] = {"DKK": cash_w.copy()}
    for t in w.columns:
        cls = meta.at[t, "class"] if t in meta.index else "unknown"
        if cls == "world":
            for c in acwi_ccy.columns:
                out[c] = out.get(c, 0.0) + w[t] * acwi_ccy[c]
            continue
        if isinstance(mix := _ccy_mix(meta, t), dict):
            for c, x in mix.items():
                out[c] = out.get(c, 0.0) + w[t] * x
            continue
        c = meta.at[t, "currency"] if t in meta.index else None
        c = c if isinstance(c, str) and c and c not in exposure.UNCOVERED and c != exposure.WORLD else UNKNOWN_CCY
        out[c] = out.get(c, 0.0) + w[t]
    return pd.DataFrame(out, index=w.index).fillna(0.0)   # zero: a currency nobody holds that day


def _ccy_mix(meta: pd.DataFrame, t: str) -> dict[str, float] | None:
    """An index fund's fixed currency mix (its index's, or its hedge currency), None for anything else."""
    mix = meta.at[t, "currency_weights"] if t in meta.index else None
    return mix if isinstance(mix, dict) and mix else None


def _mix_return(mix: pd.DataFrame, fx: pd.DataFrame) -> pd.Series:
    """The DKK return of a currency mix (rows sum to 1), NaN when a currency with weight has no rate."""
    f = fx.reindex(columns=mix.columns)
    bad = ((mix > 0) & f.isna()).any(axis=1)
    return (mix * f.fillna(0.0)).sum(axis=1).mask(bad)   # zero: masked when it would matter


def _covered(weights: pd.DataFrame, fx: pd.DataFrame) -> tuple[pd.DataFrame, float | None]:
    """ACWI's currency weights restricted to the currencies with a DKK rate, renormalised; and the share left out
    (minor currencies without a Yahoo rate), largest over the days."""
    ok = [c for c in weights.columns if c in fx and fx[c].notna().any()]
    kept = weights[ok]
    total = kept.sum(axis=1)
    left = float((1 - total).max()) if len(total) else None
    return kept.div(total.where(total > 0), axis=0), left


def _benchmark(dim: str, prices: Prices, dates: pd.DatetimeIndex, history: pd.DataFrame
               ) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, list[str]]:
    """ACWI's segment weights at each close (with the basis) and the segments' daily DKK returns, with notes."""
    notes: list[str] = []
    if dim == "sector":
        rb, notes = segments.sector_returns(prices, dates)
    else:
        cw = segments.stepped_weights(segments.snapshots(history, "region_country"), dates)
        rb, cover = segments.region_returns(prices, dates, cw)
        least = typed().attribution.min_proxy_coverage
        low = [r for r in cover if (cover[r] < least).any()]
        if low:
            notes.append(f"Region return missing on days where its country ETFs cover less than {least:.0%} of "
                         f"ACWI's weight there: {', '.join(low)}")
    snaps = segments.snapshots(history, dim)
    keep = [k for k in snaps.columns if k in rb.columns]
    lost = float(snaps.drop(columns=keep).max(axis=1).max()) if len(keep) < len(snaps.columns) else 0.0
    if lost > 0:
        notes.append(f"{dim}: ACWI keys without a proxy (up to {lost:.1%} of ACWI) are left out of its weights")
        snaps = snaps[keep].div(snaps[keep].sum(axis=1), axis=0)
    wb, basis = segments.drifted_weights(snaps, rb, dates)
    return wb, basis, rb, notes


def _weighted(w: pd.DataFrame, r: pd.DataFrame) -> pd.Series:
    """Σ w·r per day; NaN when something with weight has no return (never skipped as 0 %)."""
    bad = ((w > 0) & r.isna()).any(axis=1)
    return (w.fillna(0.0) * r.fillna(0.0)).sum(axis=1).mask(bad)   # zero: masked wherever it would matter


# ---------------- linking ----------------

def _link(days: pd.DataFrame, rp: pd.Series, rb: pd.Series) -> pd.Series:
    return at.link(days, at.carino_weights(rp, rb)) if len(days) else pd.Series(0.0, index=days.columns)


def _dimension(dim: str, frames: dict, valid: pd.Series, basis: pd.Series, tol: float) -> dict:
    """One dimension's linked tables: the period's effects by segment, month by month, and the period's totals."""
    rp, rb = frames["rp"][valid], frames["rb"][valid]
    days = pd.DataFrame({e: frames[e][valid] for e in EFFECTS})
    total = _link(days, rp, rb)
    err = at.linking_error(float(total.sum()), rp, rb) if len(rp) else 0.0
    if err > tol:
        raise RuntimeError(f"{dim}: linked effects miss the active return by {err:.2e} (tolerance {tol:.0e})")
    weights = at.carino_weights(rp, rb) if len(rp) else pd.Series(dtype=float)
    rows = []
    for seg in frames["wp"].columns.union(frames["wb"].columns):
        wp_s, wb_s = frames["wp"][seg][valid] if seg in frames["wp"] else 0.0, frames["wb"][seg][valid]
        eff = {e: float((frames["seg_" + e][seg][valid] * weights).sum()) for e in at.EFFECTS}
        held, bench = frames["rp_seg"][seg][valid].dropna(), frames["rb_seg"][seg][valid].dropna()
        rows.append({"key": seg, "w_p": num(np.mean(wp_s)), "w_b": num(np.mean(wb_s)),
                     "r_p": num(float(np.prod(1 + held) - 1)) if len(held) else None,
                     "r_b": num(float(np.prod(1 + bench) - 1)) if len(bench) else None,
                     **eff, "total": sum(eff.values())})
    rows.sort(key=lambda r: -abs(r["total"]))
    months = []
    for m, idx in rp.groupby(rp.index.to_period("M")).groups.items():
        sub = _link(days.loc[idx], rp.loc[idx], rb.loc[idx])
        b = basis.reindex(idx)
        months.append({"month": str(m), **{e: float(sub[e]) for e in EFFECTS},
                       "active": float(np.prod(1 + rp.loc[idx]) - np.prod(1 + rb.loc[idx])), "days": len(idx),
                       "basis": "back-drifted" if (b == "back-drifted").any() else "snapshot"})
    return {"rows": rows, "months": months, "totals": {e: float(total[e]) for e in EFFECTS},
            "rp": float(np.prod(1 + rp) - 1) if len(rp) else None, "rb": float(np.prod(1 + rb) - 1) if len(rb) else None,
            "days": int(valid.sum()), "linking_error": err}


def _currency_table(cur: dict, wp: pd.DataFrame, wb: pd.DataFrame, fx: pd.DataFrame, valid: pd.Series,
                    rp: pd.Series, rb: pd.Series, sector: dict) -> dict:
    """The currency effect per currency, linked over the sector table's days (the effect is the same in both
    dimensions; the cross term isn't, and the sector one is shown)."""
    weights = at.carino_weights(rp[valid], rb[valid]) if valid.any() else pd.Series(dtype=float)
    rows = []
    for c in cur["effect"].columns:
        eff = float((cur["effect"][c][valid] * weights).sum())
        wp_c = wp[c][valid] if c in wp else pd.Series(0.0, index=valid.index[valid])
        wb_c = wb[c][valid] if c in wb else pd.Series(0.0, index=valid.index[valid])
        if not (wp_c > 0).any() and not (wb_c > 0).any():
            continue
        f = fx[c][valid].dropna() if c in fx else pd.Series(dtype=float)
        rows.append({"currency": c, "w_p": num(float(wp_c.mean())), "w_b": num(float(wb_c.mean())),
                     "fx_return": num(float(np.prod(1 + f) - 1)) if len(f) else None, "effect": eff})
    rows.sort(key=lambda r: -abs(r["effect"]))
    return {"effect": sector["totals"]["currency"], "cross": sector["totals"]["cross"], "rows": rows}


# ---------------- the factor regression ----------------

def _regression(market: Market, index: pd.Series, start: pd.Timestamp, end: pd.Timestamp,
                notes: list[str]) -> dict | None:
    conf = typed().attribution
    five = factors.daily_panel(f"french_daily:{conf.factors.five}")
    mom = factors.daily_panel(f"french_daily:{conf.factors.momentum}")
    if five.empty or mom.empty:
        notes.append("No factor regression: French's daily developed factors aren't downloaded yet (radar run)")
        return None
    rf = stats.daily_rf(market)
    usd = fxrates.fx_to_dkk(market.closes, "USD")
    if rf is None or usd is None:
        notes.append("No factor regression: " + ("the ECB deposit rate (FRED ECBDFR)" if rf is None else
                                                 "the USD/DKK rate") + " is missing")
        return None
    ff = factors.to_weeks(five.join(mom, how="inner"))
    lvl = index.loc[start:end].dropna()
    frame = at.regression_frame(weekly(lvl), ff, weekly(usd.dropna()),
                                (1 + rf).resample("W-FRI").prod(min_count=1) - 1)
    r = at.factor_regression(frame, conf.min_weeks, conf.nw_lag)
    if r is None:
        notes.append(f"No factor regression: {len(frame)} weeks with portfolio and factor data, at least "
                     f"{conf.min_weeks} are needed (the factors run to {five.index[-1]:%Y-%m-%d})")
        return None
    notes.append("Factor regression on French's developed factors in DKK: the market factor converted with USD/DKK, "
                 "the long-short factors taken as currency-neutral; alpha is a measurement, not a forecast")
    return r | {"factors_to": five.index[-1].date().isoformat()}


# ---------------- the view ----------------

def cached(market: Market, ids: list[int] | None = None, scope: str | None = None, start: str | None = None,
           end: str | None = None) -> dict:
    """`build`, kept until a trade or portfolio edit, a price update or a new ACWI snapshot or factor file."""
    ids = userstore.portfolio_ids() if ids is None else ids
    stamps = tuple(p.stat().st_mtime if p.exists() else 0 for p in (constituents.SEGMENTS_FILE, factors.DAILY_FILE))
    key = (tuple(ids), scope, start, end, market.mtime, userstore.transactions_version(), stamps)
    if key not in _cache:
        if len(_cache) > 32:
            _cache.clear()
        _cache[key] = build(market, ids, scope, start, end)
    return _cache[key]


def reset() -> None:
    _cache.clear()


def build(market: Market, ids: list[int] | None = None, scope: str | None = None, start: str | None = None,
          end: str | None = None) -> dict:
    """The attribution of these portfolios (None: your real ones) vs ACWI over [start, end] (default: their whole
    history)."""
    conf = typed().attribution
    ids = userstore.portfolio_ids() if ids is None else ids
    ports = [p for p in (userstore.get_portfolio(i) for i in ids) if p]
    notes: list[str] = []
    bench = tracked.benchmark()
    asof = market.closes[bench].dropna().index[-1].date().isoformat() if bench in market.closes else None
    view: dict[str, Any] = {
        "asof": asof, "generated": datetime.now().isoformat(timespec="seconds"),
        "selection": {"ids": [p["id"] for p in ports], "names": [p["name"] for p in ports], "scope": scope},
        "period": None, "reconciliation": None, "dims": {}, "currency": None,
        "benchmark": {"first_snapshot": None, "back_drifted_months": []}, "unclassified": [], "regression": None,
        "notes": notes}
    book = performance.pool([performance.portfolio_book(p, market) for p in ports])
    if book is None:
        notes.append("No transactions in this selection")
        return view
    notes += book.missing
    index = performance.twr(book.value, book.inflow, book.outflow, breaks=book.breaks)
    known = index.dropna()
    lo = max(known.index[0], pd.Timestamp(start)) if start and len(known) else (known.index[0] if len(known) else None)
    hi = min(known.index[-1], pd.Timestamp(end)) if end and len(known) else (known.index[-1] if len(known) else None)
    if lo is None or hi is None or hi <= lo:
        notes.append("No valued history in this period")
        return view
    lo, hi = known.loc[lo:].index[0], known.loc[:hi].index[-1]
    months = (hi - lo).days / DAYS_PER_MONTH
    view["period"] = {"start": lo.date().isoformat(), "end": hi.date().isoformat(), "months": round(months, 1)}
    if months < conf.min_months - 0.5:
        notes.append(f"No attribution: {months:.0f} months of history in this period, at least {conf.min_months} "
                     "are needed before allocation and selection mean anything")
        return view

    history = constituents.acwi_segment_history()
    if history.empty:
        notes.append("No attribution yet: no weekly record of ACWI's weights (radar run keeps one from now on)")
        view["regression"] = _regression(market, index, lo, hi, notes)
        return view
    first = pd.Timestamp(min(history["asof"]))
    view["benchmark"]["first_snapshot"] = first.date().isoformat()

    dates = book.dates[(book.dates >= lo) & (book.dates <= hi)]
    prices = Prices(market)
    pos = book.positions.reindex(dates)
    syms = [t for t in pos.columns if (pos[t].fillna(0) != 0).any()]   # zero: only to skip symbols never held here
    meta = exposure.ticker_meta(syms, prices)
    value_prev = book.value.reindex(dates).shift(1)
    w = pos[syms].shift(1).div(value_prev.where(value_prev > 0), axis=0)
    cash_w = book.cash.reindex(dates).shift(1).div(value_prev.where(value_prev > 0))
    r = _returns(prices, syms, dates)
    day_ok = value_prev.gt(0) & ~book.breaks.reindex(dates).fillna(False).astype(bool)
    day_ok &= w.notna().all(axis=1) & cash_w.notna()
    day_ok.iloc[0] = False                                  # the first day only opens the period
    if book.dividends != "reinvested":
        notes.append("Dividends are counted as cash rows here, but attribution uses adjusted prices: dividends show "
                     "twice, in the returns and in the trading-and-fees line")

    # currencies: rates, ACWI's mix (minor currencies without a rate left out), local returns
    ccy_snaps = segments.stepped_weights(segments.snapshots(history, "currency"), dates)
    held_ccy = {c for t in syms for c in [meta.at[t, "currency"]] if isinstance(c, str)} - set(exposure.UNCOVERED)
    fx = _fx(market, sorted(set(ccy_snaps.columns) | held_ccy | {"DKK", "USD", UNKNOWN_CCY}), dates)
    wb_ccy, left_out = _covered(ccy_snaps, fx)
    if left_out and left_out > 1e-4:
        notes.append(f"Currencies without a DKK rate (up to {left_out:.1%} of ACWI) are left out of ACWI's currency mix")
    wb_ccy_prev = wb_ccy.shift(1)
    wp_ccy = _currency_weights(w, cash_w, meta, wb_ccy_prev)
    cols = wp_ccy.columns.union(wb_ccy_prev.columns)
    cur = at.currency_panel(wp_ccy.reindex(columns=cols, fill_value=0.0),
                            wb_ccy_prev.reindex(columns=cols, fill_value=0.0), fx.reindex(columns=cols))
    f_sym = {}
    for t in syms:
        cls, c = meta.at[t, "class"], meta.at[t, "currency"]
        if cls == "world":
            f_sym[t] = _mix_return(wb_ccy_prev, fx)
        elif (mix := _ccy_mix(meta, t)) is not None:
            f_sym[t] = _mix_return(pd.DataFrame(mix, index=dates), fx)
        elif isinstance(c, str) and c in fx:
            f_sym[t] = fx[c]
        else:
            f_sym[t] = pd.Series(0.0, index=dates)          # unknown currency: the whole return is local
    r_local = pd.DataFrame({t: (1 + r[t]) / (1 + f_sym[t]) - 1 for t in syms}, index=dates)
    rp_dkk = _weighted(w, r).where(day_ok)                  # cash earns 0 in the book

    for dim in segments.DIMS:
        wb_close, basis, rb, bnotes = _benchmark(dim, prices, dates, history)
        notes += bnotes
        wb = wb_close.shift(1)
        mix = segments.stepped_weights(segments.snapshots(history, f"{dim}_currency"), dates)
        f_seg = {}
        for seg in rb.columns:
            part = mix[[c for c in mix.columns if c.split("|", 1)[0] == seg]]
            part.columns = [c.split("|", 1)[1] for c in part.columns]
            part = part[[c for c in part.columns if c in wb_ccy.columns]]
            f_seg[seg] = _mix_return(part.div(part.sum(axis=1).where(part.sum(axis=1) > 0), axis=0), fx)
        rb_local = pd.DataFrame({s: (1 + rb[s]) / (1 + f_seg[s]) - 1 for s in rb.columns}, index=dates)
        rb_dkk = _weighted(wb.reindex(columns=rb.columns), rb).where(wb.notna().any(axis=1))
        wp, rp = _portfolio_segments(dim, w.fillna(0.0), r_local, meta, wb, rb_local)
        wp[CASH] = cash_w.fillna(0.0)
        rp[CASH] = 0.0
        segs = wp.columns.union(wb.columns)
        rb_l = rb_local.reindex(columns=segs)
        rb_l[CASH] = 0.0                                    # cash's benchmark return is its own: the cash drag
        # a day without ACWI weights has none at all: its weights sum to 0, so the panel marks it invalid
        bf = at.brinson_panel(wp.reindex(columns=segs, fill_value=0.0), wb.reindex(columns=segs).fillna(0.0),
                              rp.reindex(columns=segs), rb_l)
        active = rp_dkk - rb_dkk
        valid = day_ok & bf["valid"] & cur["valid"] & active.notna() & wb.notna().any(axis=1)
        local = bf["allocation"].sum(axis=1) + bf["selection"].sum(axis=1) + bf["interaction"].sum(axis=1)
        currency = cur["effect"].sum(axis=1)
        frames = {"rp": rp_dkk, "rb": rb_dkk, "currency": currency, "cross": active - local - currency,
                  **{e: bf[e].sum(axis=1) for e in at.EFFECTS}, **{"seg_" + e: bf[e] for e in at.EFFECTS},
                  "wp": wp.reindex(columns=segs, fill_value=0.0), "wb": wb.reindex(columns=segs).fillna(0.0),
                  "rp_seg": rp.reindex(columns=segs), "rb_seg": rb.reindex(columns=segs)}
        out = _dimension(dim, frames, valid, basis, conf.tolerance)
        missing = int((~valid).sum()) - 1                   # the period's first day only opens it
        out |= {"days_missing": missing, "proxy_notes": bnotes}
        if missing:
            notes.append(f"{dim}: {missing} of {len(dates) - 1} day(s) left out (a holding's value or price, a proxy, a "
                         "rate or ACWI's weights unknown that day, or a flow of unknown size)")
        twr = float(index.loc[hi] / index.loc[lo] - 1)
        acwi_px = performance.bench_dkk(market)
        acwi = num(float(acwi_px.asof(hi) / acwi_px.asof(lo) - 1)) if len(acwi_px) else None
        out["reconciliation"] = {
            "twr": twr, "acwi": acwi, "active": twr - acwi if acwi is not None else None,
            "trading_fees": twr - out["rp"] if out["rp"] is not None else None,
            "proxy_vs_acwi": out["rb"] - acwi if out["rb"] is not None and acwi is not None else None,
            "attributed": out["rp"] - out["rb"] if out["rp"] is not None and out["rb"] is not None else None}
        view["dims"][dim] = out
        if dim == "sector":
            view["currency"] = _currency_table(cur, wp_ccy, wb_ccy_prev, fx, valid, rp_dkk, rb_dkk, out)
            view["benchmark"]["back_drifted_months"] = sorted(
                {d.strftime("%Y-%m") for d in basis[valid].index[basis[valid] == "back-drifted"]})
            if any(m < "2023-03" for m in view["benchmark"]["back_drifted_months"]):
                notes.append("Sector weights before March 2023 are back-drifted across a GICS change (Visa, "
                             "Mastercard and PayPal moved from Technology to Financials): read those months loosely")
    view["reconciliation"] = view["dims"]["sector"]["reconciliation"] if "sector" in view["dims"] else None

    # unclassified value, listed (never counted as a 0 % return)
    for t in syms:
        if _key(meta, t, "sector") == UNCLASSIFIED and meta.at[t, "class"] not in ("world", "index_fund", "fund_sectors"):
            share = w[t][day_ok]
            view["unclassified"].append({"symbol": t, "class": meta.at[t, "class"],
                                         "avg_weight": num(float(share.mean())) if len(share) else None})
    if view["unclassified"]:
        notes.append(f"{len(view['unclassified'])} holding(s) can't be placed by sector (funds not looked through or "
                     "unknown): they form their own segment, with their own returns")
    notes.append("Benchmark segments are ETFs that track MSCI World sectors and country indices, not ACWI's own "
                 "segments: the difference shows as 'benchmark proxies vs ACWI'")
    notes.append("Each holding is classified as it is today, also for past days")
    if view["benchmark"]["back_drifted_months"]:
        notes.append(f"ACWI's weights before {first:%Y-%m-%d} (the first weekly record) are rolled back from it with "
                     "the segments' returns: index changes in between are missed")
    view["regression"] = _regression(market, index, lo, hi, notes)
    return view
