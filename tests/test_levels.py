import numpy as np
import pandas as pd
import pytest

from radar.external import parse_analyst
from radar.signals import levels

CFG = {"atr_days": 14, "k_base": 3.0, "k_min": 1.5, "k_max": 3.5, "k_step": 0.5, "strong_score": 80,
       "extended_vs_sma50": 0.25, "reward_risk": 2.0, "near_atr": 1.0, "min_analysts": 5, "target_cut": 0.05,
       "info_anchor_days": 63}

# healthy uptrend, nothing that should move k
ROW = {"last": 100.0, "sma50": 95.0, "sma200": 85.0, "above50": True, "above200": True, "trend_ok": True,
       "r1m": 0.02, "score": 60.0}


def _effects(res):
    return {r["signal"]: r["effect"] for r in res["reasons"] if r["effect"]}


def test_atr_of_constant_range_equals_range():
    idx = pd.bdate_range("2026-01-01", periods=60)
    close = pd.Series(100.0, index=idx)
    a = levels.atr(close + 1, close - 1, close, 14)
    assert a.iloc[-1] == pytest.approx(2.0)


def test_base_case_keeps_k_and_sets_stop_and_reward_risk_target():
    res = levels.levels(ROW, atr_value=2.0, anchor_value=104.0, regime_label="Risk-on", analyst=None, cfg=CFG)
    assert res["k"] == 3.0 and not _effects(res)
    assert res["stop"] == pytest.approx(98.0)                   # 104 - 3 x 2
    assert res["take_profit"] == pytest.approx(112.0)           # 100 + 2 x 3 x 2
    assert "near stop" in res["flags"]                          # 2.0 away = 1 ATR


def test_risk_off_and_broken_trend_tighten_and_explain():
    row = ROW | {"above200": False, "trend_ok": False, "sma200": 110.0}
    res = levels.levels(row, 2.0, 120.0, "Risk-off", None, CFG)
    assert res["k"] == 2.0
    assert _effects(res) == {"Trend broken": -0.5, "Macro regime": -0.5}


def test_k_is_clamped_at_minimum():
    row = ROW | {"above50": False, "above200": False, "trend_ok": False, "r1m": -0.1, "sma50": 60.0}
    analyst = {"target_mean": 80.0, "target_high": 90.0, "upside": -0.2, "n_analysts": 20, "rec_key": "hold",
               "target_change": -0.2}
    res = levels.levels(row, 2.0, 120.0, "Risk-off", analyst, CFG)
    assert res["k"] == CFG["k_min"]
    assert "above highest analyst target" in res["flags"] and res["take_profit"] is None


def test_strong_momentum_gets_more_room():
    res = levels.levels(ROW | {"score": 90.0}, 2.0, 104.0, "Risk-on", None, CFG)
    assert res["k"] == 3.5


def test_take_profit_is_the_lower_of_reward_risk_and_analyst_target():
    analyst = {"target_mean": 103.0, "target_high": 130.0, "upside": 0.03, "n_analysts": 30, "rec_key": "buy"}
    res = levels.levels(ROW, 2.0, 104.0, "Risk-on", analyst, CFG)
    assert res["take_profit"] == pytest.approx(103.0) and "analyst" in res["tp_source"]
    few = analyst | {"n_analysts": 3}                            # too few opinions: ignored
    assert levels.levels(ROW, 2.0, 104.0, "Risk-on", few, CFG)["take_profit"] == pytest.approx(112.0)


def test_price_above_mean_target_tightens():
    analyst = {"target_mean": 95.0, "target_high": 130.0, "upside": -0.05, "n_analysts": 30, "rec_key": "buy"}
    res = levels.levels(ROW, 2.0, 104.0, "Risk-on", analyst, CFG)
    assert _effects(res) == {"Above analyst target": -0.5}
    assert res["take_profit"] == pytest.approx(100 + 2 * 2.5 * 2)


def test_analyst_targets_converted_to_radar_price_units():
    idx = pd.bdate_range("2026-01-01", periods=30)
    close = pd.Series(50.0, index=idx)                          # e.g. pence vs Yahoo's pounds, or an ADR ratio
    hist = pd.DataFrame([
        {"ticker": "X", "fetched": idx[0], "quote_type": "EQUITY", "current_price": 100.0, "target_mean": 100.0,
         "target_high": 150.0, "target_low": 90.0, "target_median": 100.0, "n_analysts": 10, "rec_key": "buy", "rec_mean": 2.0},
        {"ticker": "X", "fetched": idx[-1], "quote_type": "EQUITY", "current_price": 100.0, "target_mean": 120.0,
         "target_high": 150.0, "target_low": 90.0, "target_median": 118.0, "n_analysts": 10, "rec_key": "buy", "rec_mean": 2.0},
    ])
    v = levels.analyst_view(hist, "X", close, revision_days=30)
    assert v["target_mean"] == pytest.approx(60.0)
    assert v["upside"] == pytest.approx(0.2)
    assert v["target_change"] == pytest.approx(0.2)              # 100 -> 120 over >= 30 days


def test_parse_analyst_handles_funds_and_missing_fields():
    assert parse_analyst(None) is None and parse_analyst({}) is None
    etf = parse_analyst({"quoteType": "ETF", "currency": "USD"})
    assert etf["quote_type"] == "ETF" and etf["target_mean"] is None
    stock = parse_analyst({"quoteType": "EQUITY", "targetMeanPrice": 120.5, "numberOfAnalystOpinions": 40,
                           "recommendationKey": "buy", "currentPrice": 100})
    assert stock["target_mean"] == 120.5 and stock["n_analysts"] == 40 and stock["target_high"] is None


def test_for_ticker_uses_entry_anchor():
    idx = pd.bdate_range("2026-01-01", periods=80)
    c = pd.Series(np.r_[np.linspace(100, 130, 40), np.linspace(130, 127, 40)], index=idx)
    closes, highs, lows = c.to_frame("X"), (c + 1).to_frame("X"), (c - 1).to_frame("X")
    row = ROW | {"last": float(c.iloc[-1]), "sma50": 120.0, "above50": False, "r1m": -0.05}
    res = levels.for_ticker("X", closes, highs, lows, row, idx[50], "Risk-on", None, CFG)
    assert res["anchor"] == pytest.approx(float(c.iloc[50]))     # highest close since entry, not the earlier peak
    assert "since entry" in res["anchor_basis"]


def test_trail_records_breach_and_restarts_from_the_next_high():
    idx = pd.bdate_range("2026-01-01", periods=60)
    c = pd.Series(np.r_[np.full(20, 100.0), np.full(10, 80.0), np.linspace(80, 95, 30)], index=idx)
    a = pd.Series(2.0, index=idx)
    start, breaches = levels.trail(c, a, idx[0], k=3.0)
    assert [b["date"] for b in breaches] == [idx[20].date().isoformat()]   # 80 <= 100 - 6
    assert start == idx[21] and c[start:].max() == 95.0
