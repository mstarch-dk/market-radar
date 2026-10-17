"""Valuation and sentiment: parsers on trimmed real payloads, P/E on Yahoo's mixed currencies, the readings built
from the weekly snapshots, and the switchable regime votes."""
import json

import pandas as pd
import pytest

from conftest import FIXTURES
from radar import external, sentiment, sourcelog, valuation
from radar.external import parse_ecb
from radar.signals import regime
from radar.signals import valuation as sv

FX = {"DKK": 1.0, "EUR": 7.46, "USD": 6.40, "GBP": 8.62}


# ---------------- P/E from a screener quote ----------------

def test_pe_in_one_currency():
    r = valuation.quote_valuation({"symbol": "NOVO-B.CO", "currency": "DKK", "financialCurrency": "DKK",
                                   "regularMarketPrice": 253.4, "epsTrailingTwelveMonths": 26.2, "epsCurrentYear": 21.56,
                                   "epsForward": 21.94, "bookValue": 49.97, "trailingAnnualDividendYield": 0.0456,
                                   "forwardPE": 11.55}, FX)
    assert r["pe_fy1"] == pytest.approx(253.4 / 21.94) and r["pe_cy"] == pytest.approx(253.4 / 21.56)
    assert r["pe_ttm"] == pytest.approx(253.4 / 26.2) and r["pb"] == pytest.approx(253.4 / 49.97)
    assert not r["cross_ccy"] and r["note"] is None


def test_pe_when_yahoo_mixes_currencies():
    """Shell (real screener quote): trailing and next-year EPS come in pounds, this year's in dollars."""
    q = {"symbol": "SHEL.L", "currency": "GBp", "financialCurrency": "USD", "regularMarketPrice": 3910.0,
         "epsTrailingTwelveMonths": 3.38, "epsCurrentYear": 6.25355, "epsForward": 4.2103295, "forwardPE": 9.3}
    r = valuation.quote_valuation(q, FX)
    assert r["pe_fy1"] == pytest.approx(39.10 / 4.2103295) and r["pe_ttm"] == pytest.approx(39.10 / 3.38)
    assert r["pe_cy"] == pytest.approx(39.10 * 8.62 / 6.40 / 6.25355)          # pounds → dollars
    assert r["cross_ccy"] and r["price"] == pytest.approx(39.10)
    without_rate = valuation.quote_valuation(q, {"DKK": 1.0})
    assert without_rate["pe_cy"] is None and "no GBp→USD rate" in without_rate["note"]
    assert without_rate["pe_fy1"] == pytest.approx(r["pe_fy1"])               # needs no rate


def test_loss_makers_and_impossible_values_have_no_pe():
    r = valuation.quote_valuation({"symbol": "X", "currency": "USD", "regularMarketPrice": 10.0,
                                   "epsTrailingTwelveMonths": -1.0, "epsForward": 0.005}, FX)
    assert r["pe_ttm"] is None and r["pe_fy1"] is None
    assert "negative or zero earnings" in r["note"] and "outside 1–300" in r["note"]


def test_inconsistent_single_lookup_estimates_are_dropped():
    q = {"symbol": "8035.T", "currency": "JPY", "regularMarketPrice": 11240.0, "epsTrailingTwelveMonths": 270.91,
         "epsForward": 1280.2}
    assert valuation.quote_valuation(q, FX)["pe_fy1"] == pytest.approx(11240 / 1280.2)       # screener: kept
    r = valuation.quote_valuation(q, FX, check_estimates=True)
    assert r["pe_fy1"] is None and "inconsistent estimate" in r["note"]


def test_fund_multiples_are_turned_around():
    r = valuation.fund_valuation({"Price/Earnings": 0.03121, "Price/Book": 0.08417, "Price/Sales": 0.10803,
                                  "Price/Cashflow": 0.0})
    assert r["pe"] == pytest.approx(1 / 0.03121) and r["pb"] == pytest.approx(1 / 0.08417)
    assert r["pcf"] is None                                    # 0 = unknown, not infinitely expensive
    assert valuation.fund_valuation({"Price/Earnings": 0.5})["pe"] is None   # P/E 2: outside 3–150


