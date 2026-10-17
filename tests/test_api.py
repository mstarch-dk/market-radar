"""The web API on the synthetic world: responses match their models, errors are HTTP errors."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

import world
from radar import api, api_models, dashboard, ingest, report


@pytest.fixture
def client(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers: {})   # Yahoo knows nothing new
    api.reset()
    dashboard.reset()
    return TestClient(api.app)


@pytest.fixture
def built(client):
    """The client after a `radar report` on the synthetic world."""
    report.build()
    return client


def test_profile_and_series(client):
    r = client.get("/api/ticker/s1")                                    # symbols are upper-cased
    assert r.status_code == 200
    p = api_models.Profile.model_validate(r.json())
    assert p.symbol == "S1" and p.momentum.rank == 1
    s = client.get("/api/ticker/S1/series", params={"days": 60}).json()
    assert len(s["dates"]) == 60 and len(s["close"]) == 60
    assert client.get("/api/ticker/S1/series", params={"days": 5}).status_code == 422


def test_unknown_ticker_is_404(client):
    r = client.get("/api/ticker/NOPE")
    assert r.status_code == 404 and "NOPE" in r.json()["detail"]
    assert client.get("/api/ticker/NOPE/series").status_code == 404


def test_context_lists_holdings_and_watchlist(client):
    c = client.get("/api/context").json()
    assert {(t["symbol"], t["status"]) for t in c["tickers"]} == {("S1", "holding"), ("E2", "watch")}


def test_search_puts_tracked_names_first(client, monkeypatch):
    class FakeSearch:
        def __init__(self, q, **kw):
            self.quotes = [{"symbol": "XYZ", "shortname": "Xyz Corp", "exchDisp": "NASDAQ", "quoteType": "EQUITY"},
                           {"symbol": "S1", "longname": "S One", "exchDisp": "NYSE", "quoteType": "EQUITY"},
                           {"symbol": "^IDX", "shortname": "An index", "quoteType": "INDEX"}]
    import yfinance
    monkeypatch.setattr(yfinance, "Search", FakeSearch)
    hits = client.get("/api/search", params={"q": "s"}).json()
    assert [h["symbol"] for h in hits] == ["S1", "XYZ"] and hits[0]["tracked"]


def test_openapi_schema_has_the_models(client):
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert {"Profile", "Series", "SearchHit", "AppContext", "Analyst", "Windows", "RegimeView", "RotationView",
            "MomentumView", "PositioningView", "CoverageView", "MeView", "WatchState"} <= set(schemas)


DASHBOARD = ["regime", "rotation", "momentum", "quality", "positioning", "coverage"]


@pytest.mark.parametrize("view", DASHBOARD)
def test_dashboard_views_need_a_report_first(client, view):
    r = client.get(f"/api/{view}")
    assert r.status_code == 503 and "radar run" in r.json()["detail"]


def test_dashboard_views(built):
    for view in DASHBOARD:
        r = built.get(f"/api/{view}")
        assert r.status_code == 200, (view, r.text)
        assert r.json()["asof"]
    regime = built.get("/api/regime").json()
    age = (date.today() - world.IDX[-1].date()).days                   # the world ends on the last weekday
    assert regime["overall"]["label"] == "Risk-on" and regime["age_days"] == age and regime["stale"] is False
    us = next(g for g in built.get("/api/momentum").json()["regions"] if g["key"] == "us")
    assert us["rows"][0]["ticker"] == "S1"
    assert built.get("/api/ticker/S1").json()["context"]["regime"]["label"] == "Risk-on"


def test_quality_view_profile_card_and_live_rows(built):
    qus = next(g for g in built.get("/api/quality").json()["regions"] if g["key"] == "us")
    assert qus["rows"][0]["ticker"] == "S1"
    card = api_models.Profile.model_validate(built.get("/api/ticker/S1").json()).quality
    assert card.status == "ok" and card.source == "Yahoo statements" and card.fund_set == "standard"
    assert card.quality == qus["rows"][0]["quality"]
    assert {m.key for m in card.metrics} >= {"fcf_margin", "roic", "fcf_yield", "ebit_ev"}
    roic = next(m for m in card.metrics if m.key == "roic")
    assert roic.basis == "sector" and roic.peers == 8        # S1-S5 and E1-E3: Technology, pooled over regions
    assert built.get("/api/ticker/LEAD").json().get("quality") is None               # a fund: no card
    rows = {r["symbol"]: r for r in built.get("/api/me").json()["rows"]}
    assert rows["S1"]["quality"] == card.quality and rows["S1"]["fund_source"] == "yahoo"


def test_the_quality_view_wants_a_new_report_after_an_upgrade(built, monkeypatch):
    d = dict(dashboard.load())
    d.pop("quality")
    monkeypatch.setattr(api, "_dashboard", lambda: d)
    r = built.get("/api/quality")
    assert r.status_code == 503 and "older version" in r.json()["detail"]


def test_me_is_live(built):
    rows = {r["symbol"]: r for r in built.get("/api/me").json()["rows"]}
    assert rows["S1"]["status"] == "holding" and rows["S1"]["since_buy"] is not None
    g = rows["S1"]["gauges"]
    assert g["rsi14"]["label"] == "extremely overbought" and g["excess_vs_acwi"]["level"] > 0   # beat its shadow ACWI
    assert "rsi14" in [w["key"] for w in rows["S1"]["watchouts"]]
    assert rows["E2"]["status"] == "watch" and "S3" not in rows
    assert built.put("/api/watchlist/s3").json() == {"symbol": "S3", "my_status": "watch"}
    rows = {r["symbol"]: r for r in built.get("/api/me").json()["rows"]}
    assert rows["S3"]["status"] == "watch" and rows["S3"]["score"] is not None


def test_watchlist_add_and_remove(client):
    assert client.put("/api/watchlist/S3").json()["my_status"] == "watch"
    assert client.get("/api/ticker/S3").json()["identity"]["my_status"] == "watch"
    assert ("S3", "watch") in {(t["symbol"], t["status"]) for t in client.get("/api/context").json()["tickers"]}
    assert client.delete("/api/watchlist/S3").json() == {"symbol": "S3", "my_status": None}
    assert client.delete("/api/watchlist/E2").json()["my_status"] is None        # a Yahoo-imported watch entry
    assert {t["symbol"] for t in client.get("/api/context").json()["tickers"]} == {"S1"}


def test_watchlist_rejects_holdings_and_unknown_symbols(client):
    r = client.delete("/api/watchlist/S1")
    assert r.status_code == 409 and "holding" in r.json()["detail"]
    assert client.put("/api/watchlist/S1").json()["my_status"] == "holding"     # adding a holding changes nothing
    assert client.put("/api/watchlist/NOPE").status_code == 404


def test_old_dashboard_is_flagged_stale(built, monkeypatch):
    import datetime as dt

    class Later(dt.date):
        @classmethod
        def today(cls):
            return dt.date.today() + dt.timedelta(days=30)
    monkeypatch.setattr(api, "date", Later)
    r = built.get("/api/momentum").json()
    assert r["age_days"] >= 30 and r["stale"] is True


def test_regime_vote_switches(client):
    """Valuation stretched in the world's market data: off by default, two more risk-off votes when switched on,
    at once in /api/regime and in summary.json from the next report."""
    import pandas as pd

    from radar import valuation

    months = pd.date_range(end=world.IDX[-1], periods=440, freq="MS")     # fresh as of the world's last day
    valuation._market_merge({"cape": pd.Series(range(10, 450), index=months, dtype=float)})      # last = highest
    valuation._market_merge({"erp": pd.Series([0.08 - i * 0.0001 for i in range(440)], index=months)})  # last = lowest
    report.build()
    before = client.get("/api/regime").json()
    assert {v["group"]: v["on"] for v in before["votes"]} == {"credit_eu": True, "valuation": False}
    rows = {i["name"].split(" (")[0]: i for i in before["indicators"]}
    assert rows["Valuation"]["status"] == "risk-off" and not rows["Valuation"]["votes"]

    r = client.put("/api/settings/regime-votes", json={"votes": {"valuation": True}})
    assert r.status_code == 200 and {v["group"]: v["on"] for v in r.json()}["valuation"] is True
    after = client.get("/api/regime").json()
    assert after["overall"]["off"] == before["overall"]["off"] + 2 and after["overall"]["not_voting"] == 3  # the 3 context rows
    api_models.RegimeView(**after)

    # before the next report, every reader already counts the switch: the start page, a profile, and what a
    # proposal reads (the file, not summary.json, which still has the old vote)
    from radar.model import inputs
    now = {k: after["overall"][k] for k in ("label", "net")}
    assert now["net"] != before["overall"]["net"]
    assert {k: client.get("/api/context").json()["regime"][k] for k in now} == now
    assert {k: client.get("/api/ticker/S1").json()["context"]["regime"][k] for k in now} == now
    assert {k: inputs.current_regime()[k] for k in now} == now

    import json
    out = report.build()
    summary = json.loads((report.REPORTS / "summary.json").read_text(encoding="utf-8"))
    assert "valuation" in summary["regime"]["voting_groups"] and summary["regime"]["off"] == after["overall"]["off"]
    assert out["regime"] == after["overall"]["label"]
    assert client.put("/api/settings/regime-votes", json={"votes": {"crypto": True}}).status_code == 422
