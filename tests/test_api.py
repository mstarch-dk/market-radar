"""The web API on the synthetic world: responses match their models, errors are HTTP errors."""
from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import world
from fakes import LOCAL
from radar import api, api_models, paths
from radar.reporting import dashboard, report
from radar.sources import ingest


@pytest.fixture
def client(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers: {})   # Yahoo knows nothing new
    api.reset()
    dashboard.reset()
    return TestClient(api.app, base_url=LOCAL)


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
    assert r.status_code == 404 and "NOPE" in r.json()["detail"]["message"]
    assert client.get("/api/ticker/NOPE/series").status_code == 404


def test_every_error_has_one_shape(client):
    for r, status in ((client.get("/api/ticker/NOPE"), 404),                        # the domain's NotFound
                      (client.get("/api/ops/jobs/999999"), 404),                     # an HTTPException
                      (client.get("/api/ops/jobs", params={"limit": 0}), 422),      # a request off its model
                      (client.get("/api/no-such-route"), 404)):
        d = r.json()["detail"]
        assert r.status_code == status and set(d) >= {"message", "issues"} and d["message"], r.json()
    bad = client.get("/api/ops/jobs", params={"limit": 0}).json()["detail"]
    assert bad["message"].startswith("query.limit:") and bad["issues"][0]["field"] == "query.limit"


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
    assert r.status_code == 503 and "radar run" in r.json()["detail"]["message"]


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
    monkeypatch.setattr(dashboard, "load", lambda: d)
    r = built.get("/api/quality")
    assert r.status_code == 503 and "older version" in r.json()["detail"]["message"]


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


def test_xray_api_contract(client, monkeypatch):
    """GET /api/xray validates against XrayView (`class` on the wire), an empty selection is a view with a note, the
    router came last (the others keep their OpenAPI order), and no prices at all is 503."""
    r = client.get("/api/xray")
    assert r.status_code == 200, r.json()
    v = api_models.XrayView.model_validate(r.json())
    assert v.selection.names and {c.symbol for c in v.classes} == {"S1"} and r.json()["classes"][0]["class"] == "stock"
    assert client.get("/api/xray").json()["generated"] == r.json()["generated"]           # cached until data changes
    empty = client.get("/api/xray", params={"tag": "no-such-tag"})
    assert empty.status_code == 200 and api_models.XrayView.model_validate(empty.json()).classes == []
    assert "No valued holdings in this selection" in empty.json()["notes"]
    assert client.get("/api/xray", params={"scope": "nope"}).status_code == 422
    paths_ = [p for p in client.get("/openapi.json").json()["paths"] if p.startswith("/api/")]
    at = paths_.index("/api/xray")                                         # each new router after the last one
    assert paths_[at:at + 4] == ["/api/xray", "/api/calendar", "/api/evidence", "/api/attribution"]
    at = paths_.index("/api/studies/run")
    assert paths_[at:at + 2] == ["/api/studies/run", "/api/studies/run/{key}"]
    assert paths_[-1] == "/api/rules/replay"                             # newest last
    monkeypatch.setattr(ingest, "load_prices", lambda: pd.DataFrame(columns=ingest.COLUMNS))
    api.reset()
    gone = client.get("/api/xray")
    assert gone.status_code == 503 and "radar update" in gone.json()["detail"]["message"]


