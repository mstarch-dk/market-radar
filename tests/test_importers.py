"""Importing trades from broker exports on the synthetic world: reading odd files, matching instruments to
Yahoo symbols, previewing without writing, committing as one import, and undoing it."""
import io
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import world
from radar import api, dashboard, importers, ingest, userstore
from world import IDX

D1, D2 = IDX[150].date(), IDX[220].date()
P1, P2 = 100 * 1.0006 ** 150, 100 * 1.0006 ** 220            # S4's closes on those days


@pytest.fixture
def client(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers, progress=None: {})
    monkeypatch.setattr(api, "_market", None)
    monkeypatch.setattr(dashboard, "_cache", None)
    monkeypatch.setattr(importers, "yahoo_search", lambda q: [])     # no network
    return TestClient(api.app)


def _dk(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def generic_csv() -> bytes:                         # semicolons, decimal commas, Danish words, Windows-1252
    rows = ["Dato;Type;Symbol;Antal;Kurs;Kurtage",
            f"{D1:%d-%m-%Y};Køb;S4;10;{_dk(P1)};29,00",
            f"{D2:%d-%m-%Y};Salg;S4;4;{_dk(P2)};29,00",
            f"{D2:%d-%m-%Y};Udbytte;S4;;12,50;"]
    return "\n".join(rows).encode("cp1252")


def nordnet_tsv() -> bytes:                          # Nordnet-style: UTF-16, tabs, ISIN and portfolio columns
    rows = ["Id\tHandelsdag\tDepot\tTransaktionstype\tVærdipapirer\tISIN\tAntal\tKurs\tSamlede afgifter\tValuta",
            f"901\t{D1:%Y-%m-%d}\tAktiesparekonto\tKØBT\tSome Corp\tUS0000000004\t5\t{_dk(P1)}\t19\tUSD"]
    return ("\n".join(rows)).encode("utf-16")


def _preview(client, body, **params):
    r = client.post("/api/portfolio/import/preview", content=body, params={"filename": "x.csv", **params})
    assert r.status_code == 200, r.text
    return r.json()


def test_number_date_and_symbol_helpers():
    assert importers.parse_number("1.234,56") == 1234.56 and importers.parse_number("1,234.56") == 1234.56
    assert importers.parse_number("1 234,5 DKK") == 1234.5 and importers.parse_number("") is None
    assert importers.parse_date("05.01.2026") == "2026-01-05" and importers.parse_date("20260105") == "2026-01-05"
    assert importers.saxo_to_yahoo("NOVOb:xcse") == "NOVO-B.CO" and importers.saxo_to_yahoo("AAPL:xnas") == "AAPL"
    assert importers.saxo_to_yahoo("ABC:nowhere") is None


def test_generic_file_preview_writes_nothing(client):
    pv = _preview(client, generic_csv())
    assert pv["preset"] is None and pv["mapping"]["quantity"] == "Antal" and pv["mapping"]["price"] == "Kurs"
    trades = [r for r in pv["rows"] if not r["skip"]]
    assert [(r["type"], r["quantity"], r["date"]) for r in trades] == [("BUY", 10, D1.isoformat()), ("SELL", 4, D2.isoformat())]
    assert trades[0]["price"] == pytest.approx(round(P1, 2)) and trades[0]["fee"] == 29
    assert "a dividend without a cash amount" in [r for r in pv["rows"] if r["skip"]][0]["skip"]   # not silently dropped
    assert pv["counts"] == {"rows": 3, "new": 2, "duplicates": 0, "skipped": 1, "errors": 0, "warnings": 0}
    assert userstore.transactions(symbol="S4") == []                        # preview only


def test_commit_reimport_and_undo(client):
    r = client.post("/api/portfolio/import/commit", content=generic_csv(), params={"filename": "trades.csv"}).json()
    assert r["added"] == 2 and r["source"] == "csv"
    pos = {p["symbol"]: p for p in client.get("/api/portfolio/positions").json()["total"]}
    assert pos["S4"]["quantity"] == 6
    again = _preview(client, generic_csv())
    assert again["counts"]["duplicates"] == 2 and again["counts"]["new"] == 0
    imp = client.get("/api/portfolio/imports").json()[0]
    assert imp["file_name"] == "trades.csv" and imp["rows_now"] == 2
    assert client.delete(f"/api/portfolio/imports/{imp['id']}").json() == 2
    assert userstore.transactions(symbol="S4") == []


def test_nordnet_preset_isin_matching_and_a_new_portfolio(client, monkeypatch):
    monkeypatch.setattr(importers, "yahoo_search", lambda q: [{"symbol": "S4", "name": "Some Corp", "exchange": "NYSE"}])
    pv = _preview(client, nordnet_tsv())
    assert pv["preset"] == "nordnet" and pv["verified"] is False
    m = pv["symbols"][0]
    assert m["isin"] == "US0000000004" and m["chosen"] == "S4" and m["certain"] is False   # a search hit: confirm it
    row = pv["rows"][0]
    assert row["portfolio"] == "Aktiesparekonto" and row["ext_ref"] == "901" and row["fee"] == 19
    assert pv["new_portfolios"] == ["Aktiesparekonto"]
    r = client.post("/api/portfolio/import/commit", content=nordnet_tsv(),
                    params={"filename": "nordnet.csv", "symbols": json.dumps({"US0000000004": "S4"})})
    assert r.status_code == 200 and r.json()["added"] == 1
    new = userstore.portfolio_by_name("Aktiesparekonto")
    assert new["mode"] == "real" and new["n_tx"] == 1
    assert userstore.mapped_symbol("US0000000004") == "S4"                 # remembered for next time
    monkeypatch.setattr(importers, "yahoo_search", lambda q: [])
    assert _preview(client, nordnet_tsv())["symbols"][0]["candidates"][0]["how"] == "remembered"


def test_excel_and_unknown_symbols_block_the_commit(client):
    buf = io.BytesIO()
    pd.DataFrame({"Date": [D1.isoformat()], "Side": ["BUY"], "Ticker": ["NOPE"], "Qty": [1], "Price": [10]}).to_excel(buf, index=False)
    pv = _preview(client, buf.getvalue(), filename="t.xlsx")
    assert pv["rows"][0]["issues"][0]["field"] == "symbol" and pv["counts"]["errors"] == 1
    r = client.post("/api/portfolio/import/commit", content=buf.getvalue(), params={"filename": "t.xlsx"})
    assert r.status_code == 422 and "errors" in r.json()["detail"]["message"]


def test_a_sale_after_its_buy_in_the_same_file_is_fine_but_an_oversale_is_not(client):
    bad = generic_csv().replace(b";Salg;S4;4;", b";Salg;S4;40;")
    pv = _preview(client, bad)
    sale = [r for r in pv["rows"] if r["type"] == "SELL"][0]
    assert sale["issues"][0]["field"] == "quantity" and pv["counts"]["errors"] == 1


def test_mapping_can_be_overridden(client):
    body = f"When,What,Sym,N,Px\n{D1.isoformat()},buy,S4,3,{P1:.2f}\n".encode()
    pv = _preview(client, body)
    assert "date" not in pv["mapping"]                                        # "When" isn't a known name
    pv = _preview(client, body, mapping=json.dumps({"date": "When", "type": "What", "symbol": "Sym", "quantity": "N", "price": "Px"}))
    assert pv["counts"]["new"] == 1 and pv["rows"][0]["date"] == D1.isoformat()


def test_saxo_symbols_are_translated(client, monkeypatch):
    monkeypatch.setattr(api, "_has_prices", lambda s: s == "S4")
    body = (f"Trade Date,B/S,Instrument Symbol,Instrument,Amount,Price,Trade ID\n"
            f"{D1:%d-%m-%Y},Bought,S4:xnas,S Four,2,{P1:.2f},T-1\n").encode()
    pv = _preview(client, body)
    assert pv["preset"] == "saxo" and pv["rows"][0]["symbol_in"] == "S4" and pv["rows"][0]["symbol"] == "S4"


def test_a_preset_still_uses_generic_columns_it_does_not_list(client):
    body = f"Dato;Transaktion;Fondsnavn;Symbol;Antal;Kurs\n{D1:%d-%m-%Y};Køb;Some Corp;S4;2;{_dk(P1)}\n".encode("cp1252")
    pv = _preview(client, body)
    assert pv["preset"] == "danske" and pv["mapping"]["symbol"] == "Symbol"
    assert pv["symbols"][0]["chosen"] == "S4" and pv["symbols"][0]["certain"] is True
