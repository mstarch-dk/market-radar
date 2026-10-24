"""Market views: the store, the evidence check, alignment, and where views may (and may not) appear."""
import sqlite3

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import world
from radar import api, api_models, ingest, market_views, profile, tracked, userstore
from radar.signals import views as sv
from radar.userstore import viewstore

CFG = {"theme_corr": 0.5, "min_weeks": 26, "thresholds": {"aligned": 0.35}}
AI_BUBBLE = {"statement": "AI is in a bubble", "conviction": 4, "horizon": "12m",
             "exposures": [{"kind": "etf", "key": "SMH", "effect": -1}, {"kind": "sector", "key": "Technology", "effect": -1},
                           {"kind": "etf", "key": "USMV", "effect": 1}],
             "indicators": [{"indicator": "semis", "expect": "down"}, {"indicator": "us10y", "expect": "up"}]}


# ---------------- store ----------------

def test_views_are_added_edited_deleted_and_restored(tmp_data):
    assert viewstore.views() == [] and not (tmp_data / "userdata" / userstore.DB_NAME).exists()  # reading creates nothing
    vid = viewstore.save_view(AI_BUBBLE)
    v = viewstore.get_view(vid)
    assert v["status"] == "active" and len(v["exposures"]) == 3 and v["indicators"][0]["indicator"] == "semis"
    viewstore.save_view({**AI_BUBBLE, "conviction": 2, "exposures": [], "status": "archived"}, vid)
    v2 = viewstore.get_view(vid)
    assert v2["conviction"] == 2 and v2["exposures"] == [] and v2["status"] == "archived"
    assert viewstore.views("active") == []
    gone = viewstore.delete_view(vid)
    assert viewstore.views() == []
    viewstore.restore_view(gone)
    assert viewstore.get_view(vid)["statement"] == "AI is in a bubble"
    text = viewstore.export_views_json()
    assert viewstore.import_views_json(text) == 1 and viewstore.views()[0]["statement"] == "AI is in a bubble"


def test_the_migration_keeps_an_existing_database(tmp_data):
    db = tmp_data / "userdata" / userstore.DB_NAME
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    for sql in userstore.MIGRATIONS[:8]:                 # a database from before market views
        con.execute(sql)
    con.execute("PRAGMA user_version = 8")
    con.execute("INSERT INTO meta (key, value) VALUES ('yahoo_watch', '[\"X\"]')")
    con.commit()
    con.close()
    assert viewstore.views() == [] and userstore.meta_get("yahoo_watch") == ["X"]
    viewstore.save_view(AI_BUBBLE)
    assert len(viewstore.views()) == 1 and [p["name"] for p in userstore.portfolios()] == ["ASK", "frie midler"]


def test_templates_only_use_known_indicators_and_tracked_etfs():
    known = set(market_views.config()["indicators"])
    etfs = {e.ticker for e in tracked.etfs()}
    for t in market_views.templates():
        assert {i["indicator"] for i in t["indicators"]} <= known, t["key"]
        assert {e["key"] for e in t["exposures"] if e["kind"] == "etf"} <= etfs, t["key"]
    keys = {t["key"] for t in market_views.templates()}
    assert all(t["pair"] in keys for t in market_views.templates() if t["pair"])


# ---------------- evidence ----------------

IDX = pd.bdate_range(end="2026-10-14", periods=300)


def _closes(**growth):
    t = np.arange(len(IDX))
    return pd.DataFrame({k: 100 * (1 + g) ** t for k, g in growth.items()}, index=IDX)


CAT = {"semis": {"label": "Semis vs ACWI", "kind": "rel", "ticker": "SMH", "band": 0.02},
       "us10y": {"label": "US 10Y", "kind": "fred", "series": "DGS10", "band": 0.15},
       "cli": {"label": "CLI", "kind": "cli", "area": "G20", "band": 0.1},
       "gone": {"label": "Not downloaded", "kind": "rel", "ticker": "NOPE", "band": 0.02}}


