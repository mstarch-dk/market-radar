"""The cash ledger: deposits, withdrawals, dividends, fees and interest next to the trades. The store refuses
malformed rows, validation is per type, a virtual portfolio can't spend money it doesn't have, and positions
and the holding returns ignore cash rows."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

import world
from radar import api, dashboard, importers, ingest, performance, report, trades, userstore
from radar.market import Market
from world import IDX

DAY, LATER = IDX[100].date().isoformat(), IDX[150].date().isoformat()
S2 = lambda i: 100 * 1.0010 ** i            # S2's close at bar i (USD; USDDKK is 6.5)


@pytest.fixture
def client(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers, progress=None: {})
    api.reset()
    dashboard.reset()
    monkeypatch.setattr(importers, "yahoo_search", lambda q: [])
    return TestClient(api.app)


def _sim(client, name="Sim") -> int:
    return client.post("/api/portfolios", json={"name": name, "mode": "virtual"}).json()["id"]


def _post(client, **row):
    return client.post("/api/portfolio/transactions", json=row)


def test_the_store_refuses_malformed_cash_rows(tmp_data):
    userstore.add_tx({"date": "2026-01-02", "type": "DEPOSIT", "amount": 1000, "currency": "DKK", "portfolio": "ASK"})
    for bad in ({"date": "2026-01-02", "type": "DEPOSIT", "amount": -5},                  # no negative amounts
                {"date": "2026-01-02", "type": "DEPOSIT", "amount": 5, "quantity": 1},    # no shares on cash
                {"date": "2026-01-02", "type": "DIVIDEND", "amount": 5},                  # a dividend needs its symbol
                {"date": "2026-01-02", "type": "BUY", "symbol": "A", "quantity": 1, "price": 1, "amount": 1}):
        with pytest.raises(sqlite3.IntegrityError):
            userstore.add_tx(bad | {"portfolio": "ASK"})


def test_cash_rows_are_checked_by_type(client):
    sim = _sim(client)
    r = _post(client, date=DAY, type="DEPOSIT", amount=0, portfolio_id=sim)
    assert r.status_code == 422 and r.json()["detail"]["issues"][0]["field"] == "amount"
    r = _post(client, date=DAY, type="DEPOSIT", amount=100, currency="USD", portfolio_id=sim)
    assert r.status_code == 422 and "DKK" in r.json()["detail"]["message"]
    r = _post(client, symbol="S2", date=DAY, type="DEPOSIT", amount=100, portfolio_id=sim)
    assert r.status_code == 422 and r.json()["detail"]["issues"][0]["field"] == "symbol"
    r = _post(client, date=DAY, type="DEPOSIT", amount=100, portfolio_id=sim)
    assert r.status_code == 200 and r.json()["tx"]["amount"] == 100 and r.json()["tx"]["currency"] == "DKK"


def test_a_virtual_portfolio_cannot_spend_money_it_does_not_have(client):
    sim = _sim(client)
    buy = dict(symbol="S2", date=DAY, type="BUY", quantity=10, price=round(S2(100), 4), portfolio_id=sim)
    r = _post(client, **buy)
    assert r.status_code == 422 and "negative" in r.json()["detail"]["message"]          # nothing deposited
    cost = 10 * round(S2(100), 4) * 6.5
    _post(client, date=DAY, type="DEPOSIT", amount=round(cost, 2) + 1, portfolio_id=sim)
    assert _post(client, **buy).status_code == 200
    r = _post(client, date=LATER, type="WITHDRAW", amount=100, portfolio_id=sim)
    assert r.status_code == 422                                                            # only ~1 DKK left
    cash = {c["portfolio"]: c for c in client.get("/api/portfolio/positions", params={"portfolio": sim}).json()["cash"]}
    assert cash["Sim"]["funding"] == "ledger" and cash["Sim"]["cash_dkk"] == pytest.approx(1, abs=0.01)


def test_a_buy_without_a_dkk_rate_asks_for_its_rate(client, monkeypatch):
    from radar import fxrates
    sim = _sim(client)
    _post(client, date=DAY, type="DEPOSIT", amount=100_000, portfolio_id=sim)
    monkeypatch.setattr(fxrates, "currencies", lambda syms: dict.fromkeys(syms))   # S2's currency unknown
    buy = dict(symbol="S2", date=DAY, type="BUY", quantity=10, price=round(S2(100), 4), portfolio_id=sim)
    r = _post(client, **buy)
    assert r.status_code == 422 and [i["field"] for i in r.json()["detail"]["issues"]] == ["fx_rate"]
    assert _post(client, **buy, fx_rate=6.5).status_code == 200                         # with its rate it's fine


def test_a_real_portfolio_with_a_ledger_only_warns(client):
    ask = next(p["id"] for p in client.get("/api/portfolios").json() if p["name"] == "ASK")
    _post(client, date=DAY, type="DEPOSIT", amount=100, portfolio_id=ask)
    buy = dict(symbol="S2", date=DAY, type="BUY", quantity=10, price=round(S2(100), 4), portfolio_id=ask)
    r = _post(client, **buy)
    assert r.status_code == 422 and r.json()["detail"]["issues"][0]["level"] == "warning"  # a deposit missing?
    assert _post(client, **buy, confirm=True).status_code == 200


def test_a_real_portfolio_without_cash_rows_is_not_checked(client):
    main_buy = dict(symbol="S2", date=DAY, type="BUY", quantity=10, price=round(S2(100), 4))
    assert _post(client, **main_buy).status_code == 200


def test_the_trade_rate_is_yahoos_unless_given(client):
    pc = client.get("/api/portfolio/price-check", params={"symbol": "S2", "date": DAY}).json()
    assert pc["fx"] == pytest.approx(6.5)
    sim = _sim(client)
    _post(client, date=DAY, type="DEPOSIT", amount=1000, portfolio_id=sim)
    r = _post(client, symbol="S2", date=DAY, type="BUY", quantity=1, price=100, fx_rate=7.0, portfolio_id=sim)
    assert r.status_code == 200
    rows = userstore.transactions(portfolios=[sim])
    bal, _ = performance.cash_balance(rows, Market.load())
    assert bal.iloc[-1] == pytest.approx(1000 - 700)                                     # 100 USD at 7.0, not 6.5


def test_dividends_are_recorded_but_not_double_counted(client):
    sim = _sim(client)
    _post(client, date=DAY, type="DEPOSIT", amount=10_000, portfolio_id=sim)
    _post(client, symbol="S2", date=DAY, type="BUY", quantity=5, price=round(S2(100), 4), portfolio_id=sim)
    r = _post(client, symbol="S2", date=LATER, type="DIVIDEND", amount=20, portfolio_id=sim)
    assert r.status_code == 422 and any("reinvested" in i["message"] for i in r.json()["detail"]["issues"])
    assert _post(client, symbol="S2", date=LATER, type="DIVIDEND", amount=20, portfolio_id=sim, confirm=True).status_code == 200
    r = _post(client, symbol="S3", date=LATER, type="DIVIDEND", amount=20, portfolio_id=sim)
    assert any("wasn't held" in i["message"] for i in r.json()["detail"]["issues"])
    pos = trades.holdings([sim]).set_index("symbol")
    assert pos.loc["S2", "quantity"] == 5                                                 # cash rows don't move shares


def test_holding_returns_ignore_cash_rows(client):
    report.build()
    before = {r["symbol"]: r["since_buy"] for r in client.get("/api/me").json()["rows"] if r["status"] == "holding"}
    main = userstore.default_portfolio()
    userstore.add_tx({"date": DAY, "type": "DEPOSIT", "amount": 999, "currency": "DKK", "portfolio_id": main})
    userstore.add_tx({"symbol": "S1", "date": LATER, "type": "DIVIDEND", "amount": 5, "currency": "DKK",
                      "portfolio_id": main})
    after = {r["symbol"]: r["since_buy"] for r in client.get("/api/me").json()["rows"] if r["status"] == "holding"}
    assert after == before and set(after) == {"S1"}


def test_the_csv_round_trip_keeps_cash_rows(tmp_data):
    userstore.add_tx({"date": "2026-01-02", "type": "DEPOSIT", "amount": 1000, "currency": "DKK", "portfolio": "ASK"})
    userstore.add_tx({"symbol": "A", "date": "2026-01-03", "type": "BUY", "quantity": 2, "price": 10, "fx_rate": 6.4,
                      "portfolio": "ASK"})
    text = userstore.export_transactions_csv()
    userstore.import_transactions_csv(text)
    rows = userstore.transactions()
    assert [(r["type"], r["amount"], r["fx_rate"]) for r in rows] == [("DEPOSIT", 1000, None), ("BUY", None, 6.4)]


def test_cash_rows_import_with_an_amount_column(client):
    data = "\n".join(["Dato;Type;Symbol;Antal;Kurs;Beløb;Valuta",
                      f"{DAY};Indbetaling;;;;5.000,00;DKK",
                      f"{DAY};Køb;S2;10;{S2(100):.4f}".replace(".", ",") + ";;USD",
                      f"{LATER};Udbytte;S2;;;12,50;DKK",
                      f"{LATER};Udbytte;S2;;;3,00;USD"]).encode("cp1252")
    pv = client.post("/api/portfolio/import/preview", content=data, params={"filename": "x.csv"}).json()
    kinds = [(r["type"], r["amount"], r["skip"]) for r in pv["rows"]]
    assert kinds[0] == ("DEPOSIT", 5000, None) and kinds[2] == ("DIVIDEND", 12.5, None)
    assert "only DKK" in kinds[3][2] and pv["rows"][2]["symbol"] == "S2"
