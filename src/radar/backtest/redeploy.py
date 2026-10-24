"""Redeploying the exit money: instead of parking a stopped-out position in ACWI, buy the best-scoring
name not held (`Picker`), or rotate at month-ends out of names outside a rank buffer; park /
redeploy / rotation arms compared on return and risk; `radar study redeploy` ->
reports/redeploy-study.json."""
from __future__ import annotations

from collections.abc import Collection
from typing import TYPE_CHECKING, Any

import pandas as pd

from .. import simulate, tracked
from ..config import typed
from ..model import artifacts
from ..model.panels import Panels, fill_session, formation_dates, panels, score_at
from ..model.stats import (
    daily_rf,
    nw_t,
)
from ..model.stats import mean as _mean
from . import exit_rules, study

if TYPE_CHECKING:
    from ..market import Market


class Picker:
    """The candidates for a redeploy, from data up to the day asked: the names with a price, a DKK rate and a
    score, best first. `pick` gives the best one not held and not barred that is in an uptrend (`trend`) and fits
    the caps given what is held; `rank` is a name's place among all of them (1 = best, None = unranked)."""

    def __init__(self, p: Panels, n: int, max_per_sector: int | None = None, max_per_group: int | None = None,
                 trend: bool = True):
        self.p, self.n, self.max_sector, self.max_group, self.trend = p, n, max_per_sector, max_per_group, trend
        self._ranked: dict = {}

    def ranked(self, day: pd.Timestamp) -> pd.Series:
        if day not in self._ranked:
            p = self.p
            if day not in p.m["last"].index:
                self._ranked[day] = pd.Series(dtype=float)
            else:
                ok = p.m["last"].loc[day].notna() & p.dkk.loc[day].notna()
                self._ranked[day] = score_at(p, day).where(ok).dropna().sort_values(ascending=False, kind="stable")
        return self._ranked[day]

    def rank(self, day: pd.Timestamp, t: str) -> int | None:
        r = self.ranked(day)
        return int(r.index.get_loc(t)) + 1 if t in r.index else None

    def _key(self, t: str) -> tuple[str, str]:
        sec = self.p.sector.get(t, "") if t in self.p.sector.index else ""
        sec = sec if isinstance(sec, str) and sec.strip() else f"?{t}"
        grp = self.p.group.get(t) if t in self.p.group.index else None
        return sec, grp if isinstance(grp, str) else f"?{t}"

    def capped(self, day: pd.Timestamp, n: int, held: Collection[str] = frozenset(), barred: Collection[str] = frozenset(),
               trend: bool | None = None) -> list[str]:
        """Up to `n` names, best first, that can be added to `held` under the caps."""
        trend = self.trend if trend is None else trend
        tr = self.p.m["trend_ok"]
        up = set(tr.columns[tr.loc[day].eq(True)]) if trend and day in tr.index else None
        sec: dict[str, int] = {}
        grp: dict[str, int] = {}
        for t in held:
            a, b = self._key(t)
            sec[a], grp[b] = sec.get(a, 0) + 1, grp.get(b, 0) + 1
        out = []
        for t in self.ranked(day).index:
            if t in held or t in barred or (up is not None and t not in up):
                continue
            a, b = self._key(t)
            if (self.max_sector and sec.get(a, 0) >= self.max_sector) or (self.max_group and grp.get(b, 0) >= self.max_group):
                continue
            out.append(t)
            sec[a], grp[b] = sec.get(a, 0) + 1, grp.get(b, 0) + 1
            if len(out) >= n:
                break
        return out

    def pick(self, day: pd.Timestamp, held: set[str], barred: set[str]) -> str | None:
        c = self.capped(day, 1, held, barred)
        return c[0] if c else None


REDEPLOY_HORIZONS = (6, 12)


BUFFER = 3                    # rotation: sell at month-end a holding ranked outside BUFFER x N


COOLDOWN = 21                 # sessions before a sold name can be bought again by redeploy


