"""Drafting a proposal: the portfolio's context, the ranked pool, the rule basket, the default exit and the
candidates; which account it fits."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

import pandas as pd

from .. import universe, userstore
from ..config import typed
from ..config_schema import Propose
from ..jsonsafe import clean as _clean
from ..model import inputs, tax
from ..portfolios import exposure, fees, performance, riskmodel, taxrules, trades
from ..portfolios.prices import Prices
from ..sources import constituents, tracked
from . import basket, drift, rules

if TYPE_CHECKING:
    from ..market import Market


@dataclass
class Ctx:
    market: Market
    prices: Prices

    portfolio: dict
    holdings: pd.DataFrame
    whole: pd.DataFrame
    sf: fees.SimFees
    acwi: dict | None
    regime: str | None
    notes: list[str]
    trend: str | None = None       # ACWI above ("up") or below ("down") its prior.trend_months-month average


def context(market: Market, name: str, offline: bool = False) -> Ctx:
    p = userstore.portfolio_by_name(name)
    if not p:
        known = ", ".join(x["name"] for x in userstore.portfolios(include_archived=False))
        raise ValueError(f"no portfolio called {name} (yours: {known or 'none'})")
    prices = Prices(market)
    notes = []
    held = exposure.holdings_book(market, prices, [p["id"]])
    whole = exposure.holdings_book(market, prices, userstore.portfolio_ids())
    for df, what in ((held, name), (whole, "your real portfolios")):
        miss = df[df["value_dkk"].isna()]["symbol"].tolist()
        if miss:
            notes.append(f"{what}: no price or DKK rate for {', '.join(miss)}: left out of the weights")
    acwi = constituents.acwi_weights(offline=offline)
    if acwi is None:
        notes.append("ACWI's own weights are unknown (no iShares holdings file): active-weight caps are off")
    sf = fees.SimFees.for_portfolio(p, typed().backtest.fee_bps)
    if not sf.schedule:
        notes.append(f"{name} has no fee schedule: fees are the flat backtest.fee_bps")
    return Ctx(market, prices, p, held, whole, sf, acwi, inputs.current_regime()["label"], notes, _trend(market))


def _trend(market: Market, months: int | None = None) -> str | None:
    """"up" when ACWI's last month-end close is at or above the mean of its last `months` month-ends, else
    "down" (the split the long-run prior uses); None without enough history."""
    months = months or rules.cfg().prior.trend_months
    try:
        s = market.closes[tracked.benchmark()].dropna()
    except (KeyError, AttributeError):
        return None
    me = s.groupby(s.index.to_period("M")).last()
    if len(me) < months:
        return None
    return "up" if me.iloc[-1] >= me.iloc[-months:].mean() else "down"


def values_of(df: pd.DataFrame) -> dict[str, float]:
    return {r["symbol"]: float(r["value_dkk"]) for _, r in df.iterrows() if r["value_dkk"] is not None and pd.notna(r["value_dkk"])}


def holdings_base(ctx: Ctx, extra=(), weeks: int = 52) -> basket.Base:
    vals = values_of(ctx.holdings)
    meta = exposure.ticker_meta(list(vals) + list(extra), ctx.prices)
    R = ctx.prices.weekly(list(vals) + list(extra), weeks)
    return basket.Base(vals, meta, ctx.acwi, values_of(ctx.whole), R)


def ranked_pool(ctx: Ctx, tilt: str, ticket: float, p=None, raw: pd.DataFrame | None = None
                ) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Gated and scored pool for this portfolio (correlation with its weekly returns), the exclusions and the
    ungated pool."""
    c = rules.cfg()
    df = raw if raw is not None else basket.pool(ctx.market, ctx.prices, p)
    kept, excluded = basket.gates(df, tilt, ticket, c)
    vals = values_of(ctx.holdings)
    R = ctx.prices.weekly(list(kept.index) + list(vals) + [tracked.benchmark()], 52)
    book_r = riskmodel.weekly_returns(vals, R, tracked.benchmark()) if vals else None
    corr = basket.corr_to(R.reindex(columns=list(kept.index)), book_r, c.min_weeks) if book_r is not None else None
    kept = exposure.annotate(kept, exposure.ticker_meta(list(kept.index), ctx.prices))
    return basket.proposal_score(kept, tilt, c, corr), excluded, df


