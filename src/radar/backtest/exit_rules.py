"""Variants of the exit rule on every month-end's top-N basket: return and risk (max drawdown,
volatility, worst 20 sessions, the 10 % worst outcome, Sharpe / Sortino / Calmar / IR) against
holding, in-sample and in the holdout, with a pass/fail verdict; `radar study exits` ->
reports/exit-study.json."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import money, performance, simulate, universe
from ..config import settings
from ..model import artifacts
from ..model.panels import Panels, fill_session, formation_dates, panels
from ..model.stats import mean as _mean
from ..model.stats import (
    nw_t,
    path_stats,
    risk_adjusted,
)
from ..signals.risk import annualised_vol
from . import study


def exit_rule_variants():
    """The exit rule's variants (RuleSpec) that `radar study exits` compares, the current rule first."""
    from .exits import RuleSpec as R

    wide4 = (("k_base", 4.0), ("k_min", 3.0), ("k_max", 5.0))
    return [
        R(),
        R("atr-tp", "ATR stop with take-profit (the rule until 2026-10)"),
        R("tp-off", "ATR stop, take-profit off", tp="off"),
        R("tp-off-noext", "TP off, no tightening when extended", (("extended_vs_sma50", None),), tp="off"),
        R("k4", "TP off, k 4 (3-5)", wide4, tp="off"),
        R("k5", "TP off, k 5 (4-6)", (("k_base", 5.0), ("k_min", 4.0), ("k_max", 6.0)), tp="off"),
        R("atr63-k4", "TP off, ATR over 63 days, k 4 (3-5)", (("atr_days", 63),) + wide4, tp="off"),
        R("trail20", "20 % trail from the high", tp="off", stop="pct", pct=0.20),
        R("trail30", "30 % trail from the high", tp="off", stop="pct", pct=0.30),
        R("sma200", "Close below the 200-day average", tp="off", stop="trend", sma=200),
        R("sma100", "Close below the 100-day average", tp="off", stop="trend", sma=100),
    ]


EXIT_HORIZONS = (3, 6)


COST_PER_6M = 0.02            # a variant may cost at most this much return per 6 months against holding


DD_CUT = 0.25                 # ... and must cut the mean max drawdown by at least this share


FIRST_CANDIDATE = 4           # variants from this index on are candidates for the re-entry run


MIXES = (0.75, 0.5)           # no exit rule: the basket at this weight, the rest in ACWI from the start (sizing)


def path(rows: list[dict], market, start: pd.Timestamp, end: pd.Timestamp, bench: pd.Series | None = None,
         rf: pd.Series | None = None) -> dict | None:
    """Return, max drawdown, volatility and worst 20-session return of a run's value from `start` to `end`, per DKK
    put in (the first day's buying fees included). None when the value at the end is unknown. With `rf` (a daily
    return series): Sharpe and Sortino of the daily returns over it, annualised; with `bench` (ACWI in DKK): the
    information ratio and tracking error against it. Calmar is the annualised return over the max drawdown."""
    rows = [dict(r, fee=r.get("fee") or 0.0, currency="DKK" if r["type"] not in ("BUY", "SELL") else None) for r in rows]
    b = performance.book(rows, market)
    if b is None:
        return None
    v = b.value.loc[start:end].dropna()
    if not len(v) or v.index[-1] != end:
        return None
    ext = float((b.inflow - b.outflow).loc[:end].sum())
    if ext <= 0:
        return None
    idx = v / ext
    r = idx.pct_change().dropna()
    p = path_stats(idx)
    out = {"ret": p["ret"], "max_dd": p["max_dd"], "vol": annualised_vol(r) if len(r) > 2 else None,
           "worst20": p["worst20"]}
    out |= risk_adjusted(idx, out["max_dd"], bench, rf)
    return out


def _pct(v, q):
    v = [x for x in v if x is not None]
    return float(np.percentile(v, q)) if v else None


