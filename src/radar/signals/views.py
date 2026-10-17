"""Your market views against the data: what the radar's readings say about each view (evidence), and how a stock
or fund lines up with your views (alignment).

Views are the user's subjective beliefs. Nothing here judges them: evidence reports what the radar's own readings
did over the last three months, and alignment says which views a name would profit from or suffer under if they
turned out right. Missing data stays "no data"; a name with no link to a view is "unrelated", not neutral."""
from __future__ import annotations

import numpy as np
import pandas as pd

MAX_AGE = {"rel": 10, "ratio": 10, "pct": 10, "fred": 75, "fred_pct": 75, "cli": 120}   # days before "no data"
BARS_3M = 63


# ---------------- evidence ----------------

def _ret(s: pd.Series, n: int = BARS_3M) -> tuple[float, pd.Timestamp | None]:
    s = s.dropna()
    if len(s) <= n:
        return np.nan, None
    return float(s.iloc[-1] / s.iloc[-1 - n] - 1), s.index[-1]


def _change(s: pd.Series, pct: bool) -> tuple[float, pd.Timestamp | None]:
    """Change over about three months of a dated series (FRED, CLI): last value vs the value ~91 days before."""
    s = s.dropna()
    if len(s) < 2:
        return np.nan, None
    last = s.index[-1]
    before = s[:last - pd.Timedelta(days=88)]
    if before.empty:
        return np.nan, None
    v0, v1 = float(before.iloc[-1]), float(s.iloc[-1])
    return ((v1 / v0 - 1) if pct else (v1 - v0)), last


def reading(spec: dict, closes: pd.DataFrame, fred: pd.DataFrame, cli: pd.DataFrame, bench: str) -> tuple[float, pd.Timestamp | None]:
    """One catalogue indicator's 3-month change (NaN and None when the data isn't there)."""
    kind = spec["kind"]
    if kind == "rel":
        if spec["ticker"] not in closes or bench not in closes:
            return np.nan, None
        r, d = _ret(closes[spec["ticker"]])
        b, _ = _ret(closes[bench][:d] if d is not None else closes[bench])
        return r - b, d
    if kind == "pct":
        return _ret(closes[spec["ticker"]]) if spec["ticker"] in closes else (np.nan, None)
    if kind == "ratio":
        if spec["a"] not in closes or spec["b"] not in closes:
            return np.nan, None
        return _ret(closes[spec["a"]] / closes[spec["b"]])
    if kind in ("fred", "fred_pct"):
        return _change(fred[spec["series"]], kind == "fred_pct") if spec["series"] in fred else (np.nan, None)
    if kind == "cli":
        return _change(cli[spec["area"]], False) if spec["area"] in cli else (np.nan, None)
    raise ValueError(f"unknown indicator kind {kind!r}")


def readings(catalogue: dict, closes: pd.DataFrame, fred: pd.DataFrame, cli: pd.DataFrame, bench: str,
             today: pd.Timestamp | None = None) -> dict[str, dict]:
    """Every catalogue indicator: value (3-month change), as-of date, and whether it is current."""
    today = pd.Timestamp(today or pd.Timestamp.today()).normalize()
    out = {}
    for key, spec in catalogue.items():
        v, d = reading(spec, closes, fred, cli, bench)
        current = d is not None and not np.isnan(v) and (today - pd.Timestamp(d)).days <= MAX_AGE[spec["kind"]]
        out[key] = {"key": key, "label": spec["label"], "kind": spec["kind"], "band": spec.get("band", 0),
                    "value": None if np.isnan(v) else v, "asof": None if d is None else pd.Timestamp(d).date().isoformat(),
                    "current": bool(current)}
    return out


def evidence(view: dict, reads: dict[str, dict]) -> dict:
    """Each of the view's indicators as supports / contradicts / flat / no data, and the counts."""
    items = []
    for ind in view.get("indicators") or []:
        r = reads.get(ind["indicator"])
        if r is None or not r["current"] or r["value"] is None:
            state = "no data"
        elif abs(r["value"]) <= r["band"]:
            state = "flat"
        else:
            state = "supports" if (r["value"] > 0) == (ind["expect"] == "up") else "contradicts"
        items.append({"indicator": ind["indicator"], "label": r["label"] if r else ind["indicator"],
                      "kind": r["kind"] if r else None, "expect": ind["expect"],
                      "value": r["value"] if r else None, "asof": r["asof"] if r else None, "state": state})
    counts = {s: sum(i["state"] == s for i in items) for s in ("supports", "contradicts", "flat", "no data")}
    sup, con = counts["supports"], counts["contradicts"]
    verdict = ("no data" if not items or counts["no data"] == len(items) else
               "supported" if sup and not con else "contradicted" if con and not sup else
               "mixed" if sup and con else "unclear")
    return {"items": items, "counts": counts, "verdict": verdict}


# ---------------- alignment ----------------

