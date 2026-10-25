"""attribution.py on the synthetic world: the reconciliation adds up, a world fund alone has no allocation,
unclassified and unvalued holdings are listed (never a 0 % return), and too short a history gives notes, not
numbers."""
import numpy as np
import pandas as pd
import pytest

import world
from conftest import with_settings
from radar import attribution, universe, userstore
from radar.config import write_csv
from radar.market import Market
from radar.model import stats
from radar.portfolios import performance, segments
from radar.sources import constituents, factors
from world import IDX

FX = 6.5
ATTR = {"sectors": {"Technology": "LEAD", "Financial Services": "LAG"},
        "regions": {"us": {"United States": "ACWI"}}}
SNAP = [("sector", "Technology", 0.7), ("sector", "Financial Services", 0.3), ("region", "us", 1.0),
        ("country", "United States", 1.0), ("currency", "USD", 1.0), ("sector_currency", "Technology|USD", 0.7),
        ("sector_currency", "Financial Services|USD", 0.3), ("region_currency", "us|USD", 1.0),
        ("region_country", "us|United States", 1.0)]


def px(t, i):
    return 100 * (1 + world.G[t]) ** i


@pytest.fixture
def market(tmp_data, monkeypatch):
    extra = world.install(tmp_data, monkeypatch)
    gappy = world.bars("GAPPY", 100 * 1.001 ** np.arange(world.N))
    extra["GAPPY"] = gappy.drop(index=range(200, 212))   # longer than the 5 sessions prices are carried over
    monkeypatch.setattr(segments, "universe_config", lambda: world.UNIVERSE | {"attribution": ATTR})
    secs = {"THEME1": ""}                                    # no sector: neither a stock with one nor a known fund
    monkeypatch.setattr(universe, "sectors", lambda ts: pd.DataFrame(
        {"sector": [secs.get(t, "Technology") for t in ts], "industry": "x"}, index=pd.Index(ts, name="ticker")))
    performance.reset()
    return Market.load()


def _history(day=150):
    rows = [{"asof": IDX[day].date().isoformat(), "recorded": IDX[day].date().isoformat(), "dim": d, "key": k,
             "weight": w} for d, k, w in SNAP]
    write_csv(pd.DataFrame(rows), constituents.SEGMENTS_FILE, index=False)


def _portfolio(rows):
    pid = userstore.save_portfolio({"name": "Test", "mode": "virtual", "tags": []})
    for r in rows:
        userstore.add_tx(r | {"portfolio_id": pid})
    return pid


def _buy(sym, i, qty, price):
    return {"symbol": sym, "date": IDX[i].date().isoformat(), "type": "BUY", "quantity": qty, "price": price, "fee": 0.0}


def _deposit(i, amount):
    return {"symbol": None, "date": IDX[i].date().isoformat(), "type": "DEPOSIT", "amount": amount, "currency": "DKK"}


def test_the_reconciliation_adds_up_and_the_effects_link_exactly(market):
    _history()
    pid = _portfolio([_deposit(20, 12 * px("S1", 20) * FX), _buy("S1", 20, 10, px("S1", 20))])
    v = attribution.build(market, [pid])
    rec = v["reconciliation"]
    assert rec["active"] == pytest.approx(rec["trading_fees"] + rec["proxy_vs_acwi"] + rec["attributed"], abs=1e-12)
    for dim in ("sector", "region"):
        d = v["dims"][dim]
        assert sum(d["totals"].values()) == pytest.approx(d["rp"] - d["rb"], abs=1e-8)
        assert d["linking_error"] < 1e-8 and d["days_missing"] == 0
        assert sum(m["days"] for m in d["months"]) == d["days"]
    rows = {r["key"]: r for r in v["dims"]["sector"]["rows"]}
    assert 0.1 < rows["cash"]["w_p"] < 2 / 12                                  # a sixth kept as cash, then S1 grows
    assert rows["cash"]["selection"] == 0 and rows["cash"]["interaction"] == 0  # the cash drag is allocation
    assert rows["Technology"]["w_p"] > 0.8 and rows["Financial Services"]["w_p"] == 0
    assert v["benchmark"]["first_snapshot"] == IDX[150].date().isoformat()
    assert v["benchmark"]["back_drifted_months"]                                # days before the snapshot
    assert any("proxies" in n.lower() for n in v["notes"])
    assert v["regression"] is None and any("No factor regression" in n for n in v["notes"])


