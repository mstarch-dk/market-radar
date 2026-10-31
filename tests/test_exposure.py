"""Fund classification and exposure coverage (portfolios/exposure.py): a fund is looked through where the data
allows or labelled 'fund: not looked through', never filed under where it is listed; coverage says how much of the
value each dimension could classify, and only real keys count as active weight."""
from __future__ import annotations

import pandas as pd
import pytest

from radar import universe
from radar.config_schema import SettingsError, check_index_funds
from radar.portfolios import exposure as ex
from radar.sources import constituents, external, tracked

STOCK_SECTORS = {"S1": "Technology", "RY.TO": "Financial Services", "NOVO-B.CO": "Healthcare"}


def _fund(sectors: dict[str, float] | None) -> dict:
    raw = {"symbol": "x", "fetched": "2026-09-01T08:00:00", "info": {"quoteType": "ETF"}}
    if sectors is not None:
        raw["fund"] = {"sector_weightings": sectors}
    return raw


DETAILS = {
    "SEMI.L": _fund({"technology": 0.8, "industrials": 0.15}),              # one sector >= 50 %: a sector fund
    "WIDE500.L": _fund({"technology": 0.3, "healthcare": 0.2, "financial_services": 0.2, "industrials": 0.3}),
    "BARE.L": _fund(None),                                                   # a fund, but no sector weights
}


class FakePrices:
    CCY = {"S1": "USD", "RY.TO": "CAD", "NOVO-B.CO": "DKK", "SEMI.L": "USD", "WIDE500.L": "USD", "BARE.L": "GBp"}

    def preload(self, tickers):
        pass

    def ccy(self, t):
        return self.CCY.get(t)


@pytest.fixture
def meta(monkeypatch):
    monkeypatch.setattr(universe, "sectors", lambda ts: pd.DataFrame(
        {"sector": [STOCK_SECTORS.get(t, "") for t in ts], "industry": "x"}, index=pd.Index(ts, name="ticker")))
    monkeypatch.setattr(external, "cached_detail", lambda t: (
        (DETAILS[t], "ok", DETAILS[t]["fetched"]) if t in DETAILS else (None, "missing", None)))
    bench = tracked.benchmark()
    tickers = [bench, "XLK", "EXV3.DE", "SEMI.L", "WIDE500.L", "BARE.L", "S1", "RY.TO", "NOVO-B.CO", "MYSTERY.L"]
    return ex.ticker_meta(tickers, FakePrices()), bench


def test_fund_classes(meta):
    m, bench = meta
    assert m.loc[bench, "class"] == "world"
    assert m.loc["XLK", ["class", "sector", "region", "currency"]].tolist() == [
        "sector_fund", "Technology", "us", "USD"]                          # a universe.yaml sector ETF, US map
    assert m.loc["EXV3.DE", ["class", "sector", "region", "currency"]].tolist() == [
        "sector_fund", "Technology", "europe", ex.NOT_LOOKED_THROUGH]      # a European sector map: currency unknown
    semi = m.loc["SEMI.L"]
    assert semi["class"] == "sector_fund" and semi["sector"] == "Technology" and semi["detail_asof"] == "2026-09-01"
    assert semi["sector_weights"] == {"Technology": 0.8, "Industrials": 0.15}
    wide = m.loc["WIDE500.L"]                                                # an S&P 500-like fund listed in London
    assert wide["class"] == "fund_sectors" and wide["region"] == ex.NOT_LOOKED_THROUGH != "europe"
    assert wide["currency"] == ex.NOT_LOOKED_THROUGH and wide["sector"] == ex.NOT_LOOKED_THROUGH
    assert m.loc["BARE.L", ["class", "sector", "region", "currency"]].tolist() == [
        "fund", ex.NOT_LOOKED_THROUGH, ex.NOT_LOOKED_THROUGH, ex.NOT_LOOKED_THROUGH]
    assert m.loc["S1", ["class", "sector", "region", "currency"]].tolist() == ["stock", "Technology", "us", "USD"]
    assert m.loc["S1", "detail_asof"] is None                       # None, not pandas' NaN: the API wants str | None
    assert m.loc["RY.TO", ["region", "currency"]].tolist() == ["other", "CAD"]          # Canada: ACWI's "other"
    assert m.loc["NOVO-B.CO", "region"] == "nordic"
    assert m.loc["MYSTERY.L", ["class", "sector", "region", "currency"]].tolist() == ["unknown"] + [ex.UNKNOWN] * 3
    assert set(m["class"]) <= set(ex.CLASSES)