def summarize_exits(recs: list[dict], key: str, lag: int) -> dict | None:
    """Across dates, one variant (`key`) against holding on the same dates."""
    pairs = [(r["hold"], r[key]) for r in recs if r.get("hold") and r.get(key)]
    if not pairs:
        return None
    hold, var = [h for h, _ in pairs], [v for _, v in pairs]
    diff = [v["ret"] - h["ret"] for h, v in pairs]
    out = {"dates": len(pairs), "ret_mean": _mean([v["ret"] for v in var]), "ret_median": _pct([v["ret"] for v in var], 50),
           "ret_p10": _pct([v["ret"] for v in var], 10), "diff_mean": _mean(diff), "diff_median": _pct(diff, 50),
           "diff_t": nw_t(diff, lag), "helped": _mean([float(x > 0) for x in diff]),
           "dd_mean": _mean([v["max_dd"] for v in var]), "dd_worst": min(v["max_dd"] for v in var),
           "vol_mean": _mean([v["vol"] for v in var]), "worst20_mean": _mean([v["worst20"] for v in var]),
           "hold": {"ret_mean": _mean([h["ret"] for h in hold]), "ret_p10": _pct([h["ret"] for h in hold], 10),
                    "dd_mean": _mean([h["max_dd"] for h in hold]), "dd_worst": min(h["max_dd"] for h in hold),
                    "vol_mean": _mean([h["vol"] for h in hold]), "worst20_mean": _mean([h["worst20"] for h in hold])},
           "exits_mean": _mean([r.get(f"{key}_exits") for r in recs if r.get(key)]),
           "reentries_mean": _mean([r.get(f"{key}_reentries") for r in recs if r.get(key)])}
    for m in RISK_KEYS:
        out[f"{m}_mean"] = _mean([v.get(m) for v in var])
        out["hold"][f"{m}_mean"] = _mean([h.get(m) for h in hold])
    sd = [v["sharpe"] - h["sharpe"] for h, v in pairs if v.get("sharpe") is not None and h.get("sharpe") is not None]
    out["sharpe_diff_mean"], out["sharpe_diff_t"] = _mean(sd), nw_t(sd, lag) if sd else None
    rd = out["ret_mean"] / abs(out["dd_mean"]) if out["dd_mean"] else None
    hd = out["hold"]["ret_mean"] / abs(out["hold"]["dd_mean"]) if out["hold"]["dd_mean"] else None
    out["ret_per_dd"], out["hold"]["ret_per_dd"] = rd, hd
    return out


RISK_KEYS = ("ann_ret", "sharpe", "sortino", "calmar", "ir", "te")


def exit_verdict(parts: dict, months: int) -> dict:
    """Passes when, in-sample and in the holdout, it costs at most COST_PER_6M (pro rata) of mean return against
    holding, cuts the mean max drawdown by DD_CUT and lifts the 10 % worst outcome."""
    limit = COST_PER_6M * months / 6
    why = []
    for part in ("in_sample", "holdout"):
        s = parts.get(part)
        if not s or s["dates"] < 3:
            return {"label": "not enough data", "why": [f"too few {part.replace('_', '-')} dates"]}
        if s["diff_mean"] < -limit:
            why.append(f"{part.replace('_', '-')}: costs {-s['diff_mean']:.1%} (limit {limit:.0%})")
        if not s["dd_mean"] >= (1 - DD_CUT) * s["hold"]["dd_mean"]:
            why.append(f"{part.replace('_', '-')}: drawdown {s['dd_mean']:.1%} vs held {s['hold']['dd_mean']:.1%} "
                       f"(needs a {DD_CUT:.0%} cut)")
        if not s["ret_p10"] > s["hold"]["ret_p10"]:
            why.append(f"{part.replace('_', '-')}: worst 10 % {s['ret_p10']:.1%} vs held {s['hold']['ret_p10']:.1%}")
    return {"label": "passes" if not why else "fails", "why": why, "cost_limit": limit}


