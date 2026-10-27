"""The engine tools through the MCP client: a proposal from shortlist to frozen picks, evaluation, shadow, review and
check on the proposal tests' noisy world, against the --json commands; and the hindsight tools' child process."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from radar import cli, propose, userstore
from radar.mcp import common, engine
from test_mcp import ok, radar, refused  # noqa: F401 - radar: the synthetic world
from test_propose import ask, market  # noqa: F401 - the shared fixtures


@pytest.fixture
def world(market, ask):  # noqa: F811
    common.reset()
    return ask


def cli_json(*args: str):
    res = CliRunner().invoke(cli.app, list(args))
    assert res.exit_code == 0, (args, res.output, res.exception)
    return json.loads(res.stdout)


def test_a_proposal_from_shortlist_to_check(world):
    rep = ok("propose_candidates", portfolio="ASK", amount=30_000, tilt="momentum")
    assert rep == cli_json("propose", "candidates", "--portfolio", "ASK", "--amount", "30000", "--tilt", "momentum",
                           "--json")
    draft = rep["draft_picks"]
    frozen = ok("propose_freeze", meta=draft["meta"], picks=draft["picks"], filler=draft["filler"])
    assert frozen["frozen_at"] and frozen["picks"] == [p["ticker"] for p in draft["picks"]]
    stored = json.loads((propose.PROPOSALS / f"{frozen['id']}.json").read_text(encoding="utf-8"))
    assert stored["meta"]["frozen_at"] == frozen["frozen_at"]
    again = ok("propose_freeze", meta=stored["meta"], picks=draft["picks"])     # never overwritten
    assert again["id"] != frozen["id"]

    assert not ok("propose_picks", id=frozen["id"])["evaluated"]
    ev = ok("propose_evaluate", id=frozen["id"], light=True)
    assert ev["decision"]["verdict"]
    assert propose.evaluation_file(f"{frozen['id']}.json").exists()
    got = ok("propose_picks", id=frozen["id"])
    assert got["evaluated"] and [p["ticker"] for p in got["picks"]] == frozen["picks"]
    assert all("exit" in p for p in got["picks"]) and got["meta"]["frozen_at"] == frozen["frozen_at"]
    assert "evaluation" not in got
    assert ok("propose_picks", id=frozen["id"], with_evaluation=True)["evaluation"]["decision"] == ev["decision"]

    real_rows = len(userstore.transactions(portfolios=[world["id"]]))
    shadow = ok("propose_shadow", id=frozen["id"], name="Try")
    assert "Try" in shadow["names"].values()
    assert len(userstore.transactions(portfolios=[world["id"]])) == real_rows      # never your own portfolio

    assert ok("propose_review") == cli_json("propose", "review", "--json")
    assert ok("propose_check", portfolio="ASK") == cli_json("propose", "check", "--portfolio", "ASK", "--json")


def test_bad_picks_and_ids_are_refused(world):
    draft = ok("propose_candidates", portfolio="ASK", amount=30_000)["draft_picks"]
    twice = [draft["picks"][0], draft["picks"][0]]
    assert "picked twice" in refused("propose_freeze", meta=draft["meta"], picks=twice)
    assert "isn't a picks file" in refused("propose_freeze", meta={}, picks=draft["picks"])
    for bad in ("nope", "../x", f"{draft['meta']['date']}_ask-evaluation"):
        assert "No frozen proposal" in refused("propose_evaluate", id=bad)
    assert "No candidates" in refused("propose_candidates", portfolio="ASK", amount=10)


def test_sim_tools_run_the_cli_as_a_child(radar, monkeypatch):  # noqa: F811
    seen = []

    def fake(cmd, **kw):
        picks = cmd[cmd.index("--picks") + 1] if "--picks" in cmd else None
        seen.append((cmd, json.loads(Path(picks).read_text(encoding="utf-8")) if picks else None, kw["env"]))
        if "--rerun" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "Not simulated: no stored basket x\n")
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"name": "b", "asof": "2026-07-27"}), "")
    monkeypatch.setattr(engine.subprocess, "run", fake)

    assert ok("sim_picks_candidates", asof="3M", blind=True, top=20)["name"] == "b"
    cmd, _, env = seen[-1]
    assert cmd[3:] == ["sim", "picks-candidates", "--asof", "3M", "--top", "20", "--blind", "--json"]
    assert "--views" not in cmd and env["PYTHONIOENCODING"] == "utf-8"

    ok("sim_picks", asof="3M", name="b", picks=[{"ticker": "S1", "why": "trend"}], meta={"basis": "judgment"},
       tags=["picks-live"])
    cmd, given, _ = seen[-1]
    assert given == {"picks": [{"ticker": "S1", "why": "trend"}], "meta": {"basis": "judgment"}}
    assert cmd[cmd.index("--tag") + 1] == "picks-live" and "--rule" not in cmd

    ok("sim_picks", asof="3M", name="c", rule="top-n", n=10, trend=True)
    cmd, given, _ = seen[-1]
    assert given is None and cmd[cmd.index("--n") + 1] == "10" and "--trend" in cmd

    assert "no stored basket x" in refused("sim_picks", rerun="x")
