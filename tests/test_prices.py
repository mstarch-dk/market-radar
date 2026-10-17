import json

import numpy as np
import pandas as pd
import pytest

from radar import dashboard, ingest, paths, tracked, universe
from radar.mine import _vs_shadow
from radar.model.score import score_vs


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
    assert universe.fx_to_dkk(closes, "GBp").tolist() == pytest.approx([0.085, 0.085, 0.086])   # pence, ffilled
    assert universe.fx_to_dkk(closes, "GBP").iloc[-1] == pytest.approx(8.6)
    assert (universe.fx_to_dkk(closes, "DKK") == 1.0).all()
    assert universe.fx_to_dkk(closes, "XYZ") is None and universe.fx_to_dkk(closes, None) is None
    assert universe.fx_to_dkk(closes, "SEK") is None             # rate not downloaded: no silent 1.0


def test_won_and_taiwan_dollar_cross_via_usd():
    from radar import universe
    closes = pd.DataFrame({"USDDKK=X": [7.0, 6.8, np.nan], "USDKRW=X": [1400.0, np.nan, 1360.0],
                           "USDTWD=X": [32.0, 34.0, 34.0]}, index=pd.date_range("2025-01-01", periods=3))
    assert universe.fx_to_dkk(closes, "KRW").tolist() == pytest.approx([0.005, 6.8 / 1400, 0.005])   # ffilled
    assert universe.fx_to_dkk(closes, "TWD").tolist() == pytest.approx([7 / 32, 0.2, 0.2])
    assert universe.fx_to_dkk(closes.drop(columns="USDKRW=X"), "KRW") is None   # either leg missing: no rate
    assert universe.fx_to_dkk(closes.drop(columns="USDDKK=X"), "TWD") is None
    rates = universe.dkk_rates({"USDDKK=X": 6.8, "USDKRW=X": 1360.0, "GBPDKK=X": 8.6})
    assert rates == pytest.approx({"DKK": 1.0, "USD": 6.8, "GBP": 8.6, "KRW": 0.005})   # no TWD, no GBp
    assert "KRW" not in universe.dkk_rates({"USDKRW=X": 1360.0})


def test_pct_vs_is_the_mean_percentile_against_the_region():
    dist = pd.DataFrame({"r12_1": [0.1, 0.2, 0.3, 0.4], "r6m": [0.1, 0.2, 0.3, 0.4], "r3m": [0.1, 0.2, 0.3, 0.4]})
    row = pd.Series({"r12_1": 0.35, "r6m": 0.05, "r3m": 0.25})
    assert score_vs(dist, row) == pytest.approx(round(100 * (0.75 + 0 + 0.5) / 3, 1))
    assert score_vs(dist, row.copy().replace(0.35, np.nan)) is None


def test_records_are_json_safe():
    df = pd.DataFrame({"a": [np.nan, np.inf], "b": [np.int64(3), np.float64(1.5)], "c": [pd.Timestamp("2026-10-13"), None],
                       "d": [True, False]})
    rows = dashboard._records(df)
    assert rows[0] == {"a": None, "b": 3, "c": "2026-10-13", "d": True} and rows[1]["a"] is None
    json.dumps(rows)


# ---------------- update_prices: the stored history ----------------

@pytest.fixture
def price_store(tmp_path, monkeypatch):
    paths.configure(paths.Locations.flat(tmp_path))
    monkeypatch.setattr(ingest, "settings", lambda: {"history_years": 1})
    calls = []

    def install(world: dict[str, pd.DataFrame]):
        def fake(tickers, start, progress=None):
            calls.append((sorted(tickers), start))
            frames = [w[w["date"] >= pd.Timestamp(start)] for t, w in world.items() if t in tickers]
            return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=ingest.COLUMNS)
        monkeypatch.setattr(ingest, "download_bars", fake)
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


def test_a_rebased_history_is_downloaded_again_and_kept_on_one_basis(price_store):
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
    assert len(a) == 22 and (a["close"] / a["raw_close"]).round(6).eq(0.98).all()   # one adjustment basis only
    assert a["date"].min() == pd.Timestamp("2020-01-02")         # the older bar is kept, moved to the new basis
    assert len(ingest.load_prices().query("ticker == 'B'")) == 21


def test_wide_fills_holidays_but_not_dead_tickers():
    p = pd.concat([_bars("LIVE", [1.0] * 12), _bars("DEAD", [2.0] * 3)])
    w = ingest.wide(p)
    assert w["LIVE"].notna().all()
    assert w["DEAD"].notna().sum() == 3 + 5                     # five sessions forward-filled, then gaps


