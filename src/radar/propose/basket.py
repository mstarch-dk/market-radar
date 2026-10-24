"""Building the basket: the pool, the gates, the proposal score, the selection under caps, sizing around the
minimum ticket and fees, and the filler fund."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from .. import fees, fxrates, money, positive_list
from ..config_schema import Propose
from ..values import num
from . import exposure, pricing, rules

if TYPE_CHECKING:
    from ..market import Market


def pool(market: Market, prices: pricing.Prices, p=None, day=None, fund_table: pd.DataFrame | None = None,
         live: bool = True) -> pd.DataFrame:
    """The stock universe ranked on `day` (default: the latest session) with what the proposal needs."""
    from ..model import panels as mp

    p = p or mp.panels(market)
    day = pd.Timestamp(day) if day is not None else p.sessions[-1]
    df = mp.ranked(p, day).set_index("ticker")
    tick = list(df.index)
    df["history"] = p.m["history"].loc[day].reindex(tick)
    dk = p.dkk.loc[:day].iloc[-20:]
    if p.volumes is not None:
        df["adv_dkk"] = (p.volumes.reindex(columns=p.dkk.columns).loc[:day].iloc[-20:] * dk).mean().reindex(tick)
    else:
        df["adv_dkk"] = np.nan
    if live:
        last = market.prices.groupby("ticker")["date"].max()
        df["last_bar"] = last.reindex(tick)
        prices.preload(tick)
        df["currency"] = [prices.ccy(t) for t in tick]
        df["price"] = [prices.last_px(t) for t in tick]
        df["rate"] = [prices.rate(t) for t in tick]
        df["price_dkk"] = df["price"] * df["rate"]
    else:
        df["last_bar"] = day
        df["price_dkk"] = p.dkk.loc[day].reindex(tick)
    if fund_table is None and live:
        from .. import universe
        from ..fundamentals import context as fcontext

        t = fcontext.context(market.closes, market.raw_closes(), universe.tracked_stocks(),
                                 market.mtime).table()
        fund_table = t.set_index("ticker") if not t.empty else pd.DataFrame()
    for k in ("qv", "quality", "value"):
        df[k] = fund_table[k].reindex(tick).astype(float) if fund_table is not None and k in fund_table else np.nan
    df.attrs["day"] = day
    return df


def gates(df: pd.DataFrame, tilt: str, ticket: float, c: Propose | None = None, day=None) -> tuple[pd.DataFrame, dict]:
    """The names a proposal may consider, and the rest by reason (each name under its first failing gate)."""
    c = c or rules.cfg()
    g, w = c.gates, c.tilts[tilt]
    day = pd.Timestamp(day if day is not None else df.attrs.get("day", pd.Timestamp.today()))
    tests = []
    if w.momentum > 0:
        tests.append(("no momentum score", df["score"].isna()))
    if w.qv > 0:
        tests.append(("no K+V (kvalitet + værdi)", df["qv"].isna()))
    tests += [("no DKK rate", ~df["dkk"].eq(True)),
              ("stale price", (day - pd.to_datetime(df["last_bar"])).dt.days > g.max_stale_days),
              ("no price history", df["history"].isna()),
              ("short history", df["history"] < g.min_history_weeks * 5),
              ("no volume data", df["adv_dkk"].isna()),
              ("thin trading", df["adv_dkk"] < g.min_adv_dkk),
              ("no price", df["price_dkk"].isna()),
              ("share price above the ticket", df["price_dkk"] > ticket)]
    if w.momentum >= c.require_trend_from:
        tests.append(("not in an uptrend", ~df["trend_ok"].eq(True)))
    left = pd.Series(True, index=df.index)
    out: dict[str, list[str]] = {}
    for reason, bad in tests:
        hit = left & bad.reindex(df.index).fillna(False).astype(bool)
        if hit.any():
            out[reason] = sorted(df.index[hit])
        left &= ~hit
    return df[left].copy(), out


def _pctl(s: pd.Series) -> pd.Series:
    return s.rank(pct=True) * 100


def score(df: pd.DataFrame, tilt: str, c: Propose | None = None, corr: pd.Series | None = None) -> pd.DataFrame:
    """The proposal score on the gated pool, best first, with its parts."""
    c = c or rules.cfg()
    w, pen = c.tilts[tilt], c.penalties
    df = df.copy()
    parts, tot = [], 0.0
    for key, col in (("momentum", "score"), ("qv", "qv")):
        if getattr(w, key) > 0:
            df[f"c_{key}"] = _pctl(df[col])
            parts.append(getattr(w, key) * df[f"c_{key}"])
            tot += getattr(w, key)
    base = sum(parts) / tot if tot else pd.Series(np.nan, index=df.index)
    df["pen_vol"] = (pen.vol * df["vol"].rank(pct=True)).fillna(pen.vol)     # unknown volatility: the most
    hi = df["r1m"].quantile(0.9) if df["r1m"].notna().any() else np.inf
    df["pen_stretch"] = np.where(df["r1m"] >= hi, pen.stretch, 0.0)
    df["corr_book"] = corr.reindex(df.index) if corr is not None else np.nan
    pc = pen.corr * df["corr_book"].clip(lower=0)
    df["pen_corr"] = pc.fillna(pc.median() if pc.notna().any() else 0.0)   # unknown: the pool's median, not "unrelated"
    df["composite"] = base - df["pen_vol"] - df["pen_stretch"] - df["pen_corr"]
    df = df[df["composite"].notna()]
    return df.assign(_t=df.index).sort_values(["composite", "_t"], ascending=[False, True]).drop(columns="_t")


def corr_to(R: pd.DataFrame, series: pd.Series | None, min_weeks: int) -> pd.Series:
    """Each column's correlation with `series` (weekly returns), None below `min_weeks` shared weeks."""
    if series is None or R.empty:
        return pd.Series(np.nan, index=R.columns)
    s = series.reindex(R.index)
    ok = R.notna() & s.notna().to_numpy()[:, None]
    n = ok.sum()
    out = R.corrwith(s)
    return out.where(n >= min_weeks)


