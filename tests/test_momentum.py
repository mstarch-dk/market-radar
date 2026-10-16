import numpy as np
import pandas as pd
import pytest

from radar.signals import momentum

N = 300
IDX = pd.bdate_range("2025-08-01", periods=N)


def _geo(g: float, n: int = N) -> np.ndarray:
    """Price growing by `g` per bar, so an n-bar return is exactly (1+g)**n - 1."""
    return 100 * (1 + g) ** np.arange(n)


def _frame(**cols) -> pd.DataFrame:
    return pd.DataFrame(cols, index=IDX[-len(next(iter(cols.values()))):])


def test_return_windows_and_12_1_skip_the_last_month():
    closes = _frame(UP=_geo(0.001))
    m = momentum.metrics(closes, closes * 0 + 1000, ["UP"], 200).set_index("ticker").loc["UP"]
    assert m["r1m"] == pytest.approx(1.001 ** 21 - 1)
    assert m["r3m"] == pytest.approx(1.001 ** 63 - 1)
    assert m["r6m"] == pytest.approx(1.001 ** 126 - 1)
    assert m["r12_1"] == pytest.approx(1.001 ** (252 - 21) - 1)        # from 252 bars ago to 21 bars ago
    assert m["from_high"] == pytest.approx(0.0)
    assert m["sma50"] == pytest.approx(_geo(0.001)[-50:].mean())
    assert bool(m["above50"]) and bool(m["above200"]) and bool(m["trend_ok"])


def test_short_history_blanks_long_term_fields():
    c = np.r_[np.full(N - 150, np.nan), _geo(0.001, 150)]               # listed 150 bars ago
    closes = _frame(NEW=c)
    m = momentum.metrics(closes, closes * 0 + 1, ["NEW"], 200).set_index("ticker").loc["NEW"]
    assert pd.isna(m["r12_1"]) and pd.isna(m["sma200"])
    assert pd.isna(m["above200"]) and pd.isna(m["trend_ok"])            # unknown, not False
    assert m["r3m"] == pytest.approx(1.001 ** 63 - 1)                   # short windows still work


def test_from_high_and_volume_surge():
    c = np.r_[_geo(0.002, N - 40), np.full(40, _geo(0.002, N - 40)[-1] * 0.8)]
    v = np.r_[np.full(N - 20, 100.0), np.full(20, 300.0)]
    closes, volumes = _frame(X=c), _frame(X=v)
    m = momentum.metrics(closes, volumes, ["X"], 200).set_index("ticker").loc["X"]
    assert m["from_high"] == pytest.approx(-0.2)
    assert m["vol_surge"] == pytest.approx(300 / ((100 * 100 + 20 * 300) / 120))


def test_score_is_mean_percentile_and_nan_without_full_history():
    closes = _frame(A=_geo(0.003), B=_geo(0.002), C=_geo(0.001),
                    D=np.r_[np.full(N - 150, np.nan), _geo(0.004, 150)])
    lead = momentum.leaders(closes, closes * 0 + 1, {"us": ["A", "B", "C", "D", "MISSING"]}, 200).set_index("ticker")
    assert "MISSING" not in lead.index
    assert pd.isna(lead.loc["D", "score"])                              # no 12-1 return: not ranked as a leader
    assert lead.loc["A", "score"] > lead.loc["B", "score"] > lead.loc["C", "score"]
    assert lead.loc["A", "rank"] == 1 and lead.loc["C", "rank"] == 3
    # D has no 12-1 return but its faster 6m/3m returns still count in those rankings, so A has 2 of 3 names
    # strictly below it on 12-1 and 2 of 4 on 6m and 3m (model.score: the share strictly below)
    assert lead.loc["A", "score"] == pytest.approx(round((2 / 3 + 2 / 4 + 2 / 4) / 3 * 100, 1))


def test_ranks_are_per_region():
    closes = _frame(A=_geo(0.003), B=_geo(0.001), X=_geo(0.0005), Y=_geo(0.0002))
    lead = momentum.leaders(closes, closes * 0 + 1, {"us": ["A", "B"], "europe": ["X", "Y"]}, 200)
    top = lead[lead["rank"] == 1].set_index("region")["ticker"]
    assert top.to_dict() == {"us": "A", "europe": "X"}