def test_a_deeper_start_downloads_a_shallow_history_again_once(price_store):
    from datetime import date
    install, calls = price_store
    long = _hist("A", list(np.linspace(50, 120, 1800)), start="2020-01-02")
    late = _hist("B", list(range(50, 70)))                              # listed long after the start
    install({"A": long, "B": late})
    ingest.update_prices(["A", "B"])                                   # history_years back only
    assert ingest.load_prices().query("ticker == 'A'")["date"].min() > pd.Timestamp("2025-01-01")
    deep = date(2021, 1, 4)
    res = ingest.update_prices(["A", "B"], start=deep)
    a = ingest.load_prices().query("ticker == 'A'")
    assert res["deepened"] == 2 and a["date"].min() == pd.Timestamp(deep) and not a.duplicated("date").any()
    assert json.loads((ingest.CACHE / ingest.FROM_FILE).read_text())["B"] == deep.isoformat()
    res = ingest.update_prices(["A", "B"], start=deep)                 # remembered: not again, B neither
    assert res["deepened"] == 0 and calls[-1][1] > deep
    # a dividend re-bases A: the full download goes back to the deep start, not history_years
    install({"A": long.assign(close=long["close"] * 0.98), "B": late})
    res = ingest.update_prices(["A", "B"], start=deep)
    assert res["rebased"] == ["A"] and ingest.load_prices().query("ticker == 'A'")["date"].min() == pd.Timestamp(deep)


def test_history_start_reaches_back_before_your_first_trade(tmp_data, monkeypatch):
    from datetime import date

    from radar import universe, userstore
    monkeypatch.setattr(universe, "settings", lambda: {"history_years": 3,
                                                       "backtest": {"warmup_days": 400, "max_years": 10}})
    today = date(2026, 10, 14)
    assert universe.history_start(today) == date(2023, 10, 15)       # no trades: history_years
    pid = userstore.save_portfolio({"name": "Real"})
    userstore.add_tx({"symbol": "A", "date": "2023-02-08", "type": "BUY", "quantity": 1, "price": 1, "portfolio_id": pid})
    assert universe.history_start(today) == date(2022, 1, 4)          # 400 days before the first trade
    userstore.add_tx({"symbol": "A", "date": "2010-01-04", "type": "BUY", "quantity": 1, "price": 1, "portfolio_id": pid})
    assert universe.history_start(today) == date(2016, 10, 14)        # capped at max_years


def test_a_full_download_that_ends_early_keeps_the_newer_stored_bars(price_store):
    from datetime import date
    install, calls = price_store
    n = len(pd.bdate_range("2025-01-02", "2026-09-28"))
    a, b = _hist("A", list(np.linspace(50, 120, n)), start="2025-01-02"), _hist("B", [60.0] * n, start="2025-01-02")
    install({"A": a, "B": b})
    ingest.update_prices(["A", "B"])                                    # history_years back
    # the deeper download of both ends two sessions early (Yahoo's long history lagging); B was also re-based
    install({"A": a.iloc[:-2], "B": b.iloc[:-2].assign(close=59.0)})
    res = ingest.update_prices(["A", "B"], start=date(2025, 1, 2))
    assert res["deepened"] == 2
    p = ingest.load_prices()
    pa, pb = p.query("ticker == 'A'"), p.query("ticker == 'B'")
    assert pa["date"].max() == pd.Timestamp("2026-09-28") and pa["close"].iloc[-1] == 120   # kept, same basis
    assert pa["date"].min() == pd.Timestamp("2025-01-02") and not pa.duplicated("date").any()
    assert pb["date"].max() == pd.Timestamp("2026-09-28") and pb["close"].eq(59.0).all()   # kept, on the new basis


def test_tickers_without_the_benchmarks_last_session_are_asked_again(price_store, monkeypatch):
    install, calls = price_store
    world = {"BENCH": _hist("BENCH", list(range(10, 30))), "EU": _hist("EU", list(range(100, 120))),
             "HOL": _hist("HOL", list(range(50, 69)))}           # HOL: a holiday on the last session
    lagging = {"EU": world["EU"].iloc[:-1]}                      # Yahoo's first answer lacks EU's last bar
    install(world)

    def fake(tickers, start, progress=None):
        calls.append((sorted(tickers), start))
        src = lagging if len(calls) == 1 else world
        frames = [src.get(t, world[t]) for t in tickers]
        return pd.concat([f[f["date"] >= pd.Timestamp(start)] for f in frames], ignore_index=True)
    monkeypatch.setattr(ingest, "download_bars", fake)
    res = ingest.update_prices(["BENCH", "EU", "HOL"], bench="BENCH")
    assert calls[1][0] == ["EU", "HOL"]                          # one catch-up for the two behind
    assert ingest.load_prices().query("ticker == 'EU'")["date"].max() == pd.Timestamp("2026-09-28")
    assert res["behind"] == {"HOL": "2026-09-25"} and res["asof"] == "2026-09-28"
    assert ingest.update_prices(["EU"])["behind"] == {}          # no benchmark given: nothing to compare with


