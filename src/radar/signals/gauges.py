"""Graded readings: where a value sits between its thresholds, not just which side of one it is on.

A gauge maps a value to a score in [-1, 1] by linear interpolation over (value, score) anchors: +1 is good,
bullish, cheap or profitable (green), -1 is a warning (red). One-way risk measures (VIX, volatility) are
"sequential" and only go from 0 to -1. The score is cut into 9 levels (-4..4) so colours are discrete and easy
to scan, and every gauge carries a word from its label bands, so colour is never the only cue. Specs live in
settings.yaml `gauges:`; regime rows build theirs from the `regime:` thresholds (see regime.py).
"""
from __future__ import annotations

import math

from ..config import settings

LEVELS = 4  # levels run -LEVELS..LEVELS


def _num(v) -> float | None:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def interpolate(anchors: list, x: float) -> float:
    """Piecewise-linear over sorted (value, score) anchors, clamped at both ends."""
    pts = sorted((float(a), float(b)) for a, b in anchors)
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


def label_for(labels: list, x: float) -> str:
    """The first band whose upper bound is above `x`; the last band (bound null) catches the rest."""
    for upper, word in labels:
        if upper is None or x < float(upper):
            return str(word)
    return str(labels[-1][1])


def make(spec: dict, value) -> dict | None:
    """The gauge for `value` under `spec`; None when the value is missing (never graded as 0)."""
    x = _num(value)
    if x is None:
        return None
    graded = x
    if spec.get("abs_from") is not None:                 # two-sided extremes graded as one-way distance
        c = float(spec["abs_from"])
        graded = c + abs(x - c)
    score = interpolate(spec["anchors"], graded)
    if spec.get("scale") == "sequential":
        score = min(score, 0.0)
    score = max(-1.0, min(1.0, score))
    level = int(math.copysign(math.floor(abs(score) * LEVELS + 0.5), score)) if score else 0
    lo, hi = spec.get("range") or (min(a for a, _ in spec["anchors"]), max(a for a, _ in spec["anchors"]))
    return {"value": x, "score": round(score, 3), "level": level, "label": label_for(spec["labels"], x),
            "scale": spec.get("scale", "diverging"), "unit": spec.get("unit", "num"),
            "ticks": [float(t) for t in spec.get("ticks") or []],
            "lo": float(lo), "hi": float(hi)}


def gauge(key: str, value) -> dict | None:
    """The configured gauge `key` (settings.yaml `gauges:`) for `value`."""
    return make(settings()["gauges"][key], value)


def gauges(values: dict[str, object]) -> dict[str, dict]:
    """{key: gauge} for the values that have data; missing values are left out."""
    out = {k: gauge(k, v) for k, v in values.items()}
    return {k: g for k, g in out.items() if g is not None}


NAMES = {"rsi14": "RSI 14", "bb_pct_b": "Bollinger %B", "macd_atr": "MACD", "atr_pct": "Daily range (ATR)",
         "vol_surge": "Volume", "from_high": "52w high", "beta": "Beta", "score": "Momentum score",
         "stop_dist": "Stop", "tp_dist": "Target", "upside": "Analyst targets", "target_change": "Analyst targets",
         "cot_pct": "Positioning", "cli_chg": "Leading indicator", "rs_ratio": "RS-Ratio", "rs_mom": "RS-Momentum",
         "excess_vs_acwi": "vs ACWI"}
WARN_LEVEL = -3
TRAITS = {"atr_pct", "beta"}           # how a stock is, not a change worth acting on: coloured, but not a watch-out


def watchouts(gs: dict[str, dict], skip: set[str] = frozenset()) -> list[dict]:
    """The gauges deep in the red (level <= WARN_LEVEL), worst first: what to look at before anything else.
    Traits and the keys in `skip` (e.g. a hypothetical stop on a ticker that isn't held) are left out."""
    out = [{"key": k, "label": v["label"], "level": v["level"], "text": f"{NAMES.get(k, k)}: {v['label']}"}
           for k, v in gs.items() if v["level"] <= WARN_LEVEL and k not in TRAITS and k not in skip]
    return sorted(out, key=lambda w: w["level"])


# ---------------- specs built from other thresholds (regime rows) ----------------

def sequential(points: list, labels: list, ticks: list, rng: tuple[float, float]) -> dict:
    return {"scale": "sequential", "anchors": points, "labels": labels, "ticks": ticks, "range": list(rng)}


def diverging(points: list, labels: list, ticks: list, rng: tuple[float, float]) -> dict:
    return {"scale": "diverging", "anchors": points, "labels": labels, "ticks": ticks, "range": list(rng)}


def band(bad: float, good: float, labels: tuple[str, str, str], near: float = 0.5) -> dict:
    """Diverging spec for an indicator with a risk-off threshold `bad` and a risk-on threshold `good` (either
    order). Between them the score moves gently through 0 at the midpoint; beyond each it heads to +-1 over
    another band width. Labels: (bad side, middle, good side), with "near ..." steps inside the band."""
    w = good - bad
    mid = (bad + good) / 2
    lo_word, mid_word, hi_word = labels
    pts = [[bad - w, -1], [bad, -0.6], [mid, 0], [good, 0.6], [good + w, 1]]
    edge_bad, edge_good = bad + w * (1 - near) / 2, good - w * (1 - near) / 2
    if w > 0:
        lbl = [[bad, lo_word], [edge_bad, f"near {lo_word}"], [edge_good, mid_word], [good, f"near {hi_word}"], [None, hi_word]]
        rng = (bad - w, good + w)
    else:  # a higher reading is worse
        lbl = [[good, hi_word], [edge_good, f"near {hi_word}"], [edge_bad, mid_word], [bad, f"near {lo_word}"], [None, lo_word]]
        rng = (good + w, bad - w)
    return diverging(pts, lbl, sorted([bad, good]), rng)


def rising_risk(calm: float, stress: float, labels: tuple[str, str, str, str]) -> dict:
    """Sequential spec for a one-way risk reading: grey up to `calm`, warming to red past `stress`."""
    w = stress - calm
    return sequential([[calm - w / 2, 0], [calm, -0.15], [stress, -0.65], [stress + w, -1]],
                      [[calm, labels[0]], [(calm + stress) / 2, labels[1]], [stress, labels[2]], [None, labels[3]]],
                      [calm, stress], (min(0.0, calm - w), stress + w * 1.5))
