"""Broker fee schedules (fees.py): the market from a symbol, the estimate (percentage, minimum, maximum, a minimum
in another currency), no estimate rather than 0 when something is missing, the presets, and the API round trip."""
import pytest
from fastapi.testclient import TestClient

import world
from radar import api, dashboard, fees, ingest, userstore
from radar.api_models import FeePreset
from world import IDX

SCHEDULE = {"markets": [{"market": "US", "pct": 0.1, "min": 29, "currency": "DKK"},
                        {"market": "DK", "pct": 0.1, "min": 29, "max": 100, "currency": "DKK"}], "fx_pct": 0.25}
USD = 7.0                                                  # DKK per USD in these tests


def _usd(amount, ccy):
    return amount / USD if ccy == "DKK" else None


@pytest.mark.parametrize("symbol, market", [("NOVO-B.CO", "DK"), ("VOLV-B.ST", "NORDIC"), ("AAPL", "US"), ("BRK-B", "US"),
                                            ("SAP.DE", "EU"), ("VUSA.L", "UK"), ("7203.T", "OTHER"), ("^GSPC", "OTHER"),
                                            ("EURUSD=X", "OTHER"), ("", "OTHER")])
def test_the_market_comes_from_the_suffix(symbol, market):
    assert fees.market_of(symbol) == market


def test_percentage_minimum_and_maximum():
    big = fees.estimate(SCHEDULE, "AAPL", 100, 300, "USD", _usd)                 # 30,000 USD × 0.1%
    assert big["fee"] == 30 and big["applied"] == "pct" and big["basis"] == "0.1% (min 29 DKK)"
    assert big["fx_fee"] == 75 and big["fx_pct"] == 0.25                        # apart, not in the fee
    small = fees.estimate(SCHEDULE, "AAPL", 1, 100, "USD", _usd)                 # 0.10 USD < 29 DKK
    assert small["fee"] == pytest.approx(29 / USD, abs=0.01) and small["applied"] == "min"
    capped = fees.estimate(SCHEDULE, "NOVO-B.CO", 1000, 500, "DKK", _usd)        # 500 DKK > max 100
    assert capped["fee"] == 100 and capped["applied"] == "max" and capped["fx_fee"] is None


def test_other_markets_fall_back_to_the_other_rule_or_give_nothing():
    assert fees.estimate(SCHEDULE, "SAP.DE", 10, 100, "EUR", _usd) is None       # no EU, no OTHER rule
    with_other = SCHEDULE | {"markets": [*SCHEDULE["markets"], {"market": "OTHER", "pct": 0.2, "currency": "EUR"}]}
    est = fees.estimate(with_other, "SAP.DE", 10, 100, "EUR", _usd)
    assert est["fee"] == 2 and est["market"] == "EU" and est["rule_market"] == "OTHER"


def test_missing_data_gives_no_estimate_never_zero():
    assert fees.estimate(None, "AAPL", 1, 100, "USD", _usd) is None
    assert fees.estimate(SCHEDULE, "AAPL", None, 100, "USD", _usd) is None
    assert fees.estimate(SCHEDULE, "AAPL", 1, 100, None, _usd) is None
    assert fees.estimate(SCHEDULE, "AAPL", 1, 100, "USD", lambda a, c: None) is None   # no rate for the minimum


def test_the_presets_are_valid_dated_and_sourced():
    ps = fees.presets()
    assert {p["id"] for p in ps} >= {"saxo-classic", "danske-online"}
    for p in ps:
        FeePreset.model_validate(p)
        assert p["source_url"].startswith("https://") and p["as_of"]
        assert {r["market"] for r in p["schedule"]["markets"]} <= set(fees.MARKETS)


# ---------------- in the app ----------------

@pytest.fixture
def client(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers, progress=None: {})
    monkeypatch.setattr(api, "_market", None)
    monkeypatch.setattr(dashboard, "_cache", None)
    return TestClient(api.app)


def _ask(client) -> dict:
    return next(p for p in client.get("/api/portfolios").json() if p["name"] == "ASK")


def test_a_schedule_is_saved_kept_by_older_clients_and_cleared_with_null(client):
    ask = _ask(client)
    r = client.put(f"/api/portfolios/{ask['id']}", json={"name": "ASK", "kind": "ask", "fee_schedule": SCHEDULE})
    assert r.status_code == 200 and r.json()["fee_schedule"]["markets"][0]["min"] == 29
    r = client.put(f"/api/portfolios/{ask['id']}", json={"name": "ASK", "kind": "ask", "note": "renamed"})
    assert r.json()["fee_schedule"]["fx_pct"] == 0.25                          # left out: kept
    r = client.put(f"/api/portfolios/{ask['id']}", json={"name": "ASK", "kind": "ask", "fee_schedule": None})
    assert r.json()["fee_schedule"] is None
    assert len(client.get("/api/portfolios/fee-presets").json()) == len(fees.presets())


def test_validate_estimates_the_fee_from_the_portfolios_schedule(client):
    ask = _ask(client)
    day = IDX[200].date().isoformat()
    trade = {"symbol": "S3", "date": day, "type": "BUY", "quantity": 10, "price": 100.0, "portfolio_id": ask["id"],
             "fx_rate": USD}
    assert client.post("/api/portfolio/validate", json=trade).json()["fee_estimate"] is None   # no schedule yet
    client.put(f"/api/portfolios/{ask['id']}", json={"name": "ASK", "kind": "ask", "fee_schedule": SCHEDULE})
    est = client.post("/api/portfolio/validate", json=trade).json()["fee_estimate"]
    assert est["currency"] == "USD" and est["market"] == "US"
    assert est["fee"] == pytest.approx(29 / USD, abs=0.01) and est["applied"] == "min"        # 1 USD < 29 DKK
    cash = {"date": day, "type": "DEPOSIT", "amount": 100, "portfolio_id": ask["id"]}
    assert client.post("/api/portfolio/validate", json=cash).json()["fee_estimate"] is None


def test_the_bundle_carries_the_schedule(tmp_data):
    pid = userstore.save_portfolio({"name": "Acct", "fee_schedule": SCHEDULE})
    assert userstore.get_portfolio(pid)["fee_schedule"] == SCHEDULE
    assert '"fx_pct": 0.25' in userstore.export_portfolios_json()


def test_runs_are_listed_for_a_simulated_portfolio(client):
    pid = userstore.save_portfolio({"name": "Sim run", "mode": "virtual", "origin": "sim", "strategy": "picks-hold"})
    day = IDX[100].date().isoformat()
    userstore.replace_sim_run(pid, {"strategy": "picks-hold", "start": day},
                              [{"date": day, "type": "DEPOSIT", "amount": 1000, "currency": "DKK"}])
    runs = client.get(f"/api/portfolios/{pid}/runs").json()
    assert [(r["strategy"], r["rows"], r["status"]) for r in runs] == [("picks-hold", 1, "ok")]
    assert client.get("/api/portfolios/9999/runs").status_code == 404