# ---------------- parsers (trimmed real payloads) ----------------

def test_parse_multpl_cape():
    s = valuation.parse_multpl((FIXTURES / "multpl_cape.html").read_text(encoding="utf-8"), min_rows=3)
    assert len(s) == 6 and s.index.is_monotonic_increasing
    assert s.iloc[-1] == 41.84 and s.index[-1] == pd.Timestamp("2026-10-13")   # today's estimate
    with pytest.raises(ValueError, match="CAPE rows"):
        valuation.parse_multpl("<html>moved</html>")


def test_parse_damodaran_erp():
    df = valuation.parse_damodaran((FIXTURES / "damodaran_erp.xlsx").read_bytes(), min_rows=3)
    last = df.iloc[-1]
    assert last["date"] == pd.Timestamp("2026-10-01") and last["erp"] == 0.037 and last["tbond"] == 0.0529


def test_parse_aaii():
    df = sentiment.parse_aaii((FIXTURES / "aaii_sentiment.xlsx").read_bytes(), min_rows=3)
    last = df.iloc[-1]
    assert last["date"] == pd.Timestamp("2026-10-08")
    assert last["bullish"] == pytest.approx(0.402524) and last["bearish"] == pytest.approx(0.389831)


def test_parse_cboe_and_ecb():
    r = sentiment.parse_cboe(json.loads((FIXTURES / "cboe_daily_options.json").read_text()))
    assert r == {"total": 0.83, "index": 1.06, "equity": 0.54}
    with pytest.raises(ValueError, match="TOTAL PUT/CALL"):
        sentiment.parse_cboe({"ratios": []})
    s = parse_ecb((FIXTURES / "ecb_yc_10y.csv").read_text(encoding="utf-8"))
    assert len(s) == 5 and s.index[-1] == pd.Timestamp("2026-10-13") and s.iloc[-1] == pytest.approx(3.491778165)


class _Resp:
    def __init__(self, status, data=None):
        self.status_code, self._data = status, data

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_putcall_skips_holidays_and_fails_loudly_when_nothing_comes(tmp_data):
    day = json.loads((FIXTURES / "cboe_daily_options.json").read_text())
    holiday = "2026-10-12"
    got = lambda url: _Resp(404) if holiday in url else _Resp(200, day)  # noqa: E731
    msg = sentiment.update_putcall(pd.Timestamp("2026-10-14").date(), get=got, sleep=lambda s: None)
    df = sentiment.load_putcall()
    assert "new days" in msg and pd.Timestamp(holiday) not in set(df["date"]) and len(df) > 200
    sentiment.PUTCALL_FILE.unlink()
    with pytest.raises(ValueError, match="no CBOE statistics"):
        sentiment.update_putcall(pd.Timestamp("2026-10-14").date(), get=lambda url: _Resp(404), sleep=lambda s: None)


# ---------------- readings from the snapshots ----------------

def _snaps(rows_by_date: dict[str, list[dict]]) -> pd.DataFrame:
    return pd.DataFrame([r | {"date": pd.Timestamp(d)} for d, rows in rows_by_date.items() for r in rows])


def test_pe_vs_sector_median_needs_enough_peers():
    now = pd.DataFrame({"pe_fy1": [10.0, 20.0, 30.0, 40.0, 50.0, 15.0]}, index=list("ABCDEF"))
    group = dict.fromkeys("ABCDEF", "nordic")
    sector = dict.fromkeys("ABCDE", "Industrials") | {"F": "Energy"}
    rel = sv.vs_sector(now, group, sector, min_peers=5)
    assert rel["A"] == pytest.approx(10 / 30) and rel["E"] == pytest.approx(50 / 30)
    assert rel["F"] is None                                    # one Energy name: no median


