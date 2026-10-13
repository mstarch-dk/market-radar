import numpy as np
import pandas as pd
import pytest

from radar.signals import technicals

IDX = pd.bdate_range("2025-01-01", periods=300)


def _s(values):
    return pd.Series(np.asarray(values, dtype=float), index=IDX[:len(values)])


def test_rsi_extremes_and_balance():
    assert technicals.rsi(_s(np.arange(100, 160))).iloc[-1] == 100.0
    assert technicals.rsi(_s(np.arange(160, 100, -1))).iloc[-1] == pytest.approx(0.0)
    assert technicals.rsi(_s([100.0] * 40)).iloc[-1] == 50.0
    zigzag = _s([100 + (i % 2) for i in range(200)])                  # +1, -1, +1, ... equal gains and losses
    assert technicals.rsi(zigzag).iloc[-1] == pytest.approx(50.0, abs=2)
    assert technicals.rsi(_s(np.arange(100, 110))).isna().all()        # fewer than 14 changes


def test_rsi_matches_wilder_by_hand():
    c = _s([44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28,
            46.28, 46.00, 46.03, 46.41, 46.22, 45.64])
    d = c.diff()
    up, dn = d.clip(lower=0), -d.clip(upper=0)
    ag, al = up.iloc[1:15].mean(), dn.iloc[1:15].mean()               # seeded with a simple average
    for i in range(15, len(c)):
        ag, al = (ag * 13 + up.iloc[i]) / 14, (al * 13 + dn.iloc[i]) / 14
    wilder = 100 - 100 / (1 + ag / al)
    assert technicals.rsi(c).iloc[-1] == pytest.approx(wilder, abs=1e-9)
    first = 100 - 100 / (1 + up.iloc[1:15].mean() / dn.iloc[1:15].mean())
    assert technicals.rsi(c).iloc[14] == pytest.approx(first) and np.isnan(technicals.rsi(c).iloc[13])
    # StockCharts' worked example on the same closes (their table rounds the averages, hence the tolerance)
    published = [70.53, 66.32, 66.55, 69.41, 66.36, 57.97]
    assert technicals.rsi(c).iloc[14:].tolist() == pytest.approx(published, abs=0.1)


def test_macd_sign_follows_the_trend():
    up = technicals.macd(_s(100 * 1.002 ** np.arange(200)))
    down = technicals.macd(_s(100 * 0.998 ** np.arange(200)))
    assert up["macd"].iloc[-1] > 0 > down["macd"].iloc[-1]
    assert up["hist"].iloc[-1] == pytest.approx(up["macd"].iloc[-1] - up["signal"].iloc[-1])
    assert up["macd"].iloc[:25].isna().all()


def test_bollinger_pct_b():
    c = _s([100.0, 102.0] * 15)
    b = technicals.bollinger(c, 20, 2.0).iloc[-1]
    assert b["mid"] == pytest.approx(101.0) and b["upper"] == pytest.approx(103.0)
    assert b["pct_b"] == pytest.approx(0.75)                           # 102 is a quarter below the top band


def test_volatility_drawdown_and_beta():
    rng = np.random.default_rng(7)
    bench = _s(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 300))))
    lev = _s(100 * np.cumprod(1 + 2 * bench.pct_change().fillna(0).to_numpy()))   # twice the daily moves
    beta, corr = technicals.beta_corr(lev, bench)
    assert beta == pytest.approx(2.0, abs=0.15) and corr > 0.98
    assert technicals.realised_vol(bench) == pytest.approx(0.01 * np.sqrt(252), rel=0.25)
    assert technicals.max_drawdown(_s([100, 120, 90, 110, 95])) == pytest.approx(90 / 120 - 1)
    assert np.isnan(technicals.beta_corr(bench.iloc[:60], bench.iloc[:60])[0])  # too few weeks