@dataclass
class Base:
    """What the caps are measured against: the portfolio's DKK values by ticker and their meta, ACWI's weights
    (constituents.acwi_weights, from the iShares MSCI ACWI UCITS holdings file; None without it, and then the
    active-weight caps are skipped and the active weights shown as unknown), the whole real book's values (every real
    portfolio: the position limit), and weekly returns for the correlation cap."""
    values: dict[str, float]
    meta: pd.DataFrame
    acwi: dict | None
    whole: dict[str, float] = field(default_factory=dict)
    R: pd.DataFrame = field(default_factory=pd.DataFrame)

    def dim_values(self) -> dict[str, dict[str, float]]:
        ex = exposure.exposures(self.values, self.meta, self.acwi)
        return {d: {k: w * ex["total_dkk"] for k, w in ex["weights"][d].items()} for d in exposure.DIMS}


def select(scored: pd.DataFrame, n: int, amount: float, base: Base, c: Propose | None = None, mode: str = "conviction",
           max_position: float | None = None, min_weeks: int = 26) -> tuple[list[dict], dict]:
    """Greedy by proposal score under the caps; returns the picks and, for names passed over, why."""
    c = c or rules.cfg()
    if mode not in rules.MODES:
        raise ValueError(f"mode is one of {', '.join(rules.MODES)}")
    df = scored.copy()
    if df.empty or n <= 0:
        return [], {}
    held = base.dim_values()
    book_total = sum(v for v in base.values.values() if v)
    total_after = book_total + amount
    ticket = amount / n
    if mode == "fill-gaps" and base.acwi:
        sw = {k: v / book_total for k, v in held["sector"].items()} if book_total > 0 else {}
        deficit = df["sector"].map(lambda s: max(0.0, base.acwi["sector"].get(s, 0.0) - sw.get(s, 0.0)))
        df["bonus"] = (deficit / 0.10).clip(upper=1.0) * c.fill_gaps_bonus
        df["composite"] = df["composite"] + df["bonus"]
        df = df.assign(_t=df.index).sort_values(["composite", "_t"], ascending=[False, True]).drop(columns="_t")
    whole_total = sum(v for v in base.whole.values() if v) + amount
    book_names = [t for t, v in base.values.items() if v and book_total > 0 and v / book_total >= 0.02]
    R = base.R
    corr = R.corr(min_periods=min_weeks) if not R.empty else pd.DataFrame()
    picked: list[dict] = []
    added: dict[str, dict[str, float]] = {d: {} for d in exposure.DIMS}
    per_sector: dict[str, int] = {}
    passed: dict[str, str] = {}
    for t, r in df.iterrows():
        if len(picked) >= n:
            break
        why = None
        if per_sector.get(r["sector"], 0) >= c.max_per_sector:
            why = f"already {c.max_per_sector} new names in {r['sector']}"
        if why is None and base.acwi:
            for d in exposure.DIMS:
                k = r[d]
                before = held[d].get(k, 0.0) + added[d].get(k, 0.0)
                if before <= 0:
                    continue                       # a bucket's first name: one ticket isn't a pile-up
                act = (before + ticket) / total_after - base.acwi[d].get(k, 0.0)
                cap = getattr(c.caps, d)
                if act > cap:
                    why = f"{d} {k} would be {act:+.0%} vs ACWI (cap {cap:+.0%})"
                    break
        if why is None and t in corr.index:
            for o in [x["ticker"] for x in picked] + book_names:
                v = corr.at[t, o] if o in corr.columns else np.nan
                if pd.notna(v) and o != t and v > c.max_corr:
                    why = f"correlation {v:.2f} with {o} (cap {c.max_corr})"
                    break
        if why is None and max_position:
            share = (base.whole.get(t, 0.0) + ticket) / whole_total
            if share > max_position:
                why = f"{share:.1%} of your whole book (limit {max_position:.1%})"
        if why:
            passed[t] = why
            continue
        picked.append({"ticker": t, "composite": num(r["composite"]), "sector": r["sector"], "region": r["region"],
                       "currency": r["currency"]})
        per_sector[r["sector"]] = per_sector.get(r["sector"], 0) + 1
        for d in exposure.DIMS:
            added[d][r[d]] = added[d].get(r[d], 0.0) + ticket
    return picked, passed


