"""Forks (a virtual copy of a portfolio at a day's close, for A/B tests) and the interface simulations write
through: one checked, idempotent run per simulated portfolio, never into a real one."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import world
from radar import api, dashboard, ingest, performance, profile, simulate, userstore
from world import IDX, N

FX = 6.5
c1 = lambda i: 100 * 1.0012 ** i            # noqa: E731
END = N - 1


@pytest.fixture
def market(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(performance, "_cache", {})
    return profile.Market.load()


class BuyAndHold:
    """A test strategy: deposit the capital, put it all into one symbol at the first close."""
    key = "buy-and-hold"

    def rows(self, market, start, end, capital_dkk, params):
        sym = params["symbol"]
        day = market.closes.index[market.closes.index >= start][0]
        px = float(market.closes.loc[day, sym])
        qty = int(capital_dkk / (px * FX))
        return [{"date": day.date().isoformat(), "type": "DEPOSIT", "amount": capital_dkk},
                {"symbol": sym, "date": day.date().isoformat(), "type": "BUY", "quantity": qty, "price": px}]


def test_a_fork_starts_level_with_its_source(market):
    userstore.watch("X")
    src = userstore.default_portfolio() or userstore.save_portfolio({"name": "Main"})
    userstore.add_tx({"symbol": "S1", "date": IDX[50].date().isoformat(), "type": "BUY", "quantity": 10,
                      "price": c1(50), "portfolio_id": src})
    at = IDX[150].date().isoformat()
    fork = simulate.fork(src, "Main, copy", at, market, extra_cash_dkk=1000, tags=["ab"])
    f = userstore.get_portfolio(fork)
    assert (f["mode"], f["origin"], f["parent_id"], f["forked_at"], f["tags"]) == ("virtual", "fork", src, at, ["ab"])
    rows = userstore.transactions(portfolios=[fork])
    assert [(r["type"], r["quantity"]) for r in rows] == [("DEPOSIT", None), ("BUY", 10)]
    assert rows[0]["amount"] == pytest.approx(10 * c1(150) * FX + 1000)
    cmp = performance.compare(market, [src, fork], start=at)
    lines = {s["name"]: s["values"] for s in cmp["chart"]["series"]}
    assert lines["Main"][0] == lines["Main, copy"][0] == 100                # both open at that close
    # the copy also holds 1000 DKK cash, so it trails a little: same shares, a larger base
    expected = (10 * c1(END) * FX + 1000) / (10 * c1(150) * FX + 1000)
    assert lines["Main, copy"][-1] == pytest.approx(100 * expected)
    assert lines["Main"][-1] == pytest.approx(100 * c1(END) / c1(150))
    with pytest.raises(ValueError, match="already"):
        simulate.fork(src, "Main, copy", at, market)


def test_a_run_is_checked_stored_once_and_rerun_in_place(market):
    pid = simulate.new_sim_portfolio("BH S1", "buy-and-hold", {"symbol": "S1"}, tags=["sim"])
    start = IDX[100].date().isoformat()
    first = simulate.run(BuyAndHold(), pid, start, IDX[-1].date().isoformat(), 100_000, market, {"symbol": "S1"})
    again = simulate.run(BuyAndHold(), pid, start, IDX[-1].date().isoformat(), 100_000, market, {"symbol": "S1"})
    rows = userstore.transactions(portfolios=[pid])
    assert len(rows) == 2 and {r["source"] for r in rows} == {"sim"} and {r["run_id"] for r in rows} == {again["run_id"]}
    assert [r["id"] for r in userstore.sim_runs(pid)] == [again["run_id"]] != [first["run_id"]]
    assert again["stats"]["twr_total"] == pytest.approx(first["stats"]["twr_total"])
    assert pid not in userstore.portfolio_ids()                                  # never yours


def test_runs_never_go_into_real_or_ordinary_portfolios(market):
    plain = userstore.save_portfolio({"name": "Plain virtual", "mode": "virtual"})
    ask = userstore.portfolio_by_name("ASK")["id"]                               # seeded with the store
    with pytest.raises(ValueError, match="already"):
        userstore.save_portfolio({"name": "ASK"})
    for pid in (ask, plain):
        with pytest.raises(ValueError, match="simulations"):
            simulate.run(BuyAndHold(), pid, IDX[100], IDX[-1], 10_000, market, {"symbol": "S1"})


def test_a_run_that_does_not_add_up_stores_nothing(market):
    pid = simulate.new_sim_portfolio("Broken", "x")
    day = IDX[100].date().isoformat()
    over = [{"date": day, "type": "DEPOSIT", "amount": 100},
            {"symbol": "S1", "date": day, "type": "BUY", "quantity": 10, "price": c1(100)}]   # costs far more
    with pytest.raises(ValueError, match="negative"):
        simulate.write_run(pid, "x", {}, day, None, over, market)
    oversold = [{"date": day, "type": "DEPOSIT", "amount": 1e6},
                {"symbol": "S1", "date": day, "type": "SELL", "quantity": 1, "price": c1(100)}]
    with pytest.raises(ValueError, match="sold 1"):
        simulate.write_run(pid, "x", {}, day, None, oversold, market)
    with pytest.raises(ValueError, match="type"):
        simulate.write_run(pid, "x", {}, day, None, [{"date": day, "type": "DIVIDEND", "amount": 1}], market)
    assert userstore.transactions(portfolios=[pid]) == [] and userstore.sim_runs(pid) == []


def test_fork_through_the_api(market, monkeypatch):
    monkeypatch.setattr(ingest, "update_prices", lambda tickers, progress=None: {})
    monkeypatch.setattr(api, "_market", None)
    monkeypatch.setattr(dashboard, "_cache", None)
    client = TestClient(api.app)
    client.get("/api/portfolios")                                                # moves the world's trade in
    main = next(p for p in client.get("/api/portfolios").json() if p["name"] == "Main")
    r = client.post(f"/api/portfolios/{main['id']}/fork", json={"name": "B", "date": IDX[200].date().isoformat()})
    assert r.status_code == 200 and r.json()["mode"] == "virtual" and r.json()["origin"] == "fork"
    r = client.post(f"/api/portfolios/{main['id']}/fork", json={"name": "C", "date": "1990-01-01"})
    assert r.status_code == 422
