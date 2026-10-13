import numpy as np
import pandas as pd

from radar.report import _clusters
from radar.signals import regime

CFG = {"vix_calm": 18, "vix_stress": 25, "breadth_strong": 60, "breadth_weak": 40, "highs_lows_band": 3,
       "vix_term_calm": 0.9, "rates_shock": 0.5, "copper_gold_band": 0.05, "oil_shock": 0.30, "revisions_band": 0.5}
MACRO = {"VIX": "^VIX", "VIX3M": "^VIX3M", "Copper": "HG=F", "Gold": "GC=F", "Oil (WTI)": "CL=F"}


def _closes(n=300):
    idx = pd.bdate_range("2025-06-02", periods=n)
    up = np.linspace(100, 150, n)
    return pd.DataFrame({
        "ACWI": up, "S1": up, "S2": up, "S3": up[::-1],
        "^VIX": 30.0, "^VIX3M": 25.0,                 # inverted term structure
        "HG=F": up, "GC=F": 100.0,                    # copper/gold rising
        "CL=F": np.r_[np.full(n - 63, 60.0), np.full(63, 90.0)],  # +50% in 3 months
    }, index=idx)


def _by_name(inds):
    return {i["name"].split(" (")[0]: i for i in inds}


def test_net_highs_lows_counts_highs_minus_lows():
    s = regime.net_highs_lows(_closes(), ["S1", "S2", "S3"])
    assert round(s.iloc[-1], 1) == round(100 * (2 - 1) / 3, 1)


def test_indicators_new_votes():
    closes = _closes()
    fred_idx = pd.bdate_range("2026-01-01", periods=100)
    fred = pd.DataFrame({"T10Y2Y": -0.2, "DGS10": np.linspace(4.0, 5.0, 100)}, index=fred_idx)
    cli = pd.DataFrame([{"area": "G20", "label": "G20", "asof": pd.Timestamp("2026-09-01"), "cli": 99.0,
                         "chg_3m": -0.4, "phase": "Contraction"}])
    fs = {"quarter": "Q3 2026", "growth_now": 29.5, "growth_start": 26.7, "guidance_pos": 72, "guidance_neg": 44,
          "report_date": pd.Timestamp("2026-10-09")}
    inds, _ = regime.indicators(closes, fred, "ACWI", {"us": ["S1", "S2", "S3"]}, {"us": "US"}, MACRO, CFG, cli, fs)
    st = {k: v["status"] for k, v in _by_name(inds).items()}
    assert st["VIX term structure"] == regime.OFF
    assert st["Yield curve"] == regime.OFF          # inverted
    assert st["US 10Y yield"] == regime.OFF         # +~0.6 in 3 months
    assert st["Copper/gold ratio"] == regime.ON
    assert st["Oil"] == regime.OFF                  # oil shock
    assert st["Leading indicators"] == regime.OFF
    assert st["Earnings revisions"] == regime.ON
    assert st["New highs – new lows"] == regime.ON


def test_indicators_without_optional_inputs_show_as_na():
    closes = _closes()[["ACWI", "S1", "S2"]]
    inds, _ = regime.indicators(closes, pd.DataFrame(), "ACWI", {"us": ["S1", "S2"]}, {"us": "US"}, {}, CFG)
    st = {k: v["status"] for k, v in _by_name(inds).items()}
    assert st["Global trend"] != regime.NA and st["Breadth – US"] != regime.NA
    for name in ("Credit", "Yield curve", "US 10Y yield", "US dollar", "Volatility", "Leading indicators",
                 "Earnings revisions"):
        assert st[name] == regime.NA, name
    o = regime.overall(inds)
    assert o["na"] == sum(s == regime.NA for s in st.values()) and o["total"] == len(inds)
    assert o["on"] + o["off"] + o["neutral"] + o["na"] + o["stale"] == o["total"]


def test_stale_factset_stops_voting():
    closes = _closes()
    fs = {"quarter": "Q3 2026", "growth_now": 29.5, "growth_start": 26.7, "guidance_pos": None, "guidance_neg": None,
          "report_date": pd.Timestamp("2026-06-05")}
    inds, _ = regime.indicators(closes, pd.DataFrame(), "ACWI", {"us": ["S1", "S2", "S3"]}, {"us": "US"}, MACRO, CFG,
                                factset=fs)
    before = regime.overall(inds)
    regime.apply_freshness(inds, closes.index[-1], {"factset": 14, "prices": 7})
    row = _by_name(inds)["Earnings revisions"]
    assert row["status"] == regime.STALE and "not counted" in row["note"]
    after = regime.overall(inds)
    assert after["on"] == before["on"] - 1 and after["stale"] == 1
    assert _by_name(inds)["Global trend"]["status"] != regime.STALE  # prices are current


def test_clusters_need_overrepresentation():
    region = pd.DataFrame({"ticker": [f"T{i}" for i in range(40)],
                           "industry": ["Semis"] * 4 + ["Banks"] * 16 + ["Other"] * 20,
                           "sector": ["Tech"] * 4 + ["Fin"] * 16 + ["Misc"] * 20})
    top = region.iloc[[0, 1, 2, 4, 5, 6, 20, 21, 22, 23]].assign(new=[True, False, False] + [False] * 7)
    out = {c["name"]: c for c in _clusters(top, region, min_count=3, min_ratio=1.5)}
    assert out["Semis"]["count"] == 3 and out["Semis"]["new"] == 1   # 3 vs 1.0 expected
    assert "Banks" not in out                                        # 3 vs 4.0 expected: normal weight
    assert "Tech" not in out                                         # same names as the Semis cluster