def test_a_world_fund_alone_has_no_allocation(market):
    _history()
    pid = _portfolio([_deposit(20, 10 * px("ACWI", 20) * FX), _buy("ACWI", 20, 10, px("ACWI", 20))])
    v = attribution.build(market, [pid])
    d = v["dims"]["sector"]
    assert d["totals"]["allocation"] == pytest.approx(0.0, abs=1e-12)
    assert d["totals"]["interaction"] == pytest.approx(0.0, abs=1e-12)
    # what's left is ACWI's own return against the proxies' mix: selection
    assert d["totals"]["selection"] == pytest.approx(d["rp"] - d["rb"], abs=1e-8)


def test_unclassified_and_gaps_are_listed_never_zero(market):
    _history()
    pid = _portfolio([_deposit(20, 10 * (px("S1", 20) + px("THEME1", 20) + 100 * 1.001 ** 20) * FX),
                      _buy("S1", 20, 10, px("S1", 20)), _buy("THEME1", 20, 10, px("THEME1", 20)),
                      _buy("GAPPY", 20, 10, 100 * 1.001 ** 20)])
    v = attribution.build(market, [pid])
    assert [u["symbol"] for u in v["unclassified"]] == ["THEME1"]
    rows = {r["key"]: r for r in v["dims"]["sector"]["rows"]}
    assert rows["unclassified"]["r_p"] == pytest.approx(px("THEME1", world.N - 1) / px("THEME1", 20) - 1, rel=0.05)
    d = v["dims"]["sector"]
    assert d["days_missing"] >= 5                                     # GAPPY's missing prices: days left out
    assert any("left out" in n for n in v["notes"])
    rec = v["reconciliation"]
    assert rec["active"] == pytest.approx(rec["trading_fees"] + rec["proxy_vs_acwi"] + rec["attributed"], abs=1e-12)


def test_the_factor_regression_runs_on_the_books_weeks(market, monkeypatch):
    _history()
    rng = np.random.default_rng(1)
    days = pd.bdate_range(IDX[0], IDX[-1])
    five = pd.DataFrame(rng.normal(0, 0.002, (len(days), 5)), index=days, columns=["Mkt-RF", "SMB", "HML", "RMW", "CMA"])
    five["RF"] = 0.0001
    mom = pd.DataFrame({"WML": rng.normal(0, 0.002, len(days))}, index=days)
    monkeypatch.setattr(factors, "daily_panel", lambda key: five if "ff5" in key else mom)
    monkeypatch.setattr(stats, "daily_rf", lambda m: pd.Series(0.0001, index=days))
    pid = _portfolio([_deposit(20, 10 * px("S1", 20) * FX), _buy("S1", 20, 10, px("S1", 20))])
    with_settings(monkeypatch, attribution={"min_weeks": 40})
    r = attribution.build(market, [pid])["regression"]
    assert r is not None and r["n_weeks"] >= 40 and r["alpha_t"] is not None
    assert r["factors_to"] == IDX[-1].date().isoformat() and len(r["loadings"]) == 6
    with_settings(monkeypatch, attribution={"min_weeks": 400})
    attribution.reset()
    v = attribution.build(market, [pid])
    assert v["regression"] is None and any("at least 400 are needed" in n for n in v["notes"])


def test_too_short_or_without_acwi_weights_gives_notes(market):
    pid = _portfolio([_deposit(20, 10 * px("S1", 20) * FX), _buy("S1", 20, 10, px("S1", 20))])
    v = attribution.build(market, [pid])
    assert v["dims"] == {} and any("weekly record of ACWI" in n for n in v["notes"])
    _history()
    short = attribution.build(market, [pid], start=IDX[-60].date().isoformat())
    assert short["dims"] == {} and short["reconciliation"] is None
    assert any("months of history" in n for n in short["notes"])
    assert attribution.build(market, [])["notes"] == ["No transactions in this selection"]
