"""The point-in-time fundamentals panel (backtest/fund.py) and the study's other signals (backtest/study.py SIGNALS):
scores on a past day come from the facts filed by then only, match the live scoring code on the same inputs, and
the momentum study is unchanged by the registry."""
import copy

import numpy as np
import pandas as pd
import pytest

import world
from radar import profile
from radar.backtest import study
from radar.backtest.fund import FundPIT
from radar.config import settings
from radar.fundamentals import context as fcontext
from radar.fundamentals import store

LAG = 40


def edgar(rows: pd.DataFrame | None = None) -> pd.DataFrame:
    """The world's fiscal years as SEC EDGAR facts: a flow spans its year, a balance has no start, each is filed
    LAG days after the year end and known the day after (backtest.fundamentals_lag_days)."""
    y = world.statements() if rows is None else rows
    y = y[(y["fp"] == "FY") & y["ticker"].isin(world.UNIVERSE["stock_groups"]["us"]["tickers"])].copy()
    flows = ~y["item"].isin(["total_assets", "cash", "current_liabilities", "debt_current", "debt_noncurrent",
                             "equity", "shares"])
    y["source"] = "edgar"
    y["start"] = (y["end"] - pd.Timedelta(days=364)).where(flows)
    y["form"] = "10-K"
    y["filed"] = y["end"] + pd.Timedelta(days=LAG)
    y["known"] = y["filed"] + pd.Timedelta(days=1)
    y["accn"] = "0000000000-00-000000"
    return store.normalize(y)


