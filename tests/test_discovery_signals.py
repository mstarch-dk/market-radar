import numpy as np
import pandas as pd
import pytest

from radar.signals import discovery as sig

N = 300
IDX = pd.bdate_range(end="2026-10-14", periods=N)
T = np.arange(N)
CFG = {"flags": {"new_high_vol": 1.5, "trend_turn_days": 20, "d_score_days": 21, "rs_high_days": 5},
       "size_dkk": {"large": 5e10, "mid": 5e9}, "liquidity_floor_dkk": 1e6, "check_data_move": 0.6}
FX = {"DKK": 1.0, "EUR": 7.46, "GBP": 8.6}


def _geo(g):
    return 100 * (1 + g) ** T


def _world():
    c = {"ACWI": _geo(0.0004), "A": _geo(0.002), "B": _geo(0.001), "C": _geo(0.0005), "D": _geo(0.001)}
    turn = np.r_[np.linspace(150, 100, N - 15), np.linspace(100, 140, 15)]      # falls, then crosses its 200d
    c["TURN"] = turn
    jump = _geo(0.0005).copy()
    jump[200:] *= 1.7                                                            # a one-day +70%: bad data?
    c["JUMP"] = jump
    closes = pd.DataFrame(c, index=IDX)
    volumes = pd.DataFrame(1000.0, index=IDX, columns=closes.columns)
    volumes.loc[IDX[-20:], "A"] = 3000.0                                         # volume surge on A
    return closes, volumes


META = pd.DataFrame({
    "ticker": ["A", "B", "C", "TURN", "JUMP", "D"],
    "market": ["m1", "m1", "m1", "m1", "m1", "m2"],
    "currency": ["GBp", "EUR", "EUR", "EUR", "EUR", None],
    "market_cap_dkk": [6e10, 6e9, 1e9, None, 1e9, 1e9],
})


def _compute(closes, volumes, tracked=frozenset({"B"})):
    return sig.compute(closes, closes, volumes, META, "ACWI", FX, set(tracked), CFG, 200, IDX[-1]).set_index("ticker")


def test_scores_rank_within_each_market_and_compare_with_a_month_ago():
    closes, volumes = _world()
    df = _compute(closes, volumes)
    assert df.loc["A", "score"] > df.loc["B", "score"] > df.loc["C", "score"]
    assert df.loc["D", "market"] == "m2" and df.loc["D", "score"] == 100     # alone in its market
    assert df.loc["A", "d_score"] == pytest.approx(df.loc["A", "score"] - df.loc["A", "score_prev"])
    assert df.loc["A", "r1w"] == pytest.approx((1.002) ** 5 - 1)


def test_size_liquidity_and_ownership():
    closes, volumes = _world()
    df = _compute(closes, volumes)
    assert df.loc["A", "size"] == "large" and df.loc["B", "size"] == "mid" and df.loc["C", "size"] == "small"
    assert pd.isna(df.loc["TURN", "size"])                                   # unknown cap stays unknown
    # A is quoted in pence: price x volume / 100 x GBP rate
    a = closes["A"].iloc[-20:] * 3000
    assert df.loc["A", "liquidity_dkk"] == pytest.approx(a.median() / 100 * 8.6)
    assert bool(df.loc["A", "thin"]) is True                                 # far below 1m DKK a day
    assert pd.isna(df.loc["D", "liquidity_dkk"]) and pd.isna(df.loc["D", "thin"])   # no currency: unknown
    assert not df.loc["B", "off_radar"] and df.loc["A", "off_radar"]


def test_flags():
    closes, volumes = _world()
    df = _compute(closes, volumes)
    assert bool(df.loc["A", "new_high"]) is True and bool(df.loc["B", "new_high"]) is False
    assert bool(df.loc["TURN", "trend_turn"]) is True and bool(df.loc["A", "trend_turn"]) is False
    assert bool(df.loc["JUMP", "check_data"]) is True and bool(df.loc["A", "check_data"]) is False
    assert df.loc["A", "quadrant"] in ("Leading", "Improving", "Weakening", "Lagging")


def test_stale_names_are_flagged():
    closes, volumes = _world()
    closes.loc[IDX[-10:], "C"] = np.nan
    df = _compute(closes, volumes)
    assert bool(df.loc["C", "stale"]) is True and bool(df.loc["A", "stale"]) is False


def test_size_bucket_and_sparkline():
    assert sig.size_bucket(None, 10, 5) is None and sig.size_bucket(float("nan"), 10, 5) is None
    assert sig.size_bucket(7, 10, 5) == "mid"
    s = pd.Series(_geo(0.001), index=IDX)
    sp = sig.sparkline(s)
    assert len(sp) == 26 and sp[-1] == pytest.approx(s.iloc[-1], rel=1e-3)
