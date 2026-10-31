"""/scout's writes and follow-up on the synthetic world: a market view added through add_view (dry run first, origin
kept), a candidate frozen and never overwritten, its basket against ACWI by decision and stage, the hypothesis
journal entry, and the frozen tickers in the daily update."""
from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import world
from conftest import with_settings
from radar import cli, evidence, notebook, scout, universe
from radar.market import Market
from radar.mcp import common
from radar.reporting import dashboard
from radar.sources import ingest
from radar.userstore import viewstore
from test_mcp import ok, refused
from world import IDX

VIEW = {"statement": "Small reactors get built", "conviction": 2, "horizon": "12m",
        "falsifier": "No new licence within a year", "exposures": [{"kind": "etf", "key": "THEME1", "effect": 1}],
        "indicators": [{"indicator": "semis", "expect": "up"}], "origin": "scout:2026-10-31:nuclear-smr"}
CANDIDATE = {"slug": "nuclear-smr", "statement": "Small reactors get built", "stage": "whisper",
             "decision": "adopted", "horizon": "6m", "proxies": ["THEME1"], "stocks": ["s1", "S2"]}


@pytest.fixture
def radar(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers: {})   # Yahoo knows nothing new
    common.reset()
    dashboard.reset()
    return tmp_data


def test_add_view_saves_only_when_confirmed_and_keeps_its_origin(radar):
    draft = ok("add_view", **VIEW)
    assert not draft["saved"] and not draft["blocked"] and draft["issues"] == []
    assert draft["view"]["origin"] == VIEW["origin"] and draft["evidence"]["items"][0]["indicator"] == "semis"
    assert viewstore.views() == []
    saved = ok("add_view", **VIEW, confirm=True)
    assert saved["saved"] and saved["view"]["origin"] == VIEW["origin"] and saved["view"]["status"] == "active"

    again = ok("add_view", **VIEW)                                  # the same candidate twice: blocked
    assert again["blocked"] and "already adopted" in again["issues"][0]["message"]
    assert "already adopted" in refused("add_view", **VIEW, confirm=True)
    assert len(viewstore.views()) == 1

    v = viewstore.get_view(saved["id"])                             # the app's edit sends no origin: it stays
    viewstore.save_view({**v, "origin": None, "statement": "Reactors, edited"}, saved["id"])
    assert viewstore.get_view(saved["id"])["origin"] == VIEW["origin"]

    other = ok("add_view", statement="Reactors stall", exposures=[{"kind": "etf", "key": "theme1", "effect": -1}])
    assert other["issues"][0]["level"] == "warning" and "Contradicts" in other["issues"][0]["message"]


def test_add_view_refuses_what_the_app_would(radar):
    assert "exposure" in refused("add_view", statement="x", exposures=[{"kind": "country", "key": "DK", "effect": 1}])
    assert "exposure" in refused("add_view", statement="x", exposures=[{"kind": "etf", "key": "SMH", "effect": 2}])
    assert "Horizon" in refused("add_view", statement="x", horizon="5y")
    assert "Unknown indicator" in refused("add_view", statement="x", indicators=[{"indicator": "vibes", "expect": "up"}])
    assert "origin" in refused("add_view", statement="x", origin="somewhere")
    assert "statement" in refused("add_view", statement="  ")


def test_scout_freeze_is_never_overwritten_and_checks_its_tickers(radar):
    first = ok("scout_freeze", **CANDIDATE, view_id=1, reason="Licences are coming")
    assert first["stocks"] == ["S1", "S2"] and first["frozen_at"] and first["reason"] == "Licences are coming"
    second = ok("scout_freeze", **(CANDIDATE | {"decision": "watch"}))
    assert second["id"] == first["id"] + "-2"
    assert json.loads((scout.RECORDS / f"{first['id']}.json").read_text(encoding="utf-8"))["decision"] == "adopted"
    assert [r["id"] for r in scout.records()] == [first["id"], second["id"]]
    assert scout.symbols() == {"THEME1", "S1", "S2"}
    assert "no Yahoo prices for NOPE" in refused("scout_freeze", **(CANDIDATE | {"stocks": ["NOPE"]}))
    assert "view_id" in refused("scout_freeze", **(CANDIDATE | {"decision": "dismissed"}), view_id=3)
    assert "stage" in refused("scout_freeze", **(CANDIDATE | {"stage": "hype"}))
    assert "proxy" in refused("scout_freeze", **(CANDIDATE | {"proxies": [], "stocks": []}))
    assert len(scout.records()) == 2


