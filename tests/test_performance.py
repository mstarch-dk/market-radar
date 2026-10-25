"""Portfolio returns over time (performance.py) on the synthetic world, where every answer is known in advance:
S1 grows 0.12% a bar, S2 0.10%, ACWI 0.04%, everything is quoted in USD and USD/DKK is 6.5."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import world
from fakes import LOCAL
from radar import api, mine, userstore
from radar.api_models import Comparison, Performance
from radar.config import settings
from radar.market import Market
from radar.portfolios import performance
from radar.reporting import dashboard, report
from radar.sources import fxrates, ingest
from world import IDX, N

FX = 6.5
c1 = lambda i: 100 * 1.0012 ** i            # noqa: E731
c2 = lambda i: 100 * 1.0010 ** i            # noqa: E731
acwi = lambda i: 100 * 1.0004 ** i          # noqa: E731
END = N - 1


@pytest.fixture
def market(tmp_data, monkeypatch):
    extra = world.install(tmp_data, monkeypatch)
    v = np.full(N, 100.0)                                     # GAPPY: no prices for 20 sessions in the middle
    gappy = world.bars("GAPPY", 100 * 1.001 ** np.arange(N))
    extra["GAPPY"] = gappy.drop(index=range(120, 140))
    div = world.bars("DIV", v)                                # DIV: adjusted 100 flat; traded 102 until a 2.00
    div["raw_close"] = np.where(np.arange(N) < 200, 102.0, 100.0)   # dividend goes ex at bar 200
    extra["DIV"] = div
    performance.reset()
    return Market.load()


def _buy(sym, i, qty, price, **kw):
    return {"symbol": sym, "date": IDX[i].date().isoformat(), "type": "BUY", "quantity": qty, "price": price, "fee": 0.0} | kw


def _sell(sym, i, qty, price, **kw):
    return _buy(sym, i, qty, price, **kw) | {"type": "SELL"}


def _cash(kind, i, amount, sym=None):
    return {"symbol": sym, "date": IDX[i].date().isoformat(), "type": kind, "amount": amount, "currency": "DKK"}


def _run(rows, market, dividends="reinvested", **kw):
    return performance.analyze(performance.book(rows, market, dividends), market, **kw)


def test_a_fully_invested_ledger_earns_the_stock_and_acwi_its_own(market):
    res = _run([_cash("DEPOSIT", 50, 10 * c1(50) * FX), _buy("S1", 50, 10, c1(50))], market)
    st = res["stats"]
    assert res["funding"] == "ledger" and st["start"] == IDX[50].date().isoformat()
    assert st["twr_total"] == pytest.approx(1.0012 ** (END - 50) - 1, abs=1e-9)
    assert st["acwi_twr_total"] == pytest.approx(1.0004 ** (END - 50) - 1, abs=1e-9)
    assert st["value_dkk"] == pytest.approx(10 * c1(END) * FX)
    assert res["series"]["cash_dkk"][-1] == pytest.approx(0, abs=1e-6)


def test_more_money_later_barely_changes_the_time_weighted_return(market):
    rows = [_cash("DEPOSIT", 50, 10 * c1(50) * FX), _buy("S1", 50, 10, c1(50)),
            _cash("DEPOSIT", 150, 5 * c1(150) * FX), _buy("S1", 150, 5, c1(150))]
    twr = _run(rows, market)["stats"]["twr_total"]
    # a deposit counts from the start of its day: on bar 150 the new money sat as cash until the close
    day150 = 15 * c1(150) / (10 * c1(149) + 5 * c1(150))
    assert twr == pytest.approx((c1(149) / c1(50)) * day150 * (c1(END) / c1(150)) - 1, abs=1e-9)
    assert twr == pytest.approx(1.0012 ** (END - 50) - 1, abs=1e-3)


def test_without_a_ledger_it_matches_the_holdings_tables_shadow_method(market):
    report.build()                                   # world: S1 bought at bar 50, held in Main (no cash rows)
    rows = userstore.transactions()
    res = _run(rows, market)
    me = {r["symbol"]: r for r in mine.table(market.closes, market.highs, market.lows, market.volumes,
                                             market.raw_closes(), market.leaders(), [], None, settings())}
    assert res["funding"] == "implicit"
    assert res["stats"]["twr_total"] == pytest.approx(me["S1"]["since_buy"], abs=1e-9)
    assert res["stats"]["acwi_twr_total"] == pytest.approx(me["S1"]["bench_since_buy"], abs=1e-9)
    sf = res["series"]["acwi_same_flows_dkk"][-1]
    assert sf / res["stats"]["invested_dkk"] - 1 == pytest.approx(me["S1"]["bench_since_buy"], abs=1e-9)


def test_the_first_day_counts_the_fee_and_the_trade_price(market):
    res = _run([_buy("S1", 50, 10, c1(50), fee=12)], market)
    assert res["series"]["index"][0] == pytest.approx(100 * (10 * c1(50)) / (10 * c1(50) + 12))


def test_selling_everything_leaves_a_gap_and_buying_again_resumes(market):
    rows = [_buy("S1", 50, 10, c1(50)), _sell("S1", 100, 10, c1(100)), _buy("S1", 200, 3, c1(200))]
    res = _run(rows, market)
    idx = res["series"]["index"]
    dates = res["series"]["dates"]
    at = lambda i: idx[dates.index(IDX[i].date().isoformat())]  # noqa: E731
    assert at(100) == pytest.approx(100 * c1(100) / c1(50))
    assert at(101) is None and at(199) is None                      # no capital: no return, never 0
    assert idx[-1] == pytest.approx(100 * (c1(100) / c1(50)) * (c1(END) / c1(200)))
    st = res["stats"]["periods"]                                    # 6m starts on a day without capital: flat,
    assert st["6m"]["portfolio"] == pytest.approx(c1(END) / c1(200) - 1)   # known, so only the new money counts


def test_a_missing_price_is_a_gap_not_a_zero(market):
    res = _run([_buy("GAPPY", 100, 10, 100 * 1.001 ** 100)], market)
    idx, dates = res["series"]["index"], res["series"]["dates"]
    assert None in idx and 0 not in res["series"]["value_dkk"]
    assert idx[-1] == pytest.approx(100 * 1.001 ** (END - 100))      # chained across the gap
    assert any("gaps" in n for n in res["notes"])
    per = res["stats"]["periods"]
    assert per["3m"]["portfolio"] == pytest.approx(1.001 ** 63 - 1)      # after the gap: known
    series = pd.Series([np.nan if v is None else v for v in idx], index=pd.to_datetime(dates))
    assert performance.period_return(series, END - 130) is None                 # starts inside the gap: unknown
    res = _run([_buy("NOPX", 100, 1, 10)], market)                    # never had prices
    assert res["missing"] == ["NOPX: no prices"] and all(v is None for v in res["series"]["value_dkk"])


def test_positions_add_up_to_the_holdings_with_the_same_gaps(market):
    rows = [_buy("S1", 50, 10, c1(50)), _sell("S1", 100, 4, c1(100)), _buy("GAPPY", 110, 10, 100 * 1.001 ** 110)]
    b = performance.book(rows, market)
    assert list(b.positions.columns) == ["GAPPY", "S1"]
    total = b.positions.sum(axis=1, min_count=1)
    assert total.isna().equals(b.holdings.isna())                       # GAPPY's missing prices: unknown, not 0
    assert np.allclose(total.dropna(), b.holdings.dropna())
    at = b.positions.index.get_loc(IDX[80])
    assert b.positions["S1"].iloc[at] == pytest.approx(10 * c1(80) * FX)
    assert b.positions["GAPPY"].iloc[at] == 0                           # not held yet
    assert b.positions["S1"].iloc[-1] == pytest.approx(6 * c1(END) * FX)
    nopx = performance.book([_buy("NOPX", 100, 1, 10)], market)         # never priced: unknown while held
    assert nopx.positions["NOPX"].isna().all()

    other = performance.book([_buy("S2", 150, 5, c2(150))], market)
    pooled = performance.pool([b, other])
    assert list(pooled.positions.columns) == ["GAPPY", "S1", "S2"]
    assert pooled.positions["S2"].loc[: IDX[149]].eq(0).all()           # before that book opened: not held
    assert pooled.positions["S1"].equals(b.positions["S1"].reindex(pooled.dates, fill_value=0.0))
    assert pooled.positions["S2"].iloc[-1] == pytest.approx(5 * c2(END) * FX)


def test_an_unpriced_trade_after_the_last_close_leaves_the_history_known(market, monkeypatch):
    monkeypatch.setattr(fxrates, "currencies", lambda ts: {t: None if t == "NOPX" else "USD" for t in ts})
    today = (IDX[END] + pd.Timedelta(days=3)).date().isoformat()      # booked before the next update
    rows = [_cash("DEPOSIT", 50, 10 * c1(50) * FX), _buy("S1", 50, 10, c1(50)),
            _buy("NOPX", 0, 1, 10) | {"date": today}]
    res = _run(rows, market)
    assert any("NOPX" in m for m in res["missing"])                    # the gap is still said
    assert res["stats"]["value_dkk"] == pytest.approx(10 * c1(END) * FX)
    assert res["stats"]["twr_total"] == pytest.approx(1.0012 ** (END - 50) - 1, abs=1e-9)


def test_dividends_count_once_either_way(market):
    buy = _buy("DIV", 100, 10, 102.0)
    reinvested = _run([_cash("DEPOSIT", 100, 10 * 102 * FX), buy, _cash("DIVIDEND", 200, 10 * 2 * FX, "DIV")], market)
    cash = _run([_cash("DEPOSIT", 100, 10 * 102 * FX), buy, _cash("DIVIDEND", 200, 10 * 2 * FX, "DIV")], market, "cash")
    assert reinvested["stats"]["twr_total"] == pytest.approx(0, abs=1e-9)   # adjusted prices: dividend inside
    assert cash["stats"]["twr_total"] == pytest.approx(0, abs=1e-9)         # traded prices + the cash dividend
    assert cash["stats"]["value_dkk"] == pytest.approx(reinvested["stats"]["value_dkk"])
    assert any("not counted" in n for n in reinvested["notes"])


def test_a_booked_rate_is_used_for_the_money_put_in(market):
    res = _run([_buy("S1", 50, 10, c1(50), fx_rate=7.0)], market)
    assert res["series"]["index"][0] == pytest.approx(100 * FX / 7.0)


def test_money_weighted_equals_annualised_time_weighted_with_one_flow(market):
    st = _run([_buy("S1", 0, 10, c1(0))], market)["stats"]
    days = (IDX[END] - IDX[0]).days
    assert days >= 365
    assert st["mwr_ann"] == pytest.approx((1 + st["twr_total"]) ** (365 / days) - 1, rel=1e-6)


def test_rows_older_than_the_price_history_open_the_series(market):
    old = (IDX[0] - pd.Timedelta(days=40)).date().isoformat()
    res = _run([_buy("S1", 0, 10, 90.0) | {"date": old}], market)
    idx = res["series"]["index"]
    assert idx[0] == 100 and res["stats"]["start"] == IDX[0].date().isoformat()
    assert res["stats"]["twr_total"] == pytest.approx(1.0012 ** END - 1, abs=1e-9)   # from what was held then
    assert any("Prices start" in n for n in res["notes"])
    assert res["series"]["invested_dkk"][0] == pytest.approx(10 * c1(0) * FX)       # opening value as money put in


def test_a_break_leaves_one_days_return_out():
    d = pd.bdate_range("2026-01-05", periods=5)
    v = pd.Series([100.0, 110.0, 220.0, 231.0, 231.0], index=d)       # day 2: +100 of unknown size came in
    zero = pd.Series(0.0, index=d)
    inflow = zero.copy()
    inflow.iloc[0] = 100.0
    brk = pd.Series([False, False, True, False, False], index=d)
    idx = performance.twr(v, inflow, zero, breaks=brk)
    assert idx.iloc[1] == pytest.approx(110) and np.isnan(idx.iloc[2])
    assert idx.iloc[3] == pytest.approx(110 * 1.05) and idx.iloc[4] == pytest.approx(110 * 1.05)


def test_xirr_known_answers():
    t0 = pd.Timestamp("2025-01-01")
    assert performance.xirr([t0, pd.Timestamp("2026-01-01")], [-100, 110]) == pytest.approx(0.10, abs=1e-6)
    assert performance.xirr([t0, pd.Timestamp("2026-01-01")], [-100, -5]) is None


# ---------------- through the store and the API ----------------

@pytest.fixture
def client(market, monkeypatch):
    monkeypatch.setattr(ingest, "update_prices", lambda tickers, progress=None: {})
    api.reset()
    dashboard.reset()
    return TestClient(api.app, base_url=LOCAL)


def _portfolio(name, rows, tags=()):
    pid = userstore.save_portfolio({"name": name, "mode": "virtual", "tags": list(tags)})
    for r in rows:
        userstore.add_tx(r | {"portfolio_id": pid})
    return pid


def test_compare_rebases_every_line_at_the_common_start(client, market):
    a = _portfolio("A", [_cash("DEPOSIT", 50, 10 * c1(50) * FX), _buy("S1", 50, 10, c1(50))], ["ab"])
    b = _portfolio("B", [_cash("DEPOSIT", 100, 10 * c2(100) * FX), _buy("S2", 100, 10, c2(100))], ["ab"])
    cmp = client.get("/api/portfolios/compare", params=[("portfolio", a), ("portfolio", b), ("tag", "ab")]).json()
    Comparison.model_validate(cmp)
    assert cmp["start"] == IDX[100].date().isoformat()
    lines = {s["name"]: s for s in cmp["chart"]["series"]}
    assert lines["A"]["values"][0] == pytest.approx(100) and lines["B"]["values"][0] == pytest.approx(100)
    assert lines["A"]["values"][-1] == pytest.approx(100 * 1.0012 ** (END - 100))
    assert lines["B"]["values"][-1] == pytest.approx(100 * 1.0010 ** (END - 100))
    assert lines["ACWI (DKK)"]["values"][-1] == pytest.approx(100 * 1.0004 ** (END - 100))
    pooled = next(r for r in cmp["rows"] if r["kind"] == "tag")
    assert pooled["members"] == ["A", "B"] and pooled["stats"]["value_dkk"] == pytest.approx(
        10 * c1(END) * FX + 10 * c2(END) * FX)


def test_the_performance_endpoint(client):
    a = _portfolio("A", [_cash("DEPOSIT", 50, 10 * c1(50) * FX), _buy("S1", 50, 10, c1(50))])
    res = client.get(f"/api/portfolios/{a}/performance").json()
    Performance.model_validate(res)
    assert res["portfolio"]["name"] == "A" and res["stats"]["twr_total"] == pytest.approx(1.0012 ** (END - 50) - 1)
    assert client.get("/api/portfolios/999/performance").status_code == 404
