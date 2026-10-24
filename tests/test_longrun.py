from datetime import date

import numpy as np
import pandas as pd
import pytest

from radar.backtest import longrun
from radar.config_schema import Longrun
from radar.model import artifacts, prior
from radar.model import prior as mprior
from radar.sources import factors


def _months(n: int) -> pd.DatetimeIndex:
    return pd.period_range("1960-01", periods=n, freq="M").to_timestamp(how="end").normalize()


def _panel(returns: pd.DataFrame, market: pd.Series | None = None) -> longrun.Panel:
    m = returns.mean(axis=1) if market is None else market
    return longrun.Panel("test", "Test panel", returns, m, n_top=6, min_names=20)


def _cfg(monkeypatch, holdout="1990-01-01"):
    monkeypatch.setattr(longrun, "cfg", lambda: Longrun(holdout_from=holdout, horizons=[1, 6], regime_months=10))


def _momentum_world(n_months=480, members=30, seed=1, persistent=True) -> pd.DataFrame:
    """Each member's expected return drifts slowly (AR(1) with a long half-life), so past winners keep winning;
    with `persistent` off the returns are pure noise."""
    rng = np.random.default_rng(seed)
    drift = np.zeros(members)
    rows = []
    for _ in range(n_months):
        drift = 0.95 * drift + rng.normal(0, 0.003, members) if persistent else np.zeros(members)
        rows.append(drift + rng.normal(0, 0.04, members))
    return pd.DataFrame(rows, index=_months(n_months), columns=[f"m{i}" for i in range(members)])


def test_windows_follow_the_production_lookbacks():
    r = pd.DataFrame({"a": [0.1] * 14}, index=_months(14))
    c = longrun.components(r)
    t = r.index[12]
    assert c["r12_1"].loc[t, "a"] == pytest.approx(1.1 ** 11 - 1)     # months t-11..t-1
    assert c["r6m"].loc[t, "a"] == pytest.approx(1.1 ** 6 - 1)
    assert np.isnan(c["r12_1"].iloc[10, 0])                            # not enough months yet
    f = longrun.forward(r, 1)
    assert f.loc[t, "a"] == pytest.approx(0.1) and np.isnan(f.iloc[-1, 0])


def test_a_missing_month_leaves_the_window_missing():
    r = pd.DataFrame({"a": [0.01] * 14}, index=_months(14))
    r.iloc[5, 0] = np.nan
    assert mprior.window(r, 6).iloc[5:11, 0].isna().all()


@pytest.mark.slow
def test_finds_a_planted_momentum_effect(monkeypatch):
    _cfg(monkeypatch)
    rep = longrun.run(_panel(_momentum_world()), variants=["score", "r12_1"])
    a = rep["results"]["1"]["score"]["all"]
    assert a["ic_mean"] > 0 and a["ic_t"] > 2
    assert a["eff_n"] == a["dates"]
    assert rep["results"]["6"]["score"]["all"]["eff_n"] == pytest.approx(a["dates"] / 6, abs=1)
    assert {"1960s", "1980s"} <= set(rep["results"]["1"]["score"]["by_decade"])
    assert rep["variants_tried"] == 1


@pytest.mark.slow
def test_finds_nothing_in_noise(monkeypatch):
    _cfg(monkeypatch)
    rep = longrun.run(_panel(_momentum_world(persistent=False, seed=3)), variants=["score", "r6m", "w_long"])
    a = rep["results"]["1"]["score"]["all"]
    assert abs(a["ic_t"]) < 2
    assert not any("candidate" in v["label"] for v in rep["verdicts"]["1"].values())


def test_load_panel_adds_rf_and_keeps_members(monkeypatch):
    idx = _months(30)
    data = pd.concat([
        factors.long_rows("jkp:mkt_countries", pd.DataFrame({"dnk": 0.01, "usa": 0.02, "zzz": 0.5}, index=idx), date(2026, 1, 1)),
        factors.long_rows("jkp:mkt_world", pd.DataFrame({"world": 0.015}, index=idx), date(2026, 1, 1)),
        factors.long_rows("french:ff3_us", pd.DataFrame({"Mkt-RF": 0.01, "RF": 0.001}, index=idx), date(2026, 1, 1)),
    ])
    monkeypatch.setattr(longrun, "cfg", lambda: Longrun.model_validate({"panels": {"c": {
        "data": "jkp:mkt_countries", "excess": True, "market": "world", "members": ["dnk", "usa", "nor"]}}}))
    p = longrun.load_panel("c", data)
    assert list(p.returns.columns) == ["dnk", "usa"]                   # configured members only; nor isn't there
    assert p.returns["dnk"].iloc[0] == pytest.approx(0.011)
    assert p.market.iloc[0] == pytest.approx(0.016)


