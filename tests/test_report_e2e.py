"""report.build() end to end on a small synthetic market whose answers are known in advance.

Unit tests check each calculation; this checks the wiring between them: that the right series reach the
right signal and land under the right key in summary.json (and that the template still renders).
"""
import json
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from radar import external, report, snapshot, universe
from radar.config import settings

N = 300
END = pd.Timestamp(date.today())
IDX = pd.bdate_range(end=END, periods=N)
T = np.arange(N)
G = {"ACWI": 0.0004, "S1": 0.0012, "S2": 0.0010, "S3": 0.0008, "S4": 0.0006, "S5": 0.0004, "S6": 0.0002,
     "E1": 0.0009, "E2": 0.0005, "E3": 0.0001, "THEME1": 0.0007, "THEME2": 0.0003}
BUY_AT = 50

UNIVERSE = {
    "benchmark": {"ticker": "ACWI", "name": "MSCI ACWI"},
    "watchlist": [],
    "etf_groups": {
        "sectors": {"label": "Sectors", "region": "us",
                    "items": [{"ticker": "LEAD", "name": "Leader"}, {"ticker": "LAG", "name": "Laggard"}]},
        "themes": {"label": "Themes", "region": "global",
                   "items": [{"ticker": "THEME1", "name": "Theme one"}, {"ticker": "THEME2", "name": "Theme two"}]},
    },
    "stock_groups": {"us": {"label": "US", "tickers": ["S1", "S2", "S3", "S4", "S5", "S6"]},
                     "europe": {"label": "Europe", "tickers": ["E1", "E2", "E3"]}},
    "macro": {"yahoo": {"VIX": "^VIX", "VIX3M": "^VIX3M", "Copper": "HG=F", "Gold": "GC=F", "Oil (WTI)": "CL=F"},
              "fred": {"BAMLH0A0HYM2": "US high-yield spread", "T10Y2Y": "US 10Y-2Y curve", "DGS10": "US 10Y yield",
                       "DTWEXBGS": "USD broad index"}},
    "external": {"cot": {}, "oecd_cli": {"G20": "G20"}},
}


def _closes() -> dict[str, np.ndarray]:
    c = {t: 100 * (1 + g) ** T for t, g in G.items()}
    acwi = c["ACWI"]
    # LEAD started beating ACWI three months ago; LAG started trailing it
    c["LEAD"] = acwi * np.r_[np.ones(N - 60), 1.003 ** np.arange(60)]
    c["LAG"] = acwi * np.r_[np.ones(N - 60), 0.997 ** np.arange(60)]
    c["^VIX"], c["^VIX3M"], c["USDDKK=X"] = np.full(N, 14.0), np.full(N, 16.0), np.full(N, 6.5)
    return c


def _prices() -> pd.DataFrame:
    return pd.concat([pd.DataFrame({"date": IDX, "ticker": t, "high": v * 1.01, "low": v * 0.99, "close": v,
                                    "raw_close": v, "volume": 1000.0}) for t, v in _closes().items()],
                     ignore_index=True)


def _fred() -> pd.DataFrame:
    return pd.DataFrame({"BAMLH0A0HYM2": np.linspace(4.0, 3.0, N), "T10Y2Y": 0.5, "DGS10": 4.0,
                         "DTWEXBGS": 120.0}, index=IDX)


@pytest.fixture
def summary(tmp_data, monkeypatch):
    monkeypatch.setattr(report, "REPORTS", tmp_data / "reports")
    monkeypatch.setattr(snapshot, "SNAPSHOTS", tmp_data / "snapshots")
    monkeypatch.setattr(report, "universe_config", lambda: UNIVERSE)
    monkeypatch.setattr(universe, "universe_config", lambda: UNIVERSE)
    monkeypatch.setattr(report, "load_prices", _prices)
    monkeypatch.setattr(report, "load_fred", _fred)
    for fn in ("load_cot", "load_oecd_cli", "load_factset", "load_analyst"):
        monkeypatch.setattr(external, fn, pd.DataFrame)
    monkeypatch.setattr(universe, "names", lambda ts: {t: f"{t} name" for t in ts})
    monkeypatch.setattr(universe, "currencies", lambda ts: {t: "USD" for t in ts})
    monkeypatch.setattr(universe, "sectors", lambda ts: pd.DataFrame(
        {"sector": "Tech", "industry": "Software"}, index=pd.Index(ts, name="ticker")))

    buy_px = 100 * 1.0012 ** BUY_AT
    (tmp_data / "holdings.csv").write_text(
        "symbol,status,quantity,avg_price,first_trade,last_sell_date,last_sell_price\n"
        f"S1,holding,10,{buy_px},{IDX[BUY_AT].date()},,\nE2,watch,,,,,\n", encoding="utf-8")
    (tmp_data / "transactions.csv").write_text(
        f"symbol,date,type,quantity,price\nS1,{IDX[BUY_AT].date()},BUY,10,{buy_px}\n", encoding="utf-8")

    # snapshots from 10 days ago: LEAD ranked 2nd, and the US top list held S2 and a stock that has left
    old = date.today() - timedelta(days=10)
    snapshot.save("rotation", pd.DataFrame({"ticker": ["LAG", "LEAD"], "rank": [1, 2], "score": [0, 0],
                                            "group": "sectors"}), old)
    snapshot.save("momentum", pd.DataFrame({"ticker": ["S2", "OLD"], "rank": [1, 2], "score": [0, 0],
                                            "region": "us"}), old)

    res = report.build()
    assert (tmp_data / "reports" / "radar.html").stat().st_size > 10_000
    out = json.loads((tmp_data / "reports" / "summary.json").read_text(encoding="utf-8"))
    return out | {"_res": res}


def test_summary_schema(summary):
    assert set(summary) - {"_res"} == {
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
