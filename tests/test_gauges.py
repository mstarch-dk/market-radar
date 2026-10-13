"""Graded readings: interpolation, levels, labels, one-way risk scales and missing data."""
import math

import pytest

from radar.signals import gauges as g


def test_interpolation_and_clamping():
    a = [[0, -1], [10, 1]]
    assert g.interpolate(a, 5) == pytest.approx(0)
    assert g.interpolate(a, 2.5) == pytest.approx(-0.5)
    assert g.interpolate(a, -50) == -1 and g.interpolate(a, 50) == 1
    assert g.interpolate([[10, 1], [0, -1]], 5) == pytest.approx(0)      # anchor order doesn't matter


def test_rsi_close_to_overbought_is_already_orange():
    r = g.gauge("rsi14", 69.5)
    assert r["label"] == "near overbought" and r["level"] in (-2, -3) and r["score"] < -0.5
    assert g.gauge("rsi14", 72)["label"] == "overbought"
    assert g.gauge("rsi14", 50)["level"] == 0 and g.gauge("rsi14", 50)["label"] == "neutral"
    assert g.gauge("rsi14", 25)["level"] > 0 and g.gauge("rsi14", 25)["label"] == "oversold"
    assert g.gauge("rsi14", 85)["level"] == -4


def test_missing_values_are_not_graded():
    assert g.gauge("rsi14", None) is None
    assert g.gauge("rsi14", math.nan) is None
    assert g.gauges({"rsi14": None, "beta": 1.2}).keys() == {"beta"}


def test_one_way_risk_never_turns_green():
    assert all(g.gauge("atr_pct", v)["score"] <= 0 for v in (0, 0.005, 0.02, 0.1))
    spec = g.rising_risk(18, 25, ("calm", "normal", "elevated", "stress"))
    assert g.make(spec, 10)["score"] == 0 and g.make(spec, 10)["label"] == "calm"
    assert g.make(spec, 24)["label"] == "elevated" and g.make(spec, 40)["level"] == -4


def test_crowding_is_graded_by_distance_from_the_middle():
    lo, hi = g.gauge("cot_pct", 5), g.gauge("cot_pct", 95)
    assert lo["level"] == hi["level"] < 0 and lo["score"] == hi["score"]
    assert (lo["label"], hi["label"]) == ("crowded short", "crowded long")
    assert g.gauge("cot_pct", 50)["level"] == 0


def test_band_works_in_both_directions():
    breadth = g.band(40, 60, ("weak", "neutral", "strong"))           # higher is better
    assert g.make(breadth, 61)["label"] == "strong" and g.make(breadth, 61)["level"] > 0
    assert g.make(breadth, 57)["label"] == "near strong"
    assert g.make(breadth, 50)["level"] == 0 and g.make(breadth, 30)["level"] < 0
    spread = g.band(1.03, 0.97, ("widening", "steady", "tightening"))  # higher is worse
    assert g.make(spread, 1.05)["label"] == "widening" and g.make(spread, 1.05)["level"] < 0
    assert g.make(spread, 0.95)["level"] > 0 and g.make(spread, 1.02)["label"] == "near widening"


def test_every_configured_spec_is_valid():
    from radar.config import settings

    for key, spec in settings()["gauges"].items():
        assert spec["scale"] in ("diverging", "sequential"), key
        assert spec["labels"][-1][0] is None, f"{key}: the last label band must be open-ended"
        lo, hi = spec["range"]
        r = g.gauge(key, (lo + hi) / 2)
        assert -4 <= r["level"] <= 4 and r["label"], key


def test_watchouts_are_red_signals_not_traits():
    gs = g.gauges({"rsi14": 85, "beta": 2.5, "atr_pct": 0.09, "stop_dist": -0.01, "score": 50})
    assert gs["beta"]["level"] <= -3 and gs["atr_pct"]["level"] <= -3      # coloured red, but traits
    assert sorted(w["key"] for w in g.watchouts(gs)) == ["rsi14", "stop_dist"]
    assert [w["text"] for w in g.watchouts(gs, skip={"stop_dist"})] == ["RSI 14: extremely overbought"]
