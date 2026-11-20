"""Sector ETFs (plans/F13-sector-etfs.md): /sector-etfs' record (checked, frozen, never overwritten, partial runs
carried over), the ranking and the page's view on the synthetic world, and the API, MCP and CLI over them."""
from __future__ import annotations

import json
from datetime import date

import pytest

import world
from conftest import with_settings
from radar import sector_etf_view, sector_etfs, universe
from radar.config import sector_etf_taxonomy
from radar.errors import Invalid, NotFound
from radar.market import Market
from radar.reporting import dashboard
from radar.sources import ingest

TECH = {"key": "Technology", "pick": "IE00BM67HT60", "reason": None, "etfs": [
    {"isin": "IE00BM67HT60", "ticker": "XDWT.L", "name": "Xtrackers MSCI World IT 1C", "scope": "world",
     "ter": 0.0025, "distribution": "acc", "domicile": "ie", "currency": "usd", "aum_musd": 4000,
     "sources": ["https://etf.dws.com/"], "checked": "2026-11-20"},
    {"isin": "IE00B3WJKG14", "ticker": "IUIT.L", "name": "iShares S&P 500 IT (Acc)", "scope": "us", "ter": 0.0015},
]}
BANKS = {"key": "Banks", "pick": "DE000A0F5UJ7", "etfs": [
    {"isin": "DE000A0F5UJ7", "ticker": "EXV1.DE", "name": "iShares STOXX Europe 600 Banks", "scope": "europe"}]}


def test_a_record_is_checked_and_missing_stays_missing():
    rec = sector_etfs.check({"sectors": [TECH]})
    xdwt, iuit = rec["sectors"][0]["etfs"]
    assert (xdwt["domicile"], xdwt["currency"], xdwt["ter"]) == ("IE", "USD", 0.0025)
    assert iuit["aum_musd"] is None and iuit["tracking_diff"] is None and iuit["distribution"] is None


@pytest.mark.parametrize("change, match", [
    ({"key": "Tech"}, "not a sector"),
    ({"pick": "IE00B6R52259"}, "the pick is the ISIN"),
    ({"etfs": []}, "at least its go-to"),
    ({"etfs": [TECH["etfs"][0]] * 2}, "listed twice"),
    ({"etfs": [{**TECH["etfs"][0], "isin": "IE00BM67HT61"}]}, "not a valid ISIN"),
    ({"etfs": [{**TECH["etfs"][0], "ticker": "xd wt"}]}, "not a Yahoo symbol"),
    ({"etfs": [{**TECH["etfs"][0], "ter": 0.25}]}, "ter is a fraction"),
    ({"etfs": [{**TECH["etfs"][0], "scope": "asia"}]}, "scope is one of"),
    ({"etfs": [{**TECH["etfs"][0], "distribution": "both"}]}, "acc or dist"),
    ({"etfs": [{**TECH["etfs"][0], "domicile": "Ireland"}]}, "two-letter"),
    ({"etfs": [{**TECH["etfs"][0], "sources": ["justetf"]}]}, "web address"),
    ({"etfs": [{**TECH["etfs"][0], "aum_musd": -1}]}, "aum_musd"),
    ({"rank_override": True}, "needs its reason"),
])
def test_a_record_refuses_what_would_mislead(change, match):
    with pytest.raises(Invalid, match=match):
        sector_etfs.check({"sectors": [{**TECH, **change}]})


def test_a_record_needs_sectors_once_each():
    with pytest.raises(Invalid, match="at least one sector"):
        sector_etfs.check({"sectors": []})
    with pytest.raises(Invalid, match="listed twice"):
        sector_etfs.check({"sectors": [TECH, TECH]})


