"""The score study (backtest/study.py) on constructed markets whose answers are known: persistent drifts rank
perfectly (IC 1), pure noise doesn't (IC about 0), nothing after a date's horizon is read, missing forward
returns are counted rather than treated as 0, and the holdout split and Newey-West errors are as specified."""
import copy
import math

import numpy as np
import pandas as pd
import pytest

from radar.backtest import study
from radar.config import settings
from radar.signals import momentum

DAYS = 520
IDX = pd.bdate_range("2020-01-01", periods=DAYS)


def panels(closes: pd.DataFrame) -> study.Panels:
    tickers = list(closes.columns)
    half = len(tickers) // 2
    group = pd.Series(["us"] * half + ["europe"] * (len(tickers) - half), index=tickers)
    sector = pd.Series([("Tech", "Energy", "Health")[i % 3] for i in range(len(tickers))], index=tickers)
    return study.Panels(closes, closes * 6.5, momentum.metrics_panel(closes, tickers, 200),
                        np.log(closes).diff().rolling(63, min_periods=32).std() * math.sqrt(252), group, sector,
                        closes.index, pd.Series(100 * 1.0003 ** np.arange(DAYS) * 6.5, index=closes.index))


def drifting(n: int = 40) -> pd.DataFrame:
    g = np.linspace(-0.001, 0.002, n)
    return pd.DataFrame({f"T{i:02d}": 100 * (1 + g[i]) ** np.arange(DAYS) for i in range(n)}, index=IDX)


def noise(n: int = 200, seed: int = 1) -> pd.DataFrame:
    r = np.random.default_rng(seed).normal(0, 0.02, (DAYS, n))
    return pd.DataFrame(100 * np.exp(np.cumsum(r, axis=0)), index=IDX, columns=[f"N{i:03d}" for i in range(n)])


@pytest.fixture
def cfg(monkeypatch):
    c = copy.deepcopy(settings())
    c["backtest"] |= {"study_min_names": 20, "study_holdout_from": "2021-06-01", "fill": "next"}
    monkeypatch.setattr(study, "settings", lambda: c)
    return c


def run(closes, **kw):
    return study.run(None, kw.pop("horizons", (1, 3)), kw.pop("variants", ["score", "r3m", "r1m"]), 5,
                     with_regime=False, p=panels(closes), **kw)


def test_persistent_drift_ranks_perfectly(cfg):
    rep = run(drifting())
    for h in ("1", "3"):
        a = rep["results"][h]["score"]["all"]
        assert a["dates"] > 3 and a["ic_mean"] == pytest.approx(1.0)
        assert a["monotone"] and a["q"][0] < 0 < a["q"][-1] and a["top_hit"] == 1.0
    assert rep["turnover"]["score"] == 0.0


def test_noise_has_no_ic(cfg):
    rep = run(noise())
    a = rep["results"]["1"]["score"]["all"]
    assert abs(a["ic_mean"]) < 0.05 and a["dates"] >= 10


def test_cross_section_by_hand():
    x = pd.Series(np.arange(50.0), index=[f"T{i}" for i in range(50)])
    cs = study.cross_section(x, x * 0.01, 5, 20)
    assert cs["ic"] == pytest.approx(1.0) and cs["n"] == 50
    assert cs["top"] == ["T49", "T48", "T47", "T46", "T45"]
    assert cs["q"] == pytest.approx([(np.mean(range(q * 10, q * 10 + 10)) - 24.5) * 0.01 for q in range(5)])
    assert study.cross_section(x.iloc[:10], x.iloc[:10], 5, 20) is None


def test_newey_west_by_hand():
    v = [0.1, 0.3, -0.2, 0.4, 0.0, 0.2]
    e = np.array(v) - np.mean(v)
    n = len(v)
    s0 = e @ e / n
    assert study.nw_t(v, 0) == pytest.approx(np.mean(v) / math.sqrt(s0 / n))
    s1 = s0 + 2 * 0.5 * (e[1:] @ e[:-1]) / n
    assert study.nw_t(v, 1) == pytest.approx(np.mean(v) / math.sqrt(s1 / n))
    assert study.nw_t([0.1, None], 0) is None