def test_profile_refresh_fetches_a_tracked_tickers_missing_sessions(monkeypatch):
    from types import SimpleNamespace

    from radar import profile, universe
    idx = pd.bdate_range("2026-10-01", periods=5)
    closes = pd.DataFrame({"ACWI": range(5), "RHM.DE": [1.0, 2, 3, 4, np.nan]}, index=idx, dtype=float)
    market = SimpleNamespace(closes=closes)
    calls = []
    monkeypatch.setattr(tracked, "benchmark", lambda: "ACWI")
    monkeypatch.setattr(universe, "all_price_tickers", lambda **kw: ["ACWI", "RHM.DE"])
    monkeypatch.setattr(ingest, "update_prices", lambda t, **kw: calls.append((t, kw)))
    monkeypatch.setattr(profile.Market, "load", classmethod(lambda cls: market))
    profile.ensure_prices("RHM.DE", market)
    assert calls == []                                           # tracked: the daily update brings it
    profile.ensure_prices("RHM.DE", market, refresh=True)
    assert calls == [(["RHM.DE"], {})]


# ---------------- a full download never shrinks the stored history (hardening 1.1, 2.1) ----------------

TODAY = __import__("datetime").date(2026, 10, 15)


def test_a_full_download_that_starts_late_keeps_the_older_bars_and_tries_again(price_store):
    from datetime import date
    install, calls = price_store
    install({"A": _hist("A", list(np.linspace(50, 80, 260)), start="2025-10-16")})
    ingest.update_prices(["A"], today=TODAY)                           # a year, as history_years says
    stored_first = ingest.load_prices()["date"].min()
    # asked to go deeper, Yahoo answers with a history that starts later than the one stored
    install({"A": _hist("A", list(np.linspace(70, 80, 100)), start="2026-05-25")})
    res = ingest.update_prices(["A"], start=date(2024, 10, 1), today=TODAY)
    a = ingest.load_prices()
    assert a["date"].min() == stored_first and not a.duplicated("date").any()
    assert res["short"] == {"A": "2026-05-25"}
    assert json.loads((ingest.CACHE / ingest.FROM_FILE).read_text())["A"] != "2024-10-01"   # not marked done
    calls.clear()
    ingest.update_prices(["A"], start=date(2024, 10, 1), today=TODAY)
    assert calls[0] == (["A"], date(2024, 10, 1))                      # so the next run asks again


def test_older_bars_on_another_basis_are_rescaled_at_the_seam(price_store):
    from datetime import date
    install, calls = price_store
    install({"A": _hist("A", list(np.linspace(50, 80, 260)), start="2025-10-16")})
    ingest.update_prices(["A"], today=TODAY)
    # a dividend re-based Yahoo's history by 0.98, and the deeper answer starts late
    install({"A": _hist("A", list(np.linspace(70, 80, 100)), start="2026-05-25", factor=0.98)})
    ingest.update_prices(["A"], start=date(2024, 10, 1), today=TODAY)
    a = ingest.load_prices()
    assert a["date"].min() == pd.Timestamp("2025-10-16")
    assert (a["close"] / a["raw_close"]).round(6).eq(0.98).all()      # one adjustment basis throughout


def test_a_legacy_store_keeps_the_tickers_yahoo_did_not_return(price_store):
    install, calls = price_store
    legacy = pd.concat([_hist("A", [10.0] * 20), _hist("B", [20.0] * 20)]).drop(columns="raw_close")
    legacy.to_parquet(ingest.PRICES_FILE, index=False)                 # stored before raw closes were kept
    install({"A": _hist("A", [10.0] * 21)})
    ingest.update_prices(["A", "B"], today=TODAY)
    p = ingest.load_prices()
    assert len(p.query("ticker == 'A'")) == 21 and p.query("ticker == 'A'")["raw_close"].notna().all()
    b = p.query("ticker == 'B'")
    assert len(b) == 20 and b["raw_close"].isna().all()                # kept; its traded close is unknown, not 0


def test_two_writers_at_once_keep_each_others_tickers(price_store, monkeypatch):
    import threading
    install, calls = price_store
    world = {"A": _hist("A", [10.0] * 20), "B": _hist("B", [20.0] * 20)}
    started, release = threading.Event(), threading.Event()

    def download(tickers, start, progress=None):
        if tickers == ["A"]:            # the long update: downloads while the app adds B
            started.set()
            release.wait(5)
        return pd.concat([world[t][world[t]["date"] >= pd.Timestamp(start)] for t in tickers], ignore_index=True)
    monkeypatch.setattr(ingest, "download_bars", download)
    slow = threading.Thread(target=ingest.update_prices, args=(["A"],), kwargs={"today": TODAY})
    slow.start()
    started.wait(5)
    ingest.update_prices(["B"], today=TODAY)                           # a ticker lookup in the app meanwhile
    release.set()
    slow.join(10)
    assert set(ingest.load_prices()["ticker"]) == {"A", "B"}
