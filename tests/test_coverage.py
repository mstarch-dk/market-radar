from datetime import date

import pandas as pd
import pytest

from radar import coverage, universe
from radar.signals import levels


def test_status_boundaries():
    ref = date(2026, 10, 13)
    assert coverage.status(pd.Timestamp("2026-09-29"), ref, 14) == ("ok", 14)
    assert coverage.status(pd.Timestamp("2026-09-28"), ref, 14) == ("stale", 15)
    assert coverage.status(None, ref, 14) == ("missing", None)
    assert coverage.status(pd.Timestamp("2020-01-01"), ref, None)[0] == "ok"  # no limit


def test_record_keeps_last_success_on_failure(tmp_data):
    coverage.record("fred", True, "4 series")
    ok = coverage.load_log()["fred"]["last_success"]
    coverage.record("fred", False, error="HTTPError: 503")
    entry = coverage.load_log()["fred"]
    assert entry["error"] == "HTTPError: 503" and entry["last_success"] == ok


def test_constituents_fall_back_to_cache_when_download_fails(tmp_data, monkeypatch):
    pd.DataFrame({"ticker": ["AAPL", "MSFT"], "name": ["Apple", "Microsoft"]}).to_csv(
        tmp_data / "constituents_us.csv", index=False)

    def boom():
        raise ConnectionError("ssga down")
    monkeypatch.setattr(universe, "_spy_holdings", boom)
    assert universe.us_constituents(refresh=True) == ["AAPL", "MSFT"]
    assert "ssga down" in coverage.load_log()["constituents"]["error"]
    assert universe.us_constituents(offline=True) == ["AAPL", "MSFT"]


def test_analyst_view_ignores_old_consensus():
    close = pd.Series(100.0, index=pd.bdate_range("2026-08-03", "2026-10-13"))
    hist = pd.DataFrame([{"ticker": "X", "fetched": pd.Timestamp("2026-09-01"), "current_price": 100.0,
                          "target_mean": 120.0, "target_high": 140.0, "target_low": 90.0, "target_median": 120.0,
                          "n_analysts": 10, "rec_key": "buy", "rec_mean": 2.0, "quote_type": "EQUITY"}])
    fresh = levels.analyst_view(hist, "X", close, max_age_days=60)
    assert fresh["target_mean"] == pytest.approx(120.0) and not fresh.get("stale")
    old = levels.analyst_view(hist, "X", close, max_age_days=21)
    assert old["stale"] and "target_mean" not in old


def test_build_reports_missing_tickers_and_stale_sources(tmp_data):
    ref = date(2026, 10, 13)
    idx = pd.bdate_range("2026-09-01", "2026-10-13")
    prices = pd.concat([pd.DataFrame({"ticker": t, "date": idx[:n], "close": 1.0})
                        for t, n in (("ACWI", len(idx)), ("OLD", 5))])
    fred = pd.DataFrame({"DGS10": 4.0}, index=pd.bdate_range("2026-08-01", "2026-09-15"))  # a month old
    cfg = {"coverage": {"max_age": {"prices": 7, "fred": 14, "cftc": 14, "factset": 14, "oecd": 75, "analyst": 21},
                        "blind_spots": ["no valuation"]},
           "stops": {"min_analysts": 5}, "constituents_max_age_days": 30}
    inds = [{"name": "Credit", "status": "n/a"}, {"name": "Trend", "status": "risk-on"}]
    cov = coverage.build(ref, prices, ["ACWI", "OLD", "GONE"], fred, {"DGS10": "US 10Y"}, pd.DataFrame(), ["S&P 500"],
                         pd.DataFrame(), {"G20": "G20"}, pd.DataFrame(), pd.DataFrame(), [], ["ACWI"],
                         pd.DataFrame(), None, inds, cfg, today=ref, log={})
    src = {s["key"]: s for s in cov["sources"]}
    assert cov["missing_tickers"] == ["GONE"] and cov["stale_tickers"] == ["OLD"]
    assert src["prices"]["status"] == "ok" and src["prices"]["coverage"].startswith("2 of 3")
    assert src["fred"]["status"] == "stale" and src["fred"]["age_days"] == 28
    assert src["fred"]["name"] in cov["stale_sources"]
    assert cov["oldest"]["name"] == src["fred"]["name"]
    assert src["cftc"]["status"] == "missing" and src["oecd"]["status"] == "missing"
    assert cov["regime"] == {"total": 2, "current": 1, "na": ["Credit"], "stale": []}
    assert cov["blind_spots"] == ["no valuation"]
