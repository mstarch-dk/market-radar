"""The Evidence page: how well the scores have worked, read from the study reports and the forward record.

One card per score study (momentum, quality, value, K+V) and the long-run study, a header row for each rule study
(proposals, exits, redeploy), and a forward scoreboard of the A/B test, the `picks-live` paper trail and the frozen
proposals, each against ACWI over the same days. It only reads: the reports through model/artifacts.py (never
backtest/), the portfolios through portfolios/, and computes nothing a study or the portfolio code doesn't already
give. A report of another rule is `stale` and its numbers stay inside its own card; missing is None with a note.

The plan: plans/F2-evidence-page.md; the guide: brugervejledning/scoretest.md."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

import pandas as pd

from . import abtest
from .config import typed
from .model import artifacts as art
from .model.stats import mean
from .portfolios import performance, simulate
from .propose import rules, store

if TYPE_CHECKING:
    from .market import Market

DAYS_PER_MONTH = 365.25 / 12
SCORE_ROW = ("dates", "ic_mean", "ic_t", "ic_pos", "q", "monotone", "spread", "spread_t", "top_excess",
             "top_excess_t", "top_dkk", "acwi_dkk", "top_vs_acwi", "top_vs_acwi_t", "top_beats_acwi")
LONGRUN_ROW = ("dates", "eff_n", "ic_mean", "ic_t", "spread", "spread_t", "top_excess", "top_excess_t",
               "top_vs_market", "top_vs_market_t")
# Each mean and its t: a mean without its t in the report (an older one) gets a note, never a silent blank. The
# top N in DKK is judged against ACWI, by the t of the difference.
SCORE_T = {"ic_mean": "ic_t", "spread": "spread_t", "top_excess": "top_excess_t", "top_vs_acwi": "top_vs_acwi_t",
           "top_dkk": "top_vs_acwi_t"}
LONGRUN_T = {"ic_mean": "ic_t", "spread": "spread_t", "top_excess": "top_excess_t", "top_vs_market": "top_vs_market_t"}
RULE_STUDIES = (("propose-study", "Proposal rule"), ("exit-study", "Stop rule variants"),
                ("redeploy-study", "Money from an exit, redeployed"))


def _iso(d) -> str | None:
    return d.isoformat() if d is not None else None


def head(loaded: art.Loaded, label: str, command: str, rule_now: str | None, max_age: int, today: date,
         signal: str | None = None) -> dict:
    """A report's header row: status and why, age, the rule it tested and today's. `old_data`: an ok report whose
    last day of data is older than `max_age` days (the same rule, but the market has moved on)."""
    rep = loaded.report
    asof = rep.data_asof if rep is not None else None
    age = (today - asof).days if asof is not None else None
    return {"name": loaded.name, "signal": signal, "label": label, "status": loaded.status, "reason": loaded.reason,
            "command": command, "created": rep.created.isoformat(timespec="seconds") if rep is not None else None,
            "data_asof": _iso(asof), "age_days": age,
            "old_data": loaded.status == "ok" and age is not None and age > max_age,
            "rule_hash": rep.rule_hash if rep is not None else None, "rule_hash_now": rule_now,
            "legacy": loaded.legacy}


def _row(s, keys: tuple[str, ...]) -> dict | None:
    return None if s is None else {k: getattr(s, k) for k in keys}


def _t_missing(rows: list[dict | None], pairs: dict[str, str]) -> bool:
    return any(r is not None and r[m] is not None and r[t] is None for r in rows for m, t in pairs.items())


def _baseline(variants: list[art.VariantInfo], results: dict[str, dict], default: str) -> str | None:
    base = next((v.key for v in variants if v.baseline), None)
    if base:
        return base
    keys = [k for res in results.values() for k in res]
    return default if default in keys else (keys[0] if keys else None)


def _verdicts(verdicts: dict[str, dict[str, art.Verdict]]) -> list[dict]:
    return [{"h": int(h), "variant": k, "label": v.label, "in_sample_ic": v.in_sample_ic, "holdout_ic": v.holdout_ic,
             "holdout_ic_t": v.holdout_ic_t, "holdout_diff_t": v.holdout_diff_t}
            for h, per in verdicts.items() for k, v in per.items()]


def score_card(signal: str, today: date) -> dict:
    """One score study's card: the baseline per horizon (all, in-sample, holdout), each variant's verdict,
    turnover, the rank correlation with momentum (fund scores) and caveats. No numbers unless the report could be
    read (`ok`, or `stale`: shown greyed by the page)."""
    sig = art.SCORE_SIGNALS[signal]
    loaded = art.score(signal, rule_hash=art.study_rule_hash("score-study", signal))
    card: dict[str, Any] = {
        "head": head(loaded, sig.label, sig.command, art.study_rule_hash("score-study", signal),
                     typed().evidence.max_age_days.score, today, signal),
        "universe": None, "us_only": sig.fund, "baseline": None, "variants_tried": None, "n_top": None,
        "holdout_from": None, "horizons": [], "verdicts": [], "turnover": None, "momentum_corr": None,
        "caveats": [], "notes": []}
    rep = loaded.report
    if not isinstance(rep, art.ScoreStudy):
        return card
    u = rep.universe
    base = _baseline(rep.variants, rep.results, signal if sig.fund else "score")
    horizons: list[dict[str, Any]] = []
    for h, res in rep.results.items():
        v = res.get(base) if base else None
        horizons.append({"h": int(h), "all": _row(v.all if v else None, SCORE_ROW),
                         "in_sample": _row(v.in_sample if v else None, SCORE_ROW),
                         "holdout": _row(v.holdout if v else None, SCORE_ROW)})
    rows = [r for x in horizons for r in (x["all"], x["in_sample"], x["holdout"])]
    if _t_missing(rows, SCORE_T):
        card["notes"].append(f"Some t-statistics are not in this report (written before they were recorded): "
                             f"run `{sig.command}` again")
    if any(x["in_sample"] is None and x["all"] is not None for x in horizons):
        card["notes"].append("The in-sample split is not in this report: only all dates and the holdout are shown")
    mc = rep.momentum_corr
    card |= {"universe": {"tickers": u.tickers, "fund_names": u.fund_names, "first": u.first, "last": u.last},
             "baseline": base, "variants_tried": rep.variants_tried, "n_top": rep.settings.n_top,
             "holdout_from": rep.settings.holdout_from, "horizons": horizons, "verdicts": _verdicts(rep.verdicts),
             "turnover": rep.turnover.get(base) if base else None,
             "momentum_corr": mc.mean if mc is not None else None, "caveats": list(rep.caveats)}
    return card


def longrun_card(today: date) -> dict:
    """The long-run study's card: per panel the baseline per horizon (all, holdout), by decade and by recession,
    the verdicts; the survivorship gauge and the factors' base rates."""
    loaded = art.load("longrun-study", rule_hash=art.study_rule_hash("longrun-study"))
    card: dict[str, Any] = {
        "head": head(loaded, "Momentum over decades", art.ARTIFACTS["longrun-study"].command,
                     art.study_rule_hash("longrun-study"), typed().evidence.max_age_days.longrun, today),
        "holdout_from": None, "panels": [], "survivorship": None, "base_rates": [], "caveats": [], "notes": []}
    rep = loaded.report
    if not isinstance(rep, art.LongrunStudy):
        return card
    panels = []
    for key, p in rep.panels.items():
        base = _baseline(p.variants, p.results, "score")
        hs: list[dict[str, Any]] = []
        decades: list[dict] = []
        recessions: list[dict] = []
        for h, res in p.results.items():
            v = res.get(base) if base else None
            hs.append({"h": int(h), "all": _row(v.all if v else None, LONGRUN_ROW),
                       "holdout": _row(v.holdout if v else None, LONGRUN_ROW)})
            if v is not None:
                decades += [{"h": int(h), "part": d, "row": _row(s, LONGRUN_ROW)} for d, s in v.by_decade.items()]
                recessions += [{"h": int(h), "part": g, "row": _row(s, LONGRUN_ROW)} for g, s in v.by_recession.items()]
        if _t_missing([r for x in hs for r in (x["all"], x["holdout"])], LONGRUN_T):
            card["notes"].append(f"{p.label or key}: some t-statistics are not in this report: run "
                                 f"`{art.ARTIFACTS['longrun-study'].command}` again")
        panels.append({"key": key, "label": p.label, "members": p.members, "n_top": p.n_top, "months": p.months,
                       "first": _iso(p.first), "last": _iso(p.last), "baseline": base,
                       "variants_tried": p.variants_tried, "horizons": hs, "by_decade": decades,
                       "by_recession": recessions, "verdicts": _verdicts(p.verdicts), "error": None})
    panels += [{"key": k, "label": None, "members": None, "n_top": None, "months": None, "first": None,
                "last": None, "baseline": None, "variants_tried": None, "horizons": [], "by_decade": [],
                "by_recession": [], "verdicts": [], "error": e} for k, e in rep.errors.items() if k not in rep.panels]
    s = rep.survivorship
    card |= {"holdout_from": rep.settings.holdout_from, "panels": panels,
             "survivorship": None if s is None else {
                 "implied_haircut": s.implied_haircut, "configured_haircut": s.configured_haircut,
                 "first": _iso(s.window.first), "last": _iso(s.window.last),
                 "study_top_quintile_excess_1m": s.study_top_quintile_excess_1m,
                 "survivorship_free_same_months": s.survivorship_free_same_months,
                 "survivorship_free_since_1927": s.survivorship_free_since_1927, "note": s.note},
             "base_rates": [{"label": label, "first": _iso(b.first) if b else None, "last": _iso(b.last) if b else None,
                             "ann_return": b.ann_return if b else None, "t": b.t if b else None,
                             "last_10y_ann": b.last_10y_ann if b else None,
                             "share_neg_6m": b.roll6.share_negative if b else None,
                             "share_neg_12m": b.roll12.share_negative if b else None,
                             "max_dd": b.drawdown.max if b else None} for label, b in rep.base_rates.items()],
             "caveats": list(rep.caveats)}
    return card