def rule_basket(ctx: Ctx, scored: pd.DataFrame, amount: float, n: int, mode: str, max_position: float | None,
                weighting: str) -> tuple[list[dict], dict, dict]:
    base = holdings_base(ctx, list(scored.index[: max(4 * n, 40)]))
    chosen, passed = basket.select(scored, n, amount, base, rules.cfg(), mode, max_position)
    return chosen, passed, basket.size_picks(amount, chosen, scored, ctx.prices, ctx.sf, weighting)


def default_exit(tilt: str, fill: str, horizon: int, c: Propose | None = None) -> dict:
    """The standard exit criteria every pick gets (thesis checks are added by the skill)."""
    c = c or rules.cfg()
    st = typed().stops
    w = c.tilts[tilt]
    sig = ({"metric": "score", "below": c.exit.min_score} if w.momentum >= w.qv
           else {"metric": "qv", "below": c.exit.min_qv})
    review = (pd.Timestamp(fill) + pd.DateOffset(months=horizon)).date().isoformat()
    return {"review_level": {"rule": f"close below the {st.trend_sma}-day average", "sma": st.trend_sma,
                             "mode": st.mode, "action": st.action},
            "signal": sig, "time_stop": review, "thesis": []}


def candidates(market: Market, name: str, amount: float, tilt: str = "mix", mode: str = "conviction", n: int | None = None,
               weighting: str = "equal", max_position: float | None = None, etf: bool = True, horizon: int = 6,
               top: int = 40, offline: bool = False) -> dict:
    """The context, the gates, a scored shortlist and the rule-only basket as a draft picks file."""
    c = rules.cfg()
    if tilt not in rules.TILTS:
        raise ValueError(f"tilt is one of {', '.join(rules.TILTS)}")
    if amount < c.min_ticket_dkk:
        raise ValueError(f"{amount:,.0f} DKK is less than one ticket ({c.min_ticket_dkk:,.0f} DKK): consider the "
                         "ACWI ETF instead")
    ctx = context(market, name, offline)
    n = basket.n_for(amount, c, n)
    ticket = amount / n
    scored, excluded, _ = ranked_pool(ctx, tilt, ticket)
    chosen, passed, sz = rule_basket(ctx, scored, amount, n, mode, max_position, weighting)
    fill_ = basket.filler(sz["leftover_dkk"], ctx.portfolio["kind"], ctx.prices, ctx.sf, etf, c)
    today = pd.Timestamp(market.closes.index[-1]).date().isoformat()
    vals = values_of(ctx.holdings)
    meta = exposure.ticker_meta(list(vals), ctx.prices)
    rows = []
    names = universe.names(list(scored.index[:top]))
    for t, r in scored.head(top).iterrows():
        rows.append({"ticker": t, "name": names.get(t), "composite": r["composite"],
                     "c_momentum": r.get("c_momentum"), "c_qv": r.get("c_qv"), "pen_vol": r["pen_vol"],
                     "pen_stretch": r["pen_stretch"], "pen_corr": r["pen_corr"], "corr_book": r["corr_book"],
                     "momentum_score": r["score"], "qv": r["qv"], "quality": r["quality"], "value": r["value"],
                     "r1m": r["r1m"], "r3m": r["r3m"], "r6m": r["r6m"], "r12_1": r["r12_1"], "from_high": r["from_high"],
                     "trend_ok": r["trend_ok"], "vol": r["vol"], "sector": r["sector"], "region": r["region"],
                     "currency": r["currency"], "adv_dkk": r["adv_dkk"], "price_dkk": r["price_dkk"],
                     "half_spread": basket.half_spread(r["adv_dkk"], c), "in_rule_basket": t in {x["ticker"] for x in chosen},
                     "passed_over": passed.get(t), "ask_flag": ask_flag(t) if ctx.portfolio["kind"] == "ask" else None})
    ex = default_exit(tilt, today, horizon, c)
    draft = {"type": "propose-picks", "meta": {"portfolio": name, "portfolio_id": ctx.portfolio["id"], "amount": amount,
                                                "tilt": tilt, "mode": mode, "n": n, "horizon": horizon,
                                                "weighting": weighting, "max_position": max_position, "etf": etf,
                                                "date": today, "settings_hash": rules.rule_hash(),
                                                "stops": typed().stops.model_dump(mode="json"),
                                                "rule_basket": [x["ticker"] for x in chosen], "frozen_at": None},
             "picks": [{"ticker": x["ticker"], "why": None, "swapped_from": None, "swap_reason": None, "exit": ex}
                       for x in chosen],
             "filler": fill_}
    return _clean({
        "portfolio": {"id": ctx.portfolio["id"], "name": name, "mode": ctx.portfolio["mode"], "kind": ctx.portfolio["kind"],
                      "value_dkk": sum(vals.values()), "holdings": len(vals)},
        "asof": today, "amount": amount, "tilt": tilt, "mode": mode, "n": n, "ticket_dkk": ticket,
        "regime": ctx.regime, "trend": ctx.trend, "fee_model": ctx.sf.describe(), "notes": ctx.notes,
        "exposure_now": exposure.exposures(vals, meta, ctx.acwi), "acwi_weights": ctx.acwi is not None,
        "gates": {"pool": int(len(scored)) + sum(len(v) for v in excluded.values()), "kept": int(len(scored)),
                  "excluded": {k: {"count": len(v), "tickers": v} for k, v in excluded.items()}},
        "shortlist": rows,
        "rule_basket": {"picks": chosen, "passed_over": passed, "size": sz, "filler": fill_},
        "study": drift.study_view(drift.load_study(), tilt, n, horizon, ctx.regime, trend=ctx.trend),
        "ask": ask_account(ctx, amount) if ctx.portfolio["kind"] == "ask" else None,
        "draft_picks": draft,
        "columns": {"composite": "the proposal score: tilt-weighted percentiles less penalties (0-100 scale)",
                    "c_momentum": "momentum score percentile in the gated pool", "c_qv": "K+V percentile in the pool",
                    "corr_book": "weekly DKK correlation with the portfolio over a year",
                    "half_spread": "estimated half-spread (an estimate by liquidity bucket)"},
    })


