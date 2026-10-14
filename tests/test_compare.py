"""Several tickers side by side (profile.compare / `radar info A B`): ACWI as the benchmark candidate,
personal data left out unless asked for, unknown tickers as error entries."""
import json

import pytest
from typer.testing import CliRunner

import world
from radar import cli, ingest, profile


@pytest.fixture
def env(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers: {})       # Yahoo knows nothing new


def _row(c, label):
    return next(r for r in c["table"] if r["metric"] == label)


def test_side_by_side_with_acwi(env):
    c = profile.compare(["s1", "S2", "S1"])                                 # upper-cased, de-duplicated
    assert list(c["tickers"]) == ["S1", "S2"] and c["benchmark"]["symbol"] == "ACWI"
    r3 = _row(c, "Return 3m")
    assert set(r3["values"]) == {"S1", "S2", "ACWI"} and r3["best"] == "S1"
    assert r3["values"]["S1"] == pytest.approx(1.0012 ** 63 - 1)
    assert _row(c, "Momentum score (region)")["best"] == "S1"
    assert _row(c, "RSI 14")["best"] is None                                # context only, no "better" direction
    assert c["correlation"]["symbols"] == ["S1", "S2", "ACWI"]
    json.dumps(c)                                                            # no NaN, no numpy types


def test_personal_data_is_left_out_by_default(env):
    c = profile.compare(["S1", "S2"])
    s1 = c["tickers"]["S1"]
    assert c["personal_included"] is False and "mine" not in c
    assert s1["identity"]["my_status"] is None and s1["identity"]["my_position"] is None
    assert "since entry" not in json.dumps(s1["levels"])                     # stop not anchored on his buy date
    p = profile.compare(["S1", "S2"], personal=True)
    assert p["tickers"]["S1"]["identity"]["my_status"] == "holding" and p["mine"]["S1"]["since_buy"] is not None


def test_unknown_ticker_is_an_error_entry(env):
    c = profile.compare(["S1", "NOPE"])
    assert "error" in c["tickers"]["NOPE"] and "NOPE" not in _row(c, "Return 3m")["values"]


def test_cli_single_ticker_output_is_unchanged_and_several_write_a_file(env, tmp_path):
    one = json.loads(CliRunner().invoke(cli.app, ["info", "S1"]).output)
    assert one["ticker"] == "S1" and one["my_status"] == "holding" and "identity" in one   # the /research contract
    out = tmp_path / "exports" / "cmp.json"
    res = CliRunner().invoke(cli.app, ["info", "S1", "S2", "--out", str(out)])
    assert res.exit_code == 0 and "Wrote" in res.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["personal_included"] is False and set(data["tickers"]) == {"S1", "S2"}


def test_pe_basis_is_explicit_and_acwi_has_no_self_regression_noise(env, monkeypatch):
    from radar import external
    raw = {"fetched": "2026-10-13T00:00:00", "info": {"quoteType": "EQUITY", "currency": "USD"},
           "eps_trend": {}, "eps_revisions": {}, "growth_estimates": {}}
    monkeypatch.setattr(external, "detail", lambda *a, **k: (raw, "ok"))
    monkeypatch.setattr(external, "parse_eps_trend", lambda *a: [
        {"period": "0y", "label": "This year", "eps": 2.0, "currency": "USD"},
        {"period": "+1y", "label": "Next year", "eps": 4.0, "currency": "EUR"}])      # other currency: no ratio
    c = profile.compare(["S1", "S2"])
    last = c["tickers"]["S1"]["price"]["last"]
    assert _row(c, "P/E on this year's EPS estimate")["values"]["S1"] == pytest.approx(last / 2.0)
    assert _row(c, "P/E on next year's EPS estimate")["values"]["S1"] is None
    for w in c["benchmark"]["risk"].values():
        if w:
            assert w["alpha_t"] is None and w["beta_se"] is None and w["beta"] == 1.0