def test_load_panel_without_data_says_what_to_run(monkeypatch):
    monkeypatch.setattr(longrun, "cfg", lambda: Longrun.model_validate({"panels": {"c": {"data": "jkp:mkt_countries"}}}))

    with pytest.raises(ValueError, match="radar update"):
        longrun.load_panel("c", pd.DataFrame(columns=factors.COLUMNS))


def test_base_rates_drawdown_and_losing_windows():
    r = pd.Series([0.02] * 24 + [-0.10] * 3 + [0.05] * 24, index=_months(51))
    b = longrun.base_rates(r)
    d = b["drawdown"]
    assert d["max"] == pytest.approx(0.9 ** 3 - 1)
    assert d["peak"] == r.index[23] and d["trough"] == r.index[26]
    assert d["months_to_recover"] == 3 + 7                             # 1.05^7 > 1/0.729 > 1.05^6
    assert 0 < b["roll6"]["share_negative"] < 1
    assert longrun.base_rates(r.iloc[:20]) is None                     # too short to say anything


def test_survivorship_gauge_compares_the_same_months():
    idx = _months(24)
    deciles = pd.DataFrame({f"d{i}": [i / 1000] * 24 for i in range(10)}, index=idx)
    data = factors.long_rows("french:mom10_us", deciles, date(2026, 1, 1))
    study = artifacts.ScoreStudy.model_validate(
        {"schema_version": 1, "kind": "score-study", "created": "2026-01-01T00:00:00", "data_asof": None,
         "results": {"1": {"score": {"all": {"q": [0, 0, 0, 0, 0.01], "dates": 6}}}},
         "universe": {"first": str(idx[5].date()), "last": str(idx[10].date())}})
    g = longrun.survivorship_gauge(data, study)
    # top two deciles (0.008, 0.009) minus the mean of all ten (0.0045)
    assert g["survivorship_free_same_months"] == pytest.approx(0.004)
    assert g["window"]["french_months"] == 6
    assert g["implied_haircut"] == pytest.approx(0.6)


def _terciles(n=120, edge=0.01, seed=5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = rng.normal(0.005, 0.04, n)
    return pd.DataFrame({"1": base - edge, "2": base, "3": base + edge}, index=_months(n))


def test_tercile_excess_is_top_minus_the_mean_of_three():
    x = prior.tercile_excess(_terciles(edge=0.01), 1)
    assert x.dropna().iloc[0] == pytest.approx(0.01)
    assert prior.tercile_excess(pd.DataFrame({"1": [0.1]}, index=_months(1)), 1).empty


def test_prior_weights_spread_the_tilt_over_characteristics():
    comps = {"momentum": ["ret_12_1", "ret_6_1"], "value": ["fcf_me", "eqnpo_me"], "quality": ["qmj"]}
    w = prior.prior_weights({"momentum": 0.5, "qv": 0.5}, comps, {"value": 0.5, "quality": 0.5})
    assert w == pytest.approx({"ret_12_1": 0.25, "ret_6_1": 0.25, "fcf_me": 0.125, "eqnpo_me": 0.125, "qmj": 0.25})
    assert prior.prior_weights({"momentum": 1.0, "qv": 0.0}, comps, {"value": 0.5, "quality": 0.5}) == \
        {"ret_12_1": 0.5, "ret_6_1": 0.5}


def test_tilt_prior_weights_characteristics_and_splits_by_trend():
    data = pd.concat([factors.long_rows("jkp_pf:developed:a", _terciles(edge=0.01), date(2026, 1, 1)),
                      factors.long_rows("jkp_pf:developed:b", _terciles(edge=0.03, seed=6), date(2026, 1, 1))])
    p = prior.tilt_prior({"a": 0.5, "b": 0.5}, 3, "developed", data)
    assert p["mean"] == pytest.approx(0.02 * 3, rel=0.05)           # ≈ 2 % a month for three months
    assert p["eff_n"] == pytest.approx(p["months"] / 3, abs=0.05) and p["t"] > 2
    assert set(p["by_trend"]) == {"up", "down"}
    assert p["components"]["a"] < p["components"]["b"]
    assert prior.tilt_prior({"a": 1.0, "missing": 1.0}, 3, "developed", data) is None   # never a partial prior
    later = prior.tilt_prior({"a": 1.0}, 3, "developed", data, since="1965-01-01")
    assert later["first"] >= pd.Timestamp("1965-01-01")
