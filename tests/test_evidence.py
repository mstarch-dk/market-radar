"""The Evidence page (evidence.py): the study cards from the reports, never mixing a stale report with current
numbers, a t next to every mean, and the forward scoreboard, where a record too young to judge is labelled and left
out of any mean."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

import world
from conftest import with_settings
from radar import abtest, evidence
from radar.backtest import picks
from radar.market import Market
from radar.model import artifacts as art
from radar.portfolios import performance
from world import IDX

TODAY = date(2026, 10, 25)


def _summary(ic: float, *, new: bool = True) -> dict:
    s = {"dates": 40, "ic_mean": ic, "ic_t": 2.4, "ic_pos": 0.6, "q": [-0.01, 0, 0, 0.005, 0.01], "monotone": True,
         "spread": 0.02, "spread_t": 2.1, "top_excess": 0.01, "top_excess_t": 1.7, "top_dkk": 0.03, "acwi_dkk": 0.02,
         "top_beats_acwi": 0.55}
    return s | ({"top_vs_acwi": 0.01, "top_vs_acwi_t": 1.2} if new else {})


def _write_score(signal: str, ic: float, rule_hash: str | None, asof: str = "2026-10-16", new: bool = True) -> None:
    sig = art.SCORE_SIGNALS[signal]
    base = signal if sig.fund else "score"
    split = {"all": _summary(ic, new=new), "in_sample": _summary(ic, new=new), "holdout": _summary(ic, new=new)}
    rep = {"generated": "2026-10-16T20:00:00", "asof": asof, "signal": signal,
           "universe": {"tickers": 50, "first": "2017-10-31", "last": "2026-09-30"},
           "settings": {"holdout_from": "2024-10-01", "n_top": 15},
           "variants": [{"key": base, "baseline": True}, {"key": "r3m"}], "variants_tried": 1,
           "results": {"6": {base: split, "r3m": split}},
           "verdicts": {"6": {"r3m": {"label": "not better", "in_sample_ic": 0.01, "holdout_ic": 0.0,
                                      "holdout_ic_t": 0.3, "holdout_diff_t": -0.5}}},
           "turnover": {base: 0.3}, "caveats": ["the universe is today's"]}
    art.write("score-study", rep, data_asof=asof, file=sig.file, rule_hash=rule_hash)


def _write_longrun() -> None:
    row = {"dates": 900, "eff_n": 150, "ic_mean": 0.06, "ic_t": 4.0, "spread": 0.01, "spread_t": 3.0,
           "top_excess": 0.004, "top_excess_t": 2.5, "top_vs_market": 0.005, "top_vs_market_t": 2.2}
    panel = {"label": "US industries", "members": 49, "n_top": 10, "months": 1100, "first": "1927-07-31",
             "last": "2026-08-31", "variants": [{"key": "score", "baseline": True}], "variants_tried": 0,
             "results": {"6": {"score": {"all": row, "holdout": row, "by_decade": {"1990s": row},
                                         "by_recession": {"recession": row}}}}}
    art.write("longrun-study", {"generated": "2026-10-16T20:00:00", "datasets_asof": {"french:ind49": "2026-08"},
                                "panels": {"french49": panel}, "errors": {"countries": "no JKP data yet"},
                                "base_rates": {"Momentum, US": {"ann_return": 0.06, "t": 3.1}}},
              data_asof="2026-08-31", rule_hash=art.study_rule_hash("longrun-study"))


def _current(signal: str) -> str:
    return art.study_rule_hash("score-study", signal)


def test_evidence_missing_reports(tmp_data):
    page = evidence.build(None, TODAY)
    assert [c["head"]["signal"] for c in page["scores"]] == ["momentum", "quality", "value", "qv"]
    for c in page["scores"]:
        assert c["head"]["status"] == "missing" and c["head"]["command"] in c["head"]["reason"]
        assert c["horizons"] == [] and c["verdicts"] == [] and c["turnover"] is None and c["universe"] is None
    assert page["scores"][1]["head"]["command"] == "radar study score --signal quality"
    assert page["longrun"]["head"]["status"] == "missing" and page["longrun"]["panels"] == []
    assert [h["status"] for h in page["rules"]] == ["missing"] * 3
    assert page["forward"] is None and "radar run" in page["notes"][0]


def test_evidence_stale_not_mixed(tmp_data):
    _write_score("momentum", 0.777, rule_hash="0ldru1e00000")
    _write_score("quality", 0.05, rule_hash=_current("quality"))
    page = evidence.build(None, TODAY)
    mom, qual = page["scores"][0], page["scores"][1]
    assert mom["head"]["status"] == "stale" and "another rule" in mom["head"]["reason"]
    assert mom["head"]["rule_hash"] == "0ldru1e00000" and mom["head"]["rule_hash_now"] == _current("momentum")
    assert mom["horizons"][0]["all"]["ic_mean"] == 0.777                # shown inside its own (greyed) card
    assert qual["head"]["status"] == "ok" and qual["horizons"][0]["all"]["ic_mean"] == 0.05
    rest = json.dumps({k: v for k, v in page.items() if k != "scores"} | {"others": page["scores"][1:]})
    assert "0.777" not in rest                                          # nowhere outside the stale card


def test_unrecorded_rule_is_an_older_rule(tmp_data):
    _write_score("value", 0.04, rule_hash=None)                         # as every report before schema 2
    head = evidence.build(None, TODAY)["scores"][2]["head"]
    assert head["status"] == "stale" and head["rule_hash"] is None and "before studies recorded" in head["reason"]


def test_evidence_t_next_to_every_mean(tmp_data):
    _write_score("momentum", 0.05, rule_hash=_current("momentum"))
    _write_score("qv", 0.03, rule_hash=_current("qv"), new=False)       # an older report: no top_vs_acwi t
    _write_longrun()
    page = evidence.build(None, TODAY)
    for card in page["scores"]:
        for h in card["horizons"]:
            for row in (h["all"], h["in_sample"], h["holdout"]):
                assert row is not None and all(t in row for t in evidence.SCORE_T.values())
    assert page["scores"][0]["notes"] == []
    qv = page["scores"][3]
    assert qv["horizons"][0]["all"]["top_vs_acwi_t"] is None and any("t-statistics" in n for n in qv["notes"])
    assert qv["verdicts"] == [{"h": 6, "variant": "r3m", "label": "not better", "in_sample_ic": 0.01,
                               "holdout_ic": 0.0, "holdout_ic_t": 0.3, "holdout_diff_t": -0.5}]
    lr = page["longrun"]
    assert lr["head"]["status"] == "ok" and lr["notes"] == []
    p = lr["panels"][0]
    for row in [p["horizons"][0]["all"], p["horizons"][0]["holdout"], p["by_decade"][0]["row"]]:
        assert all(row[m] is not None and row[t] is not None for m, t in evidence.LONGRUN_T.items())
    assert lr["panels"][1]["key"] == "countries" and lr["panels"][1]["error"] == "no JKP data yet"
    assert lr["base_rates"][0]["ann_return"] == 0.06 and lr["base_rates"][0]["max_dd"] is None


def test_evidence_holdout_from_settings(tmp_data, monkeypatch):
    with_settings(monkeypatch, backtest={"study_holdout_from": "2023-05-01"}, longrun={"holdout_from": "2001-01-01"})
    page = evidence.build(None, TODAY)
    assert page["holdout_from"] == "2023-05-01" and page["longrun_holdout_from"] == "2001-01-01"


def test_old_data_is_a_badge_not_staleness(tmp_data, monkeypatch):
    with_settings(monkeypatch, evidence={"max_age_days": {"score": 30, "longrun": 120, "rules": 120}})
    _write_score("momentum", 0.05, rule_hash=_current("momentum"), asof=(TODAY - timedelta(days=31)).isoformat())
    _write_score("quality", 0.05, rule_hash=_current("quality"), asof=(TODAY - timedelta(days=30)).isoformat())
    mom, qual = evidence.build(None, TODAY)["scores"][:2]
    assert mom["head"]["status"] == "ok" and mom["head"]["old_data"] and mom["head"]["age_days"] == 31
    assert not qual["head"]["old_data"]


def test_the_proposal_study_is_judged_by_its_rule(tmp_data):
    from radar.propose import rules

    art.write("propose-study", {"generated": "2026-10-16T20:00:00", "asof": "2026-10-16", "results": {}},
              data_asof="2026-10-16", rule_hash="another")
    art.write("exit-study", {"generated": "2026-10-16T20:00:00", "asof": "2026-10-16"}, data_asof="2026-10-16")
    prop, ex, rd = evidence.build(None, TODAY)["rules"]
    assert prop["status"] == "stale" and prop["rule_hash_now"] == rules.rule_hash()
    assert ex["status"] == "ok" and ex["rule_hash"] is None and ex["age_days"] == 9
    assert rd["status"] == "missing" and rd["command"] == "radar study redeploy"


# ---------------- the forward scoreboard ----------------

@pytest.fixture
def market(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    performance.reset()
    from radar.fundamentals import context as fcontext

    fcontext.reset()
    with_settings(monkeypatch, backtest={"fill": "next", "fee_bps": 10, "random_baskets": 20})
    return Market.load()


def test_forward_too_short_not_ranked(market, monkeypatch):
    picks.run(market, IDX[150].date().isoformat(), [{"ticker": "S1"}, {"ticker": "S2"}], "live-a", tags=["picks-live"])
    picks.run(market, IDX[-15].date().isoformat(), [{"ticker": "S3"}], "live-b", tags=["picks-live"])
    picks.run(market, IDX[150].date().isoformat(), [{"ticker": "S4"}], "not-live")           # no tag
    today = IDX[-1].date()
    pt = evidence.build(market, today)["forward"]["paper_trail"]
    old, new = pt["records"]
    assert [old["label"], new["label"]] == ["live-a", "live-b"]
    assert not old["too_short"] and old["excess"] == pytest.approx(old["ret"] - old["acwi"])
    assert new["too_short"] and new["ret"] is not None                  # listed with its numbers, not judged
    c = pt["cohort"]
    assert (c["count"], c["enough"], c["mean_excess"], c["beat_acwi"]) == (1, False, None, None)
    with_settings(monkeypatch, backtest={"fill": "next", "fee_bps": 10, "random_baskets": 20},
                  evidence={"cohort_min": 1})
    c = evidence.build(market, today)["forward"]["paper_trail"]["cohort"]
    assert c["enough"] and c["mean_excess"] == pytest.approx(old["excess"]) and c["beat_acwi"] == 1.0


def test_forward_missing_is_none(market):
    abtest.create(market, capital=30000, n=3)            # picked on the last session: nothing bought yet
    fwd = evidence.build(market, IDX[-1].date())["forward"]
    ab = fwd["abtest"]
    assert ab["running"] and len(ab["records"]) == 3
    for r in ab["records"]:
        assert r["ret"] is None and r["excess"] is None and r["too_short"]       # never 0
    assert "too short" in ab["note"]
    assert not fwd["proposals"]["running"] and fwd["proposals"]["records"] == []
    assert not fwd["paper_trail"]["running"] and "picks-live" in fwd["paper_trail"]["note"]
