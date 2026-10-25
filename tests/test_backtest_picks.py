"""Hindsight baskets (backtest/picks.py) on the synthetic world: candidates know nothing after their day, blind ids
resolve, caps hold, the kept basket returns what its weights say, the rule variant equals it when nothing
triggers, random baskets are repeatable, reruns replace, and none of it ever counts as yours."""

import numpy as np
import pandas as pd
import pytest

import world
from conftest import with_settings
from radar import userstore
from radar.backtest import picks, study
from radar.market import Market
from radar.model import panels as mp
from radar.portfolios import performance, simulate
from radar.userstore import viewstore
from world import IDX, N

D = 260                                     # the score needs 12-1-month momentum: about 252 bars of history


@pytest.fixture
def market(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    performance.reset()
    with_settings(monkeypatch, backtest={"fill": "next", "fee_bps": 10, "random_baskets": 200})
    return Market.load()


def day(i=D):
    return IDX[i].date().isoformat()


def test_candidates_know_nothing_after_their_day(market):
    first = picks.candidates(market, day())
    assert first["asof"] == day() and first["fill"] == day(D + 1)
    assert [c["ticker"] for c in first["candidates"][:3]] == ["S1", "S2", "E1"]       # by drift
    market.closes.loc[market.closes.index > IDX[D]] *= 3.0
    again = picks.candidates(market, day())
    assert again["candidates"] == first["candidates"]


def test_blind_hides_names_and_its_ids_resolve(market):
    blind = picks.candidates(market, day(), blind=True)
    assert all(c["ticker"] is None and c["name"] is None and "close" not in c for c in blind["candidates"])
    rep = picks.run(market, day(), [{"id": "C001"}, {"id": "C002"}], "blind test")
    assert [p["ticker"] for p in rep["picks"]] == ["S1", "S2"]
    with pytest.raises(ValueError):
        picks.run(market, day(), [{"id": "C999"}], "bad id")


def test_select_respects_caps_and_weights(market):
    df = picks.ranked(mp.panels(market), IDX[D])
    two_each = picks.select(df, 4, max_per_group=2)
    assert [p["ticker"] for p in two_each] == ["S1", "S2", "E1", "E2"]
    assert all(p["weight"] == pytest.approx(0.25) for p in two_each)
    by_score = picks.select(df, 3, weighting="score")
    assert by_score[0]["weight"] > by_score[-1]["weight"] and sum(p["weight"] for p in by_score) == pytest.approx(1)
    assert len(picks.select(df, 9, max_per_sector=2)) == 2                         # one sector in this world


def test_the_kept_basket_returns_its_weighted_return_after_fees(market):
    rep = picks.run(market, day(), [{"ticker": "S1", "weight": 3}, {"ticker": "E3", "weight": 1}], "weighted")
    g = world.G
    r = lambda t: (1 + g[t]) ** (N - 1 - (D + 1)) - 1                                 # noqa: E731
    gross = 0.75 * r("S1") + 0.25 * r("E3")
    assert rep["yardsticks"]["basket_gross_dkk"] == pytest.approx(gross)
    hold, kept = rep["portfolios"]["hold"], rep["portfolios"]["exits"]
    assert hold["return_dkk"] == pytest.approx((1 + gross) / 1.001 - 1, rel=1e-6)            # the buying fee included
    assert hold["stats"]["twr_total"] == pytest.approx(gross, rel=1e-6)          # the Returns page: from after the buy
    assert kept["return_dkk"] == pytest.approx(hold["return_dkk"])
    assert rep["exits"]["summary"]["stops"] == rep["exits"]["summary"]["take_profits"] == 0   # steady rises: no trigger
    assert not rep["same_as_control"] and "control" in rep["portfolios"]


def test_a_mechanical_basket_is_its_own_control(market):
    rep = picks.run(market, day(), None, "mech", meta={"n": 3})
    assert rep["same_as_control"] and set(rep["portfolios"]) == {"hold", "exits"}
    assert [p["ticker"] for p in rep["picks"]] == ["S1", "S2", "E1"] and rep["meta"]["basis"] == "score"
    assert rep["score_check"]["ic"] == pytest.approx(1.0)                              # drifts persist in this world


def test_random_baskets_are_repeatable(market):
    a = picks.run(market, day(), [{"ticker": "S1"}, {"ticker": "S2"}], "rnd")["yardsticks"]["random"]
    b = picks.run(market, day(), [{"ticker": "S1"}, {"ticker": "S2"}], "rnd")["yardsticks"]["random"]
    assert a == b and a["draws"] == 200
    same = 1 / 36                                    # random draws of exactly the two best names tie, counted half
    assert 100 - 100 * same * 3 < a["percentile"] < 100


def test_a_rerun_replaces_the_run_and_sims_are_never_yours(market):
    first = picks.run(market, day(), [{"ticker": "S3"}], "again", tags=["picks-live"])
    ids = {k: v["id"] for k, v in first["portfolios"].items()}
    n_rows = {k: userstore.get_portfolio(v)["n_tx"] for k, v in ids.items()}
    [hold] = simulate.picks_baskets("picks-live")
    second = picks.rerun(market, hold)
    assert {k: v["id"] for k, v in second["portfolios"].items()} == ids
    assert {k: userstore.get_portfolio(v)["n_tx"] for k, v in ids.items()} == n_rows
    for pid in ids.values():
        p = userstore.get_portfolio(pid)
        assert p["mode"] == "virtual" and p["origin"] == "sim" and "picks-live" in p["tags"]
    assert not set(ids.values()) & set(userstore.portfolio_ids())


def test_asof_specs(market):
    s = market.closes["ACWI"].dropna().index
    assert picks.resolve_asof("today", s)[0] == s[-2]
    assert picks.resolve_asof("today", s, "same")[0] == s[-1]
    assert picks.resolve_asof("3M", s)[0] == s[s <= s[-1] - pd.DateOffset(months=3)][-1]
    assert picks.resolve_asof(day(), s)[0] == IDX[D]
    with pytest.raises(ValueError):
        picks.run(market, day(N - 1), [{"ticker": "S1"}], "too late", )


def test_views_are_only_those_created_by_the_day(market):
    old = viewstore.save_view({"statement": "Tech leads", "conviction": 4, "created_at": day(100),
                               "exposures": [{"kind": "sector", "key": "Technology", "effect": 1}]})
    viewstore.save_view({"statement": "New view", "exposures": [{"kind": "sector", "key": "Technology", "effect": -1}]})
    rep = picks.candidates(market, day(), views=True)
    assert [v["id"] for v in rep["views"]] == [old]
    assert all(c["views"] is None or c["views"]["views"] == [old] for c in rep["candidates"])


def test_picks_without_a_known_name_are_refused(market):
    with pytest.raises(ValueError):
        picks.run(market, day(), [{"ticker": "NOPE"}], "x")
    with pytest.raises(ValueError):
        picks.run(market, day(), [{"ticker": "S1"}, {"ticker": "S1"}], "x")
    assert np.isclose(sum(p["weight"] for p in picks.resolve_picks([{"ticker": "S1"}, {"ticker": "S2"}],
                                                             picks.ranked(mp.panels(market), IDX[D]))), 1)


def test_the_studys_score_equals_the_rules_score(market):
    from radar.backtest import pit

    p = mp.panels(market)
    ctx = pit.Context.build(market, {"S3", "E2"})
    for i in (255, 270, N - 1):
        s = study.BY_KEY["score"].fn(p, IDX[i])
        for t in ("S3", "E2"):
            assert ctx.score(t, IDX[i]) == pytest.approx(round(float(s[t]), 1))
