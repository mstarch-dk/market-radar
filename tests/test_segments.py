"""Attribution's benchmark segments (portfolios/segments.py): ACWI's weights drifted from the weekly snapshots and
rolled back before the first, and segment returns from the proxy ETFs, missing (never 0) where a proxy is."""
import numpy as np
import pandas as pd
import pytest

from radar.portfolios import segments
from radar.sources import tracked

D = pd.bdate_range("2026-03-02", periods=6)


class FakePrices:
    """Prices.dkk for hand-made DKK closes."""

    def __init__(self, closes: dict[str, list[float]], index=D):
        self.closes = {t: pd.Series(v, index=index[-len(v):], dtype=float) for t, v in closes.items()}

    def dkk(self, t):
        return self.closes.get(t)


def _snaps(rows: dict[str, dict[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows).T.rename(index=pd.Timestamp).sort_index()


def test_backdrift_rolls_the_first_snapshot_back_with_the_returns():
    rets = pd.DataFrame({"A": [np.nan, 0.10, 0.0, 0.0, 0.0, 0.0], "B": [np.nan, 0.0, 0.0, 0.0, 0.0, 0.0]}, index=D)
    snaps = _snaps({"2026-03-04": {"A": 0.6, "B": 0.4}})     # the snapshot is on D[2], after A's +10 % on D[1]
    w, basis = segments.drifted_weights(snaps, rets, D)
    # before the gain A weighed 0.6/1.1 against 0.4: renormalised
    a0 = (0.6 / 1.1) / (0.6 / 1.1 + 0.4)
    assert w.loc[D[0], "A"] == pytest.approx(a0) and w.loc[D[1], "A"] == pytest.approx(0.6)
    assert list(basis) == ["back-drifted", "back-drifted", "snapshot", "snapshot", "snapshot", "snapshot"]
    assert np.allclose(w.sum(axis=1), 1.0)


def test_weights_drift_forward_from_the_last_snapshot():
    rets = pd.DataFrame({"A": [np.nan, 0.0, 0.0, 0.20, 0.0, 0.0], "B": 0.0}, index=D)
    snaps = _snaps({"2026-03-03": {"A": 0.5, "B": 0.5}, "2026-03-06": {"A": 0.5, "B": 0.5}})
    w, _ = segments.drifted_weights(snaps, rets, D)
    assert w.loc[D[2], "A"] == pytest.approx(0.5)
    assert w.loc[D[3], "A"] == pytest.approx(0.6 / 1.1)       # +20 % on D[3], drifted
    assert w.loc[D[4], "A"] == pytest.approx(0.5)             # the next snapshot resets it


def test_a_missing_return_leaves_the_weights_missing_not_frozen():
    rets = pd.DataFrame({"A": [np.nan, 0.01, np.nan, 0.01, 0.01, 0.01], "B": 0.0}, index=D)
    snaps = _snaps({"2026-03-05": {"A": 0.5, "B": 0.5}})      # D[3]
    w, basis = segments.drifted_weights(snaps, rets, D)
    assert w.loc[D[:2]].isna().all().all() and basis.iloc[:2].isna().all()   # the gap on D[2] lies between
    assert w.loc[D[2:]].notna().all().all()
    weightless = _snaps({"2026-03-05": {"A": 0.0, "B": 1.0}})                 # a key that weighs nothing
    w, _ = segments.drifted_weights(weightless, rets, D)
    assert w.notna().all().all()


def test_stepped_weights_take_the_last_snapshot_or_the_first():
    snaps = _snaps({"2026-03-03": {"X": 1.0}, "2026-03-05": {"X": 2.0}})
    s = segments.stepped_weights(snaps, D)["X"].tolist()
    assert s == [1.0, 1.0, 1.0, 2.0, 2.0, 2.0]


def test_sector_returns_fall_back_before_the_proxy_and_stay_missing_without_one(monkeypatch):
    conf = {"sector_etfs": {"us": {"Technology": "XLK", "Energy": "XLE"}},
            "attribution": {"sectors": {"Technology": "XDWT", "Energy": "XDW0", "Utilities": "XDWU"},
                            "sector_fallback": "us"}}
    monkeypatch.setattr(segments, "universe_config", lambda: conf)
    px = FakePrices({"XDWT": [10, 11, 11, 11], "XLK": [100, 110, 121, 121, 121, 121], "XLE": [50] * 6})
    r, notes = segments.sector_returns(px, D)
    assert r["Technology"].iloc[1:3].tolist() == pytest.approx([0.10, 0.10])     # XLK before XDWT's first return
    assert r["Technology"].iloc[3] == pytest.approx(0.10)                         # XDWT's own, from D[3]
    assert r["Technology"].iloc[4] == 0.0
    assert r["Energy"].iloc[1:].eq(0.0).all()                                      # all fallback
    assert r["Utilities"].isna().all()                                             # no proxy, no fallback: missing
    assert any("XLK" in n for n in notes) and any("Utilities" in n and "missing" in n for n in notes)
    monkeypatch.setattr(tracked, "universe_config", lambda: conf)
    assert tracked.attribution_tickers() == {"XDWT", "XDW0", "XDWU", "XLK", "XLE"}


def test_region_returns_mix_countries_and_need_the_coverage(monkeypatch):
    conf = {"attribution": {"regions": {"europe": {"United Kingdom": "EWU", "Germany": "EWG"},
                                        "asia": {"Japan": "EWJ"}}}}
    monkeypatch.setattr(segments, "universe_config", lambda: conf)
    px = FakePrices({"EWU": [100, 110] * 3, "EWG": [100, 100] * 3, "EWJ": [100, 101, 102, 103, 104, 105]})
    w = pd.DataFrame({"europe|United Kingdom": 0.3, "europe|Germany": 0.1, "europe|Ireland": 0.05,
                      "asia|Japan": 0.05, "asia|Taiwan": 0.05}, index=D)
    r, cover = segments.region_returns(px, D, w)
    assert cover["europe"].iloc[0] == pytest.approx(0.4 / 0.45)                    # Ireland has no proxy
    assert r["europe"].iloc[1] == pytest.approx(0.75 * 0.10)                       # 3:1 UK to Germany
    assert cover["asia"].iloc[0] == pytest.approx(0.5) and r["asia"].isna().all()  # under min_proxy_coverage


def test_currency_mix_from_the_snapshot_on_or_before_the_day():
    h = pd.DataFrame({"asof": ["2026-03-03"] * 3 + ["2026-03-10"] * 2,
                      "dim": ["sector_currency"] * 3 + ["sector_currency"] * 2,
                      "key": ["Technology|USD", "Technology|EUR", "Energy|USD", "Technology|USD", "Energy|USD"],
                      "weight": [0.3, 0.1, 0.1, 0.4, 0.1]})
    first = segments.currency_mix(h, "sector", pd.Timestamp("2026-03-01"))      # before any: the first
    assert first["Technology"] == pytest.approx({"USD": 0.75, "EUR": 0.25}) and first["Energy"] == {"USD": 1.0}
    assert segments.currency_mix(h, "sector", pd.Timestamp("2026-03-11"))["Technology"] == {"USD": 1.0}
