"""The portfolio X-ray (xray.py) on the noisy synthetic world: the same exposure and risk as a proposal for the same
holdings, unvalued positions left out of every weight, the coverage rules for risk, and cash only where a ledger
says what it is."""
from __future__ import annotations

import pytest

from conftest import with_settings
from radar import paths, propose, userstore, xray
from radar.portfolios import performance
from radar.portfolios.exposure import DIMS
from test_propose import _draft, ask, market  # noqa: F401 - the shared fixtures
from world import IDX


def test_xray_same_as_proposal(market, ask):  # noqa: F811
    """For the same holdings the X-ray and a proposal's "before" agree exactly: the exposure, and every risk figure,
    since each set of holdings is modelled on its own covariance (riskmodel.book_risk), never on one shared with
    the proposal's candidates."""
    with paths.TRANSACTIONS_FILE.open("a", encoding="utf-8") as f:                 # the world's holdings: its CSV
        f.write(f"S3,{IDX[150].date()},BUY,40,{market.closes['S3'].iloc[150]}\n")
    xr = xray.build(market, [ask["id"]])
    ev = propose.evaluate(market, _draft(market, ask)["draft_picks"], offline=True, light=True)
    before = ev["exposure"]["before"]
    for d in DIMS:
        assert {r["key"]: r["weight"] for r in xr["exposure"][d]["rows"] if r["weight"]} == pytest.approx(
            before["weights"][d])
        assert xr["exposure"][d]["coverage"] == before["coverage"][d]
    rb = ev["risk"]["before"]
    for k in ("vol_ann", "beta", "te_ann", "div_ratio", "coverage"):
        assert xr["risk"][k] == pytest.approx(rb[k], rel=1e-12), k
    assert {p["symbol"]: p["share_total"] for p in xr["risk"]["positions"]} == pytest.approx(rb["contributions"])
    assert {p["symbol"] for p in xr["risk"]["positions"]} == {"S1", "S3"}
    assert sum(p["share_total"] for p in xr["risk"]["positions"]) == pytest.approx(1)
    assert 1 < xr["concentration"]["effective_n"] < 2


def test_xray_missing_price_is_unvalued(market, ask):  # noqa: F811
    with paths.TRANSACTIONS_FILE.open("a", encoding="utf-8") as f:                 # the world's holdings: its CSV
        f.write(f"GONE,{IDX[210].date()},BUY,7,50.0\n")
    xr = xray.build(market, [ask["id"]])
    assert xr["totals"]["unvalued"] == [{"symbol": "GONE", "quantity": 7.0, "reason": "no price"}]
    assert "GONE" not in {c["symbol"] for c in xr["classes"]}            # in no weight, never valued at 0
    for d in DIMS:
        assert sum(r["weight"] for r in xr["exposure"][d]["rows"]) == pytest.approx(1)
    assert xr["risk"]["coverage"] == 1 and all(p["symbol"] != "GONE" for p in xr["risk"]["positions"])
    assert any("GONE" in n for n in xr["notes"])


def test_xray_low_coverage_hides_risk(market, ask, monkeypatch):  # noqa: F811
    with_settings(monkeypatch, base=market.cfg, risk={"xray": {"min_coverage": 1.01}})
    hidden = xray.build(market, [ask["id"]])
    assert hidden["risk"] is None and any("Risk figures not shown" in n for n in hidden["notes"])
    with_settings(monkeypatch, base=market.cfg, risk={"xray": {"min_coverage": 0.0, "warn_coverage": 1.01}})
    warned = xray.build(market, [ask["id"]])
    assert warned["risk"]["warn"] is True and warned["risk"]["vol_ann"] is not None


def test_xray_cash_lines(market, ask):  # noqa: F811
    implicit = xray.build(market, [ask["id"]])
    assert implicit["totals"]["cash_dkk"] is None
    assert any("No cash ledger" in n and ask["name"] in n for n in implicit["notes"])
    userstore.add_tx({"date": IDX[150].date().isoformat(), "type": "DEPOSIT", "amount": 1_000_000.0,
                      "portfolio_id": ask["id"]})
    ledger = xray.build(market, [ask["id"]])
    rows = userstore.transactions(portfolios=[ask["id"]])
    assert ledger["totals"]["cash_dkk"] == pytest.approx(float(performance.cash_balance(rows, market)[0].iloc[-1]))
    assert 0 < ledger["totals"]["cash_dkk"] < 1_000_000
    assert not any("No cash ledger" in n for n in ledger["notes"])


def test_xray_of_nothing_is_a_view_with_a_note(market):  # noqa: F811
    xr = xray.build(market, [])
    assert xr["risk"] is None and xr["classes"] == [] and xr["totals"]["invested_dkk"] == 0
    assert any("No valued holdings" in n for n in xr["notes"])
