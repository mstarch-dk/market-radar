"""report.build() end to end on a small synthetic market whose answers are known in advance.

Unit tests check each calculation; this checks the wiring between them: that the right series reach the
right signal and land under the right key in summary.json and dashboard.json.
"""
import json
from datetime import date, timedelta

import pandas as pd
import pytest

import world
from radar import api_models, snapshot
from radar.config import settings
from radar.reporting import report
from radar.sources import fxrates
from world import BUY_AT, IDX, N


@pytest.fixture
def summary(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)

    # snapshots from 10 days ago: LEAD ranked 2nd, and the US top list held S2 and a stock that has left
    old = date.today() - timedelta(days=10)
    snapshot.save("rotation", pd.DataFrame({"ticker": ["LAG", "LEAD"], "rank": [1, 2], "score": [0, 0],
                                            "group": "sectors"}), old)
    snapshot.save("momentum", pd.DataFrame({"ticker": ["S2", "OLD"], "rank": [1, 2], "score": [0, 0],
                                            "region": "us"}), old)

    res = report.build()
    out = json.loads((tmp_data / "reports" / "summary.json").read_text(encoding="utf-8"))
    dash = json.loads((tmp_data / "reports" / "dashboard.json").read_text(encoding="utf-8"))
    return out | {"_res": res, "_dash": dash}


def test_summary_schema(summary):
    assert set(summary) - {"_res", "_dash"} == {
        "asof", "regime", "indicators", "rotation", "momentum_top10", "momentum_new_entrants",
        "momentum_dropped_out", "me", "momentum_clusters", "positioning_cot", "leading_indicators",
        "earnings_factset", "stale_tickers", "behind_tickers", "coverage", "portfolios", "valuation", "revisions_regional", "sentiment",
        "quality_top10", "quality_new_entrants", "quality_coverage", "abtest", "calendar"}
    assert summary["abtest"] == {"running": False}
    assert summary["asof"] == IDX[-1].date().isoformat()


def _built_calendar(tmp_data) -> dict:
    report.build()
    return json.loads((tmp_data / "reports" / "summary.json").read_text(encoding="utf-8"))["calendar"]


def test_summary_calendar_key(tmp_data, monkeypatch):
    """summary.json["calendar"] is the calendar of your real portfolios and the watchlist, an AgendaView without
    the selection and the build time, counted from asof."""
    world.install(tmp_data, monkeypatch)
    world.calendar_reads(IDX[-1])
    cal = _built_calendar(tmp_data)
    assert "selection" not in cal and "generated" not in cal
    v = api_models.AgendaView.model_validate(cal | {"generated": "x", "selection": {"ids": [], "names": []}})
    assert v.today == v.asof == IDX[-1].date().isoformat() and v.days == settings()["calendar"]["days"]
    items = {i.symbol: i for i in v.items}
    assert set(items) == {"S1", "E2"}                       # held and watched; S3 is neither
    assert items["S1"].level == "high" and v.soon == [items["S1"].id]


def test_summary_deterministic(tmp_data, monkeypatch):
    """Two builds on the same data give the same calendar: dates against asof, not the clock."""
    world.install(tmp_data, monkeypatch)
    world.calendar_reads(IDX[-1])
    assert _built_calendar(tmp_data) == _built_calendar(tmp_data)


def test_summary_portfolios_are_your_real_ones_with_returns_vs_acwi(summary):
    [main] = summary["portfolios"]                    # the world's S1 trade, in Main (no cash rows)
    s1 = next(r for r in summary["me"] if r["symbol"] == "S1")
    assert main["name"] == "Main" and main["funding"] == "implicit"
    assert main["twr_total"] == pytest.approx(s1["since_buy"]) and main["acwi_twr_total"] == pytest.approx(s1["bench_since_buy"])
    assert main["twr_3m"] == pytest.approx(1.0012 ** 63 - 1) and main["acwi_3m"] == pytest.approx(1.0004 ** 63 - 1)