def test_freeze_never_overwrites_and_carries_the_other_sectors(tmp_data):
    first = sector_etfs.freeze({"sectors": [TECH, BANKS]}, today=date(2026, 8, 1))
    assert first["id"] == "2026-08-01" and first["carried"] == []
    again = sector_etfs.freeze({"sectors": [TECH]}, today=date(2026, 8, 1))
    assert again["id"] == "2026-08-01-2"                  # a second run the same day: a new file
    later = sector_etfs.freeze({"sectors": [{**TECH, "pick": "IE00B3WJKG14", "rank_override": False}]},
                               today=date(2026, 11, 20))
    assert [s["key"] for s in later["sectors"]] == ["Technology", "Banks"]     # the taxonomy's order
    assert later["carried"] == ["Banks"]
    by = {s["key"]: s for s in later["sectors"]}
    assert by["Technology"]["updated"] == "2026-11-20" and by["Banks"]["updated"] == "2026-08-01"
    assert [r["id"] for r in sector_etfs.records()] == ["2026-08-01", "2026-08-01-2", "2026-11-20"]
    assert sector_etfs.latest()["sectors"][0]["pick"] == "IE00B3WJKG14"


def test_latest_skips_and_flags_an_unreadable_record(tmp_data):
    assert sector_etfs.latest() is None and sector_etfs.symbols() == set()
    sector_etfs.freeze({"sectors": [TECH]}, today=date(2026, 8, 1))
    (sector_etfs.RECORDS / "2026-09-01.json").write_text("{not json", encoding="utf-8")
    bad = {"type": "sector-etfs", "date": "2026-10-01", "sectors": [{**TECH, "key": "Gone"}]}
    (sector_etfs.RECORDS / "2026-10-01.json").write_text(json.dumps(bad), encoding="utf-8")
    recs = sector_etfs.records()
    assert [("problem" in r) for r in recs] == [False, True, True]
    assert sector_etfs.latest()["id"] == "2026-08-01"


def test_the_latest_records_tickers_are_in_the_daily_update(tmp_data, monkeypatch):
    sector_etfs.freeze({"sectors": [TECH, BANKS]}, today=date(2026, 8, 1))
    assert sector_etfs.symbols() == {"XDWT.L", "IUIT.L", "EXV1.DE"}
    monkeypatch.setattr(universe, "stock_groups", lambda refresh=False, offline=False: {})
    assert {"XDWT.L", "IUIT.L", "EXV1.DE"} <= set(universe.all_price_tickers(offline=True))


# ---------------- ranking and the page's view (sector_etf_view.py) ----------------

def _etf(code, tax="yes", **kw):
    return {"isin": code, "ticker": "T", "name": code, "scope": "world", "ter": None, "aum_musd": None,
            "tracking_diff": None, "distribution": None, "tax": {"status": tax}, **kw}


def test_rank_puts_tax_first_then_size_ter_tracking_and_accumulating():
    etfs = [_etf("off", tax="no", ter=0.0001),
            _etf("small", ter=0.0005, aum_musd=10),
            _etf("dear", ter=0.0040, aum_musd=900),
            _etf("cheap", ter=0.0015, aum_musd=900, tracking_diff=-0.001, distribution="dist"),
            _etf("cheap_acc", ter=0.0015, aum_musd=900, tracking_diff=-0.001, distribution="acc"),
            _etf("cheap_tracks", ter=0.0015, tracking_diff=0.0005),
            _etf("unknown", tax="no_sheet", ter=0.0001)]
    order = [e["isin"] for e in sector_etf_view.rank(etfs, min_aum_musd=100)]
    assert order == ["cheap_tracks", "cheap_acc", "cheap", "dear", "small", "unknown", "off"]
    first = sector_etf_view.rank(etfs, min_aum_musd=100)[0]
    assert first["rank"] == 1 and first["reasons"][0].startswith("on the positive list")
    assert "TER 0.15 %" in first["reasons"]
    assert any("smaller than 100m" in r for r in sector_etf_view.rank(etfs, 100)[4]["reasons"])


