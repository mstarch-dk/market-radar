"""Evaluating a frozen proposal: its metrics, the alternatives (ACWI, the rule basket, other tilts, sizes,
topping up, sector ETFs, random baskets) and the decision rule fixed beforehand."""
from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from ..config import typed, universe_config
from ..config_schema import Propose
from ..jsonsafe import clean as _clean
from ..portfolios import fees
from ..sources import tracked
from ..values import num
from . import basket, draft, drift, exposure, picks_file, pricing, riskmodel, rules

if TYPE_CHECKING:
    from ..market import Market


def picks_sha(doc: dict) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, default=str).encode()).hexdigest()[:16]


def net_drift(drift: float | None, cost_pct: float | None) -> float | None:
    """The modelled drift after the round-trip cost; unknown when either is (an unknown cost is not a free trade)."""
    return None if drift is None or cost_pct is None else drift - cost_pct


def cost_share(parts: list[tuple[float | None, float]], amount: float) -> float | None:
    """The cost of several buys as a share of `amount`: each (round-trip share, DKK); unknown when any part is."""
    known = [(share, dkk) for share, dkk in parts if share is not None]
    if amount <= 0 or len(known) < len(parts):
        return None
    return sum(share * dkk for share, dkk in known) / amount


def _mean_known(shares: list[float | None]) -> float | None:
    """The mean cost share, unknown when any share is."""
    known = [x for x in shares if x is not None]
    return float(np.mean(known)) if known and len(known) == len(shares) else None


def alternative_metrics(values: dict[str, float], ctx: draft.Ctx, cov: pd.DataFrame, R: pd.DataFrame, horizon: int, drift: float | None,
            cost_pct: float | None, c: Propose, before: dict[str, float] | None = None, draws: int | None = None) -> dict:
    """One alternative on the common metrics: risk alone and in the portfolio, the bootstrap, costs, the drift."""
    bench = tracked.benchmark()
    cc = c.model_copy(update={"bootstrap": c.bootstrap.model_copy(update={"draws": draws or c.bootstrap.draws})})
    rp = riskmodel.weekly_returns(values, R, bench)
    weeks = round(horizon * rules.WEEKS_PER_MONTH)
    boot = riskmodel.bootstrap(rp, R[bench], weeks, net_drift(drift, cost_pct), cc) \
        if rp is not None and bench in R else {"note": "no weekly returns"}
    after = dict(before or {})
    for t, v in values.items():
        after[t] = after.get(t, 0.0) + v
    return {"risk": riskmodel.ex_ante_risk(values, cov, bench),
            "after": riskmodel.ex_ante_risk(after, cov, bench) if before is not None else None,
            "bootstrap": boot, "cost_pct": cost_pct, "drift_gross": drift,
            "drift_net": net_drift(drift, cost_pct),
            "realised_dd_1y": riskmodel.realised_dd(rp, 52), "realised_dd_3y": riskmodel.realised_dd(rp, 156)}


def adv_dkk(prices: pricing.Prices, t: str) -> float | None:
    """Mean daily traded value over the last 20 sessions in DKK (None without volumes)."""
    v = getattr(prices.market, "volumes", None)
    s = prices.dkk(t)
    if v is None or t not in v or s is None:
        return None
    x = (v[t].reindex(s.index) * s).dropna().iloc[-20:]
    return num(x.mean()) if len(x) else None


def _cost_one(prices: pricing.Prices, sf: fees.SimFees, t: str, amount: float, adv=None) -> float | None:
    """Round-trip cost share of putting `amount` DKK into `t` (fees both ways, FX surcharge, half-spread)."""
    adv = adv if adv is not None else adv_dkk(prices, t)
    if adv is None and t in exposure.look_through():
        adv = adv_dkk(prices, tracked.benchmark())      # a world fund modelled with ACWI trades like it
    rate = prices.rate(t)
    if rate is None:
        tm = sf.terms(t, None, None, count=False)
        v = tm.value_for_budget(amount)
        return (2 * tm.fee(v)) / v if v > 0 else None
    tm = basket.terms_for(prices, sf, t)
    v = tm.value_for_budget(amount / rate)
    hs = basket.half_spread(adv)
    return (2 * tm.fee(v) + 2 * v * hs) / v if v > 0 else None