ACWI = {"sector": {"Technology": 0.3, "Healthcare": 0.1, "Financial Services": 0.2, "Industrials": 0.4},
        "region": {"us": 0.6, "europe": 0.2, "nordic": 0.05, "asia": 0.1, "other": 0.05},
        "currency": {"USD": 0.65, "EUR": 0.15, "DKK": 0.05, "JPY": 0.15}}


def test_exposure_coverage(meta):
    m, bench = meta
    values = {bench: 100.0, "S1": 100.0, "WIDE500.L": 200.0, "SEMI.L": 100.0}
    e = ex.exposures(values, m, ACWI)
    for d in ex.DIMS:
        assert sum(e["weights"][d].values()) == pytest.approx(1)
    # sector: the world fund, the stock and both funds' named sectors; only SEMI's unnamed 5 % is uncovered
    assert e["coverage"]["sector"] == pytest.approx(1 - 0.05 * 100 / 500)
    assert e["weights"]["sector"][ex.FUND_OTHER] == pytest.approx(0.05 * 100 / 500)
    # region and currency: neither fund is looked through, so 300 of 500 DKK is uncovered
    assert e["coverage"]["region"] == pytest.approx(0.4) and e["coverage"]["currency"] == pytest.approx(0.4)
    assert e["weights"]["region"][ex.NOT_LOOKED_THROUGH] == pytest.approx(0.6)
    assert e["weights"]["region"]["europe"] == pytest.approx(100 * 0.2 / 500)          # only via the world fund
    for d in ex.DIMS:                                    # never active weight: not a region, sector or currency
        assert not set(e["active"][d]) & ex.UNCOVERED
    assert e["active"]["region"]["us"] == pytest.approx((100 + 100 * 0.6) / 500 - 0.6)


def test_exposure_without_acwi_weights_is_uncovered_for_world_funds(meta):
    m, bench = meta
    e = ex.exposures({bench: 100.0, "S1": 100.0}, m, None)
    assert e["active"] is None and e["coverage"]["region"] == pytest.approx(0.5)
    assert e["weights"]["region"][ex.ACWI_UNKNOWN] == pytest.approx(0.5)
    assert ex.exposures({}, m, ACWI)["coverage"] == {d: None for d in ex.DIMS}


# ---------------- index funds (config/index_funds.yaml) ----------------

HOLDINGS = pd.DataFrame([      # ACWI's holdings as constituents.parse_acwi_holdings gives them (German countries)
    {"ticker": "AAPL", "sector": "Technology", "country": "Vereinigte Staaten", "region": "us", "currency": "USD", "weight": 0.5},
    {"ticker": "JPM", "sector": "Financial Services", "country": "Vereinigte Staaten", "region": "us", "currency": "USD", "weight": 0.2},
    {"ticker": "NOVO", "sector": "Healthcare", "country": "Dänemark", "region": "nordic", "currency": "DKK", "weight": 0.1},
    {"ticker": "DSV", "sector": "Industrials", "country": "Dänemark", "region": "nordic", "currency": "DKK", "weight": 0.1},
    {"ticker": "TSMC", "sector": "Technology", "country": "Taiwan", "region": "asia", "currency": "TWD", "weight": 0.1},
]).assign(name="x", asof="2026-10-23")


INDEX_FUNDS = check_index_funds({
    "indexes": {"world": {"label": "MSCI World", "countries": ["United States", "Denmark"]},
                "em": {"label": "MSCI EM", "countries": "all", "exclude": ["United States", "Denmark"],
                       "note": "a caveat"},
                "dk": {"label": "Denmark", "countries": ["Denmark"]}},
    "funds": {"WORLD.CO": {"name": "World", "index": "world"},
              "WORLDH.CO": {"name": "World hedged", "index": "world", "hedged": "DKK"},
              "EM.CO": {"name": "EM", "index": "em"},
              "DK.CO": {"name": "Denmark", "index": "dk"}}})


