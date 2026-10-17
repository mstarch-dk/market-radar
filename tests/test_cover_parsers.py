"""Coverage for the update steps and the parsers' error branches: small hand-made answers in the real formats."""
import io
import re
from datetime import date

import numpy as np
import pandas as pd
import pytest

from radar import coverage, external, factors, ingest, net, sentiment, trades, updater, valuation
from radar.fundamentals import edgar, yahoo

# ---------------- updater: one failing step never stops the rest ----------------

def test_a_failing_step_is_recorded_and_the_next_steps_still_run(tmp_data):
    ran, lines = [], []

    def boom():
        ran.append("b")
        raise RuntimeError("source down")
    updater._steps({"a": ("Step A", lambda: ran.append("a") or "3 rows"),
                    "b": ("Step B", boom),
                    "c": ("Step C", lambda: ran.append("c") or "fine")}, lines.append)
    assert ran == ["a", "b", "c"]
    log = coverage.load_log()
    assert log["a"]["detail"] == "3 rows" and log["a"]["error"] is None and "last_success" in log["a"]
    assert log["b"]["error"] == "RuntimeError: source down" and "last_success" not in log["b"]
    assert log["c"]["detail"] == "fine" and log["c"]["error"] is None
    assert "Step A: 3 rows." in lines
    assert "Step B: FAILED (RuntimeError: source down); using cached data." in lines


def test_a_failure_keeps_the_last_success_time_of_the_source(tmp_data):
    updater._steps({"a": ("A", lambda: "ok")}, lambda m: None)
    first = coverage.load_log()["a"]["last_success"]
    updater._steps({"a": ("A", lambda: (_ for _ in ()).throw(ValueError("bad shape")))}, lambda m: None)
    entry = coverage.load_log()["a"]
    assert entry["last_success"] == first and entry["error"] == "ValueError: bad shape"


def test_every_external_source_is_tried_even_when_one_raises(tmp_data, monkeypatch):
    ran = []

    def ok(name, value="done"):
        return lambda *a, **k: ran.append(name) or value

    def fails(*a, **k):
        ran.append("ecb")
        raise ValueError("ECB changed its format")
    monkeypatch.setattr(trades, "holdings", lambda: pd.DataFrame())
    monkeypatch.setattr(external, "update_cot", ok("cftc", 5))
    monkeypatch.setattr(external, "update_oecd_cli", ok("oecd"))
    monkeypatch.setattr(external, "update_factset", ok("factset", None))
    monkeypatch.setattr(external, "update_analyst", ok("analyst"))
    monkeypatch.setattr(external, "update_ecb", fails)
    monkeypatch.setattr(valuation, "update_cape", ok("cape"))
    monkeypatch.setattr(valuation, "update_erp", ok("erp"))
    monkeypatch.setattr(sentiment, "update_putcall", ok("putcall"))
    monkeypatch.setattr(sentiment, "update_aaii", ok("aaii"))
    monkeypatch.setattr(factors, "update_factors", ok("factors"))
    monkeypatch.setattr(valuation, "update_etfs", ok("valuation_etfs"))
    monkeypatch.setattr(valuation, "update_stocks", ok("valuation_stocks"))
    monkeypatch.setattr(edgar, "update_edgar", ok("fundamentals_edgar"))
    monkeypatch.setattr(yahoo, "update_yahoo", ok("fundamentals_yahoo"))
    lines = []
    updater.update_external(lines.append)
    assert ran == ["cftc", "oecd", "factset", "analyst", "ecb", "cape", "erp", "putcall", "aaii", "factors",
                   "valuation_etfs", "valuation_stocks", "fundamentals_edgar", "fundamentals_yahoo"]
    log = coverage.load_log()
    assert log["ecb"]["error"] == "ValueError: ECB changed its format"
    assert log["cftc"]["detail"] == "5 new rows" and log["factset"]["detail"] == "no new report"
    assert all(log[k]["error"] is None for k in log if k != "ecb")
    assert any("ECB euro-area rates: FAILED" in line and "using cached data" in line for line in lines)


# ---------------- ECB ----------------

ECB_HEAD = "KEY,FREQ,TIME_PERIOD,OBS_VALUE\n"


def test_an_ecb_answer_without_time_period_or_obs_value_is_refused():
    with pytest.raises(ValueError, match="TIME_PERIOD / OBS_VALUE"):
        external.parse_ecb("KEY,FREQ,DATE,VALUE\nYC.B.X,B,2026-10-01,3.1\n")


def test_an_ecb_answer_with_only_a_header_is_refused():
    with pytest.raises(ValueError, match="TIME_PERIOD / OBS_VALUE"):
        external.parse_ecb(ECB_HEAD)


def test_an_ecb_answer_holding_two_series_is_refused():
    text = ECB_HEAD + "YC.B.X,B,2026-10-01,3.1\nYC.B.Y,B,2026-10-01,2.9\n"
    with pytest.raises(ValueError, match="2 series in one answer"):
        external.parse_ecb(text)