def evaluate(market: Market, doc: dict, max_position: float | None = None, tolerance: float | None = None,
             offline: bool = False, light: bool = False) -> dict:
    """Everything the memo needs for a frozen picks file: sizing, constraints, exposures, risk, the drawdown three
    ways, the modelled return, the alternatives A0-A6 and the decision rule."""
    c = rules.cfg()
    m = picks_file.check(doc).meta
    name, amount = m.portfolio, m.amount
    tilt, mode, horizon, weighting = m.tilt, m.mode, m.horizon, m.weighting
    max_position = max_position if max_position is not None else m.max_position
    if amount <= 0:
        raise ValueError("the picks file needs a positive meta.amount")
    ctx = draft.context(market, name, offline)
    bench = tracked.benchmark()
    tickers = [x["ticker"] for x in doc["picks"]]
    n = len(tickers)
    ticket = amount / n
    scored, excluded, raw = draft.ranked_pool(ctx, tilt, ticket)
    for t in tickers:
        if t not in market.closes.columns:
            raise ValueError(f"{t}: no prices in the radar (not a tracked ticker)")
    frame = scored.reindex(tickers).combine_first(raw.reindex(tickers))
    frame = exposure.annotate(frame, exposure.ticker_meta(tickers, ctx.prices))
    picks_list = [{"ticker": t} for t in tickers]
    sz = basket.size_picks(amount, picks_list, frame, ctx.prices, ctx.sf, weighting, c)
    fl_doc = doc.get("filler")
    fl = basket.filler(sz["leftover_dkk"], ctx.portfolio["kind"], ctx.prices, ctx.sf, bool(fl_doc) or m.etf, c)
    vals = draft.values_of(ctx.holdings)
    new = {r["ticker"]: r["value_dkk"] for r in sz["rows"] if r["value_dkk"]}
    if fl and fl.get("value_dkk"):
        new[fl["ticker"]] = new.get(fl["ticker"], 0.0) + fl["value_dkk"]
    after = dict(vals)
    for t, v in new.items():
        after[t] = after.get(t, 0.0) + v
    every = list(dict.fromkeys([*after, *tickers, bench, *(scored.index[:60])]))
    meta = exposure.ticker_meta(every, ctx.prices)
    weeks = c.history_weeks
    R = ctx.prices.weekly(every + [f for f in typed().risk.factors if f in market.closes], weeks)
    cov = riskmodel.shrunk_cov(R.reindex(columns=[t for t in every if t in R]), c.shrink, c.min_weeks)

    # constraints
    base = draft.holdings_base(ctx, tickers)
    _, passed = basket.select(frame.assign(composite=np.arange(n, 0, -1)), n, amount, base, c, "conviction", max_position)
    rule = m.rule_basket
    swaps = [t for t in tickers if rule and t not in rule]
    # zero: a budget that couldn't be sized fails the minimum ticket
    cons = [{"check": "min ticket", "ok": all((r["budget_dkk"] or 0) >= c.min_ticket_dkk - 1 for r in sz["rows"]),
             "detail": f"{c.min_ticket_dkk:,.0f} DKK per name"},
            {"check": "sized", "ok": not sz["flags"], "detail": "; ".join(sz["flags"]) or "every pick has whole shares"},
            {"check": "caps (sector, region, currency, per sector, correlation, position)", "ok": not passed,
             "detail": "; ".join(f"{t}: {w}" for t, w in passed.items()) or "all within"},
            {"check": "swaps from the rule basket", "ok": len(swaps) <= c.max_swaps,
             "detail": f"{len(swaps)} of at most {c.max_swaps}" + (f" ({', '.join(swaps)})" if swaps else "")},
            {"check": "names in the gated pool", "ok": all(t in scored.index for t in tickers),
             "detail": "; ".join(f"{t}: {next((k for k, v in excluded.items() if t in v), 'not ranked')}"
                                 for t in tickers if t not in scored.index) or "all passed the gates"}]
    if ctx.portfolio["kind"] == "ask":
        fl_ask = [f"{t}: {draft.ask_flag(t)}" for t in tickers if draft.ask_flag(t)]
        cons.append({"check": "aktiesparekonto", "ok": not fl_ask and not (fl and fl.get("positive_list") == "no"),
                     "detail": "; ".join(fl_ask) or "no listing flags"})

    # the model
    sv = {h: drift.study_view(drift.load_study(), tilt, n, h, ctx.regime, c, ctx.trend) for h in c.horizons}
    cost_pct = sz["roundtrip_pct"]
    hv = sv.get(horizon) or drift.study_view(drift.load_study(), tilt, n, horizon, ctx.regime, c, ctx.trend)
    draws = 1000 if light else None
    prop = alternative_metrics(new, ctx, cov, R, horizon, hv["drift_gross"], cost_pct, c, vals, draws)
    st = riskmodel.stress(new, ctx.prices, bench, c)
    kept = (hv.get("kept") or {}).get("all") or {}
    lenses: dict[str, Any] = {"study": {"median": kept.get("dd_median"), "p10": kept.get("dd_p10"), "dates": kept.get("dates")},
              "bootstrap": (prop["bootstrap"] or {}).get("max_dd"),
              "stress_worst": min((s["max_dd"] for s in st if s["max_dd"] is not None), default=None)}
    meds = [x for x in (lenses["study"]["median"], (lenses["bootstrap"] or {}).get("median")) if x is not None]
    bads = [x for x in (lenses["study"]["p10"], (lenses["bootstrap"] or {}).get("p10"), lenses["stress_worst"]) if x is not None]
    dd = {"expected": float(np.median(meds)) if meds else None, "bad_case": min(bads) if bads else None,
          "lenses": lenses, "note": "expected = the median of the study's and the bootstrap's median drawdown; bad case "
                                    "= the worst of their 10th percentiles and the worst stress window"}

    # alternatives
    alts = alternatives(ctx, scored, raw, tickers, amount, n, tilt, mode, weighting, max_position, horizon, cov, R,
                        vals, meta, c) if not light else {}
    decision = decide(prop, hv, dd, tolerance, c)
    pmeta = exposure.ticker_meta(list(new), ctx.prices)
    # the rule study tests K+V on US stocks only (SEC EDGAR); outside the US only the factor-level prior speaks
    untested = sorted(t for t in tickers if c.tilts[tilt].qv > 0
                      and pmeta["region"].get(t, "us") != "us")
    if untested:
        ex = (((hv.get("prior") or {}).get("regions") or {}).get("world_ex_us") or {})
        ctx.notes.append(f"{', '.join(untested)}: outside the US, where the rule study never tested K+V; the only "
                         "evidence is JKP's factor-level prior ex US"
                         + (f" ({ex['mean']:+.1%} over {horizon} months, t {ex['t']:.1f})"
                            if ex.get("mean") is not None and ex.get("t") is not None else ""))
    return _clean({
        "portfolio": {"id": ctx.portfolio["id"], "name": name, "kind": ctx.portfolio["kind"], "mode": ctx.portfolio["mode"]},
        "asof": pd.Timestamp(market.closes.index[-1]).date().isoformat(), "picks_sha": picks_sha(doc),
        "meta": doc["meta"], "regime": ctx.regime, "trend": ctx.trend, "notes": ctx.notes, "untested_kv": untested,
        "picks": [{**x, **{k: v for k, v in (next(r for r in sz["rows"] if r["ticker"] == x["ticker"])).items()},
                   "sector": pmeta["sector"].get(x["ticker"]), "region": pmeta["region"].get(x["ticker"]),
                   "momentum_score": num(frame.at[x["ticker"], "score"]) if "score" in frame else None,
                   "qv": num(frame.at[x["ticker"], "qv"]) if "qv" in frame else None,
                   "vol": num(frame.at[x["ticker"], "vol"]),
                   "contribution": prop["risk"]["contributions"].get(x["ticker"])} for x in doc["picks"]],
        "size": sz, "filler": fl, "constraints": cons,
        "exposure": {"before": exposure.exposures(vals, meta, ctx.acwi), "after": exposure.exposures(after, meta, ctx.acwi),
                     "basket": exposure.exposures(new, meta, ctx.acwi)},
        "factors": factors(new, R, market),
        "risk": {"basket": prop["risk"], "before": riskmodel.ex_ante_risk(vals, cov, bench) if vals else None, "after": prop["after"]},
        "model": {"horizon": horizon, "study": sv, "drift_gross": hv["drift_gross"], "cost_pct": cost_pct,
                  "drift_net": prop["drift_net"], "bootstrap": prop["bootstrap"],
                  "realised_dd_1y": prop["realised_dd_1y"], "realised_dd_3y": prop["realised_dd_3y"]},
        "drawdown": dd, "stress": st, "alternatives": alts, "decision": decision,
        "ask": draft.ask_account(ctx, amount) if ctx.portfolio["kind"] == "ask" else None,
        "caveats": [
            "The expected excess comes from the rule study (the same rule on past month-ends), cut by a "
            "survivorship haircut and shrunk toward the long-run prior (JKP's survivorship-free tercile portfolios "
            "since prior.since); the picks' own past returns are not used: they were chosen for being high.",
            "The bootstrap and the stress windows describe risk, not a forecast; ACWI's drift is an assumption "
            f"({c.acwi_drift_annual:.0%} a year).",
            "Returns are before tax. Spreads are estimates by liquidity bucket.",
        ],
    })


