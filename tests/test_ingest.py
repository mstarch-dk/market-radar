"""The Yahoo price download offline: batches, tickers missing from a batch, frames without Adj Close, and the
exchange-local calendar day."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from radar import net
from radar.progress import Progress, labelled
from radar.sources import ingest

# ---------------- Yahoo price download ----------------

def _bars(n=3, start="2026-10-06", adj=True):
    idx = pd.DatetimeIndex(pd.bdate_range(start, periods=n), name="Date")
    close = np.arange(100.0, 100.0 + n)
    df = pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1, "Close": close,
                       "Adj Close": close * 0.5, "Volume": 1000}, index=idx)
    return df if adj else df.drop(columns="Adj Close")


class _FakeYf:
    def __init__(self, answer):
        self.answer, self.asked = answer, []

    def download(self, batch, **kw):
        self.asked.append(list(batch))
        return self.answer(list(batch))


@pytest.fixture
def fake_yf(monkeypatch):
    monkeypatch.setattr(ingest, "BATCH", 2)
    monkeypatch.setattr(net, "install_yfinance", lambda: None)

    def install(answer):
        fake = _FakeYf(answer)
        monkeypatch.setattr(ingest, "yf", fake)
        return fake
    return install


def _multi(batch, **frames):
    return pd.concat({t: frames.get(t, _bars()) for t in batch}, axis=1)


def test_the_download_asks_in_batches_and_concatenates_them(fake_yf):
    fake = fake_yf(lambda b: _multi(b) if len(b) > 1 else _bars())
    progress = []
    out = ingest.download_bars(["A", "B", "C", "D", "E"], date(2026, 10, 1), lambda d, t: progress.append((d, t)))
    assert fake.asked == [["A", "B"], ["C", "D"], ["E"]]
    assert progress == [(0, 5), (2, 5), (4, 5), (5, 5)]          # 0 before the first batch, done after each
    assert sorted(out["ticker"].unique()) == ["A", "B", "C", "D", "E"] and len(out) == 15
    assert list(out.columns) == ingest.COLUMNS


def test_a_tracker_hears_the_phase_by_name_and_unusable_tickers_at_once(fake_yf):
    fake_yf(lambda b: _multi(b, A=_bars(adj=False)))
    p = Progress()
    ingest.download_bars(["A", "B", "C"], date(2026, 10, 1), labelled(p, "Known tickers (new bars)"))
    s = p.snapshot()
    assert s["phase"] == {"done": 3, "total": 3, "label": "Known tickers (new bars)"}
    assert [i["level"] for i in s["issues"]] == ["warn"] and "A" in s["issues"][0]["message"]


def test_a_ticker_missing_from_its_batch_is_skipped(fake_yf):
    fake_yf(lambda b: _multi([t for t in b if t != "B"]))
    out = ingest.download_bars(["A", "B", "C", "D"], date(2026, 10, 1))
    assert sorted(out["ticker"].unique()) == ["A", "C", "D"]


def test_a_single_ticker_batch_with_flat_columns_is_read_as_that_ticker(fake_yf):
    fake_yf(lambda b: _multi(b) if len(b) > 1 else _bars(n=2))
    out = ingest.download_bars(["A", "B", "C"], date(2026, 10, 1))
    c = out[out["ticker"] == "C"]
    assert len(c) == 2 and c["close"].tolist() == [50.0, 50.5] and c["raw_close"].tolist() == [100.0, 101.0]


def test_an_empty_batch_is_skipped_and_the_others_kept(fake_yf):
    fake_yf(lambda b: pd.DataFrame() if b == ["C", "D"] else _multi(b))
    out = ingest.download_bars(["A", "B", "C", "D"], date(2026, 10, 1))
    assert sorted(out["ticker"].unique()) == ["A", "B"]


def test_a_frame_without_adj_close_fails_clearly_or_skips_that_ticker(fake_yf):
    fake_yf(lambda b: _multi(b, A=_bars(adj=False)))
    try:
        out = ingest.download_bars(["A", "B"], date(2026, 10, 1))
    except KeyError:
        raise AssertionError("bare KeyError") from None
    except ValueError:
        return                                   # a clear error naming the column is fine too
    assert out["ticker"].unique().tolist() == ["B"]


@pytest.mark.parametrize("tz, stamps", [
    ("Europe/Berlin", ["2026-10-06 00:00", "2026-10-07 00:00"]),      # UTC: the evening before
    ("America/New_York", ["2026-10-06 00:00", "2026-10-07 00:00"]),
    ("Asia/Tokyo", ["2026-10-06 00:00", "2026-10-07 00:00"]),         # UTC: 15:00 the day before
    ("America/New_York", ["2026-10-06 21:30", "2026-10-07 21:30"]),   # UTC: already the next day
])
def test_norm_dates_keeps_the_exchange_local_calendar_day(tz, stamps):
    df = pd.DataFrame({"date": pd.DatetimeIndex(stamps).tz_localize(tz), "close": [1.0, 2.0]})
    out = ingest.norm_dates(df)
    assert out["date"].tolist() == [pd.Timestamp("2026-10-06"), pd.Timestamp("2026-10-07")]
    assert out["date"].dt.tz is None
    assert df["date"].dt.tz is not None          # the input isn't changed


def test_an_answer_where_no_ticker_has_adj_close_says_the_format_changed(fake_yf):
    fake_yf(lambda b: _multi(b, A=_bars(adj=False), B=_bars(adj=False)))
    with pytest.raises(ValueError, match="Adj Close"):
        ingest.download_bars(["A", "B"], date(2026, 10, 1))


def test_norm_dates_drops_the_time_of_day_on_naive_dates():
    out = ingest.norm_dates(pd.DataFrame({"date": pd.to_datetime(["2026-10-06 16:00", "2026-10-07 00:00"])}))
    assert out["date"].tolist() == [pd.Timestamp("2026-10-06"), pd.Timestamp("2026-10-07")]


# ---------------- weekend stubs ----------------
# A `radar run` on Sunday 25 Oct 2026: Yahoo answered with a Sunday bar for the FX pairs (Friday's close again, no
# volume). Stored, it put a Sunday into every wide frame, ACWI forward-filled Friday's close into it, and the
# report's as-of date (the benchmark's last session) became the Sunday.

def _with_sunday_stub(bars: pd.DataFrame) -> pd.DataFrame:
    stub = bars.iloc[[-1]].copy()
    stub.index = pd.DatetimeIndex([pd.Timestamp("2026-10-25")], name="Date")
    stub["Volume"] = 0
    return pd.concat([bars, stub])


def test_a_sunday_stub_from_yahoo_is_not_kept_as_a_session(fake_yf):
    bars = _with_sunday_stub(_bars(5, "2026-10-19"))
    fake_yf(lambda b: _multi(b, A=bars, B=bars))
    out = ingest.download_bars(["A", "B"], date(2026, 10, 19))
    a = out[out["ticker"] == "A"]
    assert a["date"].max() == pd.Timestamp("2026-10-23")             # Friday, not the Sunday
    assert len(a) == 5 and (pd.to_datetime(out["date"]).dt.dayofweek < 5).all()


def test_a_sunday_stub_in_a_tz_aware_answer_is_dropped_on_the_local_calendar_day(fake_yf):
    bars = _with_sunday_stub(_bars(5, "2026-10-19"))
    bars.index = bars.index.tz_localize("Europe/London")
    fake_yf(lambda b: _multi(b, A=bars, B=bars))
    out = ingest.norm_dates(ingest.download_bars(["A", "B"], date(2026, 10, 19)))
    assert out.loc[out["ticker"] == "A", "date"].max() == pd.Timestamp("2026-10-23")


def test_a_stored_sunday_stub_is_not_a_session_and_the_next_update_drops_it(tmp_data, monkeypatch):
    from radar.market import Market
    from radar.paths import PRICES_FILE

    week = pd.bdate_range("2026-10-19", "2026-10-23")
    rows = [pd.DataFrame({"date": week, "ticker": t, "high": c, "low": c, "close": c, "raw_close": c,
                          "volume": v}) for t, c, v in (("ACWI", 156.8, 1e6), ("USDDKK=X", 6.66, 0.0))]
    stub = pd.DataFrame({"date": [pd.Timestamp("2026-10-25")], "ticker": "USDDKK=X", "high": 6.66, "low": 6.66,
                         "close": 6.66, "raw_close": 6.66, "volume": 0.0})
    PRICES_FILE.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([*rows, stub], ignore_index=True).to_parquet(PRICES_FILE, index=False)   # as an older version stored it

    market = Market.load()
    assert market.closes["ACWI"].dropna().index[-1] == pd.Timestamp("2026-10-23")
    assert pd.Timestamp("2026-10-25") not in market.closes.index

    monkeypatch.setattr(ingest, "download_bars", lambda tickers, start, progress=None: pd.DataFrame(
        columns=ingest.COLUMNS))
    res = ingest.update_prices(["ACWI", "USDDKK=X"], bench="ACWI", today=date(2026, 10, 25))
    assert res["asof"] == "2026-10-23" and res["behind"] == {}
    assert (pd.read_parquet(PRICES_FILE)["date"].dt.dayofweek < 5).all()