def _redeploy_arms(buffer: int = BUFFER, cooldown: int = COOLDOWN):
    """(spec, twin): each arm with the arm it is judged against besides holding (redeploy against parking the
    same exits; a rotation with an exit rule against the rotation alone)."""
    from .exits import RuleSpec as R

    atr = (("mode", "atr"),)
    sc: dict[str, Any] = {"redeploy": "score", "cooldown": cooldown}
    rot = sc | {"rotate": buffer}
    arms = [
        (R("sma200-park", "Close below the 200-day average, parked in ACWI", tp="off", stop="trend", sma=200), None),
        (R("sma200-redeploy", "Close below the 200-day average, redeployed", tp="off", stop="trend", sma=200, **sc),
         "sma200-park"),
        (R("atr-tp-park", "ATR stop and take-profit, parked in ACWI", atr), None),
        (R("atr-tp-redeploy", "ATR stop and take-profit, redeployed", atr, **sc), "atr-tp-park"),
        (R("tp-only-park", "Take-profit only, parked in ACWI", atr, stop="none"), None),
        (R("tp-only-redeploy", "Take-profit only, redeployed", atr, stop="none", **sc), "tp-only-park"),
        (R("rotate", f"No exit rule; month-end rotation out of names outside the top {buffer}xN", tp="off",
           stop="none", **rot), None),
        (R("rotate-sma200", "Rotation and the 200-day stop, redeployed", tp="off", stop="trend", sma=200, **rot),
         "rotate"),
        (R("rotate-atr-tp", "Rotation and the ATR stop with take-profit, redeployed", atr, **rot), "rotate"),
        (R("rotate-tp-only", "Rotation and the take-profit only, redeployed", atr, stop="none", **rot), "rotate"),
    ]
    return arms


def _paired(flat: list[dict], a: str, b: str, metric: str, lag: int) -> dict | None:
    d = [x[a][metric] - x[b][metric] for x in flat
         if x.get(a) and x.get(b) and x[a].get(metric) is not None and x[b].get(metric) is not None]
    return {"mean": _mean(d), "t": nw_t(d, lag), "share": _mean([float(v > 0) for v in d]), "dates": len(d)} if d else None


def redeploy_verdict(parts: dict, months: int) -> dict:
    """Better risk-adjusted only when, in-sample and in the holdout, its mean Sharpe beats holding and its twin's
    (parking the same exits, or the rotation alone) and its mean return costs at most COST_PER_6M (pro rata)
    against holding."""
    limit = exit_rules.COST_PER_6M * months / 6
    why = []
    for part in ("in_sample", "holdout"):
        s = parts.get(part)
        name = part.replace("_", "-")
        if not s or s["dates"] < 3 or s.get("sharpe_mean") is None:
            return {"label": "not enough data", "why": [f"too few {name} dates (or no risk-free rate)"]}
        if not s["sharpe_mean"] > s["hold"]["sharpe_mean"]:
            why.append(f"{name}: Sharpe {s['sharpe_mean']:.2f} vs held {s['hold']['sharpe_mean']:.2f}")
        tw = (parts.get("vs_twin") or {}).get(part)
        if tw is not None and not tw["sharpe"]["mean"] > 0:
            why.append(f"{name}: Sharpe {tw['sharpe']['mean']:+.2f} vs {parts['twin']}")
        if s["diff_mean"] < -limit:
            why.append(f"{name}: costs {-s['diff_mean']:.1%} (limit {limit:.0%})")
    return {"label": "better" if not why else "not better", "why": why, "cost_limit": limit}