def rule_heads(today: date) -> list[dict]:
    """The proposal, exit and redeploy studies' header rows (their numbers stay on the pages that act on them).
    Only the proposal study records its rule; the others are judged by age alone."""
    max_age = typed().evidence.max_age_days.rules
    out = []
    for name, label in RULE_STUDIES:
        now = rules.rule_hash() if name == "propose-study" else None
        out.append(head(art.load(name, rule_hash=now), label, art.ARTIFACTS[name].command, now, max_age, today))
    return out


# ---------------- the forward scoreboard ----------------

def _months(days: int | None) -> float | None:
    return None if days is None else days / DAYS_PER_MONTH


def _record(label: str, start, days: int | None, ret, acwi, excess, max_dd, min_months: float, note=None) -> dict:
    months = _months(days)
    return {"label": label, "start": start, "days": days, "ret": ret, "acwi": acwi, "excess": excess,
            "max_dd": max_dd, "too_short": months is None or months < min_months, "note": note}


def _cohort(records: list[dict], need: int, what: str) -> dict:
    """The mean excess and share ahead of ACWI over the records long enough to count, from `need` of them. No t:
    the windows overlap and the counts are small. A record without a result (no prices since) doesn't count."""
    judged = [r["excess"] for r in records if not r["too_short"] and r["excess"] is not None]
    enough = len(judged) >= need
    return {"count": len(judged), "need": need, "enough": enough,
            "mean_excess": mean(judged) if enough else None,
            "beat_acwi": mean([float(x > 0) for x in judged]) if enough else None,
            "note": None if enough else f"{len(judged)} {what} long enough to judge: the mean is shown from {need}"}


