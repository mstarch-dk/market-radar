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