def test_eps_revisions_need_history_and_follow_the_fiscal_year():
    hist = _snaps({"2026-09-16": [{"ticker": "A", "eps_cy": 2.0, "eps_fy1": 2.4, "cross_ccy": False},
                                  {"ticker": "R", "eps_cy": 2.0, "eps_fy1": 2.4, "cross_ccy": False},
                                  {"ticker": "X", "eps_cy": 2.0, "eps_fy1": 2.4, "cross_ccy": True}],
                   "2026-10-14": [{"ticker": "A", "eps_cy": 2.0, "eps_fy1": 2.52, "cross_ccy": False},
                                  {"ticker": "R", "eps_cy": 2.43, "eps_fy1": 2.9, "cross_ccy": False},   # year rolled
                                  {"ticker": "X", "eps_cy": 2.0, "eps_fy1": 2.6, "cross_ccy": True}]})
    rev, base = sv.revisions(hist, 4)
    assert base == pd.Timestamp("2026-09-16")
    assert rev["A"] == pytest.approx(0.05)
    assert rev["R"] == pytest.approx(2.43 / 2.4 - 1)          # this year's now vs next year's then
    assert "X" not in rev                                      # cross-currency: FX moves would look like revisions
    assert sv.revisions(hist, 12)[0].empty                     # no snapshot 12 weeks back yet
    assert sv.revisions(hist.iloc[:0], 4)[0].empty


def test_revision_breadth():
    rev = pd.Series([0.05] * 6 + [-0.05] * 2 + [0.0] * 2, index=[f"T{i}" for i in range(10)])
    [row] = sv.breadth(rev, dict.fromkeys(rev.index, "europe"), band=0.01, min_names=10)
    assert row["up"] == 0.6 and row["down"] == 0.2 and row["net"] == pytest.approx(0.4) and row["names"] == 10
    assert sv.breadth(rev, dict.fromkeys(rev.index, "europe"), min_names=11) == []


def test_etf_rows_relative_to_the_benchmark_and_their_own_history():
    weeks = pd.date_range("2026-01-07", periods=27, freq="7D")
    hist = pd.DataFrame([{"date": d, "ticker": "XLK", "pe": 25 + i * 0.25} for i, d in enumerate(weeks)]
                        + [{"date": weeks[-1], "ticker": "ACWI", "pe": 20.0}])
    rows = sv.etf_rows(hist, "ACWI", min_weeks=26)
    assert rows["XLK"]["pe_vs_acwi"] == pytest.approx(31.5 / 20) and rows["XLK"]["pe_pct"] == pytest.approx(100 * 26 / 27, abs=0.1)
    assert rows["ACWI"]["pe_pct"] is None                       # one week stored


def test_market_valuation():
    cape = pd.Series([10.0, 20.0, 30.0, 40.0], index=pd.to_datetime(["1980-01-01", "1995-01-01", "2010-01-01", "2026-10-13"]))
    erp = pd.Series([0.06, 0.05, 0.04], index=pd.to_datetime(["2008-09-01", "2016-01-01", "2026-10-01"]))
    m = sv.market(cape, erp, fwd_pe=20.0, real10y=pd.Series([2.0], index=pd.to_datetime(["2026-10-09"])))
    assert m["cape"]["pct_all"] == 100.0 and m["cape"]["pct_1990"] == 100.0 and m["cape"]["median"] == 25.0
    assert m["erp"]["pct"] == 0.0
    assert m["yield_gap"]["value"] == pytest.approx(5.0 - 2.0)
    assert sv.market(pd.Series(dtype=float), pd.Series(dtype=float), None, pd.Series(dtype=float)) == \
        {"cape": None, "erp": None, "yield_gap": None}


def test_sentiment_extremes():
    dates = pd.date_range("2020-01-02", periods=200, freq="7D")
    df = pd.DataFrame({"date": dates, "bullish": 0.4, "neutral": 0.3, "bearish": 0.3})
    df.loc[df.index[-1], ["bullish", "bearish"]] = [0.2, 0.5]
    a = sv.aaii(df, extreme=10)
    assert a["spread"] == pytest.approx(-0.3) and a["pct"] == 0.0 and a["flag"] == "extreme fear"
    pc = pd.DataFrame({"date": pd.bdate_range("2026-01-01", periods=80), "equity": [0.5] * 79 + [1.5]})
    p = sv.putcall(pc, lookback=756)
    assert p["equity_10d"] == pytest.approx(0.6) and p["pct"] == 100.0


# ---------------- regime: switchable groups ----------------