def redeploy_study(market: Market, n_top: int = 15, horizons=REDEPLOY_HORIZONS, buffer: int = BUFFER, cooldown: int = COOLDOWN,
                   max_per_sector: int | None = None, max_per_group: int | None = None, trend: bool = True, since=None,
                   keys: list[str] | None = None, log=lambda *_: None, p: Panels | None = None) -> dict:
    """Each month-end's top N (under the caps, equal weights, fees) held against the exit rules with the money
    parked in ACWI and redeployed into the next momentum name, and against a month-end rotation with and without
    the rules: return, risk and risk-adjusted return per horizon, in-sample and holdout, with a verdict per arm."""
    from . import exits as ex
    from .pit import Context

    bt = typed().backtest
    fee = bt.fee_bps
    park = bt.park or tracked.benchmark()
    holdout = pd.Timestamp(bt.study_holdout_from)
    arms = _redeploy_arms(buffer, cooldown)
    if keys:
        unknown = set(keys) - {s.key for s, _ in arms}
        if unknown:
            raise ValueError(f"unknown arm(s): {', '.join(sorted(unknown))} (known: {', '.join(s.key for s, _ in arms)})")
        want = set(keys) | {t for s, t in arms if s.key in keys and t}
        arms = [(s, t) for s, t in arms if s.key in want]
    for h in horizons:
        if h not in study.HORIZONS:
            raise ValueError(f"horizons are months among {', '.join(map(str, study.HORIZONS))}")
    p = p or panels(market)
    picker = Picker(p, n_top, max_per_sector, max_per_group, trend)
    rf = daily_rf(market)
    bench = p.bench_dkk
    longest = max(horizons)
    baskets = []
    for day in formation_dates(p.sessions, since):
        fi = fill_session(p.sessions, day, bt.fill)
        if fi is None or fi + study.HORIZONS[min(horizons)] >= len(p.sessions):
            continue
        names = picker.capped(day, n_top, trend=False)
        if len(names) >= n_top:
            baskets.append((day, fi, names))
    if not baskets:
        raise ValueError("no formation date with a complete horizon: not enough price history yet")
    ctx = study.fast(Context.build(market, set(p.closes.columns) | {park}), p)
    log(f"{len(baskets)} formation dates, {len(arms)} arms, {len(p.closes.columns)} names to redeploy into")

    recs: list[dict | None] = []
    for day, fi, names in baskets:
        f = p.sessions[fi]
        rows, problems = simulate.basket_rows(market, {t: 1 / len(names) for t in names}, f, 100_000.0, fee)
        if not rows:
            recs.append(None)
            continue
        ends = {h: p.sessions[fi + study.HORIZONS[h]] for h in horizons if fi + study.HORIZONS[h] < len(p.sessions)}
        end = p.sessions[min(fi + study.HORIZONS[longest], len(p.sessions) - 1)]
        by = {"hold": {h: exit_rules.path(rows, market, f, e, bench, rf) for h, e in ends.items()}}
        for key, w in (("mix50", 0.5), ("acwi", 0.0)):
            mix, _ = simulate.basket_rows(market, {**({t: w / len(names) for t in names} if w else {}), park: 1 - w},
                                       f, 100_000.0, fee)
            by[key] = {h: exit_rules.path(mix, market, f, e, bench, rf) for h, e in ends.items()} if mix else {}
        recs.append({"date": day, "fill": f, "_rows": rows, "_end": end, "_ends": ends, "_by": by, "skipped": problems,
                     "names": names, "runs": {}})
    for spec, _ in arms:
        for rec in recs:
            if rec is None:
                continue
            rep = ex.replay(rec["_rows"], ctx, "rules", end=rec["_end"], fee_bps=fee, spec=spec,
                            picker=picker if spec.redeploy == "score" else None)
            rec["_by"][spec.key] = {h: exit_rules.path(rep["rows"], market, rec["fill"], e, bench, rf) for h, e in rec["_ends"].items()}
            trades = [r for r in rep["rows"] if r["type"] in ("BUY", "SELL") and r["symbol"] != park]
            kinds: dict = {}
            for e in rep["exits"]:
                kinds[e["trigger"]] = kinds.get(e["trigger"], 0) + 1
            rec["runs"][spec.key] = {"exits": len(rep["exits"]), "by_trigger": kinds, "redeploys": len(rep["redeploys"]),
                                     "skipped": sum(ev["kind"] == "redeploy skipped" for ev in rep["events"]),
                                     "trades": len(trades), "fees_pct": sum(r["fee"] * r["fx_rate"] for r in rep["rows"]
                                                                            if r["type"] in ("BUY", "SELL")) / 100_000.0,
                                     "new_names": sorted({r["symbol"] for r in rep["redeploys"]})}
            rec[f"{spec.key}_exits"] = len(rep["exits"])
        log(f"  {spec.key}: done")

    arm_keys = [s.key for s, _ in arms] + ["mix50", "acwi"]
    twins = {s.key: t for s, t in arms}
    results: dict = {}
    for h in horizons:
        lag = max(h - 1, 0)
        flat = []
        for r in recs:
            if r is None or not r["_by"]["hold"].get(h):
                continue
            flat.append({"date": r["date"], "hold": r["_by"]["hold"][h], **{k: r["_by"].get(k, {}).get(h) for k in arm_keys},
                         **{f"{k}_exits": r.get(f"{k}_exits", 0) for k in arm_keys}})
        split = {"all": flat, "in_sample": [x for x in flat if holdout is None or x["date"] < holdout],
                 "holdout": [x for x in flat if holdout is not None and x["date"] >= holdout]}
        results[str(h)] = {}
        for k in arm_keys:
            parts = {part: exit_rules.summarize_exits(xs, k, lag) for part, xs in split.items()}
            tw = twins.get(k)
            if tw:
                parts["twin"] = tw
                parts["vs_twin"] = {part: {"sharpe": _paired(xs, k, tw, "sharpe", lag), "ret": _paired(xs, k, tw, "ret", lag),
                                           "max_dd": _paired(xs, k, tw, "max_dd", lag)} for part, xs in split.items()}
            if k not in ("mix50", "acwi"):
                runs = [r["runs"][k] for r in recs if r is not None and k in r["runs"]]
                parts["activity"] = {"exits": _mean([x["exits"] for x in runs]), "redeploys": _mean([x["redeploys"] for x in runs]),
                                     "skipped": _mean([x["skipped"] for x in runs]), "trades": _mean([x["trades"] for x in runs]),
                                     "fees_pct": _mean([x["fees_pct"] for x in runs]),
                                     "by_trigger": {t: _mean([x["by_trigger"].get(t, 0) for x in runs])
                                                    for t in sorted({t for x in runs for t in x["by_trigger"]})},
                                     "over": f"{longest} months"}
            parts["verdict"] = redeploy_verdict(parts, h) if k not in ("mix50", "acwi") else None
            results[str(h)][k] = parts
    per_date = []
    for r in recs:
        if r is None:
            continue
        per_date.append({"date": r["date"].date().isoformat(), "fill": r["fill"].date().isoformat(), "names": r["names"],
                         "skipped": r["skipped"], "runs": r["runs"],
                         **{k: {str(h): v for h, v in by.items()} for k, by in r["_by"].items()}})
    return {
        "generated": pd.Timestamp.now().isoformat(timespec="seconds"), "asof": p.sessions[-1].date().isoformat(),
        "settings": {"n_top": n_top, "fee_bps": fee, "park": park, "horizons": list(horizons), "buffer": buffer,
                     "cooldown": cooldown, "max_per_sector": max_per_sector, "max_per_group": max_per_group,
                     "trend": trend, "holdout_from": holdout.date().isoformat() if holdout is not None else None,
                     "cost_per_6m": exit_rules.COST_PER_6M, "rf": "ECB deposit rate (FRED ECBDFR)" if rf is not None else None},
        "arms": [{"key": s.key, "label": s.label, "twin": t, "stop": s.stop, "tp": s.tp, "redeploy": s.redeploy,
                  "rotate": s.rotate, "cooldown": s.cooldown} for s, t in arms]
                + [{"key": "mix50", "label": f"No exits: 50% in the basket, 50% in {park} (sizing)", "twin": None},
                   {"key": "acwi", "label": f"All in {park}", "twin": None}],
        "results": results, "dates": per_date,
        "caveats": [
            "Survivorship: the universe is today's list, so every name redeployed into is one that survived to be on "
            "it. That flatters redeploying and rotating more than holding, which only ever owns the first basket.",
            "Sectors and stock groups (the caps) are today's.",
            "No tax: on frie midler every exit and rotation realises a gain or loss (realisationsbeskatning); on the "
            "aktiesparekonto (lagerbeskattet) turnover costs no extra tax. Trades and fees are given per arm so this "
            "can be judged.",
            "Sharpe and Sortino are over the ECB deposit rate (the krone follows the euro); annualised from 6- or "
            "12-month windows they are noisy, so compare them across arms, not with long-run figures.",
            "The rule as it would have been set then: analyst data didn't exist for most of the period, so it moves "
            "nothing there.",
        ] + ([] if rf is not None else ["No ECB deposit rate in the data: Sharpe and Sortino are missing."]),
    }


REDEPLOY_REPORT_FILE = "redeploy-study.json"


def write_redeploy(rep: dict) -> artifacts.RedeployStudy:
    out = artifacts.write("redeploy-study", rep, data_asof=rep["asof"], file=REDEPLOY_REPORT_FILE)
    assert isinstance(out, artifacts.RedeployStudy)
    return out
