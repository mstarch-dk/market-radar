import numpy as np
import pandas as pd
import pytest

from radar.signals import rotation
from radar.tracked import Instrument

N = 300
IDX = pd.bdate_range("2025-08-01", periods=N)
RRG_LEAD = (109.44352, 101.492552)  # RS-Ratio, RS-Momentum of LEAD below


def _inst(t, group="sectors"):
    return Instrument(t, f"{t} fund", group, "us")


def _closes(**cols):
    bench = 100 * 1.0004 ** np.arange(N)
    return pd.DataFrame({"ACWI": bench, **cols}, index=IDX)


def test_quadrant_mapping():
    assert rotation.quadrant(101, 101) == "Leading"
    assert rotation.quadrant(101, 99) == "Weakening"
    assert rotation.quadrant(99, 99) == "Lagging"
    assert rotation.quadrant(99, 101) == "Improving"
    assert rotation.quadrant(np.nan, 101) == "n/a"


def test_rrg_places_a_fresh_outperformer_leading_and_a_fading_one_weakening():
    t = np.arange(N)
    bench = 100 * 1.0004 ** t
    lead = bench * np.r_[np.ones(N - 60), 1.003 ** np.arange(60)]          # started beating ACWI 3 months ago
    peak = np.r_[np.ones(N - 60), 1.004 ** np.arange(40)]                  # beat it, then gave some back
    fade = bench * np.r_[peak, peak[-1] * 0.999 ** np.arange(20)]
    lag = bench * np.r_[np.ones(N - 60), 0.997 ** np.arange(60)]
    closes = _closes(LEAD=lead, FADE=fade, LAG=lag)
    ratio, mom = rotation.rrg(closes, "ACWI", ["LEAD", "FADE", "LAG"], window=14, tail=8)
    q = {k: rotation.quadrant(ratio[k].iloc[-1], mom[k].iloc[-1]) for k in ratio}
    assert q == {"LEAD": "Leading", "FADE": "Weakening", "LAG": "Lagging"}
    assert len(ratio) == 8                                                  # the tail, in weeks
    # pinned values: a change to the RRG method (smoothing, windows) must be a deliberate one
    assert (ratio["LEAD"].iloc[-1], mom["LEAD"].iloc[-1]) == pytest.approx(RRG_LEAD, abs=1e-6)


def test_relative_returns_rank_and_minimum_history():
    t = np.arange(N)
    closes = _closes(FAST=100 * 1.001 ** t, SLOW=100 * 1.0002 ** t, OTHER=100 * 1.0005 ** t,
                     YOUNG=np.r_[np.full(N - 100, np.nan), 100 * 1.002 ** np.arange(100)])
    insts = [_inst("FAST"), _inst("SLOW"), _inst("OTHER", "themes"), _inst("YOUNG"), _inst("NOT_LOADED")]
    df = rotation.relative_table(closes, "ACWI", insts, 14, 8).set_index("ticker")
    assert set(df.index) == {"FAST", "SLOW", "OTHER"}                       # < 130 bars and unknown tickers drop
    assert df.loc["FAST", "r3m"] == pytest.approx(1.001 ** 63 - 1)
    assert df.loc["FAST", "rel_r3m"] == pytest.approx((1.001 ** 63 - 1) - (1.0004 ** 63 - 1))
    assert df.loc["SLOW", "rel_r6m"] < 0
    w = df.loc["FAST"]
    assert w["rs_score"] == pytest.approx(0.2 * w["rel_r1m"] + 0.4 * w["rel_r3m"] + 0.4 * w["rel_r6m"])
    assert (df.loc["FAST", "rank"], df.loc["SLOW", "rank"], df.loc["OTHER", "rank"]) == (1, 2, 1)  # per group


def test_stale_etf_is_compared_with_the_benchmark_over_the_same_dates():
    acwi = 100 * 1.0004 ** np.arange(N) * np.r_[np.ones(N - 15), 1.003 ** np.arange(1, 16)]  # rallied lately
    stale = np.r_[acwi[:N - 15], np.full(15, np.nan)]                       # tracked ACWI, then stopped updating
    closes = pd.DataFrame({"ACWI": acwi, "STALE": stale}, index=IDX)
    df = rotation.relative_table(closes, "ACWI", [_inst("STALE")], 14, 8).set_index("ticker")
    # windows ending on its last bar: no relative performance, rather than missing 15 days of ACWI gains
    # (ingest.wide() forward-fills up to 5 days, so a stale ticker still carries up to a week of that error;
    # coverage lists it under stale tickers)
    assert df.loc["STALE", "rel_r1m"] == pytest.approx(0.0, abs=1e-12)
    assert df.loc["STALE", "rel_r3m"] == pytest.approx(0.0, abs=1e-12)
