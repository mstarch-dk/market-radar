import json

import numpy as np
import pandas as pd
import pytest

from radar import ingest, report
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


def test_shadow_return_partial_sell_keeps_both_sides_proportional():
    px = _series([100, 110, 121])
    one = _series([1.0] * 3)
    bench = _series([10.0, 10.0, 12.0])
    tx = pd.DataFrame({"date": [px.index[0], px.index[1]], "type": ["BUY", "SELL"], "quantity": [10.0, 4.0],
                       "price": [100.0, 110.0]})
    pos, shadow = _vs_shadow(tx, px, one, bench)
    assert pos == pytest.approx(0.21) and shadow == pytest.approx(0.2)   # a sale doesn't change either return
    tx_all = tx.assign(quantity=[10.0, 10.0])
    assert _vs_shadow(tx_all, px, one, bench) is None                    # fully sold: no open position


def test_shadow_return_is_in_dkk():
    px = _series([100.0, 100.0])                 # flat in USD...
    usddkk = _series([6.0, 6.6])                 # ...but the dollar rose 10% against DKK
    tx = pd.DataFrame({"date": [px.index[0]], "type": ["BUY"], "quantity": [1.0], "price": [100.0]})
    pos, shadow = _vs_shadow(tx, px, usddkk, _series([60.0, 60.0]))
    assert pos == pytest.approx(0.10) and shadow == pytest.approx(0.0)


def test_fx_to_dkk_handles_pence_and_unknown_currencies():
    closes = pd.DataFrame({"GBPDKK=X": [8.5, np.nan, 8.6], "USDDKK=X": [6.9, 7.0, 7.1]},
                          index=pd.bdate_range("2026-01-05", periods=3))
    assert report._fx_to_dkk(closes, "GBp").tolist() == pytest.approx([0.085, 0.085, 0.086])   # pence, ffilled
    assert report._fx_to_dkk(closes, "GBP").iloc[-1] == pytest.approx(8.6)
    assert (report._fx_to_dkk(closes, "DKK") == 1.0).all()
    assert report._fx_to_dkk(closes, "XYZ") is None and report._fx_to_dkk(closes, None) is None
    assert report._fx_to_dkk(closes, "SEK") is None             # rate not downloaded: no silent 1.0


def test_pct_vs_is_the_mean_percentile_against_the_region():
    dist = pd.DataFrame({"r12_1": [0.1, 0.2, 0.3, 0.4], "r6m": [0.1, 0.2, 0.3, 0.4], "r3m": [0.1, 0.2, 0.3, 0.4]})
    row = pd.Series({"r12_1": 0.35, "r6m": 0.05, "r3m": 0.25})
    assert report._pct_vs(dist, row) == pytest.approx(round(100 * (0.75 + 0 + 0.5) / 3, 1))
    assert report._pct_vs(dist, row.copy().replace(0.35, np.nan)) is None


def test_records_are_json_safe():
    df = pd.DataFrame({"a": [np.nan, np.inf], "b": [np.int64(3), np.float64(1.5)], "c": [pd.Timestamp("2026-10-13"), None],
                       "d": [True, False]})
    rows = report._records(df)
    assert rows[0] == {"a": None, "b": 3, "c": "2026-10-13", "d": True} and rows[1]["a"] is None
    json.dumps(rows)


# ---------------- update_prices: the stored history ----------------

@pytest.fixture
def price_store(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "DATA", tmp_path)
    monkeypatch.setattr(ingest, "PRICES_FILE", tmp_path / "prices.parquet")
    monkeypatch.setattr(ingest, "settings", lambda: {"history_years": 1})
    calls = []

    def install(world: dict[str, pd.DataFrame]):
        def fake(tickers, start):
            calls.append((sorted(tickers), start))
            frames = [w[w["date"] >= pd.Timestamp(start)] for t, w in world.items() if t in tickers]
            return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=ingest.COLUMNS)
        monkeypatch.setattr(ingest, "_download", fake)
    return install, calls


def _hist(ticker, closes, start="2026-09-01", factor=1.0):
    d = _bars(ticker, [c * factor for c in closes], start)
    return d.assign(high=d["close"], low=d["close"], raw_close=closes, volume=1)[ingest.COLUMNS]


def test_update_prices_appends_new_bars_without_duplicates(price_store):
    install, calls = price_store
    install({"A": _hist("A", list(range(100, 120)))})
    ingest.update_prices(["A"])
    install({"A": _hist("A", list(range(100, 125)))})            # five more sessions
    res = ingest.update_prices(["A", "GONE"])
    stored = ingest.load_prices()
    assert len(stored) == 25 and not stored.duplicated(["ticker", "date"]).any()
    assert res["missing"] == ["GONE"] and res["rebased"] == []
    assert calls[-1][0] == ["A"] and calls[-1][1] < stored["date"].iloc[19].date()   # overlap re-fetched


def test_update_prices_replaces_a_rebased_history_wholesale(price_store):
    install, calls = price_store
    install({"A": _hist("A", list(range(100, 120))), "B": _hist("B", list(range(50, 70)))})
    ingest.update_prices(["A", "B"])
    ancient = _hist("A", [90.0], start="2020-01-02")              # stored back when history_years was longer
    pd.concat([ancient, ingest.load_prices()]).to_parquet(ingest.PRICES_FILE, index=False)
    # A paid a dividend: Yahoo now reports every earlier adjusted close 2% lower
    install({"A": _hist("A", list(range(100, 121)), factor=0.98), "B": _hist("B", list(range(50, 71)))})
    res = ingest.update_prices(["A", "B"])
    assert res["rebased"] == ["A"]
    a = ingest.load_prices().query("ticker == 'A'")
    assert len(a) == 21 and (a["close"] / a["raw_close"]).round(6).eq(0.98).all()   # one adjustment basis only
    assert a["date"].min() > pd.Timestamp("2020-01-02")          # the old-basis bar is gone, not kept
    assert len(ingest.load_prices().query("ticker == 'B'")) == 21


def test_wide_fills_holidays_but_not_dead_tickers():
    p = pd.concat([_bars("LIVE", [1.0] * 12), _bars("DEAD", [2.0] * 3)])
    w = ingest.wide(p)
    assert w["LIVE"].notna().all()
    assert w["DEAD"].notna().sum() == 3 + 5                     # five sessions forward-filled, then gaps