@pytest.fixture
def index_meta(monkeypatch):
    monkeypatch.setattr(ex, "index_funds", lambda: INDEX_FUNDS)
    monkeypatch.setattr(universe, "sectors", lambda ts: pd.DataFrame(
        {"sector": [""] * len(ts), "industry": "x"}, index=pd.Index(ts, name="ticker")))
    monkeypatch.setattr(external, "cached_detail", lambda t: (None, "missing", None))
    monkeypatch.setattr(constituents, "acwi_holdings", lambda **kw: HOLDINGS)
    return ex.ticker_meta(["WORLD.CO", "WORLDH.CO", "EM.CO", "DK.CO"], FakePrices())


def test_an_index_fund_is_counted_as_its_index(index_meta):
    m = index_meta
    w = m.loc["WORLD.CO"]
    assert w["class"] == "index_fund" and w["detail_asof"] == "2026-10-23"
    assert w["sector"] == w["region"] == w["currency"] == ex.SPREAD          # several keys: spread, never listed
    assert w["sector_weights"] == pytest.approx({"Technology": 0.5 / 0.9, "Financial Services": 0.2 / 0.9,
                                                 "Healthcare": 0.1 / 0.9, "Industrials": 0.1 / 0.9})
    assert w["region_weights"] == pytest.approx({"us": 0.7 / 0.9, "nordic": 0.2 / 0.9})   # Taiwan is not in it
    assert m.loc["WORLDH.CO", "currency"] == "DKK" and m.loc["WORLDH.CO", "currency_weights"] == {"DKK": 1.0}
    assert m.loc["WORLDH.CO", "region_weights"] == w["region_weights"]       # hedging moves only the currency
    assert m.loc["EM.CO", ["region", "currency"]].tolist() == ["asia", "TWD"]   # one key: named as it
    assert m.loc["DK.CO", ["sector", "region", "currency"]].tolist() == [ex.SPREAD, "nordic", "DKK"]


def test_index_fund_exposure_and_coverage(index_meta):
    e = ex.exposures({"WORLDH.CO": 90.0, "DK.CO": 10.0}, index_meta, ACWI)
    assert e["coverage"] == {d: pytest.approx(1) for d in ex.DIMS}
    assert e["weights"]["currency"] == pytest.approx({"DKK": 1.0})
    assert e["weights"]["region"]["nordic"] == pytest.approx(0.9 * 0.2 / 0.9 + 0.1)
    assert e["weights"]["sector"]["Healthcare"] == pytest.approx(0.9 * 0.1 / 0.9 + 0.1 * 0.5)


def test_an_index_fund_without_acwi_holdings_is_not_looked_through(monkeypatch, index_meta):
    monkeypatch.setattr(constituents, "acwi_holdings", lambda **kw: None)
    m = ex.ticker_meta(["WORLD.CO", "WORLDH.CO"], FakePrices())
    assert m.loc["WORLD.CO", ["class", "sector", "region", "currency"]].tolist() == [
        "fund", ex.NOT_LOOKED_THROUGH, ex.NOT_LOOKED_THROUGH, ex.NOT_LOOKED_THROUGH]
    assert m.loc["WORLDH.CO", ["class", "currency"]].tolist() == ["fund", "DKK"]     # the hedge is still known


def test_index_funds_are_diversified_not_looked_through_as_acwi(monkeypatch):
    monkeypatch.setattr(ex, "index_funds", lambda: INDEX_FUNDS)
    assert {"WORLD.CO", "DK.CO"} <= ex.diversified() and not {"WORLD.CO", "DK.CO"} & ex.look_through()


def test_an_index_naming_an_unknown_index_fails_at_load():
    with pytest.raises(SettingsError, match="X.CO"):
        check_index_funds({"indexes": {}, "funds": {"X.CO": {"name": "x", "index": "nope"}}})