def factors(values: dict[str, float], R: pd.DataFrame, market: Market) -> dict | None:
    from ..signals import risk as rk

    bench = tracked.benchmark()
    rp = riskmodel.weekly_returns(values, R, bench)
    if rp is None or bench not in R:
        return None
    tilts = {f: R[f] for f in typed().risk.factors if f in R}
    rf = market.fred().get("DGS3MO")   # None without the series: raw returns, said by alpha_basis
    return rk.factor_loadings(rp, R[bench], tilts, rf, rules.cfg().history_weeks, rules.cfg().min_weeks)


def decide(prop: dict, hv: dict, dd: dict, tolerance: float | None, c: Propose) -> dict:
    """The pre-committed rule: stocks only if the modelled excess after costs beats ACWI by `min_edge`, the
    holdout agrees in sign, and the bad-case drawdown is within your tolerance."""
    net = prop["drift_net"]
    hold = ((hv.get("kept") or {}).get("holdout") or {})
    checks = {"edge": None if net is None else net > c.min_edge,
              "holdout_sign": None if hold.get("gross_mean") is None else hold["gross_mean"] > 0,
              "drawdown": None if tolerance is None or dd["bad_case"] is None else dd["bad_case"] >= -abs(tolerance)}
    if net is None:
        verdict, why = "A0", "no evidence for an edge (the rule study is missing or stale): ACWI is the default"
    elif all(v is not False for v in checks.values()) and checks["edge"]:
        verdict, why = "stocks", "the modelled edge after costs clears the bar and nothing contradicts it"
    else:
        failed = [k for k, v in checks.items() if v is False]
        verdict, why = "A0", "fails: " + ", ".join(failed) + " (ACWI, or topping up / ETFs, is the disciplined choice)"
    return {"verdict": verdict, "why": why, "checks": checks, "min_edge": c.min_edge, "tolerance": tolerance,
            "unchecked": [k for k, v in checks.items() if v is None]}