def test_nothing_after_the_horizon_is_read(cfg):
    c = drifting()
    first = run(c, horizons=(1,))["dates"][0]
    end = IDX[IDX.get_loc(pd.Timestamp(first["fill"])) + 21]
    changed = c.copy()
    changed.loc[changed.index > end] *= np.random.default_rng(3).uniform(0.5, 2, changed.loc[changed.index > end].shape)
    again = run(changed, horizons=(1,))["dates"][0]
    assert again["date"] == first["date"] and again["horizons"]["1"] == first["horizons"]["1"]


def test_missing_forward_returns_are_counted_not_zero(cfg):
    c = drifting()
    d = run(c, horizons=(1,))["dates"][0]
    gone = c.copy()
    gone.loc[gone.index > pd.Timestamp(d["fill"]), "T39"] = np.nan        # the best name stops trading
    rec = run(gone, horizons=(1,))["dates"][0]["horizons"]["1"]
    assert rec["fwd_missing"] == 1 and "T39" not in rec["top"]
    assert rec["ic"]["score"] == pytest.approx(1.0)


def test_holdout_split_and_verdicts(cfg):
    rep = run(drifting())
    res = rep["results"]["1"]["score"]
    assert res["in_sample"]["dates"] + res["holdout"]["dates"] == res["all"]["dates"]
    assert all(d["date"] >= "2021-06-01" for d in rep["dates"][-res["holdout"]["dates"]:])
    assert rep["variants_tried"] == 2 and set(rep["verdicts"]["1"]) == {"r3m", "r1m"}
    assert rep["verdicts"]["1"]["r3m"]["label"] in ("not better", "not enough data", "candidate, but the difference is small")


def test_formation_dates_skip_the_unfinished_month():
    s = pd.bdate_range("2024-01-01", "2024-03-13")
    assert study.formation_dates(s) == [pd.Timestamp("2024-01-31"), pd.Timestamp("2024-02-29")]
    assert study.fill_session(s, pd.Timestamp("2024-01-31"), "next") == s.get_loc(pd.Timestamp("2024-02-01"))


def test_unknown_variants_and_horizons_are_refused(cfg):
    with pytest.raises(ValueError):
        run(drifting(), variants=["nope"])
    with pytest.raises(ValueError):
        run(drifting(), horizons=(2,))


def test_exit_verdicts_follow_the_thresholds():
    def part(diff, dd, p10, hold_dd=-0.20, hold_p10=-0.15):
        return {"dates": 10, "diff_mean": diff, "dd_mean": dd, "ret_p10": p10,
                "hold": {"dd_mean": hold_dd, "ret_p10": hold_p10}}
    good = part(-0.01, -0.12, -0.08)
    assert study.exit_verdict({"in_sample": good, "holdout": good}, 6)["label"] == "passes"
    costly = study.exit_verdict({"in_sample": part(-0.03, -0.12, -0.08), "holdout": good}, 6)
    assert costly["label"] == "fails" and "costs" in costly["why"][0]
    assert study.exit_verdict({"in_sample": part(-0.015, -0.12, -0.08), "holdout": good}, 3)["label"] == "fails"  # 1 pp per 3m
    assert study.exit_verdict({"in_sample": good, "holdout": part(-0.01, -0.18, -0.08)}, 6)["label"] == "fails"
    assert study.exit_verdict({"in_sample": good, "holdout": part(-0.01, -0.12, -0.20)}, 6)["label"] == "fails"
    assert study.exit_verdict({"in_sample": good, "holdout": None}, 6)["label"] == "not enough data"


def test_summarize_exits_pairs_each_date_with_holding():
    h = lambda r, dd: {"ret": r, "max_dd": dd, "vol": 0.3, "worst20": -0.1}           # noqa: E731
    recs = [{"date": pd.Timestamp("2022-01-31"), "hold": h(0.10, -0.20), "x": h(0.08, -0.10), "x_exits": 3},
            {"date": pd.Timestamp("2022-02-28"), "hold": h(-0.10, -0.30), "x": h(-0.02, -0.12), "x_exits": 5},
            {"date": pd.Timestamp("2022-03-31"), "hold": h(0.05, -0.10), "x": None}]
    s = study.summarize_exits(recs, "x", 0)
    assert s["dates"] == 2 and s["diff_mean"] == pytest.approx(0.03) and s["helped"] == 0.5
    assert s["dd_mean"] == pytest.approx(-0.11) and s["hold"]["dd_mean"] == pytest.approx(-0.25)
    assert s["exits_mean"] == 4
