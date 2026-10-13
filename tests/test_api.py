"""The web API on the synthetic world: responses match their models, errors are HTTP errors."""
import pytest
from fastapi.testclient import TestClient

import world
from radar import api, api_models, dashboard, ingest, report


@pytest.fixture
def client(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers: {})   # Yahoo knows nothing new
    monkeypatch.setattr(api, "_market", None)
    monkeypatch.setattr(dashboard, "_cache", None)
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


DASHBOARD = ["regime", "rotation", "momentum", "positioning", "coverage"]


@pytest.mark.parametrize("view", DASHBOARD)
def test_dashboard_views_need_a_report_first(client, view):
    r = client.get(f"/api/{view}")
    assert r.status_code == 503 and "radar run" in r.json()["detail"]


def test_dashboard_views(built):
    for view in DASHBOARD:
        r = built.get(f"/api/{view}")
        assert r.status_code == 200, (view, r.text)
        assert r.json()["asof"]
    assert built.get("/api/regime").json()["overall"]["label"] == "Risk-on"
    us = next(g for g in built.get("/api/momentum").json()["regions"] if g["key"] == "us")
    assert us["rows"][0]["ticker"] == "S1"
    assert built.get("/api/ticker/S1").json()["context"]["regime"]["label"] == "Risk-on"


def test_me_is_live(built):
    rows = {r["symbol"]: r for r in built.get("/api/me").json()["rows"]}
    assert rows["S1"]["status"] == "holding" and rows["S1"]["since_buy"] is not None
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