def test_tax_status_follows_the_positive_list_of_the_year():
    years = {2026: {"IE00BM67HT60"}, 2027: set()}
    on = sector_etf_view.tax_status("IE00BM67HT60", years, 2026)
    assert on == {"status": "yes", "tax_class": "aktiebaseret", "ask_ok": True, "sheet_year": 2026, "next_year": "no"}
    off = sector_etf_view.tax_status("IE00B3WJKG14", years, 2026)
    assert (off["tax_class"], off["ask_ok"]) == ("kapitalindkomst", False)
    gap = sector_etf_view.tax_status("IE00BM67HT60", years, 2025)       # never borrowed from another year
    assert gap == {"status": "no_sheet", "tax_class": "ukendt", "ask_ok": None, "sheet_year": None,
                   "next_year": "yes"}
    assert sector_etf_view.tax_status(None, None, 2026)["status"] == "no_isin"


@pytest.fixture
def radar(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers: {})   # Yahoo knows nothing new
    year = date.today().year
    monkeypatch.setattr(sector_etf_view, "positive_list_years", lambda: {year: {"IE00BM67HT60", "DE000A0F5UJ7"}})
    dashboard.reset()
    return tmp_data


def _record():
    tech = {**TECH, "etfs": [{**TECH["etfs"][0], "ticker": "THEME1"},
                             {**TECH["etfs"][1], "ticker": "NOPRICE"}]}
    return {"sectors": [tech, {**BANKS, "etfs": [{**BANKS["etfs"][0], "ticker": "THEME2"}]}]}


def test_the_view_before_the_first_run_lists_every_sector_without_etfs(radar):
    v = sector_etf_view.view(Market.load())
    assert v["as_of"] is None and not v["stale"] and v["problems"] == []
    assert [s["key"] for s in v["sectors"]] == list(sector_etf_taxonomy().sectors)
    assert all(s["etfs"] == [] and s["pick"] is None for s in v["sectors"])


def test_the_view_gives_dkk_returns_vs_acwi_and_missing_as_none(radar):
    sector_etfs.freeze(_record())
    v = sector_etf_view.view(Market.load())
    tech = next(s for s in v["sectors"] if s["key"] == "Technology")
    by = {e["isin"]: e for e in tech["etfs"]}
    xdwt, iuit = by["IE00BM67HT60"], by["IE00B3WJKG14"]
    want = (1 + world.G["THEME1"]) ** 21 - 1
    assert xdwt["returns_dkk"]["r1m"] == pytest.approx(want)
    assert xdwt["vs_acwi"]["r1m"] == pytest.approx(want - ((1 + world.G["ACWI"]) ** 21 - 1))
    assert xdwt["returns_dkk"]["r1y"] == pytest.approx((1 + world.G["THEME1"]) ** 252 - 1)   # 300 bars: a year
    assert iuit["returns_dkk"] == dict.fromkeys(["r1m", "r3m", "r6m", "r1y", "ytd"]) and iuit["spark"] == []
    assert iuit["last_close"] is None and xdwt["spark"][0] == 1.0
    assert (xdwt["tax"]["tax_class"], iuit["tax"]["tax_class"]) == ("aktiebaseret", "kapitalindkomst")
    assert xdwt["yahoo_ter"] is None and not xdwt["ter_mismatch"]
    # the ranking: IUIT is cheaper but off the list, so XDWT (the pick) is first and nothing needs a re-check
    assert [e["isin"] for e in tech["etfs"]] == ["IE00BM67HT60", "IE00B3WJKG14"]
    assert xdwt["pick"] and xdwt["rank"] == 1 and not tech["recheck"]
    assert tech["updated"] == date.today().isoformat() and v["as_of"] == date.today().isoformat()