def alternatives(ctx: draft.Ctx, scored: pd.DataFrame, raw: pd.DataFrame, tickers: list[str], amount: float, n: int,
                 tilt: str, mode: str,
                 weighting: str, max_position, horizon: int, cov: pd.DataFrame, R: pd.DataFrame,
                 vals: dict[str, float], meta: pd.DataFrame, c: Propose) -> dict:
    """A0-A6 on the same metrics."""
    bench = tracked.benchmark()
    study = drift.load_study()
    out = {}

    def rec(label: str, values: dict, drift, cost, tests: str, extra: dict | None = None, draws: int = 2000):
        missing = [t for t in values if t not in cov.index and t not in exposure.look_through()]
        if missing:
            more = ctx.prices.weekly(missing, c.history_weeks)
            R2 = pd.concat([R, more], axis=1)
            cv = riskmodel.shrunk_cov(R2.reindex(columns=[x for x in dict.fromkeys([*cov.index, *missing]) if x in R2]),
                            c.shrink, c.min_weeks)
        else:
            R2, cv = R, cov
        mt = alternative_metrics(values, ctx, cv, R2, horizon, drift, cost, c, vals, draws)
        return {"label": label, "tests": tests, "values": values, **mt, **(extra or {})}

    a0_cost = _cost_one(ctx.prices, ctx.sf, c.etf_filler.ticker, amount)
    out["A0"] = rec("ACWI UCITS for the whole amount", {bench: amount}, 0.0, a0_cost,
                    "the null: every proposal must beat it")
    chosen, _, sz = draft.rule_basket(ctx, scored, amount, n, mode, max_position, weighting)
    rv = drift.study_view(study, tilt, n, horizon, ctx.regime, c, ctx.trend)
    out["A1"] = rec("The rule-only basket (no judgment)", {r["ticker"]: r["value_dkk"] for r in sz["rows"] if r["value_dkk"]},
                    rv["drift_gross"], sz["roundtrip_pct"], "whether the judgment's swaps add anything",
                    {"tickers": [x["ticker"] for x in chosen]})
    for other in [t for t in rules.TILTS if t != tilt]:
        sc, _, _ = draft.ranked_pool(ctx, other, amount / n, raw=raw)
        ch, _, szo = draft.rule_basket(ctx, sc, amount, n, mode, max_position, weighting)
        ov = drift.study_view(study, other, n, horizon, ctx.regime, c, ctx.trend)
        out[f"A2-{other}"] = rec(f"The rule basket with the {other} tilt", {r["ticker"]: r["value_dkk"] for r in szo["rows"]
                                                                          if r["value_dkk"]},
                                 ov["drift_gross"], szo["roundtrip_pct"], "whether the tilt matters today",
                                 {"tickers": [x["ticker"] for x in ch]})
    frontier = []
    for k in range(1, basket.n_for(amount, c) + 1):
        ch, _, szk = draft.rule_basket(ctx, scored, amount, k, mode, max_position, weighting)
        v = {r["ticker"]: r["value_dkk"] for r in szk["rows"] if r["value_dkk"]}
        rk_ = riskmodel.ex_ante_risk(v, cov if all(t in cov.index for t in v) else riskmodel.shrunk_cov(
            pd.concat([R, ctx.prices.weekly([t for t in v if t not in R], c.history_weeks)], axis=1),
            c.shrink, c.min_weeks), bench)
        kv = drift.study_view(study, tilt, k, horizon, ctx.regime, c, ctx.trend)
        frontier.append({"n": k, "tickers": [x["ticker"] for x in ch], "cost_pct": szk["roundtrip_pct"],
                         "vol_ann": rk_["vol_ann"], "te_ann": rk_["te_ann"], "drift_gross": kv["drift_gross"],
                         "study_n": kv["n_used"]})
    knee = next((f["n"] for f, g in zip(frontier, frontier[1:]) if f["vol_ann"] is not None and g["vol_ann"] is not None
                 and f["vol_ann"] - g["vol_ann"] < c.frontier_knee), frontier[-1]["n"] if frontier else None)
    out["A3"] = {"label": "Basket size: fewer or more names for the same amount", "tests": "diversification vs fee drag",
                 "frontier": frontier, "knee": knee}
    stocks = {t: v for t, v in vals.items() if t not in exposure.look_through()}
    tot = sum(stocks.values())
    if tot > 0:
        top = {t: amount * v / tot for t, v in stocks.items()}
        cost = cost_share([(_cost_one(ctx.prices, ctx.sf, t, a), a) for t, a in top.items()], amount)
        out["A4"] = rec("Top up current holdings pro rata", top, None, cost,
                        "no new names, no new research (no study drift: n/a)",
                        {"tickets_below_min": sum(a < c.min_ticket_dkk for a in top.values())})
    else:
        out["A4"] = {"label": "Top up current holdings pro rata", "tests": "no new names", "note": "nothing held to top up"}
    etf_of = {}
    for t in tickers:
        reg = "europe" if meta["region"].get(t) in ("europe", "nordic") else "us"
        se = ((universe_config().get("sector_etfs") or {}).get(reg) or {}).get(meta["sector"].get(t))
        etf_of[t] = se if isinstance(se, str) else bench
    a5: dict[str, float] = {}
    for t in tickers:
        a5[etf_of[t]] = a5.get(etf_of[t], 0.0) + amount / len(tickers)
    out["A5"] = rec("Sector ETFs with the basket's sector mix", a5, None,
                    _mean_known([_cost_one(ctx.prices, ctx.sf, t, v) for t, v in a5.items()]),
                    "whether picking stocks adds anything beyond the exposure (US/EU sector ETFs as proxies: buy "
                    "UCITS equivalents)", {"map": etf_of})
    out["A6"] = randoms(scored, tickers, amount, n, ctx, cov, R, vals, c)
    return out