def test_calendar_api_contract(built, monkeypatch):
    """GET /api/calendar validates against AgendaView: S1's report is high (held, soon, estimate cut, the whole
    portfolio), E2's window is info; an empty selection is a view with a note; the router came last; no prices is
    503."""
    from world import IDX

    world.calendar_reads(IDX[-1])
    r = built.get("/api/calendar")
    assert r.status_code == 200, r.json()
    v = api_models.AgendaView.model_validate(r.json())
    assert v.today == IDX[-1].date().isoformat() and v.selection.names
    items = {i.symbol: i for i in v.items}
    assert set(items) == {"S1", "E2"}
    s1 = items["S1"]
    assert (s1.level, s1.days, s1.weight) == ("high", 3, pytest.approx(1.0))
    assert {x.key for x in s1.reasons} >= {"held", "big_position", "estimates_cut"}
    assert v.soon == [s1.id]
    e2 = items["E2"]
    assert e2.level == "info" and e2.earnings.is_range and e2.date_end is not None
    assert built.get("/api/calendar").json()["generated"] == r.json()["generated"]       # cached until data changes
    assert {i["symbol"] for i in built.get("/api/calendar", params={"days": 5}).json()["items"]} == {"S1"}
    assert built.get("/api/calendar", params={"days": 0}).status_code == 422
    empty = built.get("/api/calendar", params={"tag": "no-such-tag"})
    assert empty.status_code == 200 and api_models.AgendaView.model_validate(empty.json()).selection.ids == []
    paths_ = [p for p in built.get("/openapi.json").json()["paths"] if p.startswith("/api/")]
    at = paths_.index("/api/calendar")
    assert paths_[at:at + 3] == ["/api/calendar", "/api/evidence", "/api/attribution"]
    monkeypatch.setattr(ingest, "load_prices", lambda: pd.DataFrame(columns=ingest.COLUMNS))
    api.reset()
    assert built.get("/api/calendar").status_code == 503


def test_tax_api_contract(built, monkeypatch):
    """GET /api/tax validates against TaxYearView (the CLI's --json is the same); the edits round-trip; a year
    without rules is a view with notes; the tax router came last; no prices is 503."""
    from world import IDX

    year = IDX[-1].year
    r = built.get("/api/tax", params={"year": year})
    assert r.status_code == 200
    v = api_models.TaxYearView.model_validate(r.json())
    assert v.rules is not None and v.disclaimer and {a.name for a in v.accounts} >= {"ASK", "frie midler"}
    assert built.get("/api/tax", params={"year": 2031}).json()["notes"]
    me = built.get("/api/tax/persons").json()[0]
    api_models.TaxPersonView.model_validate(me)
    assert built.put(f"/api/tax/persons/{me['id']}", json={"name": "Me", "capital_income_rate": 0.37}).json()[
        "capital_income_rate"] == 0.37
    assert built.put(f"/api/tax/persons/{me['id']}", json={"name": "Me", "capital_income_rate": 2}).status_code == 422
    assert built.post("/api/tax/persons", json={"name": "Me"}).status_code == 409
    inst = built.put("/api/tax/instruments/theme1", json={"isin": "IE00B4L5Y983"}).json()
    assert inst == built.get("/api/tax/instruments").json()[0] and inst["source"] == "manual"
    assert built.put("/api/tax/instruments/X", json={"isin": "nope"}).status_code == 422
    o = built.post("/api/tax/openings", json={"year": year, "pool": "listed_loss", "tax_person_id": me["id"],
                                              "amount": 250}).json()
    api_models.TaxOpeningView.model_validate(o)
    assert built.post("/api/tax/openings", json={"year": year, "pool": "ask_negative_tax", "amount": 1}).status_code == 422
    assert built.delete(f"/api/tax/openings/{o['id']}").json() == o["id"]
    assert built.delete(f"/api/tax/openings/{o['id']}").status_code == 404
    pf = built.get("/api/portfolios").json()
    ask = next(p for p in pf if p["name"] == "ASK")
    assert ask["tax_person_id"] == me["id"]
    paths_ = [p for p in built.get("/openapi.json").json()["paths"] if p.startswith("/api/")]
    at = paths_.index("/api/tax")                                          # the routers after it come later
    assert paths_[at:at + 7] == ["/api/tax", "/api/tax/persons", "/api/tax/persons/{pid}", "/api/tax/instruments",
                                 "/api/tax/instruments/{symbol}", "/api/tax/openings", "/api/tax/openings/{oid}"]
    monkeypatch.setattr(ingest, "load_prices", lambda: pd.DataFrame(columns=ingest.COLUMNS))
    api.reset()
    assert built.get("/api/tax").status_code == 503


