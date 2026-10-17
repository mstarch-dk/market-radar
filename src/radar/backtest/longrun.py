"""The momentum score's rule tested over decades, on monthly panels of US industries and developed-market countries
with no survivorship bias (factors.py): `radar study longrun` writes reports/longrun-study.json, with the factors'
base rates, the survivorship gauge and the proposals' long-run priors. What carries over is the rule, not a figure.

The method: guide/brugervejledning/scoretest.md (*Testen over årtier*) and guide/laerebog/statistik.md (*Lange
serier uden survivorship bias*); the data rules (windows on months, DKK, recessions): docs/data-conventions.md,
*Long histories*.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .. import factors, ingest
from ..config import settings
from ..model import artifacts
from ..model.prior import prior_weights, tercile_excess, tilt_prior, window  # noqa: F401 (re-exported)
from ..model.score import COMPONENTS, weighted_pct
from ..model.score import mean_pct as pct
from ..model.stats import mean as _mean
from ..signals.risk import MONTHS_PER_YEAR, underwater
from .study import QUANTILES, cross_section, holdout_diff_t, nw_t, summarize, variant_verdict

REPORT_FILE = "longrun-study.json"
BASELINE = "score"


def _cfg() -> dict:
    return settings().get("longrun") or {}


# ---------------- returns over windows ----------------

def forward(r: pd.DataFrame, months: int) -> pd.DataFrame:
    """Compounded return over the `months` months after each date."""
    return window(r, months).shift(-months)


def components(r: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {"r12_1": window(r, 11, 1), "r6m": window(r, 6), "r3m": window(r, 3), "r1m": window(r, 1),
            "r12": window(r, 12), "r6_1": window(r, 5, 1), "r3_1": window(r, 2, 1)}


wpct = weighted_pct


# ---------------- variants ----------------

@dataclass
class Variant:
    key: str
    label: str
    fn: Callable[[dict, pd.Timestamp], pd.Series]
    note: str = ""


def _comp(c: dict, day, keys=COMPONENTS) -> pd.DataFrame:
    return pd.DataFrame({k: c[k].loc[day] for k in keys})


VARIANTS = [
    Variant("score", "Momentum score (as in production)", lambda c, d: pct(_comp(c, d)),
            "mean percentile of 12-1, 6- and 3-month returns"),
    Variant("r12_1", "12-1-month return alone", lambda c, d: c["r12_1"].loc[d]),
    Variant("r6m", "6-month return alone", lambda c, d: c["r6m"].loc[d],
            "industry momentum as in Moskowitz & Grinblatt (1999)"),
    Variant("r3m", "3-month return alone", lambda c, d: c["r3m"].loc[d]),
    Variant("r1m", "1-month return alone", lambda c, d: c["r1m"].loc[d],
            "short-term reversal check: a negative IC means last month's winners tend to give back"),
    Variant("r12", "12-month return, latest month included", lambda c, d: c["r12"].loc[d]),
    Variant("score_skip", "Score with the latest month skipped in every component",
            lambda c, d: pct(_comp(c, d, ("r12_1", "r6_1", "r3_1")))),
    Variant("no_3m", "Score without the 3-month part", lambda c, d: pct(_comp(c, d, ("r12_1", "r6m")))),
    Variant("w_long", "Weights 2:1:1 (12-1 : 6 : 3 months)",
            lambda c, d: wpct(_comp(c, d), {"r12_1": 2, "r6m": 1, "r3m": 1})),
    Variant("w_short", "Weights 1:1:2 (12-1 : 6 : 3 months)",
            lambda c, d: wpct(_comp(c, d), {"r12_1": 1, "r6m": 1, "r3m": 2})),
]
BY_KEY = {v.key: v for v in VARIANTS}


# ---------------- panels ----------------

@dataclass
class Panel:
    key: str
    label: str
    returns: pd.DataFrame          # month-end x member, total USD returns (decimals)
    market: pd.Series              # the panel's market, total USD returns
    n_top: int
    min_names: int


def _market(name: str, data: pd.DataFrame) -> pd.Series:
    if name == "us":
        ff = factors.panel("french:ff3_us", data)
        return (ff["Mkt-RF"] + ff["RF"]) if {"Mkt-RF", "RF"} <= set(ff.columns) else pd.Series(dtype=float)
    if name == "world":
        w = factors.panel("jkp:mkt_world", data)
        return factors.total(w, data)["world"] if "world" in w else pd.Series(dtype=float)
    raise ValueError(f"unknown market {name} (us, world)")


def load_panel(key: str, data: pd.DataFrame | None = None) -> Panel:
    specs = _cfg().get("panels") or {}
    if key not in specs:
        raise ValueError(f"unknown panel {key} (known: {', '.join(specs)})")
    spec = specs[key]
    data = factors.load() if data is None else data
    r = factors.panel(spec["data"], data)
    if r.empty:
        raise ValueError(f"no {spec['data']} data stored: run `radar update` (or `radar study longrun --fetch`) first")
    if spec.get("members"):
        r = r.reindex(columns=[m for m in spec["members"] if m in r.columns])
    if spec.get("excess"):
        r = factors.total(r, data)
    return Panel(key, spec.get("label", key), r, _market(spec.get("market", "us"), data).reindex(r.index),
                 int(spec.get("n_top", 10)), int(spec.get("min_names", 20)))


def _fx(index: pd.DatetimeIndex) -> pd.Series:
    """DKK per USD at each month-end (the last FRED DEXDNUS value in the month); NaN without the series."""
    fred = ingest.load_fred()
    if "DEXDNUS" not in fred:
        return pd.Series(np.nan, index=index)
    s = fred["DEXDNUS"].dropna()
    return s.groupby(s.index.to_period("M")).last().reindex(index.to_period("M")).set_axis(index)


def _recessions(index: pd.DatetimeIndex) -> pd.Series:
    fred = ingest.load_fred()
    if "USREC" not in fred:
        return pd.Series(np.nan, index=index)
    s = fred["USREC"].dropna()
    return s.groupby(s.index.to_period("M")).last().reindex(index.to_period("M")).set_axis(index)


# ---------------- the study ----------------

def _eff(summary: dict | None, h: int) -> dict | None:
    if summary is None:
        return None
    return summary | {"eff_n": round(summary["dates"] / h, 1)}


def run(panel: Panel, horizons=None, variants: list[str] | None = None, since=None, log=lambda *_: None) -> dict:
    """The score and its variants on every month-end with `min_names` ranked members, from returns up to that month
    only, judged on the compounded return over the next H months. The statistics are study.cross_section and
    study.summarize unchanged (top N excess over the panel's equal weight), plus the effective number of independent
    periods (dates / H), the top N against the panel's market and in DKK, and the splits (holdout, decade, the
    market's trend, US recessions)."""
    cfg = _cfg()
    horizons = [int(h) for h in (horizons or cfg.get("horizons", [1, 3, 6, 12]))]
    holdout = pd.Timestamp(cfg["holdout_from"]) if cfg.get("holdout_from") else None
    keys = variants or [v.key for v in VARIANTS]
    unknown = [k for k in keys if k not in BY_KEY]
    if unknown:
        raise ValueError(f"unknown variant(s): {', '.join(unknown)} (known: {', '.join(BY_KEY)})")
    if BASELINE not in keys:
        keys = [BASELINE, *keys]
    r = panel.returns
    comp = components(r)
    fwd = {h: forward(r, h) for h in horizons}
    mkt_fwd = {h: forward(panel.market.to_frame("m"), h)["m"] for h in horizons}
    fx = _fx(r.index)
    fx_ratio = {h: fx.shift(-h) / fx for h in horizons}
    level = (1 + panel.market.fillna(0)).cumprod().where(panel.market.notna())
    trend = level >= level.rolling(int(cfg.get("regime_months", 10)), min_periods=int(cfg.get("regime_months", 10))).mean()
    trend = trend.where(level.rolling(int(cfg.get("regime_months", 10))).count() >= int(cfg.get("regime_months", 10)))
    rec = _recessions(r.index)

    per = {h: {k: [] for k in keys} for h in horizons}
    dates_used = []
    for day in r.index:
        if since is not None and day < pd.Timestamp(since):
            continue
        if comp["r12_1"].loc[day].notna().sum() < panel.min_names:
            continue
        dates_used.append(day)
        regime = None if pd.isna(trend.loc[day]) else ("up" if trend.loc[day] else "down")
        recession = None if pd.isna(rec.loc[day]) else bool(rec.loc[day])
        x = {k: BY_KEY[k].fn(comp, day) for k in keys}      # once per date, for every horizon
        for h in horizons:
            y = fwd[h].loc[day]
            if y.notna().sum() < panel.min_names:
                continue
            y_dkk = (1 + y) * fx_ratio[h].loc[day] - 1 if pd.notna(fx_ratio[h].loc[day]) else None
            m = mkt_fwd[h].loc[day]
            for k in keys:
                row = cross_section(x[k], y, panel.n_top, panel.min_names, y_dkk)
                if row is None:
                    continue
                top = y.reindex(row.pop("top")).dropna()
                row |= {"date": day, "regime": regime, "recession": recession,
                        "top_vs_market": float(top.mean() - m) if len(top) and pd.notna(m) else None,
                        "acwi_dkk": float((1 + m) * fx_ratio[h].loc[day] - 1)
                        if pd.notna(m) and pd.notna(fx_ratio[h].loc[day]) else None}
                per[h][k].append(row)
    if not dates_used:
        raise ValueError(f"no month with {panel.min_names} ranked members in {panel.key}")
    log(f"{panel.key}: {len(dates_used)} formation months, {dates_used[0]:%Y-%m} to {dates_used[-1]:%Y-%m}")

    results, verdicts = {}, {}
    for h in horizons:
        lag = max(h - 1, 0)
        results[str(h)] = {}
        for k in keys:
            rows = per[h][k]

            def part(sel, rows=rows, lag=lag, h=h):
                s = summarize([x for x in rows if sel(x)], lag)
                if s is not None:   # here the benchmark is the panel's market, not ACWI
                    s["market_dkk"], s["top_beats_market"] = s.pop("acwi_dkk"), s.pop("top_beats_acwi")
                    tv = [x["top_vs_market"] for x in rows if sel(x)]
                    s |= {"top_vs_market": _mean(tv), "top_vs_market_t": nw_t(tv, lag)}
                return _eff(s, h)

            decades = sorted({x["date"].year // 10 * 10 for x in rows})
            results[str(h)][k] = {
                "all": part(lambda x: True),
                "in_sample": part(lambda x: holdout is None or x["date"] < holdout),
                "holdout": part(lambda x: holdout is not None and x["date"] >= holdout),
                "by_decade": {f"{d}s": part(lambda x, d=d: x["date"].year // 10 * 10 == d) for d in decades},
                "by_trend": {g: part(lambda x, g=g: x["regime"] == g) for g in ("up", "down")},
                "by_recession": {lbl: part(lambda x, v=v: x["recession"] is v)
                                 for lbl, v in (("recession", True), ("expansion", False))},
            }
        base = results[str(h)][BASELINE]
        verdicts[str(h)] = {
            k: variant_verdict(results[str(h)][k], base, holdout_diff_t(per[h][k], per[h][BASELINE], holdout, lag))
            for k in keys if k != BASELINE}
    return {
        "panel": panel.key, "label": panel.label,
        "members": int(r.notna().any().sum()), "n_top": panel.n_top, "min_names": panel.min_names,
        "first": dates_used[0], "last": dates_used[-1], "months": len(dates_used),
        "variants": [{"key": k, "label": BY_KEY[k].label, "note": BY_KEY[k].note, "baseline": k == BASELINE}
                     for k in keys],
        "variants_tried": len(keys) - 1,
        "results": results, "verdicts": verdicts,
        "dkk": bool(fx.notna().any()),
    }


# ---------------- base rates of the long-short factors ----------------

def drawdown(r: pd.Series) -> dict:
    """The worst peak-to-trough fall of the compounded series, when it started and bottomed, and how many months
    from the peak until it was made good (None while it hasn't been)."""
    lvl = (1 + r).cumprod()
    dd = underwater(lvl)
    trough = dd.idxmin()
    start = lvl.loc[:trough].idxmax()
    after = lvl.loc[trough:]
    back = after[after >= lvl.loc[start]]
    rec = None if back.empty else int(len(lvl.loc[start:back.index[0]]) - 1)
    return {"max": float(dd.min()), "peak": start, "trough": trough, "months_to_recover": rec}


def base_rates(r: pd.Series) -> dict | None:
    r = r.dropna()
    if len(r) < 36:
        return None
    n = len(r)
    sd = float(r.std())
    out = {"first": r.index[0], "last": r.index[-1], "months": n,
           "ann_return": float(r.mean() * MONTHS_PER_YEAR), "ann_vol": sd * math.sqrt(MONTHS_PER_YEAR),
           "t": float(r.mean() / (sd / math.sqrt(n))) if sd > 0 else None,
           "sharpe": float(r.mean() / sd * math.sqrt(MONTHS_PER_YEAR)) if sd > 0 else None,
           "drawdown": drawdown(r)}
    for m in (6, 12):
        w = window(r.to_frame("f"), m)["f"].dropna()
        out[f"roll{m}"] = {"windows": int(len(w)), "share_negative": float((w < 0).mean()),
                           "p5": float(w.quantile(0.05)), "worst": float(w.min()), "median": float(w.median())}
    last10 = r.iloc[-120:]
    rest = r.iloc[:-120]
    out["last_10y_ann"] = float(last10.mean() * 12)
    out["before_ann"] = float(rest.mean() * 12) if len(rest) >= 36 else None
    out["by_decade"] = {f"{d}s": float(g.mean() * 12) for d, g in r.groupby(r.index.year // 10 * 10) if len(g) >= 24}
    return out


def factor_base_rates(data: pd.DataFrame | None = None) -> dict:
    data = factors.load() if data is None else data
    out = {}
    for label, (key, series) in (_cfg().get("factors") or {}).items():
        p = factors.panel(key, data)
        out[label] = base_rates(p[series]) if series in p else None
    return out



# ---------------- the long-run prior for a tilt (model/prior.py, read by propose.py) ----------------

def priors(data: pd.DataFrame | None = None) -> dict:
    """Every tilt's prior at the proposal horizons in each configured region (for the report and the skills)."""
    from ..propose import cfg as pcfg

    c = pcfg()
    pc = c.get("prior") or {}
    data = factors.load() if data is None else data
    out = {}
    for tilt, tw in (c.get("tilts") or {}).items():
        w = prior_weights(tw, pc.get("components") or {}, pc.get("qv") or {})
        out[tilt] = {str(h): {r: tilt_prior(w, int(h), r, data, pc.get("since"), int(pc.get("trend_months", 10)))
                              for r in [pc.get("region", "developed"), *(pc.get("report_regions") or [])]}
                     for h in c.get("horizons", [3, 6])}
    return out


# ---------------- survivorship gauge ----------------

def survivorship_gauge(data: pd.DataFrame | None = None,
                       score_study: artifacts.ScoreStudy | None = None) -> dict | None:
    """`radar study score`'s 1-month top-quintile excess over its equal-weighted universe, against the same
    figure for all US stocks without survivorship bias (French's equal-weighted 12-2 momentum deciles: the top two
    minus the mean of all ten) in the months the study covers. None without a readable score study."""
    if score_study is None:
        score_study = artifacts.load("score-study").report
        if score_study is None:
            return None
    v = (score_study.results.get("1") or {}).get("score")
    res = v.all if v is not None else None
    if res is None or not res.q:
        return None
    ours = res.q[QUANTILES - 1]
    p = factors.panel("french:mom10_us", data)
    if p.shape[1] != 10:
        return None
    top = p.iloc[:, -2:].mean(axis=1) - p.mean(axis=1)
    first, last = pd.Timestamp(score_study.universe.first), pd.Timestamp(score_study.universe.last)
    # a formation at month-end t earns month t+1
    months = top[(top.index > first) & (top.index <= last + pd.offsets.MonthEnd(1))]
    same = float(months.mean()) if len(months) else None
    return {"window": {"first": first, "last": last, "french_months": int(len(months)),
                       "study_dates": res.dates},
            "study_top_quintile_excess_1m": ours, "survivorship_free_same_months": same,
            "survivorship_free_since_1927": float(top.mean()),
            "implied_haircut": (1 - same / ours) if same is not None and ours and ours > 0 else None,
            "configured_haircut": (settings().get("propose") or {}).get("survivorship_haircut"),
            "note": "a rough gauge: S&P 500 and curated lists against all US stocks, the score against 12-2 momentum, "
                    "equal-weighted deciles on NYSE breakpoints; one window of a few years"}


# ---------------- the report ----------------

CAVEATS = [
    "These are industries and countries, not stocks: the rule (lookbacks, weights) and the base rates carry over, "
    "a stock basket's figures don't. Single stocks are more volatile and their momentum is stronger and crashes harder.",
    "The portfolios are value-weighted and rebalanced by the researchers; no costs or taxes are charged.",
    "JKP returns are in USD over the US T-bill; French's RF is added back. DKK figures use FRED's DEXDNUS from 1971.",
    "Recession months are NBER's, dated after the fact: a label for the split, not something known on the date.",
    "Several variants are tried: a few will look better by chance. Only an improvement that holds in the holdout "
    "too counts.",
    "Momentum's history includes long flat spells and sharp crashes (1932, 2009): a decade average hides them; see "
    "the base rates' drawdowns and losing windows.",
]


def build(panels: list[str] | None = None, horizons=None, variants=None, since=None, log=lambda *_: None) -> dict:
    data = factors.load()
    if data.empty:
        raise ValueError("no long histories stored: run `radar update` (or `radar study longrun --fetch`) first")
    keys = panels or list(_cfg().get("panels") or {})
    out = {"generated": pd.Timestamp.now().isoformat(timespec="seconds"),
           "datasets_asof": factors.asof(data),
           "settings": {"holdout_from": _cfg().get("holdout_from"),
                        "horizons": [int(h) for h in (horizons or _cfg().get("horizons", [1, 3, 6, 12]))],
                        "regime_months": _cfg().get("regime_months", 10), "since": since},
           "panels": {}, "errors": {}}
    for k in keys:
        try:
            out["panels"][k] = run(load_panel(k, data), horizons, variants, since, log)
        except ValueError as e:
            out["errors"][k] = str(e)
            log(f"{k}: {e}")
    out["base_rates"] = factor_base_rates(data)
    out["survivorship"] = survivorship_gauge(data)
    out["priors"] = priors(data)
    out["caveats"] = CAVEATS
    return out


def write(rep: dict) -> None:
    months = (rep.get("datasets_asof") or {}).values()
    artifacts.write("longrun-study", rep, data_asof=artifacts.month_end(max(months)) if months else None,
                    file=REPORT_FILE)