def n_for(amount: float, c: Propose | None = None, n: int | None = None) -> int:
    c = c or rules.cfg()
    most = max(1, int(amount // c.min_ticket_dkk))
    return max(1, min(n or most, most, c.max_names))


def half_spread(adv: float | None, c: Propose | None = None) -> float:
    c = c or rules.cfg()
    for b in sorted(c.spread_bps, key=lambda x: -x.min_adv_dkk):
        if adv is not None and not pd.isna(adv) and adv >= b.min_adv_dkk:
            return money.bps(b.bps)
    return money.bps(max(b.bps for b in c.spread_bps))


def terms_for(prices: pricing.Prices, sf: fees.SimFees, t: str) -> fees.Terms:
    ccy = prices.ccy(t)
    rate = prices.rate(t)
    if rate is None:
        return sf.terms(t, None, None, count=False)

    def convert(amount: float, k: str) -> float | None:
        if k == "DKK":
            return amount / rate
        fx = fxrates.fx_to_dkk(prices.market.closes, k)
        v = fx.dropna().iloc[-1] if fx is not None and len(fx.dropna()) else None
        return amount * float(v) / rate if v is not None and v > 0 else None
    return sf.terms(t, ccy, convert, count=False)


def budgets(amount: float, vols: list[float | None], weighting: str, ticket: float) -> list[float]:
    """DKK per name: equal, or inverse volatility floored at `ticket` (the rest shared by the others)."""
    n = len(vols)
    if weighting == "equal" or n == 1 or any(v is None or not v > 0 for v in vols):
        return [amount / n] * n
    inv = np.array([1 / v for v in vols if v is not None])
    fixed = np.zeros(n, dtype=bool)
    b = amount * inv / inv.sum()
    for _ in range(n):
        low = (b < ticket) & ~fixed
        if not low.any():
            break
        fixed |= low
        rest = amount - ticket * fixed.sum()
        b = np.where(fixed, ticket, rest * inv / inv[~fixed].sum() if (~fixed).any() else 0)
    return [float(x) for x in b]


def size(amount: float, picks: list[dict], df: pd.DataFrame, prices: pricing.Prices, sf: fees.SimFees, weighting: str = "equal",
         c: Propose | None = None) -> dict:
    """Whole shares per pick within its budget, every cost counted; leftover cash stated."""
    c = c or rules.cfg()
    if weighting not in rules.WEIGHTINGS:
        raise ValueError(f"weighting is one of {', '.join(rules.WEIGHTINGS)}")
    ticket = c.min_ticket_dkk
    vols = [num(df.at[x["ticker"], "vol"]) if x["ticker"] in df.index else None for x in picks]
    bud = budgets(amount, vols, weighting, ticket) if picks else []
    rows, flags = [], []
    for x, b in zip(picks, bud):
        t = x["ticker"]
        px, rate = prices.last_px(t), prices.rate(t)
        adv = num(df.at[t, "adv_dkk"]) if t in df.index else None
        hs = half_spread(adv, c)
        row = {"ticker": t, "budget_dkk": b, "price": px, "currency": prices.ccy(t), "rate": rate,
               "half_spread": hs, "quantity": None, "value_dkk": None, "cash_dkk": None, "fee_dkk": None,
               "spread_dkk": None, "roundtrip_dkk": None}
        if px is None or rate is None:
            flags.append(f"{t}: no price or DKK rate: can't be sized")
            rows.append(row)
            continue
        tm = terms_for(prices, sf, t)
        ask = px * (1 + hs)
        qty = math.floor(tm.value_for_budget(b / rate) / ask)
        if qty <= 0:
            flags.append(f"{t}: one share costs more than its budget of {b:,.0f} DKK")
            rows.append(row)
            continue
        trade = qty * ask
        fee = tm.fee(trade)
        sell_fee = tm.fee(qty * px)
        row |= {"quantity": qty, "value_dkk": qty * px * rate, "cash_dkk": (trade + fee) * rate,
                "fee_dkk": fee * rate, "spread_dkk": qty * px * hs * rate,
                "roundtrip_dkk": (fee + sell_fee + 2 * qty * px * hs) * rate}
        rows.append(row)
    ok = [r for r in rows if r["quantity"]]
    invested = sum(r["value_dkk"] for r in ok)
    out = {"rows": rows, "flags": flags, "invested_dkk": invested, "cash_dkk": sum(r["cash_dkk"] for r in ok),
           "fees_dkk": sum(r["fee_dkk"] for r in ok), "spread_dkk": sum(r["spread_dkk"] for r in ok),
           "roundtrip_dkk": sum(r["roundtrip_dkk"] for r in ok), "fee_model": sf.describe()}
    out["roundtrip_pct"] = out["roundtrip_dkk"] / invested if invested > 0 else None
    out["leftover_dkk"] = amount - out["cash_dkk"]
    return out


def filler(leftover: float, kind: str, prices: pricing.Prices, sf: fees.SimFees, allowed: bool = True,
           c: Propose | None = None) -> dict | None:
    """The ETF filler for leftover cash (ACWI UCITS), or None when it isn't wanted or the leftover is too small."""
    c = c or rules.cfg()
    f = c.etf_filler
    if not allowed or leftover < f.min_dkk:
        return None
    flag = positive_list.flag(f.isin, prices.market.positive_list())
    out: dict[str, Any] = {"ticker": f.ticker, "name": f.name, "isin": f.isin, "model": f.model,
           "positive_list": flag, "budget_dkk": leftover, "quantity": None, "value_dkk": None, "fee_dkk": None,
           "note": None}
    if kind == "ask" and flag == "no":
        return out | {"budget_dkk": 0.0, "note": "not on the positive list: an aktiesparekonto can't hold it, so the "
                                                 "leftover stays cash"}
    if kind == "ask" and flag == "?":
        out["note"] = "positive list unknown (no imports/positivliste.xlsx): check before buying on an aktiesparekonto"
    px, rate = prices.last_px(f.ticker), prices.rate(f.ticker)
    if px is None or rate is None:
        tm = sf.terms(f.ticker, None, None, count=False)
        v = tm.value_for_budget(leftover)
        return out | {"value_dkk": v, "fee_dkk": leftover - v,
                      "note": (out["note"] + "; " if out["note"] else "") + f"its price isn't tracked: sized by value "
                              f"at the flat fee, modelled with {f.model}"}
    tm = terms_for(prices, sf, f.ticker)
    qty = math.floor(tm.value_for_budget(leftover / rate) / px)
    if qty <= 0:
        return out | {"budget_dkk": 0.0, "note": "one unit costs more than the leftover"}
    return out | {"quantity": qty, "value_dkk": qty * px * rate, "fee_dkk": tm.fee(qty * px) * rate}