@pytest.fixture
def market(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(fcontext, "_ctx", None)
    return profile.Market.load()


def _day(facts: pd.DataFrame) -> pd.Timestamp:
    """A session after the last fiscal year's filing, while its figures are still fresh."""
    fy = facts["filed"].max()
    return world.IDX[world.IDX.searchsorted(fy + pd.Timedelta(days=30))]


def test_scores_on_a_day_use_only_what_was_filed_by_then(market):
    e = edgar()
    day = _day(e)
    pit = FundPIT(market, edgar=e)
    before = pit.table(day)
    assert set(before["qv"].dropna().index) >= {"S1", "S2"} and before.at["S1", "qv"] > before.at["S5", "qv"]
    # a restatement filed the next day: the earlier day's scores don't move, a later day's do
    last = e[e["end"] == e["end"].max()]
    later = last[last["item"] == "revenue"].assign(value=lambda d: d["value"] * 0.2, filed=day + pd.Timedelta(days=1),
                                                    known=day + pd.Timedelta(days=2))
    pit2 = FundPIT(market, edgar=pd.concat([e, later]))
    pd.testing.assert_frame_equal(pit2.table(day), before)
    after = pit2.table(day + pd.Timedelta(days=5))
    assert after.at["S1", "rank_fcf_margin"] != pytest.approx(before.at["S1", "rank_fcf_margin"])
    assert pit.table(pit.first_known - pd.Timedelta(days=1)).empty          # before the first filing: nothing
    assert pit.table(world.IDX[0])["qv"].isna().all()                       # the latest year too old by then: missing


def test_matches_the_live_scores_on_the_same_inputs(market):
    e = edgar()
    day = _day(e)
    live = fcontext.Context(market.closes.loc[:day], market.raw_closes().loc[:day], asof=day,
                            edgar=e[e["known"] <= day], yahoo=pd.DataFrame(columns=store.COLS),
                            tickers=FundPIT(market, edgar=e).names, pit=True)
    t = FundPIT(market, edgar=e).table(day)
    for k in ("quality", "value", "qv"):
        pd.testing.assert_series_equal(t[k].dropna().sort_index(), live.scores[k].dropna().sort_index(),
                                       check_names=False)


def test_the_pit_context_ignores_todays_yahoo_snapshot(market):
    e = edgar()
    day = _day(e)
    args = (market.closes.loc[:day], market.raw_closes().loc[:day])
    kw = {"asof": day, "edgar": e[e["known"] <= day], "yahoo": pd.DataFrame(columns=store.COLS)}
    live = fcontext.Context(*args, **kw)
    pit = fcontext.Context(*args, **kw, pit=True)
    assert not any("Yahoo's used" in n for i in pit.info.values() for n in i["notes"])
    assert set(pit.info) == set(live.info)


def test_hindsight_candidates_carry_the_scores_known_then(market, monkeypatch):
    from radar.backtest import picks

    e = edgar()
    monkeypatch.setattr(store, "load_edgar", lambda: e)
    day = _day(e)
    rep = picks.candidates(market, day.date().isoformat(), fund=True)
    rows = {r["ticker"]: r for r in rep["candidates"]}
    assert rows["S1"]["qv"] == pytest.approx(FundPIT(market, edgar=e).table(day).at["S1", "qv"])
    assert rows["E1"]["qv"] is None and "qv" in rep["columns"] and rep["fund_scored"] >= 2   # US only
    assert "qv" not in picks.candidates(market, day.date().isoformat())["candidates"][0]     # only when asked


# ---------------- the study's signals, on a constructed panel ----------------

DAYS = 520
IDX = pd.bdate_range("2020-01-01", periods=DAYS)


class Stub:
    """A FundPIT stand-in whose K+V is a known function of the names' future drift."""

    def __init__(self, g: pd.Series, noise: float = 0.0):
        self.names = list(g.index)
        self.first_known = IDX[0]
        self.g, self.noise = g, noise

    def table(self, day):
        rng = np.random.default_rng(int(pd.Timestamp(day).value % 1000))
        q = self.g.rank(pct=True) * 100 + rng.normal(0, self.noise, len(self.g))
        v = (-self.g).rank(pct=True) * 100
        return pd.DataFrame({"quality": q, "value": v, "qv": (3 * q + v) / 4, "rank_roic": q, "rank_ebit_ev": v})

    def col(self, day, key):
        t = self.table(day)
        return t[key] if key in t else pd.Series(np.nan, index=t.index)


def _panels(n: int = 40):
    from test_backtest_study import panels

    g = pd.Series(np.linspace(-0.001, 0.002, n), index=[f"T{i:02d}" for i in range(n)])
    closes = pd.DataFrame({t: 100 * (1 + g[t]) ** np.arange(DAYS) for t in g.index}, index=IDX)
    p = panels(closes)
    p.fund = Stub(g)
    return p


@pytest.fixture
def cfg(monkeypatch):
    c = copy.deepcopy(settings())
    c["backtest"] |= {"study_min_names": 20, "study_holdout_from": "2021-06-01", "fill": "next"}
    monkeypatch.setattr(study, "settings", lambda: c)
    return c


def test_a_quality_signal_ranks_on_its_own_baseline(cfg):
    rep = study.run(None, (1, 3), ["quality", "value", "magic", "momentum"], 5, with_regime=False, p=_panels(),
                    signal="quality")
    assert rep["signal"] == "quality" and [v["key"] for v in rep["variants"]][0] == "quality"
    assert rep["results"]["1"]["quality"]["all"]["ic_mean"] == pytest.approx(1.0)       # quality = the future drift
    assert rep["results"]["1"]["value"]["all"]["ic_mean"] == pytest.approx(-1.0)
    assert rep["momentum_corr"]["mean"] == pytest.approx(1.0)       # constant drifts: momentum ranks the same way
    assert set(rep["verdicts"]["1"]) == {"value", "magic", "momentum"}
    assert rep["caveats"][0].startswith("US only")


def test_the_report_file_follows_the_signal(cfg, tmp_path, monkeypatch):
    monkeypatch.setattr(study, "REPORTS", tmp_path)
    study.write(study.run(None, (1,), None, 5, with_regime=False, p=_panels(), signal="qv"))
    study.write(study.run(None, (1,), ["score", "r3m"], 5, with_regime=False, p=_panels()))
    assert sorted(f.name for f in tmp_path.iterdir()) == ["score-study-qv.json", "score-study.json"]


def test_momentum_is_unchanged_and_bad_signals_are_refused(cfg):
    p = _panels()
    a = study.run(None, (1, 3), ["score", "r3m", "r1m"], 5, with_regime=False, p=p)
    b = study.run(None, (1, 3), ["score", "r3m", "r1m"], 5, with_regime=False, p=p, signal="momentum")
    assert a["results"] == b["results"] and a["caveats"] == study.CAVEATS and "momentum_corr" not in a
    with pytest.raises(ValueError, match="unknown signal"):
        study.run(None, (1,), None, 5, with_regime=False, p=p, signal="growth")
    with pytest.raises(ValueError, match="momentum score only"):
        study.run(None, (1,), None, 5, with_regime=False, p=p, signal="qv", exits=3)
    with pytest.raises(ValueError, match="unknown variant"):
        study.run(None, (1,), ["score"], 5, with_regime=False, p=p, signal="qv")