def test_an_ecb_daily_series_parses_to_its_calendar_days_sorted():
    s = external.parse_ecb(ECB_HEAD + "YC.B.X,B,2026-10-02,3.2\nYC.B.X,B,2026-10-01,3.1\n")
    assert list(s.index) == [pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-02")]
    assert s.tolist() == [3.1, 3.2]


def test_an_ecb_answer_whose_values_are_all_blank_is_refused():
    with pytest.raises(ValueError, match="no values"):
        external.parse_ecb(ECB_HEAD + "FM.M.X,M,2026-08,\nFM.M.X,M,2026-09,NaN\n")


# ---------------- Damodaran ----------------

def _damodaran(n=5, erp=0.042, columns=("Start of month", "ERP (T12m)", "T.Bond Rate")):
    df = pd.DataFrame({"Start of month": pd.date_range("2020-01-01", periods=n, freq="MS"),
                       "ERP (T12m)": [erp] * n, "T.Bond Rate": [0.03] * n, "ERP (Net cash yield)": [0.05] * n})
    buf = io.BytesIO()
    df[[c for c in df.columns if c in columns or c == "ERP (Net cash yield)"]].to_excel(
        buf, sheet_name="Historical ERP", index=False)
    return buf.getvalue()


def test_a_well_formed_damodaran_sheet_parses_to_monthly_rows():
    df = valuation.parse_damodaran(_damodaran(), min_rows=5)
    assert len(df) == 5 and df["erp"].iloc[0] == pytest.approx(0.042) and df["tbond"].iloc[-1] == pytest.approx(0.03)


@pytest.mark.parametrize("missing", ["Start of month", "ERP (T12m)", "T.Bond Rate"])
def test_a_damodaran_sheet_without_a_required_column_names_it(missing):
    cols = tuple(c for c in ("Start of month", "ERP (T12m)", "T.Bond Rate") if c != missing)
    with pytest.raises(ValueError, match=re.escape(f"no {missing!r} column")):
        valuation.parse_damodaran(_damodaran(columns=cols), min_rows=1)


def test_damodaran_erp_given_in_percent_instead_of_fractions_is_refused():
    with pytest.raises(ValueError, match="outside -5%…20%"):
        valuation.parse_damodaran(_damodaran(erp=4.2), min_rows=1)


def test_a_damodaran_sheet_with_fewer_rows_than_expected_is_refused():
    with pytest.raises(ValueError, match="only 5 monthly ERP rows"):
        valuation.parse_damodaran(_damodaran(), min_rows=6)


# ---------------- AAII ----------------

def _aaii(rows, header=("Reported Date", "Bullish", "Neutral", "Bearish")):
    lines = [["AAII Sentiment Survey", None, None, None], list(header)] + rows
    buf = io.BytesIO()
    pd.DataFrame(lines).to_excel(buf, sheet_name="SENTIMENT", header=False, index=False)
    return buf.getvalue()


def _weeks(n, shares=(0.4, 0.3, 0.3)):
    return [[pd.Timestamp("2026-01-01") + pd.Timedelta(weeks=i), *shares] for i in range(n)]


def test_a_small_well_formed_aaii_sheet_parses_with_a_low_min_rows():
    df = sentiment.parse_aaii(_aaii(_weeks(3)), min_rows=3)
    assert len(df) == 3 and df["bullish"].tolist() == [0.4] * 3
    assert df["date"].iloc[0] == pd.Timestamp("2026-01-01")


def test_an_aaii_sheet_without_the_bullish_neutral_bearish_header_is_refused():
    with pytest.raises(ValueError, match="no Bullish / Neutral / Bearish header"):
        sentiment.parse_aaii(_aaii(_weeks(3), header=("Date", "Bull", "Neutral", "Bear")), min_rows=1)


def test_aaii_shares_given_in_percent_are_refused():
    with pytest.raises(ValueError, match="don't add up to 100%"):
        sentiment.parse_aaii(_aaii(_weeks(3, (40.0, 30.0, 30.0))), min_rows=1)


def test_an_aaii_sheet_with_too_few_weeks_is_refused():
    with pytest.raises(ValueError, match="only 3 weekly AAII rows"):
        sentiment.parse_aaii(_aaii(_weeks(3)), min_rows=4)


# ---------------- CBOE ----------------

def _cboe(**ratios):
    names = {"total": "TOTAL PUT/CALL RATIO", "equity": "EQUITY PUT/CALL RATIO", "index": "INDEX PUT/CALL RATIO"}
    return {"ratios": [{"name": names[k], "value": v} for k, v in ratios.items()]}


@pytest.mark.parametrize("total", ["0.01", "12.5", "0"])
def test_a_cboe_total_ratio_outside_the_plausible_range_is_refused(total):
    with pytest.raises(ValueError, match="out of range"):
        sentiment.parse_cboe(_cboe(total=total, equity="0.6"))


def test_a_cboe_day_with_a_blank_total_is_refused_even_when_the_others_are_there():
    with pytest.raises(ValueError, match="no TOTAL PUT/CALL RATIO"):
        sentiment.parse_cboe(_cboe(total="", equity="0.6", index="1.1"))


def test_a_cboe_day_reads_the_three_ratios_as_floats():
    assert sentiment.parse_cboe(_cboe(total="0.85", equity="0.6", index="1.2")) == {
        "total": 0.85, "equity": 0.6, "index": 1.2}


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
    assert progress == [(0, 5), (2, 5), (4, 5)]
    assert sorted(out["ticker"].unique()) == ["A", "B", "C", "D", "E"] and len(out) == 15
    assert list(out.columns) == ingest.COLUMNS


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


def test_an_aaii_answer_that_is_a_web_page_says_so():
    page = b"<!DOCTYPE html>\r\n<html><head><title>Pardon Our Interruption</title></head></html>"
    with pytest.raises(ValueError, match="web page"):
        sentiment.parse_aaii(page)