def test_a_pick_the_ranking_puts_second_is_flagged_unless_overridden(radar):
    rec = _record()
    rec["sectors"][0]["pick"] = "IE00B3WJKG14"
    sector_etfs.freeze(rec)
    tech = next(s for s in sector_etf_view.view(Market.load())["sectors"] if s["key"] == "Technology")
    assert tech["recheck"]
    rec["sectors"][0].update(rank_override=True, reason="cheaper, and held on frie midler only")
    sector_etfs.freeze(rec)
    tech = next(s for s in sector_etf_view.view(Market.load())["sectors"] if s["key"] == "Technology")
    assert not tech["recheck"] and tech["rank_override"] and tech["reason"].startswith("cheaper")


def test_the_view_is_stale_after_stale_days_and_shows_the_rotation(radar, monkeypatch):
    sector_etfs.freeze(_record(), today=date(2026, 1, 2))
    (sector_etfs.RECORDS / "2026-02-01.json").write_text("{", encoding="utf-8")
    p = dashboard.path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"rotation": {"groups": [{"key": "us_sectors", "label": "US sectors", "rows": [
        {"ticker": "XLK", "name": "Technology", "quadrant": "Leading", "rank": 1, "rs_score": 0.05}]}]}}),
        encoding="utf-8")
    with_settings(monkeypatch, sector_etfs={"stale_days": 30, "min_aum_musd": 100})
    v = sector_etf_view.view(Market.load(), today=date(2026, 3, 1))
    assert v["age_days"] == 58 and v["stale"] and [p["id"] for p in v["problems"]] == ["2026-02-01"]
    tech = next(s for s in v["sectors"] if s["key"] == "Technology")
    assert tech["rotation"] == [{"ticker": "XLK", "group": "us_sectors", "group_label": "US sectors",
                                 "name": "Technology", "quadrant": "Leading", "rank": 1, "rs_score": 0.05,
                                 "r3m": None, "rel_r3m": None}]
    assert tech["age_days"] == 58


def test_history_lists_each_runs_picks(radar):
    sector_etfs.freeze(_record(), today=date(2026, 1, 2))
    sector_etfs.freeze({"sectors": [{**TECH, "pick": "IE00B3WJKG14"}]}, today=date(2026, 3, 1))
    h = sector_etf_view.history()
    assert [r["date"] for r in h] == ["2026-01-02", "2026-03-01"]
    assert h[1]["picks"]["Technology"]["isin"] == "IE00B3WJKG14" and h[1]["picks"]["Banks"]["carried"]


def test_candidates_start_from_the_record_and_the_seeds(radar):
    sector_etfs.freeze(_record())
    c = sector_etf_view.candidates("Technology", Market.load())
    src = {e["isin"]: e["source"] for e in c["candidates"]}
    assert src["IE00BM67HT60"] == "record" and src["DE000A0H08Q4"] == "seed"
    assert c["current_pick"] == "IE00BM67HT60" and c["pool"] == []      # no discovery scan in the test world
    with pytest.raises(NotFound, match="not a sector"):
        sector_etf_view.candidates("Tech", Market.load())


def test_the_shipped_positive_list_is_read_by_year():
    years = sector_etf_view.positive_list_years()
    assert years and 2026 in years and "IE00BM67HT60" in years[2026]


def test_the_discovery_pool_offers_matching_funds_but_not_leveraged_ones(radar, monkeypatch):
    import pandas as pd

    from radar.discovery import scan
    monkeypatch.setattr(scan, "load_universe", lambda: pd.DataFrame([
        {"ticker": "A.L", "name": "Some MSCI World Information Technology UCITS ETF", "kind": "etf",
         "isin": "IE00B6R52259", "category": "Technology & AI", "exchange": "LSE"},
        {"ticker": "B.L", "name": "Leveraged Technology 3x Daily", "kind": "etf", "isin": "US0378331005"},
        {"ticker": "C.L", "name": "Technology Co", "kind": "stock", "isin": "DE000A0F5UJ7"},
        {"ticker": "XDWT.L", "name": "Xtrackers MSCI World Information Technology", "kind": "etf",
         "isin": "IE00BM67HT60"}]))                    # already a seed: not offered twice
    pool = sector_etf_view.candidates("Technology", Market.load())["pool"]
    assert [p["ticker"] for p in pool] == ["A.L"] and pool[0]["source"] == "discovery"


