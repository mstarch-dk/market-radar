"""The shared kernel (radar.model): one percentile rule and one trend exit for the app and the studies."""
import numpy as np
import pandas as pd
import pytest

from radar import propose
from radar.backtest import longrun, picks, study
from radar.model import panels as mp
from radar.model import paths as mpaths
from radar.signals import momentum
from radar.signals import score as ms
from radar.signals.score import mean_pct
from radar.sources import tracked


def _dist(seed: int = 1, n: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(rng.normal(size=(n, 3)).round(1), columns=list(ms.COMPONENTS),   # rounding makes ties
                      index=[f"T{i}" for i in range(n)])
    df.iloc[3, 0] = df.iloc[7, 1] = np.nan
    return df


def test_one_name_against_the_pool_equals_the_whole_pool_ranked():
    df = _dist()
    whole = ms.score(df)
    for t in df.index:
        one = ms.score_vs(df, df.loc[t])
        assert (one is None and pd.isna(whole[t])) or one == pytest.approx(whole[t], abs=0.051)


def test_every_caller_uses_the_same_rule():
    df = _dist(2)
    assert momentum.score(df).equals(ms.score(df))
    assert ms.mean_pct(df).equals(mean_pct(df))
    assert np.allclose(ms.weighted_pct(df, dict.fromkeys(ms.COMPONENTS, 1.0)), ms.mean_pct(df), equal_nan=True)
    assert mean_pct is ms.mean_pct and mean_pct is ms.mean_pct and longrun.wpct is ms.weighted_pct
    assert study.BY_KEY["score"].fn is mp.score_at and picks.ranked is mp.ranked and mp.Panels is mp.Panels


def test_the_share_strictly_below_with_ties():
    df = pd.DataFrame({c: [3.0, 2.0, 2.0, 1.0] for c in ms.COMPONENTS}, index=list("ABCD"))
    s = ms.score(df)
    assert s.tolist() == [75.0, 25.0, 25.0, 0.0]            # the strongest is 100 x (N-1)/N, the weakest 0


IDX = pd.bdate_range("2024-01-01", periods=12)


def test_the_trend_exit_never_triggers_on_the_buy_day_and_sells_the_next_session():
    below = pd.Series(False, index=IDX)
    below.iloc[0] = True                                     # below on the buy day: not a trigger
    assert mpaths.exit_session(IDX, below) is None
    below.iloc[4] = True
    assert mpaths.exit_session(IDX, below) == 5
    assert mpaths.exit_session(IDX, pd.Series(False, index=IDX), lambda d: d == IDX[2]) == 3
    late = pd.Series(False, index=IDX)
    late.iloc[-1] = True                                     # on the last day: no session left to sell at
    assert mpaths.exit_session(IDX, late) is None


def test_park_follows_the_benchmark_after_the_sale():
    leg = pd.Series(np.linspace(1, 0.5, len(IDX)), index=IDX)
    bench = pd.Series(np.linspace(1, 1.1, len(IDX)), index=IDX)
    out = mpaths.park(leg, IDX[5], bench, cost=0.01)
    assert out.iloc[:6].equals(leg.iloc[:6])
    assert out.iloc[-1] == pytest.approx(leg.iloc[5] * 0.99 * bench.iloc[-1] / bench.iloc[5])


class _Market:
    def __init__(self, closes):
        self.closes = closes


class _Prices:
    def __init__(self, closes):
        self.market = _Market(closes)

    def dkk(self, t):
        return self.market.closes[t] if t in self.market.closes else None


def test_review_and_the_proposal_study_exit_on_the_same_day(monkeypatch):
    n = 60
    idx = pd.bdate_range("2024-01-01", periods=n)
    up = 100 * 1.01 ** np.arange(n)
    falls = up.copy()
    falls[45:] = falls[44] * 0.9 ** np.arange(1, n - 44)     # breaks its 10-day average at session 45
    closes = pd.DataFrame({"UP": up, "FALL": falls, "ACWI": np.full(n, 50.0)}, index=idx)
    monkeypatch.setattr(tracked, "benchmark", lambda: "ACWI")
    start = idx[20]
    rev = propose.store._basket_path(_Prices(closes), ["UP", "FALL"], start, sma=10)
    below = mpaths.below_trend(closes["FALL"], 10)
    k = mpaths.exit_session(idx[20:], below)
    assert [e["ticker"] for e in rev["exits"]] == ["FALL"] and rev["exits"][0]["date"] == idx[20 + k].date().isoformat()
    assert idx[20 + k] == idx[46]                             # first close below at 45, sold at the next close


# ---------------- model/select.capped ----------------

def _row(ticker, sector, group="us"):
    from types import SimpleNamespace
    return SimpleNamespace(ticker=ticker, sector=sector, group=group)


def test_capped_keeps_the_best_under_the_caps():
    from radar.model.select import capped

    rows = [_row("A", "Tech"), _row("B", "Tech"), _row("C", "Tech", "eu"), _row("D", "Energy"), _row("E", "", "eu"),
            _row("F", "", "eu")]
    assert [r.ticker for r in capped(rows, 4, 2, None)] == ["A", "B", "D", "E"]      # a third Tech name waits
    assert [r.ticker for r in capped(rows, 6, None, 2)] == ["A", "B", "C", "E"]      # two per group
    assert [r.ticker for r in capped(rows, 3, 1, None)] == ["A", "D", "E"]           # an unknown sector is its own
    assert [r.ticker for r in capped(rows, 2, 0, 0)] == ["A", "B"]                   # 0 / None: no cap, n still counts
