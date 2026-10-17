"""The expected excess: the rule study's mean for the tilt, cut by the survivorship haircut and shrunk toward
the long-run prior."""
from __future__ import annotations

import json
import math
from typing import Any

from ..model import artifacts
from ..model import prior as mprior
from . import rules


def load_study() -> artifacts.Loaded:
    """The rule study (model/artifacts.py), stale when it tested other settings than today's rule."""
    return artifacts.load("propose-study", rule_hash=rules.rule_hash())


def haircut(c: dict | None = None, longrun: artifacts.Loaded | None = None) -> dict:
    """The survivorship haircut used: `survivorship_haircut`, or the long-run study's gauge when it implies more
    (`haircut_from_gauge`; never less than configured). Without a readable long-run study the configured one, with
    the reason."""
    c = c or rules.cfg()
    conf = float(c["survivorship_haircut"])
    lr = longrun.report if longrun is not None else None
    g = ((lr.survivorship.implied_haircut if lr is not None and lr.survivorship else None)
         if c.get("haircut_from_gauge") else None)
    if g is not None and 0 < g < 1 and g > conf:
        return {"used": float(g), "configured": conf, "gauge": float(g),
                "basis": "the long-run study's survivorship gauge (larger than configured)"}
    out = {"used": conf, "configured": conf, "gauge": g, "basis": "configured"}
    if c.get("haircut_from_gauge") and longrun is not None and longrun.report is None:
        out["gauge_note"] = longrun.reason
    return out


_PRIORS: dict = {}


def long_prior(tilt: str, horizon: int, trend: str | None, c: dict | None = None) -> dict | None:
    """The tilt's long-run prior at this horizon (model/prior.tilt_prior in `prior.region`): in today's trend
    when that split has `prior.min_trend_eff_n` independent periods, else over all dates. Cached per factors file."""
    from .. import factors

    c = c or rules.cfg()
    pc = c.get("prior") or {}
    tw = (c.get("tilts") or {}).get(tilt)
    if not pc or not tw:
        return None
    f = factors.FACTORS_FILE
    stamp = f.stat().st_mtime if f.exists() else None
    key = (tilt, horizon, trend, stamp, json.dumps(pc, sort_keys=True, default=str), json.dumps(tw, sort_keys=True))
    if key not in _PRIORS:
        data = factors.load()
        w = mprior.prior_weights(tw, pc.get("components") or {}, pc.get("qv") or {})
        regions = [pc.get("region", "developed"), *(pc.get("report_regions") or [])]
        res = {r: mprior.tilt_prior(w, horizon, r, data, pc.get("since"), int(pc.get("trend_months", 10)))
               for r in regions}
        main = res[regions[0]]
        if main is None:
            _PRIORS[key] = None
        else:
            st = (main.get("by_trend") or {}).get(trend) if trend else None
            use: dict = st if st is not None and (st.get("eff_n") or 0) >= float(pc.get("min_trend_eff_n", 20)) else main
            _PRIORS[key] = {
                "mean": use["mean"], "se": use["se"], "t": use["t"], "eff_n": use["eff_n"],
                "basis": f"{regions[0]}, {trend}trend ({use['eff_n']:g} periods)" if use is st
                         else f"{regions[0]}, all dates since {pc.get('since')} ({use['eff_n']:g} periods)",
                "region": regions[0], "trend": trend if use is st else None, "weights": w,
                "components": main.get("components"),
                "regions": {r: None if v is None else {"mean": v["mean"], "t": v["t"], "eff_n": v["eff_n"]}
                            for r, v in res.items()}}
    return _PRIORS[key]