def exit_variants(market, n_top: int = 15, horizons=EXIT_HORIZONS, keys: list[str] | None = None, since=None,
                  reentry: bool = True, log=lambda *_: None, p: Panels | None = None) -> dict:
    """Each month-end's top-N basket (equal weights, fees) held against every variant of the exit rule over each
    horizon: return and risk (max drawdown, volatility, worst 20 sessions, the 10 % worst outcome), split in-sample
    and holdout, with a verdict per variant (exit_verdict). With `reentry`, the variant that did best in-sample
    on the longest horizon is also run with re-entry."""
    from dataclasses import replace

    from . import exits as ex
    from .pit import Context

    bt = settings().get("backtest") or {}
    fee = money.fee_bps(bt)
    park = bt.get("park") or universe.benchmark()
    holdout = pd.Timestamp(bt.get("study_holdout_from")) if bt.get("study_holdout_from") else None
    specs = exit_rule_variants()
    if keys:
        unknown = set(keys) - {s.key for s in specs}
        if unknown:
            raise ValueError(f"unknown exit variant(s): {', '.join(sorted(unknown))} (known: {', '.join(s.key for s in specs)})")
        specs = [s for s in specs if s.key in keys or s.key == "rule"]
    for h in horizons:
        if h not in study.HORIZONS:
            raise ValueError(f"horizons are months among {', '.join(map(str, study.HORIZONS))}")
    p = p or panels(market)
    longest = max(horizons)
    baskets = []
    for day in formation_dates(p.sessions, since):
        fi = fill_session(p.sessions, day, bt.get("fill", "next"))
        if fi is None or fi + study.HORIZONS[min(horizons)] >= len(p.sessions):
            continue
        names = study.top_names(p, day, n_top)
        if len(names) >= n_top:
            baskets.append((day, fi, names))
    if not baskets:
        raise ValueError("no formation date with a complete horizon: not enough price history yet")
    ctx = study.fast(Context.build(market, {t for _, _, b in baskets for t in b} | {park}), p)
    log(f"{len(baskets)} formation dates, {len(specs)} variants{' + re-entry' if reentry else ''}")

    def run_spec(spec, recs):
        for i, (_day, fi, _names) in enumerate(baskets):
            rec = recs[i]
            if rec is None:
                continue
            rep = ex.replay(rec["_rows"], ctx, "rules", end=rec["_end"], fee_bps=fee, spec=spec)
            res = {}
            for h in horizons:
                if fi + study.HORIZONS[h] < len(p.sessions):
                    res[h] = path(rep["rows"], market, p.sessions[fi], p.sessions[fi + study.HORIZONS[h]])
            rec["_by"][spec.key] = res
            rec[f"{spec.key}_exits"] = len(rep["exits"])
            rec[f"{spec.key}_reentries"] = len(rep.get("reentries") or [])
        log(f"  {spec.key}: done")

    recs = []
    for day, fi, names in baskets:
        f = p.sessions[fi]
        rows, problems = simulate.basket_rows(market, {t: 1 / len(names) for t in names}, f, 100_000.0, fee)
        if not rows:
            recs.append(None)
            continue
        end = p.sessions[min(fi + study.HORIZONS[longest], len(p.sessions) - 1)]
        ends = {h: p.sessions[fi + study.HORIZONS[h]] for h in horizons if fi + study.HORIZONS[h] < len(p.sessions)}
        by = {"hold": {h: path(rows, market, f, e) for h, e in ends.items()}}
        for w in MIXES:
            mix, _ = simulate.basket_rows(market, {**{t: w / len(names) for t in names}, park: 1 - w}, f, 100_000.0, fee)
            by[_mix_key(w)] = {h: path(mix, market, f, e) for h, e in ends.items()} if mix else {}
        recs.append({"date": day, "fill": f, "_rows": rows, "_end": end, "_by": by, "skipped": problems,
                     **{f"{_mix_key(w)}_exits": 0 for w in MIXES}})
    for spec in specs:
        run_spec(spec, recs)

    def table(spec_keys):
        out = {}
        for h in horizons:
            lag = max(h - 1, 0)
            flat = []
            for r in recs:
                if r is None or h not in r["_by"]["hold"] or not r["_by"]["hold"][h]:
                    continue
                flat.append({"date": r["date"], "hold": r["_by"]["hold"][h],
                             **{k: r["_by"].get(k, {}).get(h) for k in spec_keys},
                             **{f"{k}_exits": r.get(f"{k}_exits") for k in spec_keys},
                             **{f"{k}_reentries": r.get(f"{k}_reentries") for k in spec_keys}})
            out[str(h)] = {}
            for k in spec_keys:
                parts = {"all": summarize_exits(flat, k, lag),
                         "in_sample": summarize_exits([x for x in flat if holdout is None or x["date"] < holdout], k, lag),
                         "holdout": summarize_exits([x for x in flat if holdout is not None and x["date"] >= holdout], k, lag)}
                out[str(h)][k] = parts | {"verdict": exit_verdict(parts, h)}
        return out

    mixes = [_mix_key(w) for w in MIXES]
    results = table([s.key for s in specs] + mixes)
    chosen = None
    if reentry:
        cands = [(s, results[str(longest)][s.key]["in_sample"]) for s in specs[FIRST_CANDIDATE:]]
        cands = [(s, x) for s, x in cands if x]
        cut = [(s, x) for s, x in cands if x["dd_mean"] >= (1 - DD_CUT) * x["hold"]["dd_mean"]]
        pick = max(cut, key=lambda c: c[1]["diff_mean"]) if cut else \
            max(cands, key=lambda c: c[1]["ret_per_dd"] or -1e9) if cands else None
        if pick:
            chosen = replace(pick[0], key=f"{pick[0].key}-re", label=f"{pick[0].label}, with re-entry", reentry=True)
            specs.append(chosen)
            run_spec(chosen, recs)
            results = table([s.key for s in specs] + mixes)
    per_date = []
    for r in recs:
        if r is None:
            continue
        per_date.append({"date": r["date"].date().isoformat(), "fill": r["fill"].date().isoformat(), "skipped": r["skipped"],
                         **{k: {str(h): v for h, v in by.items()} for k, by in r["_by"].items()}})
    return {
        "generated": pd.Timestamp.now().isoformat(timespec="seconds"), "asof": p.sessions[-1].date().isoformat(),
        "settings": {"n_top": n_top, "fee_bps": fee, "park": park, "horizons": list(horizons),
                     "holdout_from": holdout.date().isoformat() if holdout is not None else None,
                     "cost_per_6m": COST_PER_6M, "dd_cut": DD_CUT},
        "variants": [{"key": s.key, "label": s.label, "stops": dict(s.stops), "tp": s.tp, "stop": s.stop,
                      "pct": s.pct if s.stop == "pct" else None, "sma": s.sma if s.stop == "trend" else None,
                      "reentry": s.reentry} for s in specs]
                    + [{"key": _mix_key(w), "label": f"No exits: {w:.0%} in the basket, {1 - w:.0%} in {park} (sizing)",
                        "stops": {}, "tp": "off", "stop": "none", "pct": None, "sma": None, "reentry": False, "mix": w}
                       for w in MIXES],
        "variants_tried": len(specs), "reentry_on": chosen.key if chosen else None,
        "results": results, "dates": per_date,
        "caveats": [study.CAVEATS[0], "The rule as it would have been set then: analyst data didn't exist for most of the "
                    "period, so it moves nothing there. The baskets are the score's top N, held without rebalancing; "
                    "exits are parked in ACWI.", study.CAVEATS[4], study.CAVEATS[5]],
    }


def _mix_key(w: float) -> str:
    return f"mix{round(w * 100)}"


EXIT_REPORT_FILE = "exit-study.json"


def write_exits(rep: dict) -> None:
    artifacts.write("exit-study", rep, data_asof=rep["asof"], file=EXIT_REPORT_FILE)