def forward_abtest(market: Market, today: date) -> dict:
    """The A/B test's baskets since their first purchase (TWR, ACWI with the same flows)."""
    s = abtest.summary(market)
    if not s.get("running"):
        return {"running": False, "records": [], "cohort": None,
                "note": "No A/B test runs: start one on the Experiments page"}
    ev = typed().evidence
    recs = []
    for b in s["baskets"]:
        start = b.get("start")
        days = (today - date.fromisoformat(start)).days if start else None
        recs.append(_record(b["label"], start, days, b.get("twr"), b.get("acwi"), b.get("excess"),
                            b.get("max_drawdown"), ev.forward_min_months))
    short = [r["label"] for r in recs if r["too_short"]]
    note = (f"{', '.join(short)}: shorter than {ev.forward_min_months} months, too short to compare"
            if short else None)
    return {"running": True, "records": recs, "cohort": None, "note": note}


def forward_paper_trail(market: Market) -> dict:
    """The monthly `picks-live` baskets (kept, never traded), each since its own day against ACWI."""
    ev = typed().evidence
    baskets = simulate.picks_baskets("picks-live")
    if not baskets:
        return {"running": False, "records": [], "cohort": None,
                "note": "No paper-trail baskets yet: the monthly brief makes one a month (tag picks-live)"}
    recs = []
    for p in sorted(baskets, key=lambda p: p["name"]):
        res = performance.portfolio_performance(p["id"], market) or {}
        st = res.get("stats") or {}
        notes = (res.get("notes") or []) + (res.get("missing") or [])
        recs.append(_record(p["name"].rsplit(" · ", 1)[0], st.get("start"), st.get("days"), st.get("twr_total"),
                            st.get("acwi_twr_total"), st.get("excess_twr"), st.get("max_drawdown"),
                            ev.cohort_age_months, "; ".join(notes) or None))
    return {"running": True, "records": recs, "cohort": _cohort(recs, ev.cohort_min, "basket(s)"), "note": None}