def shrink(short: float | None, se_short: float | None, prior: dict | None, horizon: int, c: dict) -> dict:
    """Precision-weighted mean of the rule study's excess and the long-run prior (a normal-normal Bayesian update):
    w = (1/se_s²) / (1/se_s² + 1/(se_p² + tau²)), tau = `prior.tau_annual` × √(H/12). Without a standard error for
    the study (too few dates, t of 0) the prior alone; without a prior, the study alone."""
    if short is None:
        return {"drift": None, "w_short": None}
    if prior is None or prior.get("mean") is None:
        return {"drift": short, "w_short": 1.0, "note": "no long-run prior (run `radar update` for the JKP portfolios)"}
    tau = float((c.get("prior") or {}).get("tau_annual", 0)) * math.sqrt(horizon / 12)
    var_p = (prior.get("se") or 0) ** 2 + tau ** 2
    if not se_short:
        return {"drift": prior["mean"], "w_short": 0.0, "tau": tau, "note": "the study's excess has no standard error"}
    if var_p <= 0:
        return {"drift": prior["mean"], "w_short": 0.0, "tau": tau}
    w = (1 / se_short ** 2) / (1 / se_short ** 2 + 1 / var_p)
    return {"drift": w * short + (1 - w) * prior["mean"], "w_short": w, "tau": tau}


def study_view(study: artifacts.Loaded | None, tilt: str, n: int, horizon: int, regime: str | None,
               c: dict | None = None, trend: str | None = None) -> dict:
    """The rule study's figures for this tilt, the nearest basket size and the horizon, with the drift the model
    uses. The study's mean (the regime's own when it has enough dates, else all dates) is cut by the survivorship
    haircut when positive (`haircut`), then shrunk toward the tilt's long-run prior (`long_prior`, `shrink`): the
    study has few independent periods and today's universe, the prior decades of every listed stock. Gross of
    costs (the proposal's own costs are taken off in `evaluate`)."""
    c = c or rules.cfg()
    out: dict[str, Any] = {"available": False, "stale": None, "drift_gross": None, "drift_gross_raw": None,
                           "drift_short": None, "basis": None, "n_used": None, "us_only": None, "prior": None,
                           "w_short": None, "haircut": None}
    rep = study.report if study is not None else None
    if study is None or rep is None:
        out["note"] = (study.reason if study is not None else None) or "no rule study yet: run `radar study propose`"
        return out
    out["stale"] = study.status == "stale"
    res = rep.results.get(tilt) or {}
    if not res:
        out["note"] = f"the rule study has no {tilt} results"
        return out
    ns = sorted(int(k) for k in res)
    nu = min(ns, key=lambda k: (abs(k - n), k))
    cell = res[str(nu)].get(str(horizon))
    kept = cell.kept if cell is not None and cell.kept is not None else artifacts.Split()
    exits = cell.exits if cell is not None else None
    out |= {"available": kept.all is not None, "n_used": nu, "horizon": horizon,
            "kept": kept.model_dump(exclude_unset=True),
            "exits": exits.model_dump(exclude_unset=True) if exits is not None else None,
            "us_only": rep.us_only.get(tilt), "asof": rep.asof, "first": rep.universe.first}
    if out["stale"]:
        out["note"] = "the rule study was run with other settings: its numbers don't describe today's rule"
        return out
    allr = kept.all or artifacts.Summary()
    reg = kept.by_regime.get(str(regime)) if regime else None
    if reg is not None and (reg.dates or 0) >= c["min_regime_dates"]:
        use, out["basis"] = reg, f"regime {regime} ({reg.dates} dates)"
    else:
        use, out["basis"] = allr, f"all dates ({allr.dates})"
    g = use.gross_mean
    hc = haircut(c, artifacts.load("longrun-study"))
    out["drift_gross_raw"] = g
    out["haircut"] = hc
    short = None if g is None else (g * (1 - hc["used"]) if g > 0 else g)
    out["drift_short"] = short
    t, mean = use.t, use.mean
    se_short = abs(mean / t) if t and mean is not None else None
    prior = long_prior(tilt, horizon, trend, c)
    sh = shrink(short, se_short, prior, horizon, c)
    out |= {"drift_gross": sh["drift"], "w_short": sh["w_short"], "se_short": se_short, "prior": prior,
            "tau": sh.get("tau")}
    if sh.get("note"):
        out["prior_note"] = sh["note"]
    return out
