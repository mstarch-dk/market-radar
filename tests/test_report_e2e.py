"""report.build() end to end on a small synthetic market whose answers are known in advance.

Unit tests check each calculation; this checks the wiring between them: that the right series reach the
right signal and land under the right key in summary.json and dashboard.json.
"""
import json
from datetime import date, timedelta

import pandas as pd
import pytest

import world
from radar import report, snapshot, universe
from radar.config import settings
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
        "earnings_factset", "stale_tickers", "coverage"}
    assert summary["asof"] == IDX[-1].date().isoformat()


def test_regime_votes(summary):
    st = {i["name"].split(" (")[0]: i["status"] for i in summary["indicators"]}
    on = {"Global trend", "Breadth – US", "Breadth – Europe", "New highs – new lows", "Volatility",
          "VIX term structure", "Credit"}
    assert {k for k, v in st.items() if v == "risk-on"} == on
    assert {k for k, v in st.items() if v == "n/a"} == {"Equal vs cap weight", "Copper/gold ratio", "Oil",
                                                        "Leading indicators", "Earnings revisions"}
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


def test_holding_return_against_the_shadow_benchmark(summary):
    me = {r["symbol"]: r for r in summary["me"]}
    held = N - 1 - BUY_AT
    assert me["S1"]["since_buy"] == pytest.approx(1.0012 ** held - 1, rel=1e-9)
    assert me["S1"]["bench_since_buy"] == pytest.approx(1.0004 ** held - 1, rel=1e-9)
    assert "trend intact" in me["S1"]["flags"] and me["E2"]["status"] == "watch"


def test_coverage(summary):
    cov = summary["coverage"]
    assert set(cov["missing_tickers"]) == {"HG=F", "GC=F", "CL=F"} | {
        fx for fx in universe.FX_DKK.values() if fx and fx != "USDDKK=X"}
    assert summary["stale_tickers"] == []
    src = {s["key"]: s for s in cov["sources"]}
    assert src["prices"]["status"] == "ok" and src["fred"]["status"] == "ok"
    assert src["cftc"]["status"] == src["oecd"]["status"] == src["factset"]["status"] == "missing"
    assert cov["regime"]["current"] == len(summary["indicators"]) - 5
    assert cov["blind_spots"] == settings()["coverage"]["blind_spots"]


def test_dashboard_matches_the_api_models(summary):
    from radar import api_models as m

    d = summary["_dash"]
    head = {"asof": d["asof"], "generated": d["generated"]}
    m.RegimeView.model_validate(head | d["regime"])
    m.RotationView.model_validate(head | d["rotation"])
    m.MomentumView.model_validate(head | d["momentum"])
    m.PositioningView.model_validate(head | d["positioning"])
    m.CoverageView.model_validate(head | d["coverage"])


def test_dashboard_charts_and_rotation_graph(summary):
    d = summary["_dash"]
    acwi = d["regime"]["charts"][0]
    assert acwi["title"].startswith("Global trend") and [s["name"] for s in acwi["series"]][0] == "ACWI"
    assert acwi["series"][0]["values"][-1] == pytest.approx(100 * 1.0004 ** (N - 1))
    assert len(acwi["series"][0]["dates"]) == len(acwi["series"][0]["values"]) == min(N, 365)
    sectors = next(g for g in d["rotation"]["groups"] if g["key"] == "sectors")
    trail = {t["ticker"]: t for t in sectors["rrg"]}
    assert trail["LEAD"]["quadrant"] == "Leading" and trail["LAG"]["quadrant"] == "Lagging"
    assert len(trail["LEAD"]["tail"]) == settings()["rotation"]["tail"]
    # every row the summary has, plus the fields only the app shows
    assert {"rs_ratio", "rs_mom", "r3m", "above200"} <= set(sectors["rows"][0])


def test_full_momentum_rows_are_kept(summary):
    us = next(r for r in summary["_dash"]["momentum"]["regions"] if r["key"] == "us")
    assert us["label"] == "US" and [r["ticker"] for r in us["rows"]] == ["S1", "S2", "S3", "S4", "S5", "S6"]
    assert us["rows"][0]["r12_1"] is not None and us["rows"][0]["trend_ok"] is True