def relative_weekly(closes: pd.DataFrame, bench: str, weeks: int = 52) -> pd.DataFrame:
    """Weekly returns relative to the benchmark (ratio to ACWI), the last `weeks` weeks."""
    w = closes.resample("W-FRI").last()
    rel = w.div(w[bench], axis=0)
    return rel.pct_change(fill_method=None).iloc[-weeks:]


def correlations(rel: pd.DataFrame, tickers: list[str], etfs: list[str], min_weeks: int) -> pd.DataFrame:
    """tickers x etfs correlation of relative weekly returns (NaN with fewer than `min_weeks` shared weeks)."""
    etfs = [e for e in etfs if e in rel]
    tickers = [t for t in tickers if t in rel]
    out = pd.DataFrame(np.nan, index=tickers, columns=etfs)
    for e in etfs:
        out[e] = rel[tickers].corrwith(rel[e], min_periods=min_weeks) if tickers else []
    return out


def match(exp: dict, ctx: dict, theme_corr: float) -> tuple[float, str] | None:
    """How strongly one exposure applies to a name (0..1) and why; None when it doesn't apply."""
    kind, key = exp["kind"], exp["key"]
    t = ctx["ticker"]
    if kind == "ticker":
        return (1.0, f"is {key}") if t.upper() == key.upper() else None
    if kind == "etf":
        if t.upper() == key.upper() or ctx.get("ucits_of") == key:
            return 1.0, f"is {key}" if t.upper() == key.upper() else f"UCITS version of {key}"
        c = (ctx.get("corr") or {}).get(key)
        if c is not None and not np.isnan(c) and c >= theme_corr:
            return float(c), f"moves with {key} vs ACWI (ρ {c:.2f})"
        return None
    if kind == "sector":
        return (1.0, f"sector {ctx.get('sector')}") if (ctx.get("sector") or "").lower() == key.lower() else None
    if kind == "industry":
        ind = ctx.get("industry") or ""
        return (1.0, f"industry {ind}") if ind and key.lower() in ind.lower() else None
    if kind == "region":
        k = key.lower()
        if k == (ctx.get("region") or "").lower() or k == (ctx.get("country") or "").lower():
            return 1.0, f"region {key}"
        return None
    raise ValueError(f"unknown exposure kind {kind!r}")


def label(score: float, has_pos: bool, has_neg: bool, t: float) -> str:
    if has_pos and has_neg and abs(score) < t:
        return "mixed"
    if score >= t:
        return "aligned"
    if score <= -t:
        return "conflicts"
    return "mixed" if (has_pos and has_neg) else "unrelated"


def align(ctx: dict, views: list[dict], cfg: dict) -> dict:
    """A name against every view: per view aligned / conflicts / mixed / unrelated with reasons, and an overall
    label weighted by conviction (only over views the name is linked to)."""
    t = cfg["thresholds"]["aligned"]
    rows, num, den = [], 0.0, 0.0
    for v in views:
        helps, hurts, reasons = 0.0, 0.0, []
        for e in v.get("exposures") or []:
            m = match(e, ctx, cfg["theme_corr"])
            if m is None:
                continue
            strength, why = m
            if e["effect"] > 0:
                helps = max(helps, strength)
            else:
                hurts = max(hurts, strength)
            reasons.append({"effect": e["effect"], "text": f"{'helped' if e['effect'] > 0 else 'hurt'}: {why}"})
        score = helps - hurts
        lab = label(score, helps > 0, hurts > 0, t)
        rows.append({"id": v.get("id"), "statement": v["statement"], "conviction": v.get("conviction", 3),
                     "label": lab, "score": round(score, 3), "reasons": reasons})
        if lab != "unrelated":
            num += v.get("conviction", 3) * score
            den += v.get("conviction", 3)
    overall = 0.0 if not den else num / den
    related = [r for r in rows if r["label"] != "unrelated"]
    lab = ("unrelated" if not related else
           label(overall, any(r["score"] > 0 for r in related), any(r["score"] < 0 for r in related), t))
    return {"label": lab, "score": round(overall, 3), "views": rows}


def contexts(tickers: list[str], meta: pd.DataFrame, closes: pd.DataFrame, bench: str, etfs: list[str],
             ucits: dict[str, str], cfg: dict) -> dict[str, dict]:
    """Alignment inputs for many names: sector/industry/region/country from `meta` (indexed by ticker) and the
    correlation with each view ETF."""
    rel = relative_weekly(closes, bench)
    corr = correlations(rel, tickers, etfs, cfg["min_weeks"])
    out = {}
    for t in tickers:
        m = meta.loc[t] if t in meta.index else pd.Series(dtype=object)
        text = lambda k, m=m: m.get(k) if isinstance(m.get(k), str) and m.get(k) else None   # NaN / "" = unknown
        out[t] = {"ticker": t, "sector": text("sector"), "industry": text("industry"),
                  "region": text("region"), "country": text("country"), "ucits_of": ucits.get(t),
                  "corr": corr.loc[t].to_dict() if t in corr.index else {}}
    return out


def view_etfs(views: list[dict]) -> list[str]:
    return sorted({e["key"] for v in views for e in v.get("exposures") or [] if e["kind"] == "etf"})
