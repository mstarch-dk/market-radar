"""external.py beyond the parsers: the incremental CFTC update, the analyst history and the ticker-detail fetch,
all offline (the CFTC's Socrata API, yfinance and a yfinance Ticker are stand-ins)."""
import json
import re
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from conftest import FIXTURES
from fakes import Resp, fake_yf
from radar import external, net

# ---------------- CFTC: update_cot ----------------

TFF = json.loads((FIXTURES / "cftc_tff.json").read_text())          # S&P 500 (13874A), 2026-09-08 and -15
DISAGG = json.loads((FIXTURES / "cftc_disagg.json").read_text())    # Gold (088691), same two weeks
TODAY = date(2026, 10, 16)
FULL = "2022-10-16"                                                  # TODAY - int(365.25 * 4) days


def _week(records, day):
    return [r | {"report_date_as_yyyy_mm_dd": f"{day}T00:00:00.000"} for r in records]


def _cot_config(monkeypatch, tff=None):
    cfg = {"external": {"cot": {"tff": tff or {"S&P 500": "13874A"}, "disagg": {"Gold": "088691"}}}}
    monkeypatch.setattr(external, "universe_config", lambda: cfg)


def _socrata(monkeypatch, records: dict, honour_where=True) -> list[tuple[str, list[str], str]]:
    """Answer like Socrata: the dataset's records whose code is in the list and whose date is after `since`.
    Returns what was asked: (dataset, codes, since)."""
    asked = []
    monkeypatch.setattr(net, "sleep", lambda s: None)

    def get(url, params=None, **kw):
        dataset = re.search(r"resource/([\w-]+)\.json", url).group(1)
        where = params["$where"]
        codes = re.findall(r"'(\w+)'", re.search(r"in\((.*?)\)", where).group(1))
        since = re.search(r"> '(\d{4}-\d{2}-\d{2})'", where).group(1)
        asked.append((dataset, codes, since))
        rows = [r for r in records.get(dataset, []) if r["cftc_contract_market_code"] in codes
                and (not honour_where or r["report_date_as_yyyy_mm_dd"][:10] > since)]
        return Resp(json=rows)
    monkeypatch.setattr(net.requests, "get", get)
    return asked


def test_cot_first_run_asks_four_years_for_every_market_and_counts_the_rows(monkeypatch):
    _cot_config(monkeypatch)
    asked = _socrata(monkeypatch, {"gpe5-46if": TFF, "72hh-3qpy": DISAGG})
    assert external.update_cot(today=TODAY) == 6                     # 2 weeks x (2 TFF groups + 1 disagg group)
    assert sorted(asked) == [("72hh-3qpy", ["088691"], FULL), ("gpe5-46if", ["13874A"], FULL)]
    df = external.load_cot()
    assert set(df["market"]) == {"S&P 500", "Gold"} and df["date"].max() == pd.Timestamp("2026-09-15")


def test_cot_second_run_only_asks_after_the_latest_stored_week(monkeypatch):
    _cot_config(monkeypatch)
    _socrata(monkeypatch, {"gpe5-46if": TFF, "72hh-3qpy": DISAGG})
    external.update_cot(today=TODAY)
    asked = _socrata(monkeypatch, {"gpe5-46if": TFF + _week(TFF[-1:], "2026-09-22"), "72hh-3qpy": DISAGG})
    assert external.update_cot(today=TODAY) == 2                     # one new TFF week, two groups
    assert sorted(asked) == [("72hh-3qpy", ["088691"], "2026-09-15"), ("gpe5-46if", ["13874A"], "2026-09-15")]
    assert len(external.load_cot()) == 8


def test_cot_newly_configured_market_gets_full_history_while_known_ones_stay_incremental(monkeypatch):
    _cot_config(monkeypatch)
    _socrata(monkeypatch, {"gpe5-46if": TFF, "72hh-3qpy": DISAGG})
    external.update_cot(today=TODAY)
    _cot_config(monkeypatch, tff={"S&P 500": "13874A", "Nasdaq": "209742"})
    nasdaq = [r | {"cftc_contract_market_code": "209742"} for r in TFF]
    asked = _socrata(monkeypatch, {"gpe5-46if": TFF + nasdaq, "72hh-3qpy": DISAGG})
    assert external.update_cot(today=TODAY) == 4                     # Nasdaq: 2 weeks x 2 groups
    tff_asks = sorted(a for a in asked if a[0] == "gpe5-46if")
    assert tff_asks == [("gpe5-46if", ["13874A"], "2026-09-15"), ("gpe5-46if", ["209742"], FULL)]