CFG = {"breadth_strong": 60, "breadth_weak": 40, "highs_lows_band": 3, "vix_calm": 18, "vix_stress": 25,
       "vix_term_calm": 0.9, "rates_shock": 0.5, "copper_gold_band": 0.05, "oil_shock": 0.3, "revisions_band": 0.5,
       "cape_rich_pct": 90, "cape_cheap_pct": 10, "erp_low_pct": 10, "erp_high_pct": 90}


def test_valuation_rows_vote_only_when_switched_on():
    closes = pd.DataFrame({"ACWI": [100 * 1.001 ** i for i in range(260)]}, index=pd.bdate_range("2025-01-01", periods=260))
    market_val = {"cape": {"value": 41.8, "asof": "2026-10-13", "pct_all": 99.1, "pct_1990": 96.4, "median": 16.1,
                           "since": "1871-02-01"},
                  "erp": {"value": 0.037, "asof": "2026-10-01", "pct": 0.0, "median": 0.0526, "since": "2008-09-01"}}
    inds, _ = regime.indicators(closes, pd.DataFrame(), "ACWI", {}, {}, {}, CFG, market_val=market_val)
    rows = {i["name"].split(" (")[0]: i for i in inds}
    assert rows["Valuation"]["status"] == rows["Equity risk premium"]["status"] == regime.OFF
    assert rows["Valuation"]["group"] == "valuation" and rows["Euro credit"]["group"] == "credit_eu"
    off = regime.overall([dict(i) for i in inds], {"valuation": False, "credit_eu": True})
    on = regime.overall([dict(i) for i in inds], {"valuation": True, "credit_eu": True})
    assert on["off"] == off["off"] + 2 and off["not_voting"] == 2 + 3 and on["not_voting"] == 3  # + the 3 context rows
    assert "valuation" in on["voting_groups"] and "valuation" not in off["voting_groups"]
    assert regime.overall([dict(i) for i in inds])["off"] == on["off"]    # no choice given: every row votes


def test_putcall_keeps_the_days_it_got_when_a_later_day_fails(tmp_data):
    day = json.loads((FIXTURES / "cboe_daily_options.json").read_text())
    sentiment.update_putcall(pd.Timestamp("2026-10-07").date(), get=lambda url: _Resp(200, day), sleep=lambda s: None)
    before = len(sentiment.load_putcall())
    got = lambda url: _Resp(503) if "2026-10-13" in url else _Resp(200, day)  # noqa: E731
    with pytest.raises(sourcelog.PartialFailure, match="3 new days"):
        sentiment.update_putcall(pd.Timestamp("2026-10-14").date(), get=got, sleep=lambda s: None)
    stored = set(sentiment.load_putcall()["date"])
    assert {pd.Timestamp("2026-10-08"), pd.Timestamp("2026-10-09")} <= stored     # fetched before the failure
    assert len(stored) == before + 3                                               # 8, 9 and 12 Oct


def test_putcall_asks_again_for_a_day_that_was_missing(tmp_data):
    day = json.loads((FIXTURES / "cboe_daily_options.json").read_text())
    late = "2026-10-12"                         # not published yet (403) on the first run
    sentiment.update_putcall(pd.Timestamp("2026-10-14").date(), sleep=lambda s: None,
                             get=lambda url: _Resp(403) if late in url else _Resp(200, day))
    assert pd.Timestamp(late) not in set(sentiment.load_putcall()["date"])
    asked = []

    def get(url):
        asked.append(url)
        return _Resp(200, day)
    sentiment.update_putcall(pd.Timestamp("2026-10-15").date(), get=get, sleep=lambda s: None)
    assert pd.Timestamp(late) in set(sentiment.load_putcall()["date"])
    assert len(asked) == 2                      # the missing day and the new one, not the whole window


# ---------------- the ETF snapshot: never replaced by a thin answer (hardening 1.4) ----------------

def _etf_world(monkeypatch, answers: dict):
    from fakes import fake_yf
    monkeypatch.setattr(valuation, "etf_tickers", lambda: sorted(answers))
    return fake_yf(monkeypatch, funds=answers)


