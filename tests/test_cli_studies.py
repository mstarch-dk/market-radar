"""`radar sim …` and `radar study …` run end to end: each command once, on the exit tests' market (the synthetic
world plus a crash), the score study's synthetic panels or the long-run tests' synthetic world, checked for its
exit code and a line of its report."""
from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from conftest import with_settings
from radar import cli
from radar.backtest import longrun, study
from test_backtest_exits import market  # noqa: F401 - the shared fixture
from world import IDX


def run(*args: str, code: int = 0) -> str:
    res = CliRunner().invoke(cli.app, list(args))
    assert res.exit_code == code, (args, res.output, res.exception)
    return res.output


def run_json(*args: str):
    """A command's --json output: stdout only (progress goes to stderr)."""
    res = CliRunner().invoke(cli.app, list(args))
    assert res.exit_code == 0, (args, res.output, res.exception)
    return json.loads(res.stdout)


@pytest.fixture
def quick(monkeypatch):
    """The hindsight baskets' settings as their own tests use them (next-session fills, fewer random baskets)."""
    return with_settings(monkeypatch, backtest={"fill": "next", "fee_bps": 10, "random_baskets": 200})


def test_sim_exits(market):  # noqa: F811
    out = run("sim", "exits")
    assert "vs ACWI" in out and "Report: reports/sim-exits.json" in out
    assert run_json("sim", "exits", "--json", "--variant", "rules")["portfolios"]


def test_sim_picks_candidates_and_a_basket(market, quick):  # noqa: F811
    day = IDX[260].date().isoformat()                         # the score needs ~252 bars of history first
    assert run_json("sim", "picks-candidates", "--asof", day, "--json")["candidates"]
    out = run("sim", "picks", "--asof", day, "--name", "Smoke", "--rule", "top-n", "--n", "3")
    assert "Smoke" in out
    assert "Smoke" in run("sim", "picks", "--rerun", "Smoke")                  # found by its stored name


def test_study_exits_and_redeploy(market):  # noqa: F811
    assert "Report: reports/exit-study.json" in run("study", "exits", "--n", "3", "--horizons", "1")
    assert "redeploy-study.json" in run("study", "redeploy", "--n", "3", "--horizons", "1")


def test_study_score(market, monkeypatch):  # noqa: F811
    """The real study on the score tests' synthetic panels (the world's dozen stocks are too few to rank)."""
    from test_backtest_study import noise, panels

    with_settings(monkeypatch, backtest={"study_min_names": 20, "study_holdout_from": "2021-06-01", "fill": "next"})
    real = study.run
    monkeypatch.setattr(study, "run", lambda market, hs, keys, n, *a, signal="momentum", **k:
                        real(None, hs, keys, n, with_regime=False, p=panels(noise()), signal=signal))
    out = run("study", "score", "--horizons", "1,3", "--variants", "score,r3m")
    assert "1 month(s) ahead" in out and "IC decay" in out


def test_study_longrun(monkeypatch):
    """The real study on the long-run tests' synthetic momentum world; only reading the stored histories is a
    stand-in."""
    from test_longrun import _cfg, _momentum_world, _panel

    _cfg(monkeypatch)

    def build(panels, horizons, variants, since, log):
        return {"generated": "2026-10-17T12:00:00", "datasets_asof": {"syn": "2026-01-31"},
                "settings": {"holdout_from": "1990-01-01", "horizons": horizons or [1, 3], "regime_months": 10,
                             "since": since},
                "panels": {"syn": longrun.run(_panel(_momentum_world()), horizons, variants, since, log)},
                "errors": {}, "base_rates": {}, "survivorship": None, "priors": {}, "caveats": longrun.CAVEATS}

    monkeypatch.setattr(longrun, "build", build)
    out = run("study", "longrun", "--horizons", "1", "--variants", "score,r12_1")
    assert "longrun-study.json" in out
