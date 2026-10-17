import pandas as pd
import pytest

from conftest import FIXTURES
from radar.discovery import sources

FX = {"DKK": 1.0, "EUR": 7.46, "USD": 6.5, "GBP": 8.6, "CHF": 8.0, "SEK": 0.65}


def test_stoxx600_holdings_parse_to_yahoo_symbols():
    df = sources.parse_stoxx600((FIXTURES / "ishares_exsa_holdings.csv").read_text(encoding="utf-8"), min_rows=30)
    t = df.set_index("ticker")
    assert t.loc["ASML.AS", "exchange"] == "AMS" and t.loc["ASML.AS", "sector_hint"] == "Technology"
    assert t.loc["HSBA.L", "country"] == "United Kingdom"
    assert t.loc["SIE.DE", "sector_hint"] == "Industrials"
    assert "EVO.ST" in t.index                                   # "Nasdaq Omx Nordic" -> Stockholm
    assert t.loc["EVO.ST", "sector_hint"] == "Consumer Cyclical"  # trailing space in the sector name
    assert not any(s.startswith("SXO") for s in t.index)          # futures and cash rows are dropped


def test_stoxx600_layout_change_or_short_file_raises():
    text = (FIXTURES / "ishares_exsa_holdings.csv").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="only"):
        sources.parse_stoxx600(text)                              # 46 rows < 550
    with pytest.raises(ValueError, match="layout"):
        sources.parse_stoxx600(text.replace("Emittententicker", "Ticker"), min_rows=1)


def test_sp500_holdings_parse_to_plain_us_symbols():
    df = sources.parse_sp500((FIXTURES / "ishares_cspx_holdings.csv").read_text(encoding="utf-8"), min_rows=5)
    t = df.set_index("ticker")
    assert t.loc["NVDA", "exchange"] == "NMS" and t.loc["NVDA", "country"] == "United States"
    assert t.loc["BRK-B", "exchange"] == "NYQ" and t.loc["BRK-B", "sector_hint"] == "Financial Services"
    assert t.loc["BF-B", "sector_hint"] == "Consumer Defensive" and t.loc["CBOE", "exchange"] == "BTS"
    assert t.loc["AMZN", "sector_hint"] == "Consumer Cyclical"
    assert not {"HOLX", "USD", "ESZ6"} & set(t.index)            # unlisted, cash and futures rows are dropped
    with pytest.raises(ValueError, match="S&P 500"):
        sources.parse_sp500((FIXTURES / "ishares_cspx_holdings.csv").read_text(encoding="utf-8"))   # 7 < 490


def _q(sym, name, ccy, fin, cap, qt="EQUITY"):
    return {"symbol": sym, "longName": name, "currency": ccy, "financialCurrency": fin, "marketCap": cap,
            "quoteType": qt}


def test_home_listings_drop_cross_listings_and_small_names():
    quotes = {
        "CPH": [_q("NOVO-B.CO", "Novo Nordisk A/S", "DKK", "DKK", 1e12)],
        "GER": [_q("NVD.DE", "NVIDIA Corporation", "EUR", "USD", 4e12),       # US company: not European
                _q("NOV.DE", "Novo Nordisk A/S", "EUR", "DKK", 1.3e11),        # same company, away from home
                _q("SIE.DE", "Siemens AG", "EUR", "EUR", 2e11),
                _q("TINY.DE", "Tiny AG", "EUR", "EUR", 1e7),                   # below the floor
                _q("FUND.DE", "Some Fund", "EUR", "EUR", 1e10, qt="ETF")],
        "LSE": [_q("SHEL.L", "Shell plc", "GBp", "USD", 2.2e11),               # reports in USD, kept as STOXX member
                _q("HSBA.L", "HSBC Holdings plc", "GBp", "USD", 2.4e11)],      # USD reporter, not in keep -> dropped
    }
    df = sources.home_listings(quotes, FX, min_cap_dkk=3e8, keep={"SHEL.L"}).set_index("ticker")
    assert set(df.index) == {"NOVO-B.CO", "SIE.DE", "SHEL.L"}
    assert df.loc["SHEL.L", "market_cap_dkk"] == pytest.approx(2.2e11 * 8.6)   # GBp quote, cap in GBP
    assert df.loc["SIE.DE", "country"] == "Germany"


def test_check_counts_fails_loudly():
    df = pd.DataFrame({"exchange": ["CPH"] * 5})
    sources.check_counts(df, {"CPH": 5}, "Nordic")
    with pytest.raises(ValueError, match="CPH 5 < 60"):
        sources.check_counts(df, {"CPH": 60}, "Nordic")


def test_isin_mapping_is_cached_and_prefers_exchanges():
    calls = []

    def search(isin):
        calls.append(isin)
        if isin == "IE0000000001":
            return [{"symbol": "AAA.L", "quoteType": "ETF", "exchange": "LSE", "longname": "AAA ETF"},
                    {"symbol": "AAA.DE", "quoteType": "ETF", "exchange": "GER", "longname": "AAA ETF"}]
        if isin == "LU0000000002":
            return [{"symbol": "0P0000X", "quoteType": "MUTUALFUND", "exchange": "LUX"}]
        if isin == "IE0000000003":
            raise ConnectionError("rate limited")
        return []
    empty = pd.DataFrame(columns=["isin", "symbol", "exchange", "yahoo_name", "quote_type"])
    isins = ["IE0000000001", "LU0000000002", "IE0000000003", "IE0000000004"]
    m = sources.map_isins(isins, empty, ["GER", "AMS", "LSE"], search=search, workers=1).set_index("isin")
    assert m.loc["IE0000000001", "symbol"] == "AAA.DE"
    assert m.loc["LU0000000002", "symbol"] == "" and m.loc["LU0000000002", "quote_type"] == "MUTUALFUND"
    assert "IE0000000003" not in m.index                  # a failed search is retried next time
    assert m.loc["IE0000000004", "symbol"] == ""          # unresolved, cached as such
    calls.clear()
    sources.map_isins(isins, m.reset_index(), ["GER"], search=search, workers=1)
    assert calls == ["IE0000000003"]


