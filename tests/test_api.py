"""The web API on the synthetic world: responses match their models, errors are HTTP errors."""
import pytest
from fastapi.testclient import TestClient

import world
from radar import api, api_models, ingest


@pytest.fixture
def client(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers: {})   # Yahoo knows nothing new
    monkeypatch.setattr(api, "_market", None)
    return TestClient(api.app)


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
    assert {"Profile", "Series", "SearchHit", "AppContext", "Analyst", "Windows"} <= set(schemas)