def test_me_flag_matches_calendar(built):
    from world import IDX

    world.calendar_reads(IDX[-1])
    rows = {r["symbol"]: r for r in built.get("/api/me").json()["rows"]}
    days = {i["symbol"]: i["days"] for i in built.get("/api/calendar").json()["items"]}
    assert f"earnings in {days['S1']} d" in rows["S1"]["flags"]
    assert not any(f.startswith("earnings") for f in rows["E2"]["flags"])        # 10 days out: past soon_days


def test_evidence_api_contract(client, monkeypatch):
    """GET /api/evidence validates against EvidenceView with no reports run (every card says so), is cached until
    something it reads changes, and without prices still answers with the study cards and no scoreboard."""
    from radar.model import artifacts

    r = client.get("/api/evidence")
    assert r.status_code == 200, r.json()
    v = api_models.EvidenceView.model_validate(r.json())
    assert [c.head.status for c in v.scores] == ["missing"] * 4 and v.longrun.head.status == "missing"
    assert v.forward is not None and not v.forward.proposals.running
    assert client.get("/api/evidence").json()["generated"] == r.json()["generated"]       # cached
    artifacts.write("exit-study", {"generated": "2026-10-16T20:00:00", "asof": "2026-10-16"}, data_asof="2026-10-16")
    again = api_models.EvidenceView.model_validate(client.get("/api/evidence").json())
    assert again.rules[1].status == "ok"                                                  # a new report is read
    monkeypatch.setattr(ingest, "load_prices", lambda: pd.DataFrame(columns=ingest.COLUMNS))
    api.reset()
    gone = client.get("/api/evidence")
    assert gone.status_code == 200 and gone.json()["forward"] is None
    assert len(gone.json()["scores"]) == 4 and "radar run" in gone.json()["notes"][0]


def test_watchlist_add_and_remove(client):
    assert client.put("/api/watchlist/S3").json()["my_status"] == "watch"
    assert client.get("/api/ticker/S3").json()["identity"]["my_status"] == "watch"
    assert ("S3", "watch") in {(t["symbol"], t["status"]) for t in client.get("/api/context").json()["tickers"]}
    assert client.delete("/api/watchlist/S3").json() == {"symbol": "S3", "my_status": None}
    assert client.delete("/api/watchlist/E2").json()["my_status"] is None        # a Yahoo-imported watch entry
    assert {t["symbol"] for t in client.get("/api/context").json()["tickers"]} == {"S1"}


def test_watchlist_rejects_holdings_and_unknown_symbols(client):
    r = client.delete("/api/watchlist/S1")
    assert r.status_code == 409 and "holding" in r.json()["detail"]["message"]
    assert client.put("/api/watchlist/S1").json()["my_status"] == "holding"     # adding a holding changes nothing
    assert client.put("/api/watchlist/NOPE").status_code == 404


def test_old_dashboard_is_flagged_stale(built, monkeypatch):
    import datetime as dt

    class Later(dt.date):
        @classmethod
        def today(cls):
            return dt.date.today() + dt.timedelta(days=30)
    monkeypatch.setattr(api.common, "date", Later)                   # where the readings' age is taken
    r = built.get("/api/momentum").json()
    assert r["age_days"] >= 30 and r["stale"] is True


def test_regime_vote_switches(client):
    """Valuation stretched in the world's market data: off by default, two more risk-off votes when switched on,
    at once in /api/regime and in summary.json from the next report."""
    import pandas as pd

    from radar.sources import valuation

    months = pd.date_range(end=world.IDX[-1], periods=440, freq="MS")     # fresh as of the world's last day
    valuation.market_merge({"cape": pd.Series(range(10, 450), index=months, dtype=float)})      # last = highest
    valuation.market_merge({"erp": pd.Series([0.08 - i * 0.0001 for i in range(440)], index=months)})  # last = lowest
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
    summary = json.loads((paths.REPORTS / "summary.json").read_text(encoding="utf-8"))
    assert "valuation" in summary["regime"]["voting_groups"] and summary["regime"]["off"] == after["overall"]["off"]
    assert out["regime"] == after["overall"]["label"]
    assert client.put("/api/settings/regime-votes", json={"votes": {"crypto": True}}).status_code == 422