def test_one_share_class_per_sub_fund():
    funds = pd.DataFrame({"isin": ["I1", "I2", "I3", "I4"],
                          "share_class": ["World EUR Hedged (Acc)", "World USD (Dist)", "World USD (Acc)", "Gold"],
                          "sub_fund": ["World", "World", "World", "Gold fund"]})
    m = pd.DataFrame({"isin": ["I1", "I2", "I3", "I4"], "symbol": ["W1.DE", "W2.DE", "W3.L", "G.DE"],
                      "exchange": ["GER", "GER", "LSE", "GER"], "yahoo_name": "", "quote_type": "ETF"})
    picked = sources.pick_share_classes(funds, m, ["GER", "LSE"]).set_index("sub_fund")
    assert picked.loc["World", "symbol"] == "W3.L"          # unhedged and accumulating beats the exchange order
    assert picked.loc["Gold fund", "symbol"] == "G.DE"


def test_etf_category_by_name():
    table = [["Bonds", ["BOND", "TREASUR"]], ["Technology & AI", ["SEMICONDUCTOR"]], ["Global", ["WORLD"]]]
    assert sources.etf_category("iShares Core MSCI World", table) == "Global"
    assert sources.etf_category("VanEck Semiconductor UCITS", table) == "Technology & AI"
    assert sources.etf_category("Xtrackers II US Treasuries", table) == "Bonds"
    assert sources.etf_category("Something else", table) == "Other"


def test_retry_waits_out_rate_limits_but_not_other_errors():
    waits, calls = [], []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("Too Many Requests. Rate limited. Try after a while.")
        return "ok"
    assert sources.retry(flaky, wait=5, sleep=waits.append) == "ok" and waits == [5, 10]
    with pytest.raises(ValueError):
        sources.retry(lambda: (_ for _ in ()).throw(ValueError("bad layout")), sleep=waits.append)


def test_nordic_and_swiss_companies_abroad_are_cross_listings():
    quotes = {"GER": [_q("NOVA.DE", "Novo Nordisk A/S", "EUR", "DKK", 1.3e11),     # Danish reporter in Germany
                      _q("NESA.DE", "Nestle SA", "EUR", "CHF", 2e11),
                      _q("BAS.DE", "BASF SE", "EUR", "EUR", 4e10)]}
    df = sources.home_listings(quotes, FX, 3e8)
    assert list(df["ticker"]) == ["BAS.DE"]


def test_names_already_in_another_market_are_dropped():
    europe = pd.DataFrame({"ticker": ["04Q.DE", "SIE.DE", "NDA-FI.HE"], "name": ["Nordea Bank Abp", "Siemens AG", "Nordea Bank Abp"]})
    out = sources.drop_known_names(europe, ["Nordea Bank Abp", "Volvo AB"], keep={"NDA-FI.HE"})
    assert list(out["ticker"]) == ["SIE.DE", "NDA-FI.HE"]


def test_isin_lookups_stop_when_yahoo_keeps_refusing(monkeypatch):
    monkeypatch.setattr(sources, "MAX_FAILURES", 3)
    calls = []

    def refused(isin):
        calls.append(isin)
        raise RuntimeError("HTTP Error 401: Invalid Crumb")
    empty = pd.DataFrame(columns=["isin", "symbol", "exchange", "yahoo_name", "quote_type"])
    out = sources.map_isins([f"IE{i:010d}" for i in range(20)], empty, ["GER"], search=refused, workers=1)
    assert len(calls) == 3 and out.empty           # nothing cached: all are tried again next scan
    assert sources.throttled(RuntimeError("HTTP Error 401: Invalid Crumb"))
    assert not sources.throttled(ValueError("no Emittententicker header"))


def test_an_unresolved_isin_is_searched_again_after_a_while():
    from datetime import date

    import pandas as pd

    from radar.discovery import sources
    cached = pd.DataFrame([{"isin": "IE0000000001", "symbol": "", "exchange": "", "yahoo_name": "", "quote_type": "",
                            "searched": "2026-06-01"},
                           {"isin": "IE0000000002", "symbol": "", "exchange": "", "yahoo_name": "", "quote_type": "",
                            "searched": "2026-10-01"}])
    asked = []
    found = lambda i: asked.append(i) or [{"symbol": "XYZ.DE", "quoteType": "ETF", "exchange": "GER"}]  # noqa: E731
    out = sources.map_isins(["IE0000000001", "IE0000000002"], cached, ["GER"], search=found,
                            today=date(2026, 10, 15))
    assert asked == ["IE0000000001"]                       # 136 days since the last try; the other is recent
    row = out[out["isin"] == "IE0000000001"].iloc[-1]
    assert row["symbol"] == "XYZ.DE" and row["searched"] == "2026-10-15"
    assert (out["isin"] == "IE0000000001").sum() == 1      # replaced, not duplicated
