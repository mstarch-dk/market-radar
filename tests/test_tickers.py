"""/api/tickers on the synthetic world: one compact row per tracked symbol, for hover cards."""
import pytest
from fastapi.testclient import TestClient

import world
from fakes import LOCAL
from radar import api
from radar.reporting import dashboard, report
from radar.sources import ingest


@pytest.fixture
def client(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers: {})
    api.reset()
    dashboard.reset()
    return TestClient(api.app, base_url=LOCAL)


def test_summary_rows(client):
    report.build()
    rows = {r["symbol"]: r for r in client.get("/api/tickers").json()}
    assert {"S1", "E2", "LEAD", "THEME1", "ACWI"} <= set(rows)
    s1 = rows["S1"]
    assert s1["my_status"] == "holding" and s1["kind"] == "stock" and s1["group"] == "US"
    assert s1["r3m"] == pytest.approx(1.0012 ** 63 - 1) and s1["score"] is not None
    assert len(s1["spark"]) == 27 and s1["spark"][0] == pytest.approx(100)
    assert rows["E2"]["my_status"] == "watch"
    assert rows["LEAD"]["kind"] == "etf" and rows["LEAD"]["quadrant"] == "Leading" and rows["LEAD"]["my_status"] is None


def test_without_a_dashboard_quadrants_are_missing_not_guessed(client):
    rows = {r["symbol"]: r for r in client.get("/api/tickers").json()}
    assert rows["LEAD"]["quadrant"] is None and rows["LEAD"]["last"] is not None


def test_watchlist_edits_show_at_once(client):
    client.get("/api/tickers")                                # warm the cache
    client.put("/api/watchlist/S3")
    rows = {r["symbol"]: r for r in client.get("/api/tickers").json()}
    assert rows["S3"]["my_status"] == "watch"