EH = pd.DataFrame({"fund": {"Price/Earnings": 0.05, "Price/Book": 0.4}})
ETFS = [f"ETF{i}" for i in range(10)]


def test_a_thin_etf_answer_keeps_the_last_snapshot(tmp_data, monkeypatch):
    _etf_world(monkeypatch, {t: EH for t in ETFS})
    valuation.update_etfs(today=pd.Timestamp("2026-10-05").date())
    before = valuation.ETFS_FILE.read_bytes()
    _etf_world(monkeypatch, {t: (EH if t in ETFS[:3] else RuntimeError("429")) for t in ETFS})
    with pytest.raises(ValueError, match="3 of 10"):
        valuation.update_etfs(today=pd.Timestamp("2026-10-12").date())
    assert valuation.ETFS_FILE.read_bytes() == before


def test_a_same_week_rerun_carries_the_etfs_it_missed(tmp_data, monkeypatch):
    _etf_world(monkeypatch, {t: EH for t in ETFS})
    valuation.update_etfs(today=pd.Timestamp("2026-10-12").date())
    _etf_world(monkeypatch, {t: (EH if t != "ETF9" else None) for t in ETFS})
    msg = valuation.update_etfs(force=True, today=pd.Timestamp("2026-10-14").date())
    week = valuation.latest(pd.read_parquet(valuation.ETFS_FILE))
    assert set(week.index) == set(ETFS) and "carried" in week.loc["ETF9", "note"]
    assert "1 carried" in msg


def test_lookups_count_what_failed(monkeypatch):
    from fakes import fake_yf
    fake_yf(monkeypatch, info={"A.CO": {"quoteType": "EQUITY", "currency": "DKK", "regularMarketPrice": 10.0},
                               "B.CO": RuntimeError("429")})
    rows = {}
    n, failed = valuation._lookups(["A.CO", "B.CO"], {"DKK": 1.0}, (1, 300), rows)
    assert n == 1 and failed == ["B.CO"] and "A.CO" in rows


# ---------------- ECB: the frequency from FREQ; an empty series isn't stored (hardening 1.5) ----------------

def test_ecb_monthly_series_is_read_by_its_freq_column():
    text = "KEY,FREQ,TIME_PERIOD,OBS_VALUE\nFM.M.X,M,2026-08,2.1\nFM.M.X,M,2026-09,2.0\n"
    s = external.parse_ecb(text)
    assert list(s.index) == [pd.Timestamp("2026-08-01"), pd.Timestamp("2026-09-01")]


def test_ecb_series_without_values_is_refused_before_anything_is_written(tmp_data, monkeypatch):
    from fakes import Resp, serve
    (key, (sid, _label)), = list(external._cfg().get("ecb", {}).items())[:1]
    good = "KEY,FREQ,TIME_PERIOD,OBS_VALUE\n" + "".join(f"{sid},B,2026-10-{d:02d},3.{d}\n" for d in range(1, 15))
    serve(monkeypatch, {"ecb": Resp(text=good)})
    external.update_ecb()
    before = external.ECB_FILE.read_bytes()
    serve(monkeypatch, {"ecb": Resp(text=f"KEY,FREQ,TIME_PERIOD,OBS_VALUE\n{sid},B,2026-10-15,\n")})
    with pytest.raises(ValueError):
        external.update_ecb()
    assert external.ECB_FILE.read_bytes() == before


def test_the_earnings_date_is_the_exchanges_own_day():
    ts = pd.Timestamp("2026-11-04 23:30", tz="UTC").timestamp()      # 08:30 on 5 Nov in Tokyo
    q = {"symbol": "7203.T", "quoteType": "EQUITY", "currency": "JPY", "regularMarketPrice": 3000.0,
         "earningsTimestamp": ts, "exchangeTimezoneName": "Asia/Tokyo"}
    assert valuation.quote_valuation(q, {"JPY": 0.045})["earnings_date"] == "2026-11-05"
    assert valuation.quote_valuation({k: v for k, v in q.items() if k != "exchangeTimezoneName"},
                                     {"JPY": 0.045})["earnings_date"] == "2026-11-04"     # no zone given: UTC's day