# ---------------- MCP and CLI ----------------

def test_save_is_a_dry_run_until_confirmed(radar, monkeypatch):
    from radar import profile
    from radar.mcp import common
    from test_mcp import ok, refused

    common.reset()
    rec = _record()
    draft = ok("sector_etfs_save", sectors=rec["sectors"], note="first run")
    assert not draft["saved"] and sector_etfs.records() == []
    tech = next(s for s in draft["sectors"] if s["key"] == "Technology")
    assert [r["isin"] for r in tech["ranking"]] == ["IE00BM67HT60", "IE00B3WJKG14"] and tech["warnings"] == []
    assert draft["changes"][0] == {"key": "Technology", "new": True, "pick": {"from": None, "to": "IE00BM67HT60"}}
    assert "no Yahoo prices for NOPRICE" in refused("sector_etfs_save", sectors=rec["sectors"], confirm=True)
    monkeypatch.setattr(profile, "ensure_prices", lambda t, m=None, refresh=False: m)
    saved = ok("sector_etfs_save", sectors=rec["sectors"], confirm=True)
    assert saved["saved"] and saved["id"] == date.today().isoformat() and len(sector_etfs.records()) == 1
    rec["sectors"][0]["pick"] = "IE00B3WJKG14"                          # off the list, not first, no override
    again = ok("sector_etfs_save", sectors=rec["sectors"][:1])
    warn = again["sectors"][0]["warnings"]
    assert any("isn't the ranking's first" in w for w in warn) and any("kapitalindkomst" in w for w in warn)
    assert again["changes"][0]["pick"] == {"from": "IE00BM67HT60", "to": "IE00B3WJKG14"}
    assert again["carried_over"] == ["Banks"]
    assert "the pick is the ISIN" in refused("sector_etfs_save", sectors=[{**rec["sectors"][0], "pick": "x"}])
    view = ok("sector_etfs_view")
    assert view["as_of"] == date.today().isoformat()
    assert ok("sector_etf_candidates", sector="Banks")["current_pick"] == "DE000A0F5UJ7"
    assert "not a sector" in refused("sector_etf_candidates", sector="Nope")


def test_the_cli_shows_the_record_candidates_and_history(radar):
    from typer.testing import CliRunner

    from radar import cli

    run = CliRunner()
    assert "No sector ETF record yet" in run.invoke(cli.app, ["sector-etfs"]).output
    sector_etfs.freeze(_record())
    out = run.invoke(cli.app, ["sector-etfs"]).output
    assert "Technology (Teknologi)" in out and " *1 THEME1" in out and "PL" in out
    assert json.loads(run.invoke(cli.app, ["sector-etfs", "--json"]).output)["record_id"] == date.today().isoformat()
    assert "IE00BM67HT60" in run.invoke(cli.app, ["sector-etfs", "candidates", "Technology"]).output
    assert "Technology THEME1" in run.invoke(cli.app, ["sector-etfs", "history"]).output


def test_the_skills_memo_is_a_notebook_kind(radar):
    from test_mcp import ok

    w = ok("write_memo", kind="sector_etfs", name="2026-11-20", markdown="---\ndate: 2026-11-20\n---\n# Sektor-ETF'er\n")
    assert w["file"].replace("\\", "/").endswith("research/sector-etfs/2026-11-20.md")
    assert [d["name"] for d in ok("documents", kind="sector_etfs")["sector_etfs"]] == ["2026-11-20"]
    assert ok("read_document", kind="sector_etfs", name="2026-11-20")["title"].startswith("Sektor-ETF")
