"""The proposal rule study (backtest/propose_study.py) on the noisy synthetic world: it picks from data up to each
formation date only, repeats exactly, records the rule's settings hash (so a changed rule reads as stale), and
the exits arm equals the kept arm when nothing triggers."""
from __future__ import annotations

import pytest

from conftest import with_settings
from radar import propose
from radar.backtest import propose_study as ps
from radar.backtest import study
from test_propose import market  # noqa: F401 - the shared fixture


def _run(m, **kw):
    m.cfg["propose"]["require_trend_from"] = 2      # the small world has few uptrends: test the rest of the rule
    return ps.run(m, ["momentum"], [2], [1], with_regime=False, **kw)


def test_the_study_runs_and_repeats(market):  # noqa: F811
    a = _run(market)
    b = _run(market)
    assert a["results"] == b["results"] and a["dates"] == b["dates"]
    assert a["settings_hash"] == propose.rule_hash(market.cfg["propose"])
    picked = [d for d in a["dates"] if d["picks"].get("momentum", {}).get("2")]
    assert picked, "no formation date with a basket"
    kept = a["results"]["momentum"]["2"]["1"]["kept"]["all"]
    assert kept["dates"] >= 1 and kept["dd_median"] <= 0 and kept["effective_n"] == kept["dates"]
    assert a["us_only"] == {"momentum": False}


def test_picks_know_nothing_after_their_day(market):  # noqa: F811
    first = _run(market)
    d = next(x for x in first["dates"] if x["picks"].get("momentum", {}).get("2"))
    day = study.pd.Timestamp(d["date"])
    market.closes.loc[market.closes.index > day] *= 3.0
    again = _run(market, p=study.panels(market))
    same = next(x for x in again["dates"] if x["date"] == d["date"])
    assert same["picks"] == d["picks"]


def test_a_changed_rule_makes_the_study_stale(market, tmp_data, monkeypatch):  # noqa: F811
    rep = _run(market)
    ps.write(rep)
    got = propose.load_study()
    assert got.status == "ok" and not got.legacy
    assert got.report.rule_hash == rep["settings_hash"] and got.report.data_asof.isoformat() == rep["asof"]
    c = with_settings(monkeypatch, base=market.cfg, propose={"max_corr": 0.5})
    assert propose.load_study().status == "stale"
    assert propose.study_view(propose.load_study(), "momentum", 2, 1, None, c["propose"])["drift_gross"] is None


def test_exits_equal_kept_when_nothing_triggers(market, monkeypatch):  # noqa: F811
    with_settings(monkeypatch, base=market.cfg, propose={"require_trend_from": 2,
                                                         "exit": {"min_score": -1}},   # no signal exit can fire
                  stops={"trend_sma": 10_000})                                       # no average to fall below
    rep = ps.run(market, ["momentum"], [2], [1], with_regime=False)
    arms = rep["results"]["momentum"]["2"]["1"]
    k, x = arms["kept"]["all"], arms["exits"]["all"]
    assert x["mean"] == pytest.approx(k["mean"]) and x["exits_mean"] == 0


def test_unknown_tilt_is_refused(market):  # noqa: F811
    with pytest.raises(ValueError, match="unknown tilt"):
        ps.run(market, ["growth"], [2], [1], with_regime=False)
