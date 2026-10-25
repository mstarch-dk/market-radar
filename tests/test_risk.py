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
    assert f["alpha_basis"].startswith("raw returns")      # no risk-free rate: alpha is not an excess return
    rf = pd.Series(4.0, index=IDX)                           # % a year, like FRED DGS3MO
    assert risk.factor_loadings(asset, MKT, {"MTUM": mom}, rf, 156, 26)["alpha_basis"] == "excess over T-bills"


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


def test_the_shared_series_math():
    from radar.signals import risk as rk

    level = pd.Series([1.0, 1.2, 0.9, 1.0, 1.3])
    assert rk.underwater(level).tolist() == pytest.approx([0, 0, -0.25, -1 / 6, 0])
    assert rk.deepest_drawdown(level) == pytest.approx(-0.25)
    assert rk.worst_window(level, 2) == pytest.approx(1.0 / 1.2 - 1) and rk.worst_window(level, 9) is None
    r = level.pct_change().dropna()
    assert rk.annualised_vol(r) == pytest.approx(r.std() * 252 ** 0.5)


# ---------------- the portfolio risk model's additions (portfolios/riskmodel.py) ----------------

# Weekly covariance of two stocks and ACWI, by hand: vols 4 %, 3 % and 2 % a week; correlations 0.5, 0.6, 0.8
_SD = np.array([0.04, 0.03, 0.02])
_C = np.array([[1.0, 0.5, 0.6], [0.5, 1.0, 0.8], [0.6, 0.8, 1.0]])
COV = pd.DataFrame(np.outer(_SD, _SD) * _C, index=["A", "B", "ACWI"], columns=["A", "B", "ACWI"])


def test_risk_contributions_sum_to_one():
    from radar.portfolios import riskmodel as rm

    r = rm.ex_ante_risk({"A": 60, "B": 40}, COV, "ACWI")
    assert sum(r["contributions"].values()) == pytest.approx(1)
    w = pd.Series({"A": 0.6, "B": 0.4})
    active = rm.active_contributions(w, COV, "ACWI")
    assert set(active) == {"A", "B", "ACWI"} and sum(active.values()) == pytest.approx(1)
    a = np.array([0.6, 0.4, -1.0])                                   # by hand: a_i (Σa)_i / aᵀΣa
    S = COV.to_numpy()
    assert active["A"] == pytest.approx(a[0] * (S @ a)[0] / (a @ S @ a))
    assert (a @ S @ a) * 52 == pytest.approx(r["te_ann"] ** 2)       # the same tracking error as ex_ante_risk
    # holding some ACWI nets into its leg; holding only ACWI has no active risk to share out
    mixed = rm.active_contributions(pd.Series({"A": 0.5, "ACWI": 0.5}), COV, "ACWI")
    assert set(mixed) == {"A", "ACWI"} and sum(mixed.values()) == pytest.approx(1)
    assert rm.active_contributions(pd.Series({"ACWI": 1.0}), COV, "ACWI") == {}


def test_mctr_is_the_derivative_of_volatility():
    from radar.portfolios import riskmodel as rm

    w = pd.Series({"A": 0.5, "B": 0.3, "ACWI": 0.2})
    S = COV.to_numpy()

    def vol(x):
        return float(np.sqrt(x @ S @ x * 52))

    m = rm.mctr(w, COV)
    h = 1e-6
    for i, t in enumerate(w.index):
        up, down = w.to_numpy().copy(), w.to_numpy().copy()
        up[i] += h
        down[i] -= h
        assert m[t] == pytest.approx((vol(up) - vol(down)) / (2 * h), rel=1e-6)
    assert float((w * m).sum()) == pytest.approx(vol(w.to_numpy()))   # Euler: weighted, they add up to σ_p
    assert rm.mctr(pd.Series({"A": 0.0}), COV).empty                  # no variance: no answer, never 0


def test_effective_n():
    from radar.portfolios import riskmodel as rm

    for n in (1, 2, 5, 10):
        c = rm.concentration({f"S{i}": 1000.0 for i in range(n)})
        assert c["effective_n"] == pytest.approx(n)
        assert c["top5_share"] == pytest.approx(min(n, 5) / n)
    c = rm.concentration({"A": 600, "B": 300, "ACWI": 100, "X": None}, {"A": 0.3, "B": 0.7})
    assert c["largest"] == {"symbol": "A", "weight": pytest.approx(0.6)}
    assert c["largest_ctr"] == {"symbol": "B", "share": 0.7}
    assert c["world_fund_weight"] == pytest.approx(0.1)               # a world fund counts as one position here
    assert rm.concentration({})["effective_n"] is None


def test_correlated_pairs():
    from radar.portfolios import riskmodel as rm

    R = pd.DataFrame({"A": MKT + NOISE, "B": MKT - NOISE, "C": NOISE * 4, "D": MKT})
    R.loc[R.index[:-10], "D"] = np.nan                                # too few shared weeks: not judged
    pairs = rm.correlated_pairs({"A": 300, "B": 100, "C": 100, "D": 100}, R, threshold=0.7, weeks=156, min_weeks=26)
    assert [(p["a"], p["b"]) for p in pairs] == [("A", "B")]
    assert pairs[0]["corr"] > 0.7 and pairs[0]["weight"] == pytest.approx(400 / 600)
    assert rm.correlated_pairs({"A": 1}, R) == []
