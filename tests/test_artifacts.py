"""The study reports production reads (model/artifacts.py): one loader that says ok, stale, missing or invalid,
never a silent fallback; writers that stamp the header and can't write a report that breaks its contract; and
reports from before the header read as schema version 0."""
from __future__ import annotations

import json

import pytest

from radar.model import artifacts as art


def _propose(**kw) -> dict:
    kept = {"all": {"dates": 40, "gross_mean": 0.1, "mean": 0.09, "t": 3.0, "median": 0.05},
            "by_regime": {"Risk-on": {"dates": 30, "gross_mean": 0.2}}}
    return {"generated": "2026-10-16T20:49:11", "asof": "2026-10-16", "settings_hash": "abc",
            "universe": {"first": "2017-10-31", "last": "2026-09-30"}, "us_only": {"momentum": False},
            "results": {"momentum": {"5": {"6": {"kept": kept, "exits": kept}}}}, "dates": [{"date": "x"}]} | kw


def test_missing_says_what_to_run(tmp_data):
    got = art.load("propose-study")
    assert got.status == "missing" and got.report is None and not got.ok
    assert "radar study propose" in got.reason


def test_written_report_loads_with_its_header(tmp_data):
    written = art.write("propose-study", _propose(), data_asof="2026-10-16", rule_hash="abc")
    raw = json.loads(art.path("propose-study").read_text(encoding="utf-8"))
    assert list(raw)[:5] == list(art.HEADER)
    assert raw["schema_version"] == art.SCHEMA_VERSION and raw["created"] == "2026-10-16T20:49:11"
    got = art.load("propose-study", rule_hash="abc")
    assert got.ok and not got.legacy and got.report == written              # the writer gets what a reader gets
    rep = got.report
    assert isinstance(rep, art.ProposeStudy) and rep.data_asof.isoformat() == "2026-10-16"
    cell = rep.results["momentum"]["5"]["6"]
    assert cell.kept.all.gross_mean == 0.1 and cell.kept.by_regime["Risk-on"].dates == 30
    assert cell.kept.all.model_dump(exclude_unset=True)["median"] == 0.05     # the rest is kept as it is
    assert rep.model_extra["dates"] == [{"date": "x"}]


def test_a_missing_number_is_written_as_null_not_nan(tmp_data):
    """NaN isn't JSON, and a reader's `is None` check lets it through into the arithmetic (propose's drift)."""
    rep = _propose()
    rep["results"]["momentum"]["5"]["6"]["kept"]["all"]["gross_mean"] = float("nan")
    art.write("propose-study", rep, data_asof="2026-10-16", rule_hash="abc")
    assert "NaN" not in art.path("propose-study").read_text(encoding="utf-8")

    assert art.load("propose-study").report.results["momentum"]["5"]["6"].kept.all.gross_mean is None


def test_another_rule_is_stale_with_its_numbers(tmp_data):
    art.write("propose-study", _propose(), data_asof="2026-10-16", rule_hash="abc")
    got = art.load("propose-study", rule_hash="other")
    assert got.status == "stale" and got.report is not None and "radar study propose" in got.reason
    assert art.load("propose-study").ok                                  # no rule to compare: as written


def test_legacy_report_reads_as_version_0(tmp_data):
    art.path("propose-study").parent.mkdir(parents=True, exist_ok=True)
    art.path("propose-study").write_text(json.dumps(_propose()), encoding="utf-8")
    got = art.load("propose-study", rule_hash="abc")
    assert got.ok and got.legacy and got.report.schema_version == 0
    assert got.report.rule_hash == "abc" and str(got.report.created) == "2026-10-16 20:49:11"
    lr = {"generated": "2026-10-16T19:59:44", "data_asof": {"a": "2026-08", "b": "2025-12"},
          "survivorship": {"implied_haircut": 0.55}}
    art.path("longrun-study").write_text(json.dumps(lr), encoding="utf-8")
    got = art.load("longrun-study")
    assert got.ok and got.report.data_asof.isoformat() == "2026-08-31"
    assert got.report.survivorship.implied_haircut == 0.55


@pytest.mark.parametrize("content, why", [
    ("{not json", "can't be read"),
    ("[1, 2]", "not a report"),
    (json.dumps({"schema_version": 99, "kind": "propose-study"}), "newer Market Radar"),
    (json.dumps({"schema_version": 1, "kind": "score-study", "created": "2026-10-16T00:00:00",
                 "data_asof": None}), "holds a score-study report"),
    (json.dumps(_propose(results={"momentum": {"5": {"6": {"kept": {"all": {"gross_mean": "lots"}}}}}})),
     "results.momentum.5.6.kept.all.gross_mean"),
    (json.dumps(_propose(generated=None)), "created"),
])
def test_unreadable_reports_are_invalid_never_empty(tmp_data, content, why):
    f = art.path("propose-study")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    got = art.load("propose-study", rule_hash="abc")
    assert got.status == "invalid" and got.report is None and why in got.reason