def ask_flag(t: str) -> str | None:
    """A note for an aktiesparekonto: listings the radar can't place on a known exchange need checking."""
    m = fees.market_of(t)
    return None if m != "OTHER" else "listing outside the known exchanges: check that an aktiesparekonto may hold it"


def ask_account(ctx: Ctx, amount: float, today: date | None = None) -> dict:
    """The aktiesparekonto's deposit headroom this year (config/tax_dk.yaml): the cap less the account's value on
    31 December the year before and this year's deposits (skat.dk), against the amount to add."""
    year = (today or date.today()).year
    out: dict = {"cap_year": year, "deposit_cap": None, "value_prev_end_dkk": None, "deposits_dkk": None,
                 "headroom_dkk": None,
                 "note": "17 % lager on the account's yearly gain: frequent momentum trades cost no extra tax here; "
                         "funds must be on the positive list"}
    try:
        out["deposit_cap"] = taxrules.rules(year).ask.deposit_cap
    except taxrules.NoRules:
        out["cap_check"] = f"not checked: no rules for {year} in config/tax_dk.yaml"
        return out
    rows = trades.ledger([ctx.portfolio["id"]])
    if rows.empty or not rows["type"].isin(["DEPOSIT"]).any():
        out["cap_check"] = "not checked: the account has no deposit rows"
        return out
    days = pd.to_datetime(rows["date"])
    dep = rows[(rows["type"] == "DEPOSIT") & (days.dt.year == year)]
    out["deposits_dkk"] = float(dep["amount"].astype(float).sum())
    prev = 0.0 if (days.dt.year >= year).all() else None      # zero: opened this year, nothing held on 31 December
    b = performance.portfolio_book(ctx.portfolio, ctx.market) if prev is None else None
    if b is not None:
        before = b.value[b.value.index <= pd.Timestamp(year - 1, 12, 31)]
        prev = 0.0 if before.empty else (None if pd.isna(before.iloc[-1]) else float(before.iloc[-1]))
    if prev is None:
        out["cap_check"] = f"not checked: the account's value on 31 December {year - 1} is unknown"
        return out
    out["value_prev_end_dkk"] = prev
    room = tax.ask_headroom(out["deposit_cap"], prev, out["deposits_dkk"])
    out["headroom_dkk"] = room
    out["cap_check"] = "within the cap" if amount <= room else f"over the {year} cap by {amount - room:,.0f} DKK"
    return out
