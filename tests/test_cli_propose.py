"""`radar propose …` and `radar study propose` end to end on the proposal tests' noisy world: draft, freeze,
evaluate, shadow, review and check one proposal for the ASK portfolio, then the rule study; each checked for its
exit code and a line of its output."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from conftest import with_settings
from radar import cli, userstore
from test_propose import ask, market  # noqa: F401 - the shared fixtures


def run(*args: str, code: int = 0) -> str:
    res = CliRunner().invoke(cli.app, list(args))
    assert res.exit_code == code, (args, res.output, res.exception)
    return res.output


def run_json(*args: str):
    res = CliRunner().invoke(cli.app, list(args))
    assert res.exit_code == 0, (args, res.output, res.exception)
    return json.loads(res.stdout)


def test_a_proposal_from_draft_to_check(market, ask, tmp_path):  # noqa: F811
    assert "not an amount" in run("propose", "candidates", "--portfolio", "ASK", "--amount", "lots", code=2)
    rep = run_json("propose", "candidates", "--portfolio", "ASK", "--amount", "30.000", "--tilt", "momentum", "--json")
    assert rep["draft_picks"]["picks"]
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps(rep["draft_picks"]), encoding="utf-8")
    frozen = run("propose", "freeze", str(draft)).strip().splitlines()[-1]
    assert Path(frozen).exists()
    assert "Freeze the picks first" in run("propose", "evaluate", str(draft), code=1)
    out = run("propose", "evaluate", frozen, "--light")
    assert out.startswith("Verdict: ")
    real_rows = len(userstore.transactions(portfolios=[ask["id"]]))
    assert "Created: " in run("propose", "shadow", frozen, "--name", "Try")
    assert len(userstore.transactions(portfolios=[ask["id"]])) == real_rows      # never your own portfolio
    run("propose", "review")
    assert run_json("propose", "review", "--json") is not None
    run("propose", "check", "--portfolio", "ASK")
    assert run_json("propose", "check", "--json") is not None


def test_study_propose(market, monkeypatch):  # noqa: F811
    with_settings(monkeypatch, base=market.cfg, propose={"require_trend_from": 2})   # the small world has few uptrends
    out = run("study", "propose", "--tilts", "momentum", "--ns", "2", "--horizons", "1", "--no-regime")
    assert "propose-study.json" in out