def test_regime_votes(summary):
    st = {i["name"].split(" (")[0]: i["status"] for i in summary["indicators"]}
    on = {"Global trend", "Breadth – US", "Breadth – Europe", "New highs – new lows", "Volatility",
          "VIX term structure", "Credit"}
    assert {k for k, v in st.items() if v == "risk-on"} == on
    assert {k for k, v in st.items() if v == "n/a"} == {"Equal vs cap weight", "Copper/gold ratio", "Oil",
                                                        "Leading indicators", "Earnings revisions", "Euro credit",
                                                        "Valuation", "Equity risk premium",
                                                        # 300 bars and 6 stocks: too short and too few
                                                        "Momentum payoff", "Return dispersion", "Momentum-crash setup"}
    assert summary["regime"]["label"] == "Risk-on" and summary["regime"]["on"] == 7 and summary["regime"]["off"] == 0


def test_rotation(summary):
    sectors = {r["ticker"]: r for r in summary["rotation"]["sectors"]}
    assert sectors["LEAD"]["quadrant"] == "Leading" and sectors["LAG"]["quadrant"] == "Lagging"
    assert sectors["LEAD"]["rank"] == 1 and sectors["LEAD"]["rank_change"] == 1     # was 2nd
    # return difference, not ratio: (1.0004^63 x 1.003^59 - 1) - (1.0004^63 - 1)
    assert sectors["LEAD"]["rel_r3m"] == pytest.approx(1.0004 ** 63 * (1.003 ** 59 - 1), rel=1e-9)
    assert sectors["LEAD"]["positive_list"] == "?"                                   # no list loaded
    themes = [r["ticker"] for r in summary["rotation"]["themes"]]
    assert themes == ["THEME1", "THEME2"]


def test_momentum_and_snapshot_comparison(summary):
    us = summary["momentum_top10"]["us"]
    assert [r["ticker"] for r in us] == ["S1", "S2", "S3", "S4", "S5", "S6"]
    assert us[0]["r3m"] == pytest.approx(1.0012 ** 63 - 1)
    assert summary["momentum_top10"]["europe"][0]["ticker"] == "E1"
    assert summary["momentum_new_entrants"]["us"] == ["S1", "S3", "S4", "S5", "S6"]   # S2 was already there
    assert summary["momentum_dropped_out"] == {"us": ["OLD"], "europe": []}          # no europe snapshot: nothing new
    asof = IDX[-1].date()                                                             # the data's date, not today's
    assert snapshot.path("momentum", asof).exists() and snapshot.path("rotation", asof).exists()


def test_holding_return_against_the_shadow_benchmark(summary):
    me = {r["symbol"]: r for r in summary["me"]}
    held = N - 1 - BUY_AT
    assert me["S1"]["since_buy"] == pytest.approx(1.0012 ** held - 1, rel=1e-9)
    assert me["S1"]["bench_since_buy"] == pytest.approx(1.0004 ** held - 1, rel=1e-9)
    assert "trend intact" in me["S1"]["flags"] and me["E2"]["status"] == "watch"


def test_coverage(summary):
    cov = summary["coverage"]
    assert set(cov["missing_tickers"]) == {"HG=F", "GC=F", "CL=F"} | {
        fx for fx in fxrates.FX_TICKERS if fx != "USDDKK=X"}
    assert summary["stale_tickers"] == []
    src = {s["key"]: s for s in cov["sources"]}
    assert src["prices"]["status"] == "ok" and src["fred"]["status"] == "ok"
    assert src["cftc"]["status"] == src["oecd"]["status"] == src["factset"]["status"] == "missing"
    assert cov["regime"]["current"] == len(summary["indicators"]) - 11     # 5 + euro credit, CAPE, ERP, 3 momentum rows
    assert cov["blind_spots"] == settings()["coverage"]["blind_spots"]


def test_dashboard_matches_the_api_models(summary):
    """report.build checks every section against the model the API serves it with; a field the app doesn't know
    fails the build, naming it."""
    import copy

    from radar.reporting import dashboard

    dashboard.check(summary["_dash"])
    bad = copy.deepcopy(summary["_dash"])
    bad["rotation"]["groups"][0]["surprise"] = 1
    with pytest.raises(ValueError, match="rotation doesn't match api_models.RotationView: groups.0.surprise"):
        dashboard.check(bad)