def randoms(scored: pd.DataFrame, tickers: list[str], amount: float, n: int, ctx: draft.Ctx, cov: pd.DataFrame,
            R: pd.DataFrame, vals: dict[str, float], c: Propose, draws: int = 300) -> dict:
    """Random baskets of the same size from the gated pool under the same caps: where the proposal's ex-ante
    volatility, tracking error and diversification ratio sit among them."""
    bench = tracked.benchmark()
    pool_ = [t for t in scored.index if t in cov.index]
    if len(pool_) < n * 2:
        return {"label": "Random baskets", "note": "too few names with a return history in the pool"}
    rng = np.random.default_rng(c.bootstrap.seed)
    base = draft.holdings_base(ctx, pool_)
    stats: dict[str, list[float]] = {"vol_ann": [], "te_ann": [], "div_ratio": []}
    for _ in range(draws):
        order = scored.loc[pool_].iloc[rng.permutation(len(pool_))].assign(composite=np.arange(len(pool_), 0, -1))
        ch, _ = basket.select(order, n, amount, base, c)
        if len(ch) < n:
            continue
        r = riskmodel.ex_ante_risk({x["ticker"]: amount / n for x in ch}, cov, bench)
        for k in stats:
            if r[k] is not None:
                stats[k].append(r[k])
    me = riskmodel.ex_ante_risk({t: amount / n for t in tickers}, cov, bench)
    out = {"label": "Random baskets of the same size and caps", "tests": "where the proposal sits among chance",
           "draws": len(stats["vol_ann"]), "seed": c.bootstrap.seed}
    for k, v in stats.items():
        if v and me[k] is not None:
            a = np.array(v)
            out[k] = {"proposal": me[k], "median": float(np.median(a)), "percentile": float((a < me[k]).mean() * 100)}
    return out