def test_cot_rows_the_source_sends_again_are_stored_once(monkeypatch):
    _cot_config(monkeypatch)
    _socrata(monkeypatch, {"gpe5-46if": TFF, "72hh-3qpy": DISAGG}, honour_where=False)
    external.update_cot(today=TODAY)
    assert external.update_cot(today=TODAY) == 0                     # same weeks answered again
    df = external.load_cot()
    assert len(df) == 6 and not df.duplicated(["date", "market", "group"]).any()


def test_cot_renamed_columns_raise_and_leave_the_stored_file_alone(monkeypatch):
    _cot_config(monkeypatch)
    _socrata(monkeypatch, {"gpe5-46if": TFF, "72hh-3qpy": DISAGG})
    external.update_cot(today=TODAY)
    before = external.COT_FILE.read_bytes()
    renamed = [{k.replace("asset_mgr", "assetmgr").replace("lev_money", "levmoney"): v for k, v in r.items()}
               for r in _week(TFF, "2026-09-22")]
    _socrata(monkeypatch, {"gpe5-46if": renamed, "72hh-3qpy": DISAGG})
    with pytest.raises(ValueError, match="CFTC format"):
        external.update_cot(today=TODAY)
    assert external.COT_FILE.read_bytes() == before


# ---------------- Analyst consensus ----------------

def _info(target, price=100.0, quote="EQUITY"):
    return {"quoteType": quote, "currentPrice": price, "currency": "USD", "targetMeanPrice": target,
            "numberOfAnalystOpinions": 12, "recommendationKey": "buy", "recommendationMean": 2.0, "sector": "Tech"}


def test_parse_analyst_without_info_or_quote_type_is_nothing():
    assert external.parse_analyst(None) is None and external.parse_analyst({}) is None
    assert external.parse_analyst({"currentPrice": 5}) is None


def test_parse_analyst_turns_yahoos_empty_markers_into_missing():
    row = external.parse_analyst({"quoteType": "ETF", "recommendationKey": "none", "sector": ""})
    assert row["quote_type"] == "ETF" and row["rec_key"] is None and row["sector"] is None
    assert row["target_mean"] is None                                # a fund: no target, not 0


def test_analyst_ticker_fetched_recently_is_not_asked_again(monkeypatch):
    fake = fake_yf(monkeypatch, info={"AAA": _info(120)})
    assert external.update_analyst(["AAA"], 7, today=date(2026, 10, 16)) == "1 of 1 tickers refreshed"
    assert external.update_analyst(["AAA"], 7, today=date(2026, 10, 22)) == "up to date"
    assert fake.asked == [("info", "AAA")]


def test_analyst_due_ticker_appends_a_dated_row_and_keeps_the_old_one(monkeypatch):
    fake_yf(monkeypatch, info={"AAA": _info(120)})
    external.update_analyst(["AAA"], 7, today=date(2026, 10, 16))
    fake_yf(monkeypatch, info={"AAA": _info(110)})
    external.update_analyst(["AAA"], 7, today=date(2026, 10, 23))
    df = external.load_analyst()
    assert list(df["fetched"]) == [pd.Timestamp("2026-10-16"), pd.Timestamp("2026-10-23")]
    assert list(df["target_mean"]) == [120, 110]


def test_analyst_fund_is_stored_without_targets_and_empty_info_is_skipped(monkeypatch):
    fake_yf(monkeypatch, info={"ETF1": {"quoteType": "ETF", "currentPrice": 50.0}, "GONE": {}})
    assert external.update_analyst(["ETF1", "GONE"], today=date(2026, 10, 16)) == "1 of 2 tickers refreshed"
    df = external.load_analyst()
    assert list(df["ticker"]) == ["ETF1"] and pd.isna(df["target_mean"].iloc[0])


def test_analyst_every_ticker_failing_raises_and_writes_nothing(monkeypatch):
    fake_yf(monkeypatch, info={"AAA": ConnectionError("down"), "BBB": ConnectionError("down")})
    with pytest.raises(RuntimeError, match="no data for 2 tickers"):
        external.update_analyst(["AAA", "BBB"], today=date(2026, 10, 16))
    assert not external.ANALYST_FILE.exists()


