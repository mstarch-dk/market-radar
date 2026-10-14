"""Risk statistics on synthetic series whose answers are known in advance."""
import numpy as np
import pandas as pd
import pytest

from radar.signals import risk

IDX = pd.date_range("2022-01-07", periods=200, freq="W-FRI")
rng = np.random.default_rng(7)
MKT = pd.Series(rng.normal(0.002, 0.02, len(IDX)), index=IDX)
NOISE = pd.Series(rng.normal(0, 0.005, len(IDX)), index=IDX)


def test_beta_and_alpha_of_a_levered_market():
    asset = 1.5 * MKT + NOISE
    s = risk.window_stats(asset, MKT, None, 156, 26)
    assert s["n_weeks"] == 156
    assert s["beta"] == pytest.approx(1.5, abs=0.05) and s["beta_se"] < 0.05 and s["r2"] > 0.95
    assert abs(s["alpha_ann"]) < 0.03 and s["alpha_basis"].startswith("raw")
    assert s["sharpe"] is None and s["sortino"] is None                      # no risk-free rate: not assumed 0
    assert s["idio_vol_ann"] == pytest.approx(0.005 * np.sqrt(52), rel=0.2)


def test_alpha_shows_up_and_risk_free_rate_is_used():
    asset = MKT + 0.002 + NOISE                                             # +0.2%/week beyond the market
    rf = pd.Series(4.0, index=pd.date_range("2021-01-01", periods=60, freq="MS"))   # 4% a year
    s = risk.window_stats(asset, MKT, rf, 156, 26)
    assert s["alpha_ann"] == pytest.approx(0.002 * 52, abs=0.03) and s["alpha_t"] > 3
    assert s["sharpe"] is not None and s["sortino"] is not None and s["alpha_basis"].startswith("excess")


def test_downside_beta_sees_asymmetry():
    asset = MKT.where(MKT >= 0, 2 * MKT) + NOISE                            # falls twice as hard as it rises
    s = risk.window_stats(asset, MKT, None, 156, 26)
    assert s["downside_beta"] == pytest.approx(2, abs=0.15) and s["beta"] < s["downside_beta"]


def test_too_little_history_is_no_answer():
    assert risk.window_stats(MKT.iloc[:20], MKT, None, 52, 26) is None


def test_factor_clone_loads_on_its_factor():
    mom = MKT + pd.Series(rng.normal(0, 0.01, len(IDX)), index=IDX)        # a "momentum ETF"
    val = MKT + pd.Series(rng.normal(0, 0.01, len(IDX)), index=IDX)
    asset = mom + NOISE / 5
    f = risk.factor_loadings(asset, MKT, {"MTUM": mom, "VLUE": val}, None, 156, 26)
    load = {x["factor"]: x for x in f["loadings"]}
    assert load["market"]["beta"] == pytest.approx(1, abs=0.1)
    assert load["MTUM"]["beta"] == pytest.approx(1, abs=0.1) and load["MTUM"]["t"] > 10
    assert abs(load["VLUE"]["beta"]) < 0.1


def test_drawdown_and_correlation():
    r = pd.Series([0.1, -0.2, -0.1, 0.05, 0.4], index=IDX[:5])
    dd, weeks = risk.drawdown(r)
    assert dd == pytest.approx(0.9 * 0.8 * 1.1 / 1.1 - 1) and weeks == 3
    c = risk.correlation({"a": MKT, "b": 2 * MKT, "c": -MKT}, 52, 26)
    m = c["matrix"]
    assert m[0][1] == pytest.approx(1) and m[0][2] == pytest.approx(-1) and m[1][0] == m[0][1] and m[2][2] == 1.0


def test_risk_budget():
    assert risk.risk_budget(-0.05) == pytest.approx(0.2)                     # 20% position risks 1% at a 5% stop
    assert risk.risk_budget(None) is None and risk.risk_budget(0.01) is None


def test_a_week_in_progress_is_left_out():
    days = pd.bdate_range("2026-09-07", "2026-10-14")                     # ends on a Wednesday
    px = pd.Series(range(100, 100 + len(days)), index=days, dtype=float)
    w = risk.weekly(px)
    assert w.index[-1] == pd.Timestamp("2026-10-09")                        # the last complete week
    assert risk.weekly(px[:"2026-10-09"]).index[-1] == pd.Timestamp("2026-10-09")
