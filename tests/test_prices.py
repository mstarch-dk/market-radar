import numpy as np
import pandas as pd
import pytest

from radar import ingest
from radar.report import _vs_shadow


def _bars(ticker, closes, start="2026-01-05"):
    idx = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame({"ticker": ticker, "date": idx, "close": closes})


def test_adjust_scales_high_low_by_the_dividend_factor():
    raw = pd.DataFrame({"Date": pd.bdate_range("2026-01-05", periods=2), "High": [102.0, 98.0], "Low": [99.0, 95.0],
                        "Close": [100.0, 96.0], "Adj Close": [95.0, 96.0], "Volume": [10, 20]})
    out = ingest._adjust(raw, "X")
    assert list(out.columns) == ingest.COLUMNS
    assert out["high"].tolist() == pytest.approx([96.9, 98.0])
    assert out["low"].tolist() == pytest.approx([94.05, 95.0])
    assert out["raw_close"].tolist() == [100.0, 96.0]


def test_rescaled_flags_tickers_whose_history_was_rebased():
    old = pd.concat([_bars("DIV", [100.0, 101, 102, 103]), _bars("FLAT", [50.0, 51, 52, 53])])
    # overlap = last two stored bars; DIV went ex-dividend after them, so Yahoo scaled them by 0.95
    new = pd.concat([_bars("DIV", [102 * 0.95, 103 * 0.95, 98.0], start="2026-01-07"),
                     _bars("FLAT", [52.0, 53.5, 54.0], start="2026-01-07")])  # last bar corrected, not rebased
    assert ingest.rescaled(old, new) == ["DIV"]
    assert ingest.rescaled(old.iloc[0:0], new) == []


def _series(values, start="2026-01-05"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_shadow_return_counts_dividends_received_since_buy():
    # traded at 100, 5 dividend goes ex on day 3, price back to 100 by the end
    raw = _series([100, 100, 95, 100])
    adj = _series([95, 95, 95, 100])          # pre-ex bars scaled by 0.95
    one = _series([1.0] * 4)
    tx = pd.DataFrame({"date": [raw.index[0]], "type": ["BUY"], "quantity": [10.0], "price": [100.0]})
    pos, bench = _vs_shadow(tx, adj, one, _series([10.0] * 4), raw)
    assert pos == pytest.approx(100 / 95 - 1)  # +5.3%: price flat, dividend reinvested
    assert bench == pytest.approx(0.0)
    assert _vs_shadow(tx, adj, one, _series([10.0] * 4))[0] == pytest.approx(0.0)  # price-only without raw


def test_shadow_return_lot_bought_after_ex_date_gets_no_dividend():
    raw = _series([100, 100, 95, 100])
    adj = _series([95, 95, 95, 100])
    one = _series([1.0] * 4)
    tx = pd.DataFrame({"date": [raw.index[0], raw.index[2]], "type": ["BUY", "BUY"], "quantity": [10.0, 10.0],
                       "price": [100.0, 95.0]})
    pos, _ = _vs_shadow(tx, adj, one, _series([10.0] * 4), raw)
    value = 10 * 100 / 95 * 100 + 10 * 100   # first lot reinvested the dividend, second lot didn't
    assert pos == pytest.approx(value / 1950 - 1)
    assert np.isfinite(pos)