def test_evidence_supports_contradicts_flat_and_no_data():
    closes = _closes(ACWI=0.0004, SMH=-0.001)                       # semis lagging: a bubble view is supported
    fdays = pd.date_range(end="2026-10-14", periods=200, freq="D")
    fred = pd.DataFrame({"DGS10": np.linspace(4.0, 3.5, 200)}, index=fdays)   # yields falling
    cli = pd.DataFrame({"G20": [100.0, 100.0, 100.05, 100.05]}, index=pd.date_range("2026-06-01", periods=4, freq="MS"))
    r = sv.readings(CAT, closes, fred, cli, "ACWI", today=pd.Timestamp("2026-10-14"))
    assert r["semis"]["value"] == pytest.approx(0.999 ** 63 - 1.0004 ** 63, rel=1e-6) and r["semis"]["current"]
    assert r["gone"]["value"] is None and not r["gone"]["current"]
    view = {"indicators": [{"indicator": "semis", "expect": "down"}, {"indicator": "us10y", "expect": "up"},
                           {"indicator": "cli", "expect": "up"}, {"indicator": "gone", "expect": "up"}]}
    ev = sv.evidence(view, r)
    assert [i["state"] for i in ev["items"]] == ["supports", "contradicts", "flat", "no data"]
    assert ev["verdict"] == "mixed" and ev["counts"]["no data"] == 1


def test_old_readings_count_as_no_data():
    closes = _closes(ACWI=0.0004, SMH=0.002)
    r = sv.readings(CAT, closes, pd.DataFrame(), pd.DataFrame(), "ACWI", today=pd.Timestamp("2026-12-31"))
    assert not r["semis"]["current"]
    assert sv.evidence({"indicators": [{"indicator": "semis", "expect": "up"}]}, r)["verdict"] == "no data"


# ---------------- alignment ----------------

def _themed_world():
    rng = np.random.default_rng(1)
    acwi = 100 * np.cumprod(1 + rng.normal(0.0004, 0.01, len(IDX)))
    theme_rel = np.cumprod(1 + rng.normal(0, 0.012, len(IDX)))
    closes = pd.DataFrame({"ACWI": acwi, "SMH": acwi * theme_rel,
                           "FOLLOWER": acwi * theme_rel * np.cumprod(1 + rng.normal(0, 0.004, len(IDX))),
                           "OTHER": acwi * np.cumprod(1 + rng.normal(0, 0.012, len(IDX)))}, index=IDX)
    return closes


def test_alignment_by_ticker_sector_region_and_theme_correlation():
    closes = _themed_world()
    meta = pd.DataFrame({"sector": ["Technology", "Healthcare", None], "industry": ["Semiconductors", "Biotechnology", None],
                         "region": ["us", "nordic", "us"], "country": [None, "Denmark", None]},
                        index=["FOLLOWER", "OTHER", "SMH"])
    ctx = sv.contexts(["FOLLOWER", "OTHER", "SMH"], meta, closes, "ACWI", ["SMH"], {"VVSM.DE": "SMH"}, CFG)
    assert ctx["FOLLOWER"]["corr"]["SMH"] > 0.8 and abs(ctx["OTHER"]["corr"]["SMH"]) < 0.5
    bubble = {**AI_BUBBLE, "id": 1}
    nordic = {"id": 2, "statement": "The Nordics outperform", "conviction": 2,
              "exposures": [{"kind": "region", "key": "Denmark", "effect": 1}]}
    a = sv.align(ctx["FOLLOWER"], [bubble, nordic], CFG)
    assert a["label"] == "conflicts" and a["views"][0]["label"] == "conflicts" and a["views"][1]["label"] == "unrelated"
    assert any("moves with SMH" in r["text"] for r in a["views"][0]["reasons"])
    assert sv.align(ctx["OTHER"], [bubble, nordic], CFG)["label"] == "aligned"           # only the Denmark view applies
    assert sv.align(ctx["SMH"], [bubble], CFG)["views"][0]["reasons"][0]["text"] == "hurt: is SMH"
    ucits = {"ticker": "VVSM.DE", "ucits_of": "SMH"}
    assert sv.align(ucits, [bubble], CFG)["label"] == "conflicts"
    assert sv.align({"ticker": "ZZZ"}, [bubble, nordic], CFG)["label"] == "unrelated"


