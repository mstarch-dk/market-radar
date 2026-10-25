"""Yahoo ticker detail parsers, against real responses captured in tests/fixtures/yahoo_*.json."""
import json
from datetime import date

import pytest

from conftest import FIXTURES
from radar import paths
from radar.sources import external


def _raw(name):
    return json.loads((FIXTURES / f"yahoo_{name}.json").read_text(encoding="utf-8"))


def test_fundamentals_real_stock():
    f = external.parse_fundamentals(_raw("novo")["info"])
    assert f["currency"] == "DKK" and f["market_cap"] > 1e11
    assert 0 < f["forward_pe"] < 100 and 0 < f["trailing_pe"] < 100
    assert 0 < f["profit_margin"] < 1 and 0 < f["dividend_yield"] < 0.1   # fractions, not percent
    assert f["notes"] == []


def test_dividend_yield_units():
    notes = []
    assert external.dividend_yield({"dividendYield": 4.56, "trailingAnnualDividendYield": 0.044}, notes) == pytest.approx(0.0456)
    assert external.dividend_yield({"dividendYield": 0.0456, "trailingAnnualDividendYield": 0.044}, notes) == pytest.approx(0.0456)
    assert external.dividend_yield({"dividendYield": 0.72}, notes) == pytest.approx(0.0072)   # percent by default
    assert external.dividend_yield({"dividendYield": 45.0}, notes) is None and "dividend yield" in notes[0]
    assert external.dividend_yield({}, notes) is None


def test_implausible_or_meaningless_values_are_dropped_with_a_note():
    f = external.parse_fundamentals({"trailingPE": -12.0, "profitMargins": 35.3, "debtToEquity": 63.3,
                                     "netExpenseRatio": 0.15})
    assert f["trailing_pe"] is None and f["profit_margin"] is None             # 35.3 can't be a fraction
    assert f["debt_to_equity"] == pytest.approx(0.633)                         # Yahoo reports it in percent
    assert len(f["notes"]) == 2


def test_recommendation_trend():
    rec = external.parse_recommendations(_raw("msft")["recommendations"])
    assert rec[0]["period"] == "0m" and len(rec) == 4
    assert rec[0]["n"] == sum(rec[0][k] for k in ("strong_buy", "buy", "hold", "sell", "strong_sell"))
    assert 1 <= rec[0]["mean"] <= 2.5                                          # MSFT: mostly buys
    assert external.parse_recommendations([{"period": "0m"}])[0]["mean"] is None


def test_eps_trend_and_revisions():
    raw = _raw("novo")
    eps = {e["period"]: e for e in external.parse_eps_trend(raw["eps_trend"], raw["eps_revisions"], raw["growth_estimates"])}
    assert list(eps) == ["0q", "+1q", "0y", "+1y"]
    t = raw["eps_trend"]["0y"]
    assert eps["0y"]["chg_30d"] == pytest.approx(t["current"] / t["30daysAgo"] - 1)
    assert eps["0y"]["currency"] == "DKK" and eps["0y"]["up_30d"] == raw["eps_revisions"]["0y"]["upLast30days"]
    flip = external.parse_eps_trend({"0q": {"current": 0.5, "30daysAgo": -0.2}}, {}, {})
    assert flip[0]["chg_30d"] is None                                         # no % change across a sign flip


def test_calendar_picks_the_next_earnings_date():
    cal = {"Earnings Date": ["2026-07-30", "2026-11-04"], "Earnings Average": 4.9, "Ex-Dividend Date": "2026-08-14"}
    c = external.parse_calendar(cal, today=date(2026, 10, 13))
    assert c["next_earnings"] == "2026-11-04" and c["ex_dividend"] == "2026-08-14"
    assert external.parse_calendar(cal, today=date(2026, 12, 1))["next_earnings"] is None   # only past dates
    assert external.parse_calendar(_raw("msft")["calendar"], today=date(2026, 10, 13))["next_earnings"] == "2026-10-28"


