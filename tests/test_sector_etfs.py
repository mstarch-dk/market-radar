"""Sector ETFs (plans/F13-sector-etfs.md): /sector-etfs' record (checked, frozen, never overwritten, partial runs
carried over), the ranking and the page's view on the synthetic world, and the API, MCP and CLI over them."""
from __future__ import annotations

import json
from datetime import date

import pytest

from radar import sector_etfs, universe
from radar.errors import Invalid

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