def test_conviction_weights_the_overall_label_and_both_sides_make_it_mixed():
    ctx = {"ticker": "X", "sector": "Technology", "region": "europe"}
    strong = {"id": 1, "statement": "a", "conviction": 5, "exposures": [{"kind": "sector", "key": "Technology", "effect": 1}]}
    weak = {"id": 2, "statement": "b", "conviction": 1, "exposures": [{"kind": "region", "key": "europe", "effect": -1}]}
    assert sv.align(ctx, [strong, weak], CFG)["label"] == "aligned"            # (5·1 − 1·1) / 6 = 0.67
    even = {**weak, "conviction": 5}
    assert sv.align(ctx, [strong, even], CFG)["label"] == "mixed"
    both = {"id": 3, "statement": "c", "conviction": 3, "exposures": [
        {"kind": "sector", "key": "Technology", "effect": 1}, {"kind": "region", "key": "europe", "effect": -1}]}
    assert sv.align(ctx, [both], CFG)["views"][0]["label"] == "mixed"


# ---------------- where views appear ----------------

@pytest.fixture
def env(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers: {})
    monkeypatch.setattr(ingest, "load_fred", world.fred)
    api.reset()
    market_views.reset()
    viewstore.save_view({"statement": "Software keeps winning", "conviction": 4,
                         "exposures": [{"kind": "sector", "key": "Technology", "effect": 1}],
                         "indicators": [{"indicator": "us10y", "expect": "down"}]})


def test_views_only_appear_in_personal_profiles(env):
    p = profile.build("S1")
    api_models.Profile.model_validate(p)
    assert p["views"]["label"] == "aligned" and p["views"]["views"][0]["evidence"] in ("supported", "contradicted",
                                                                                       "mixed", "unclear", "no data")
    assert profile.build("S1", anonymous=True).get("views") is None


def test_views_api_round_trip(env):
    c = TestClient(api.app)
    page = api_models.ViewsPage.model_validate(c.get("/api/views").json())
    assert len(page.views) == 1 and page.views[0].evidence is not None and "subjective" in page.disclaimer
    assert any(t.key == "ai_bubble" for t in page.templates)
    r = c.post("/api/views", json={"statement": " ", "indicators": []})
    assert r.status_code == 422
    r = c.post("/api/views", json={"statement": "x", "indicators": [{"indicator": "nope", "expect": "up"}]})
    assert r.status_code == 422 and "Unknown indicator" in r.json()["detail"]["message"]
    r = c.post("/api/views", json={"statement": "Gold shines", "conviction": 2,
                                   "exposures": [{"kind": "ticker", "key": "S2", "effect": 1}]})
    assert r.status_code == 200 and len(r.json()["views"]) == 2
    aligned = c.post("/api/views/align", json={"tickers": ["S1", "S2", "E1"]}).json()
    assert aligned["S2"]["label"] == "aligned" and aligned["S1"]["label"] == "aligned"
    vid = r.json()["views"][-1]["id"]
    gone = c.delete(f"/api/views/{vid}").json()
    assert c.post("/api/views/restore", json=gone).status_code == 200
    assert c.post("/api/views/restore", json=gone).status_code == 409
    gone = c.delete(f"/api/views/{vid}").json()
    r = c.post("/api/views/restore", json=gone | {"conviction": 9})          # restored rows are checked too
    assert r.status_code == 422 and r.json()["detail"]["message"].startswith("Conviction")


def test_a_views_import_that_fails_part_way_keeps_the_old_views(tmp_data, monkeypatch):
    import json
    viewstore.save_view(AI_BUBBLE)
    viewstore.save_view({**AI_BUBBLE, "statement": "Rates stay high"})
    before = viewstore.export_views_json()
    real = viewstore.write_children
    calls = []

    def flaky(con, view_id, v):
        calls.append(view_id)
        if len(calls) == 2:
            raise sqlite3.OperationalError("disk I/O error")
        return real(con, view_id, v)
    monkeypatch.setattr(viewstore, "write_children", flaky)
    with pytest.raises(sqlite3.OperationalError):
        viewstore.import_views_json(json.dumps([{**AI_BUBBLE, "statement": "new 1"}, {**AI_BUBBLE, "statement": "new 2"}]))
    assert viewstore.export_views_json() == before                          # all or nothing
    assert any("views" in b.name for b in (tmp_data / "userdata" / "backups").iterdir())   # and a copy first