def test_parse_calendar_range():
    msft = external.parse_calendar(_raw("msft")["calendar"], today=date(2026, 10, 13))
    assert msft["earnings_start"] == msft["earnings_end"] == "2026-10-28" and msft["is_range"] is False
    assert msft["eps_low"] == pytest.approx(4.43) and msft["eps_high"] == pytest.approx(4.83363)
    assert msft["revenue_low"] < msft["revenue_estimate"] < msft["revenue_high"]
    window = {"Earnings Date": ["2026-11-06", "2026-10-30"]}                    # Yahoo's expected window
    c = external.parse_calendar(window, today=date(2026, 10, 25))
    assert (c["earnings_start"], c["earnings_end"], c["is_range"]) == ("2026-10-30", "2026-11-06", True)
    assert c["next_earnings"] == "2026-10-30"
    during = external.parse_calendar(window, today=date(2026, 11, 2))              # inside the window: still a range
    assert (during["earnings_start"], during["is_range"]) == ("2026-10-30", True)
    after = external.parse_calendar(window, today=date(2026, 11, 7))
    assert after["earnings_start"] is None and after["earnings_end"] is None and after["is_range"] is False
    assert external.parse_calendar({})["earnings_start"] is None


def test_etf_has_look_through_but_no_estimates():
    raw = _raw("iuit")
    assert raw["recommendations"] == [] and raw["eps_trend"] == {}
    fund = external.parse_fund(raw["fund"], raw["info"])
    assert fund["expense_ratio"] == pytest.approx(0.0015)                     # 0.15%, from either field
    assert fund["sector_weights"][0] == {"sector": "Technology", "weight": 1.0}
    assert fund["top_holdings"][0]["symbol"] == "NVDA" and 0 < fund["top_holdings"][0]["weight"] < 1
    only_info = external.parse_fund({}, {"netExpenseRatio": 0.15})
    assert only_info["expense_ratio"] == pytest.approx(0.0015)                # percent field, converted


def test_detail_cache_and_failure(tmp_path, monkeypatch):
    paths.configure(paths.Locations.flat(tmp_path))
    raw = _raw("msft") | {"fetched": "2026-10-13T08:00:00"}
    monkeypatch.setattr(external, "fetch_detail", lambda t: raw)
    got, status = external.detail("MSFT", max_age_hours=1e9)
    assert status == "ok" and (tmp_path / "profiles" / "MSFT.json").exists()

    def down(t):
        raise ConnectionError("yahoo down")
    monkeypatch.setattr(external, "fetch_detail", down)
    assert external.detail("MSFT", max_age_hours=1e9)[1] == "ok"               # fresh enough: no fetch
    got, status = external.detail("MSFT", max_age_hours=0)                     # due, but the fetch fails
    assert status == "stale" and got["info"]["longName"] == raw["info"]["longName"]
    assert external.detail("NEW", max_age_hours=0) == (None, "missing")
    empty = {"symbol": "X", "fetched": "2026-10-13T08:00:00", "info": {}, "recommendations": [], "eps_trend": {},
             "calendar": {}, "errors": {"info": "HTTPError: 404"}}
    monkeypatch.setattr(external, "fetch_detail", lambda t: empty)
    assert external.detail("X", max_age_hours=0) == (None, "missing")


# ---------------- a partial answer keeps the cached blocks it lacks (hardening 1.8) ----------------

def test_a_block_that_fails_keeps_its_cached_copy(tmp_data, monkeypatch):
    from radar.sources import external
    full = {"symbol": "X", "fetched": "2026-10-10T10:00:00", "errors": {},
            "info": {"quoteType": "EQUITY", "longName": "X Corp"}, "recommendations": [{"period": "0m", "buy": 3}],
            "eps_trend": {"0y": {"current": 1.0}}, "eps_revisions": {}, "growth_estimates": {}, "calendar": {}}
    partial = dict(full, fetched="2026-10-15T10:00:00", recommendations=[],
                   errors={"recommendations": "YFRateLimitError: Too Many Requests"})
    answers = iter([full, partial])
    monkeypatch.setattr(external, "fetch_detail", lambda t: next(answers))
    external.detail("X")
    raw, status = external.detail("X", refresh=True)
    assert status == "ok" and raw["recommendations"] == [{"period": "0m", "buy": 3}]
    assert raw["kept"] == {"recommendations": "2026-10-10T10:00:00"} and "recommendations" not in raw["errors"]
    raw2, _ = external.detail("X")                         # and so stored
    assert raw2["recommendations"] == [{"period": "0m", "buy": 3}]