def test_frozen_tickers_are_in_the_daily_update(radar):
    scout.freeze(CANDIDATE | {"stocks": ["NEWCO.ST"]})
    assert {"THEME1", "NEWCO.ST"} <= set(universe.all_price_tickers(offline=True))


def test_scout_review_by_decision_and_stage(radar, monkeypatch):
    m = Market.load()
    old = IDX[150].date()
    scout.freeze(CANDIDATE, today=old)
    scout.freeze(CANDIDATE | {"slug": "ai-bubble", "stage": "consensus", "decision": "dismissed",
                              "proxies": [], "stocks": ["S6", "GONE"]}, today=old)
    scout.freeze(CANDIDATE | {"slug": "fresh"}, today=IDX[-1].date())         # shown today: no prices since
    (scout.RECORDS / "broken.json").write_text("{", encoding="utf-8")
    rv = evidence.scout_review(m)
    rows = {r.get("slug") or r["id"]: r for r in rv["candidates"]}
    adopted, dismissed = rows["nuclear-smr"], rows["ai-bubble"]
    assert adopted["basket"] == ["THEME1"] and adopted["excess"] == pytest.approx(adopted["ret"] - adopted["acwi"])
    assert adopted["excess"] > 0 and adopted["stocks_excess"] > adopted["excess"]   # S1, S2 grow faster than THEME1
    assert dismissed["basket"] == ["S6", "GONE"] and dismissed["missing"] == ["GONE"] and dismissed["excess"] < 0
    assert rows["fresh"]["note"] == "no prices since yet" and rows["fresh"].get("excess") is None   # never 0
    assert "can't be read" in rows["broken"]["note"]
    by = {g["decision"]: g for g in rv["by_decision"]}
    assert (by["adopted"]["count"], by["adopted"]["enough"], by["adopted"]["mean_excess"]) == (1, False, None)

    with_settings(monkeypatch, evidence={"scout_min": 1})
    rv = evidence.scout_review(m)
    by = {g["decision"]: g for g in rv["by_decision"]}
    stage = {g["stage"]: g for g in rv["by_stage"]}
    assert by["adopted"]["mean_excess"] == pytest.approx(adopted["excess"]) and by["adopted"]["beat_acwi"] == 1.0
    assert by["watch"]["count"] == 0 and by["watch"]["mean_excess"] is None
    assert stage["consensus"]["mean_excess"] == pytest.approx(dismissed["excess"])
    fwd = evidence.build(m, IDX[-1].date())["forward"]["scout"]
    assert fwd["running"] and len(fwd["records"]) == 4
    labels = [r["label"] for r in fwd["records"]]
    assert "nuclear-smr · adopted · whisper" in labels and "broken · ? · ?" in labels   # an unreadable one is listed


def test_the_cli_shows_the_same_review(radar):
    scout.freeze(CANDIDATE, today=IDX[150].date())
    res = CliRunner().invoke(cli.app, ["scout", "review", "--json"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout)["candidates"] == ok("scout_review")["candidates"]
    res = CliRunner().invoke(cli.app, ["scout", "review"])
    assert res.exit_code == 0 and "nuclear-smr" in res.output and "Decision: adopted n=1 of 6" in res.output


def test_no_candidates_yet(radar):
    fwd = evidence.build(Market.load(), IDX[-1].date())["forward"]["scout"]
    assert not fwd["running"] and fwd["records"] == [] and "/scout" in fwd["note"]
    assert ok("scout_review")["candidates"] == []


def test_a_hypothesis_journal_entry_has_no_ticker(radar):
    f = notebook.FOLDERS["journal"] / "2026-10-31-scout.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("---\ndate: 2026-10-31\ntype: hypothesis\naction: scout\nstatus: open\nreview_by: 2027-04-30\n"
                 "views: [3]\n---\n# Scout-beslutninger\n", encoding="utf-8")
    (notebook.FOLDERS["scout"]).mkdir(parents=True, exist_ok=True)
    (notebook.FOLDERS["scout"] / "2026-10-31.md").write_text("# Scout – 2026-10-31\n", encoding="utf-8")
    entry = ok("journal_entries", status="open")["entries"][0]
    assert entry["ticker"] is None and entry["meta"]["type"] == "hypothesis" and entry["meta"]["views"] == [3]
    assert not entry["problem"]
    assert ok("documents", kind="scout")["scout"][0]["title"] == "Scout – 2026-10-31"