def forward_proposals(market: Market) -> dict:
    """The frozen proposals since their day against ACWI over the same days (propose review)."""
    rv = store.review(market)
    rows = rv.get("proposals") or []
    if not rows:
        return {"running": False, "records": [], "cohort": None, "note": "No frozen proposals yet"}
    ev = typed().evidence
    recs = [_record(f"{r.get('portfolio')} {r.get('date')}", r.get("date"), r.get("days"), r.get("ret"),
                    r.get("acwi"), r.get("excess"), r.get("max_dd"), ev.cohort_age_months, r.get("note"))
            for r in rows]
    return {"running": True, "records": recs, "cohort": _cohort(recs, rules.cfg().review_min, "proposal(s)"),
            "note": None}


def forward(market: Market, today: date) -> dict:
    return {"abtest": forward_abtest(market, today), "paper_trail": forward_paper_trail(market),
            "proposals": forward_proposals(market)}


def build(market: Market | None, today: date | None = None) -> dict:
    """The page: the study cards and rule heads always; the forward scoreboard when there are prices (`market`),
    else None with a note."""
    today = today or date.today()
    notes = []
    fwd = None
    if market is None:
        notes.append("No prices yet: the forward scoreboard needs `radar run` first")
    else:
        fwd = forward(market, today)
    return {"generated": pd.Timestamp.now().isoformat(timespec="seconds"),
            "holdout_from": typed().backtest.study_holdout_from.isoformat(),
            "longrun_holdout_from": _iso(typed().longrun.holdout_from),
            "scores": [score_card(s, today) for s in art.SCORE_SIGNALS],
            "longrun": longrun_card(today), "rules": rule_heads(today), "forward": fwd, "notes": notes}