def test_analyst_partial_failure_keeps_going_and_retries_the_failed_one_next_time(monkeypatch):
    fake_yf(monkeypatch, info={"AAA": _info(120), "BBB": ConnectionError("down")})
    assert external.update_analyst(["AAA", "BBB"], today=date(2026, 10, 16)) == "1 of 2 tickers refreshed"
    fake = fake_yf(monkeypatch, info={"AAA": _info(120), "BBB": _info(80)})
    assert external.update_analyst(["AAA", "BBB"], today=date(2026, 10, 17)) == "1 of 1 tickers refreshed"
    assert fake.asked == [("info", "BBB")]


# ---------------- Ticker detail: _frame, fetch_detail (the JSON cleaning: test_jsonsafe.py) ----------------

def test_frame_is_rows_of_columns_and_nothing_for_none_or_empty():
    df = pd.DataFrame({"current": [1.5, np.nan], "7daysAgo": [1.4, 2.0]}, index=["0q", "+1q"])
    assert external._frame(df) == {"0q": {"current": 1.5, "7daysAgo": 1.4}, "+1q": {"current": None, "7daysAgo": 2.0}}
    assert external._frame(None) == {} and external._frame(pd.DataFrame()) == {} and external._frame([1]) == {}


class _FakeTicker:
    def __init__(self, quote="EQUITY"):
        self.quote = quote

    @property
    def info(self):
        return {"quoteType": self.quote, "longName": "Fake Inc", "trailingPE": np.float64(20.0), "notAKey": 1}

    @property
    def recommendations(self):
        return pd.DataFrame([{"period": "0m", "strongBuy": np.int64(5), "buy": 3}])

    @property
    def eps_trend(self):
        raise KeyError("epsTrend")                        # Yahoo left the block out

    eps_revisions = property(lambda self: pd.DataFrame({"upLast30days": [2]}, index=["0q"]))
    growth_estimates = property(lambda self: None)
    calendar = property(lambda self: {"Earnings Date": [date(2026, 11, 5)]})

    @property
    def funds_data(self):
        return SimpleNamespace(
            top_holdings=pd.DataFrame({"Name": ["Apple"], "Holding Percent": [0.07]}, index=["AAPL"]),
            fund_operations=pd.DataFrame({"FAKE": [0.0003]}, index=["Annual Report Expense Ratio"]),
            sector_weightings={"technology": 0.3}, asset_classes={"stockPosition": 0.99}, fund_overview=None)


def _detail(monkeypatch, quote):
    monkeypatch.setattr(net, "yf", lambda: SimpleNamespace(Ticker=lambda t: _FakeTicker(quote)))
    return external.fetch_detail("FAKE")


def test_fetch_detail_records_a_failing_block_and_fills_the_others(monkeypatch):
    raw = _detail(monkeypatch, "EQUITY")
    assert raw["symbol"] == "FAKE" and list(raw["errors"]) == ["eps_trend"] and "KeyError" in raw["errors"]["eps_trend"]
    assert raw["eps_trend"] == {}
    assert raw["info"]["longName"] == "Fake Inc" and raw["info"]["trailingPE"] == 20.0 and "notAKey" not in raw["info"]
    assert raw["info"]["forwardPE"] is None                                   # asked for, absent: missing
    assert raw["recommendations"] == [{"period": "0m", "strongBuy": 5, "buy": 3}]
    assert raw["eps_revisions"] == {"0q": {"upLast30days": 2}} and raw["growth_estimates"] == {}
    assert raw["calendar"] == {"Earnings Date": ["2026-11-05"]}
    assert "fund" not in raw                                                  # a stock has no look-through
    json.dumps(raw)


def test_fetch_detail_reads_the_fund_block_only_for_etfs_and_mutual_funds(monkeypatch):
    for quote in ("ETF", "MUTUALFUND"):
        fund = _detail(monkeypatch, quote)["fund"]
        assert fund["top_holdings"] == [{"symbol": "AAPL", "name": "Apple", "weight": 0.07}]
        assert fund["operations"] == {"Annual Report Expense Ratio": 0.0003}
        assert fund["sector_weightings"] == {"technology": 0.3} and fund["overview"] == {}