def test_quality_and_value_scores(summary):
    """The world's statements reach the Quality & value section: the best business ranks first in its region,
    the bank is scored on the financial set, and momentum rows and holdings carry the scores."""
    d = summary["_dash"]
    us = next(r for r in d["quality"]["regions"] if r["key"] == "us")
    assert us["coverage"] == {"stocks": 6, "quality": 5, "value": 5, "edgar": 0, "yahoo": 6}
    by = {r["ticker"]: r for r in us["rows"]}
    assert us["rows"][0]["ticker"] == "S1" and by["S1"]["rank_q"] == 1
    assert by["S1"]["quality"] > by["S5"]["quality"]
    # the world's only bank: measured on the financial set, but with no other bank to rank it against, no score
    assert by["S6"]["fund_set"] == "financial" and by["S6"]["fcf_yield"] is None and by["S6"]["roe"] > 0
    assert by["S6"]["quality"] is None and by["S6"]["q_n"] == 0 and by["S6"]["rank_qv"] is None
    # ~14 months of prices: no complete calendar year for the dividend record, so three pillars, not four
    assert by["S1"]["momentum"] is not None and by["S1"]["q_n"] == 3 and by["S1"]["q_record"] is None
    mom = next(r for r in d["momentum"]["regions"] if r["key"] == "us")["rows"]
    assert all("quality" in r for r in mom)
    s1 = next(r for r in summary["me"] if r["symbol"] == "S1")
    assert s1["quality"] == by["S1"]["quality"]
    assert summary["quality_top10"]["us"][0]["ticker"] == "S1"
    assert summary["quality_coverage"]["europe"]["quality"] == 3


def test_dashboard_charts_and_rotation_graph(summary):
    d = summary["_dash"]
    acwi = d["regime"]["charts"][0]
    assert acwi["title"].startswith("Global trend") and [s["name"] for s in acwi["series"]][0] == "ACWI"
    assert acwi["series"][0]["values"][-1] == pytest.approx(100 * 1.0004 ** (N - 1))
    assert len(acwi["series"][0]["dates"]) == len(acwi["series"][0]["values"]) == min(N, 756)
    sectors = next(g for g in d["rotation"]["groups"] if g["key"] == "sectors")
    trail = {t["ticker"]: t for t in sectors["rrg"]}
    assert trail["LEAD"]["quadrant"] == "Leading" and trail["LAG"]["quadrant"] == "Lagging"
    assert len(trail["LEAD"]["tail"]) == settings()["rotation"]["tail"]
    assert trail["LEAD"]["tail"][-1]["date"] == d["asof"]           # the current week isn't dated after the data
    # every row the summary has, plus the fields only the app shows
    assert {"rs_ratio", "rs_mom", "r3m", "above200"} <= set(sectors["rows"][0])


def test_full_momentum_rows_are_kept(summary):
    us = next(r for r in summary["_dash"]["momentum"]["regions"] if r["key"] == "us")
    assert us["label"] == "US" and [r["ticker"] for r in us["rows"]] == ["S1", "S2", "S3", "S4", "S5", "S6"]
    assert us["rows"][0]["r12_1"] is not None and us["rows"][0]["trend_ok"] is True


def test_regime_rows_are_graded_but_the_summary_is_unchanged(summary):
    assert all("gauge" not in i for i in summary["indicators"])                  # the brief's contract
    rows = {i["name"].split(" (")[0]: i for i in summary["_dash"]["regime"]["indicators"]}
    vix = rows["Volatility"]["gauge"]
    assert vix["scale"] == "sequential" and vix["score"] <= 0 and vix["label"] == "calm"   # VIX 14 < calm 18
    assert rows["Breadth – US"]["gauge"]["level"] > 0                              # risk-on breadth reads green
    assert rows["Copper/gold ratio"]["gauge"] is None                              # no data: not graded


def test_table_rows_are_graded(summary):
    us = next(r for r in summary["_dash"]["momentum"]["regions"] if r["key"] == "us")
    assert us["rows"][0]["gauges"]["score"]["label"] in ("leader", "strong")
    sectors = next(g for g in summary["_dash"]["rotation"]["groups"] if g["key"] == "sectors")
    lead = next(r for r in sectors["rows"] if r["ticker"] == "LEAD")
    assert lead["gauges"]["rs_ratio"]["level"] > 0
    assert all("gauges" not in r for r in summary["momentum_top10"]["us"])        # the brief's contract
