"""The portfolio editor's API on the synthetic world: add, check, edit, delete and restore trades, with
validation that blocks errors and asks to confirm warnings."""
import pytest
from fastapi.testclient import TestClient

import world
from radar import api, dashboard, ingest
from world import IDX

DAY = IDX[200].date().isoformat()
S3_CLOSE = 100 * 1.0008 ** 200


@pytest.fixture
def client(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers, progress=None: {})
    monkeypatch.setattr(api, "_market", None)
    monkeypatch.setattr(dashboard, "_cache", None)
    return TestClient(api.app)


def _tx(**kw):
    return {"symbol": "S3", "date": DAY, "type": "BUY", "quantity": 10, "price": round(S3_CLOSE, 2)} | kw


def _pid(client, name: str) -> int:
    return next(p["id"] for p in client.get("/api/portfolios").json() if p["name"] == name)


def test_price_check_prefills_and_flags_a_hundredfold_price(client):
    pc = client.get("/api/portfolio/price-check", params={"symbol": "s3", "date": DAY}).json()
    assert pc["close"] == pytest.approx(S3_CLOSE) and pc["currency"] == "USD" and pc["verdict"] == "ok"
    pc = client.get("/api/portfolio/price-check", params={"symbol": "S3", "date": DAY, "price": S3_CLOSE * 100}).json()
    assert pc["verdict"] == "x100" and "pence" in pc["message"]


def test_add_shows_up_in_positions(client):
    r = client.post("/api/portfolio/transactions", json=_tx(fee=5, portfolio_id=_pid(client, "ASK")))
    assert r.status_code == 200 and r.json()["tx"]["source"] == "manual"
    pos = {p["symbol"]: p for p in client.get("/api/portfolio/positions").json()["total"]}
    assert pos["S3"]["quantity"] == 10 and pos["S3"]["avg_price"] == pytest.approx(round(S3_CLOSE, 2) + 0.5)
    assert {t["symbol"]: t["status"] for t in client.get("/api/context").json()["tickers"]}["S3"] == "holding"


def test_errors_block_and_warnings_need_confirmation(client):
    r = client.post("/api/portfolio/transactions", json=_tx(type="SELL"))          # nothing held yet
    assert r.status_code == 422 and r.json()["detail"]["issues"][0]["field"] == "quantity"
    r = client.post("/api/portfolio/transactions", json=_tx(date="2999-01-01"))
    assert r.status_code == 422 and "future" in r.json()["detail"]["message"]
    r = client.post("/api/portfolio/transactions", json=_tx(symbol="NOPE"))
    assert r.status_code == 422 and r.json()["detail"]["issues"][0]["field"] == "symbol"
    r = client.post("/api/portfolio/transactions", json=_tx(price=S3_CLOSE * 100))   # GBp-style slip
    assert r.status_code == 422 and r.json()["detail"]["issues"][0]["level"] == "warning"
    assert client.post("/api/portfolio/transactions", json=_tx(price=S3_CLOSE * 100, confirm=True)).status_code == 200


def test_validate_previews_the_effect_without_saving(client):
    client.post("/api/portfolio/transactions", json=_tx(quantity=10, price=100))
    chk = client.post("/api/portfolio/validate", json=_tx(quantity=10, price=200)).json()
    assert chk["effect"]["before"] == {"quantity": 10, "avg_price": 100}
    assert chk["effect"]["after"]["quantity"] == 20 and chk["effect"]["after"]["avg_price"] == pytest.approx(150)
    assert len(client.get("/api/portfolio/transactions", params={"symbol": "S3"}).json()) == 1   # nothing saved


def test_edit_delete_and_restore(client):
    tx = client.post("/api/portfolio/transactions", json=_tx()).json()["tx"]
    r = client.put(f"/api/portfolio/transactions/{tx['id']}", json=_tx(quantity=4))
    assert r.status_code == 200 and r.json()["tx"]["quantity"] == 4
    gone = client.delete(f"/api/portfolio/transactions/{tx['id']}").json()
    assert client.get("/api/portfolio/transactions", params={"symbol": "S3"}).json() == []
    back = client.post("/api/portfolio/transactions/restore", json=gone)
    assert back.status_code == 200 and back.json()["id"] == tx["id"] and back.json()["quantity"] == 4
    assert client.post("/api/portfolio/transactions/restore", json=gone).status_code == 409


def test_editing_a_buy_away_cannot_leave_a_later_sale_oversold(client):
    buy = client.post("/api/portfolio/transactions", json=_tx(quantity=10)).json()["tx"]
    later = IDX[220].date().isoformat()
    client.post("/api/portfolio/transactions", json=_tx(type="SELL", quantity=8, date=later, price=round(100 * 1.0008 ** 220, 2)))
    r = client.put(f"/api/portfolio/transactions/{buy['id']}", json=_tx(quantity=5))
    assert r.status_code == 422 and r.json()["detail"]["issues"][0]["field"] == "quantity"


def test_portfolios_and_csv_export(client):
    pension = client.post("/api/portfolios", json={"name": "Pension", "kind": "pension"}).json()
    assert {p["name"] for p in client.get("/api/portfolios").json()} >= {"ASK", "frie midler", "Pension"}
    assert client.post("/api/portfolios", json={"name": "Pension"}).status_code == 409
    assert client.post("/api/portfolio/transactions", json=_tx(portfolio_id=9999)).status_code == 422
    client.post("/api/portfolio/transactions", json=_tx(portfolio_id=pension["id"]))
    csv = client.get("/api/portfolio/export.csv")
    assert csv.headers["content-type"].startswith("text/csv") and "S3," in csv.text and "Pension" in csv.text


def test_cli_add_list_export(client):
    from typer.testing import CliRunner

    from radar import cli

    r = CliRunner().invoke(cli.app, ["portfolio", "add", "buy", "s3", "10", str(round(S3_CLOSE, 2)), "--date", DAY])
    assert r.exit_code == 0 and "S3: 0 → 10 shares" in r.output
    r = CliRunner().invoke(cli.app, ["portfolio", "add", "SELL", "S3", "50", "100", "--date", DAY])
    assert r.exit_code != 0 and "Not saved" in r.output
    assert "S3" in CliRunner().invoke(cli.app, ["portfolio", "list"]).output
    assert "S3," in CliRunner().invoke(cli.app, ["portfolio", "export"]).output
