import numpy as np
import pandas as pd
import pytest

from radar import coverage
from radar.dashboard import _clusters
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
    voting = [i for i in inds if i["group"] != regime.CONTEXT]
    assert o["na"] == sum(i["status"] == regime.NA for i in voting) and o["total"] == len(voting) == len(inds) - 3
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


def _votes(on=0, off=0, neutral=0, na=0):
    return ([{"status": regime.ON}] * on + [{"status": regime.OFF}] * off + [{"status": regime.NEUTRAL}] * neutral
            + [{"status": regime.NA}] * na)


def test_overall_label_thresholds():
    assert regime.overall(_votes(on=2, off=1))["label"] == "Risk-on"       # net 1/3 clears the 0.33 bar
    assert regime.overall(_votes(on=3, off=2))["label"] == "Mixed"         # net 0.2
    assert regime.overall(_votes(on=3, off=1))["label"] == "Risk-on"       # net 0.5
    assert regime.overall(_votes(on=1, off=3))["label"] == "Risk-off"
    assert regime.overall(_votes(neutral=5, na=3))["label"] == "Mixed"     # nothing votes
    o = regime.overall(_votes(on=2, neutral=10, na=5))
    assert o["label"] == "Risk-on" and o["net"] == 1.0                     # neutral and n/a rows don't dilute


def test_breadth_history_counts_only_stocks_with_a_full_window():
    idx = pd.bdate_range("2025-01-01", periods=260)
    closes = pd.DataFrame({"UP": np.linspace(100, 200, 260), "DOWN": np.linspace(200, 100, 260),
                           "NEW": np.r_[np.full(160, np.nan), np.linspace(100, 150, 100)]}, index=idx)
    h = regime.breadth_history(closes, ["UP", "DOWN", "NEW", "GONE"])
    assert h.index[0] == idx[199] and h.iloc[-1] == 50.0                   # NEW has no 200d average yet


def test_short_macro_history_shows_na_instead_of_crashing():
    closes = _closes()
    for t in ("HG=F", "GC=F", "CL=F"):
        closes[t] = np.r_[np.full(len(closes) - 30, np.nan), np.full(30, 50.0)]   # just added to the universe
    closes["RSP"], closes["SPY"] = closes["HG=F"], closes["HG=F"]
    inds, _ = regime.indicators(closes, pd.DataFrame(), "ACWI", {"us": ["S1", "S2", "S3"]}, {"us": "US"}, MACRO, CFG)
    st = {k: v["status"] for k, v in _by_name(inds).items()}
    assert st["Copper/gold ratio"] == st["Oil"] == st["Equal vs cap weight"] == regime.NA


def test_dollar_uses_the_same_3_month_window_as_the_other_rows():
    closes = _closes()
    fred = pd.DataFrame({"DTWEXBGS": np.r_[np.full(37, 100.0), np.full(63, 110.0)]},
                        index=pd.bdate_range("2026-01-01", periods=100))
    inds, _ = regime.indicators(closes, fred, "ACWI", {"us": ["S1"]}, {"us": "US"}, MACRO, CFG)
    assert _by_name(inds)["US dollar"]["value"] == "+10.0% over 3m"      # 63 bars back, like _chg


def test_breadth_row_uses_the_200_day_average():
    closes = _closes()
    n = len(closes)
    closes["V"] = np.r_[np.linspace(150, 90, n - 40), np.linspace(90, 100, 40)]   # recovering, still below 200d
    inds, _ = regime.indicators(closes, pd.DataFrame(), "ACWI", {"us": ["S1", "V"]}, {"us": "US"}, MACRO, CFG)
    row = _by_name(inds)["Breadth – US"]
    assert row["value"] == "50% > 200d" and "100% above 50d" in row["note"]


def _momentum_world(n=600, k=50, reverse_at=None):
    """k stocks with steady drifts from -0.1% to +0.2% a day; from `reverse_at` on, every drift flips sign."""
    idx = pd.bdate_range("2023-01-02", periods=n)
    g = np.linspace(-0.001, 0.002, k)
    steps = np.tile(g, (n, 1))
    if reverse_at is not None:
        steps[reverse_at:] *= -1
    c = pd.DataFrame(100 * np.cumprod(1 + steps, axis=0), index=idx, columns=[f"T{i:02d}" for i in range(k)])
    c["ACWI"] = 100 * 1.0003 ** np.arange(n)
    return c


def test_momentum_payoff_follows_the_winners():
    tickers = [f"T{i:02d}" for i in range(50)]
    assert regime.momentum_payoff(_momentum_world(), tickers, 63) > 0          # winners kept winning
    assert regime.momentum_payoff(_momentum_world(reverse_at=600 - 63), tickers, 63) < 0   # and then reversed
    assert np.isnan(regime.momentum_payoff(_momentum_world(n=300), tickers, 63))          # too little history
    assert np.isnan(regime.momentum_payoff(_momentum_world(), tickers[:20], 63))          # too few names


def test_dispersion_is_the_interquartile_spread():
    c = _momentum_world()
    tickers = [f"T{i:02d}" for i in range(50)]
    d = regime.dispersion_history(c, tickers)
    r = c[tickers].iloc[-1] / c[tickers].iloc[-64] - 1
    assert d.iloc[-1] == pytest.approx(r.quantile(0.75) - r.quantile(0.25))
    assert d.index[0] == c.index[63] and regime.dispersion_history(c, tickers[:10]).empty


def test_momentum_rows_never_vote():
    c = _momentum_world()
    cfg = CFG | {"momentum_payoff_band": 0.02, "dispersion_low_pct": 20, "dispersion_high_pct": 80, "crash_rebound": 0.05}
    groups = {"us": [f"T{i:02d}" for i in range(50)]}
    inds, _ = regime.indicators(c, pd.DataFrame(), "ACWI", groups, {"us": "US"}, {}, cfg)
    rows = _by_name(inds)
    for name in ("Momentum payoff", "Return dispersion", "Momentum-crash setup"):
        assert rows[name]["status"] == regime.NEUTRAL and rows[name]["group"] == regime.CONTEXT, name
        assert rows[name]["votes"] is False, name
    # context rows stay out of the vote, the voting groups and the coverage count, whatever the switches say
    o = regime.overall(inds, {"context": True})
    assert o["total"] == len(inds) - 3 and o["not_voting"] == 3 and "context" not in o["voting_groups"]
    assert coverage.regime_counts(inds)["total"] == len(inds) - 3
    assert rows["Momentum payoff"]["value"].startswith("+") and rows["Momentum-crash setup"]["value"] == "no"
    # a falling ACWI over two years that jumps in the last month: the crash setup
    c2 = c.copy()
    c2["ACWI"] = np.r_[np.linspace(120, 80, 579), np.linspace(80, 90, 21)]
    crash = _by_name(regime.indicators(c2, pd.DataFrame(), "ACWI", groups, {"us": "US"}, {}, cfg)[0])
    assert crash["Momentum-crash setup"]["value"] == "yes"