def test_a_report_that_breaks_its_contract_is_not_written(tmp_data):
    with pytest.raises(ValueError, match="contract"):
        art.write("propose-study", _propose(), data_asof="2026-10-16", rule_hash=None)   # the rule is required
    assert not art.path("propose-study").exists()


def test_a_rewritten_report_is_read_again(tmp_data):
    art.write("propose-study", _propose(), data_asof="2026-10-16", rule_hash="abc")
    assert art.load("propose-study", rule_hash="abc").ok
    art.write("propose-study", _propose(us_only={"momentum": True, "x": False}), data_asof="2026-10-17",
              rule_hash="new")
    got = art.load("propose-study", rule_hash="new")
    assert got.ok and got.report.data_asof.isoformat() == "2026-10-17"


def test_unknown_names_are_refused():
    with pytest.raises(ValueError, match="unknown study report"):
        art.load("nope")


# ---------------- the score studies' files and the rule a study tested ----------------

def _score(signal: str = "momentum", **kw) -> dict:
    s = {"dates": 40, "ic_mean": 0.05, "ic_t": 2.5, "top_excess": 0.01, "top_excess_t": 1.8}
    return {"generated": "2026-10-16T20:49:11", "asof": "2026-10-16", "signal": signal,
            "universe": {"tickers": 50, "first": "2017-10-31", "last": "2026-09-30"},
            "results": {"6": {"score": {"all": s, "in_sample": s, "holdout": s}}}} | kw


def test_each_score_signal_loads_from_its_own_file(tmp_data):
    for sig in art.SCORE_SIGNALS.values():
        art.write("score-study", _score(sig.key), data_asof="2026-10-16", file=sig.file,
                  rule_hash=art.study_rule_hash("score-study", sig.key))
    for sig in art.SCORE_SIGNALS.values():
        got = art.score(sig.key, rule_hash=art.study_rule_hash("score-study", sig.key))
        assert got.ok and got.report.signal == sig.key                     # the cache keeps the files apart
        assert got.report.results["6"]["score"].in_sample.top_excess_t == 1.8
    assert art.load("score-study").report.signal == "momentum"            # the momentum file stays the default


def test_a_missing_fund_score_names_its_signal(tmp_data):
    got = art.score("quality")
    assert got.status == "missing" and "radar study score --signal quality" in got.reason
    assert "--signal" not in art.score("momentum").reason


def test_a_score_file_holding_another_signal_is_invalid(tmp_data):
    art.write("score-study", _score("momentum"), data_asof="2026-10-16", file="score-study-value.json")
    got = art.score("value")
    assert got.status == "invalid" and got.report is None and "holds the momentum study" in got.reason


def test_unrecorded_rule_is_stale_with_reason(tmp_data):
    art.write("score-study", _score(), data_asof="2026-10-16")              # as every report before schema 2
    got = art.score("momentum", rule_hash=art.study_rule_hash("score-study"))
    assert got.status == "stale" and got.report is not None
    assert "before studies recorded their rule" in got.reason and "radar study score" in got.reason


def test_schema_1_score_report_still_loads(tmp_data):
    raw = {"schema_version": 1, "kind": "score-study", "created": "2026-01-01T00:00:00", "data_asof": "2025-12-31",
           "rule_hash": None, "universe": {"tickers": 10},
           "results": {"1": {"score": {"all": {"dates": 12, "ic_mean": 0.03, "ic_t": 1.1}, "holdout": None}}}}
    f = art.path("score-study")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(raw), encoding="utf-8")
    got = art.score("momentum")
    al = got.report.results["1"]["score"].all
    assert got.ok and al.ic_t == 1.1 and al.top_vs_acwi_t is None and got.report.results["1"]["score"].in_sample is None


def test_study_rule_hash_moves_with_its_keys(monkeypatch):
    from conftest import with_settings

    before = {s: art.study_rule_hash("score-study", s) for s in art.SCORE_SIGNALS}
    lr = art.study_rule_hash("longrun-study")
    assert len(set(before.values())) == 4                                   # one rule per score
    with_settings(monkeypatch, backtest={"study_holdout_from": "2025-01-01"})
    moved = {s: art.study_rule_hash("score-study", s) for s in art.SCORE_SIGNALS}
    assert all(moved[s] != before[s] for s in moved) and art.study_rule_hash("longrun-study") == lr
    with_settings(monkeypatch, backtest={"study_holdout_from": "2025-01-01"},
                  fundamentals={"quality": {"min_pillars": 2}})
    assert art.study_rule_hash("score-study") == moved["momentum"]
    assert art.study_rule_hash("score-study", "quality") != moved["quality"]
    monkeypatch.setitem(art.SCORE_REVISION, "momentum", 99)
    assert art.study_rule_hash("score-study") != moved["momentum"] and art.study_rule_hash("longrun-study") != lr
    with pytest.raises(ValueError, match="no study rule hash"):
        art.study_rule_hash("exit-study")


def test_rule_keys_exist():
    from radar.config import settings

    for keys in art.RULE_KEYS.values():
        for k in keys:
            art.setting(settings(), k)                                    # raises naming the key
    with pytest.raises(KeyError, match="backtest.nope"):
        art.setting(settings(), "backtest.nope")
