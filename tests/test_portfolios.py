"""Portfolios: real ones (your accounts) and virtual ones (simulations, A/B tests), with tags. The upgrade from the
account-label schema, the selection rules (only real portfolios are yours unless others are chosen), moves,
scoped imports and the holdings bundle."""
import json
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

import world
from fakes import LOCAL
from radar import api, universe, userstore
from radar.portfolios import trades
from radar.reporting import dashboard, report
from radar.sources import ingest
from world import IDX


def _tx(symbol, date, type_, qty, price, portfolio=None, **kw):
    return {"symbol": symbol, "date": date, "type": type_, "quantity": qty, "price": price, "fee": 0.0,
            "portfolio": portfolio} | kw


# ---------------- the upgrade from accounts ----------------

V11 = 11          # the schema before portfolios: transactions carry an optional account label


def _v11_database(tmp_data) -> None:
    db = tmp_data / "userdata" / userstore.DB_NAME
    db.parent.mkdir(parents=True)
    with closing(sqlite3.connect(db)) as con:
        for sql in userstore.MIGRATIONS[:V11]:
            con.execute(sql)
        con.execute(f"PRAGMA user_version = {V11}")
        con.execute("INSERT INTO imports (id, source, file_name, rows_added, at) VALUES (7, 'saxo', 'x.csv', 1, 'now')")
        rows = [(3, "A", "2026-01-05", "BUY", 10, 100, 1, "ASK", None),
                (5, "A", "2026-02-05", "BUY", 10, 200, 0, None, None),
                (9, "B", "2026-03-05", "BUY", 2, 50, 0, "frie midler", 7),
                (11, "A", "2026-04-05", "SELL", 5, 300, 0, None, None)]
        con.executemany("INSERT INTO transactions (id, symbol, date, type, quantity, price, fee, account, import_id, "
                        "source, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', 'c', 'u')", rows)
        con.commit()


def test_the_upgrade_turns_accounts_into_portfolios_and_keeps_every_number(tmp_data):
    _v11_database(tmp_data)
    pooled_before = {"A": (15, (1000 + 1 + 2000) / 20), "B": (2, 50)}
    pf = {p["name"]: p for p in userstore.portfolios()}
    assert {n: (p["mode"], p["kind"]) for n, p in pf.items()} == {
        "ASK": ("real", "ask"), "frie midler": ("real", "frie_midler"), "Main": ("real", "other")}
    assert pf["Main"]["is_default"] and pf["Main"]["n_tx"] == 2               # the trades without an account
    by_id = {t["id"]: t["portfolio"] for t in userstore.transactions()}
    assert by_id == {3: "ASK", 5: "Main", 9: "frie midler", 11: "Main"}        # ids kept
    pos = trades.holdings().set_index("symbol")
    for sym, (q, avg) in pooled_before.items():                              # yours, pooled: unchanged
        assert pos.loc[sym, "quantity"] == q and pos.loc[sym, "avg_price"] == pytest.approx(avg)
    with closing(sqlite3.connect(tmp_data / "userdata" / userstore.DB_NAME)) as con:
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
        assert con.execute("PRAGMA user_version").fetchone()[0] == len(userstore.MIGRATIONS)
        assert not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'accounts'").fetchone()
    assert list((tmp_data / "userdata" / "backups").glob("radar-*before-schema*.db"))
    assert userstore.undo_import(7) == 1                                     # imports still undo
    assert userstore.portfolios()[0]["name"] == "ASK"                        # reopening changes nothing


def test_a_new_database_has_the_accounts_and_main_only_when_needed(tmp_data):
    userstore.watch("X")
    assert [p["name"] for p in userstore.portfolios()] == ["ASK", "frie midler"]
    assert userstore.default_portfolio() is None
    userstore.add_tx(_tx("A", "2026-01-05", "BUY", 1, 10))                    # no portfolio chosen
    assert userstore.get_tx(1)["portfolio"] == "Main" and userstore.default_portfolio() is not None


# ---------------- tags and the selection rules ----------------

def test_tags_are_normalised_and_select_portfolios(tmp_data):
    a = userstore.save_portfolio({"name": "Sim A", "mode": "virtual", "tags": [" Momentum  A ", "SIM", "sim"]})
    b = userstore.save_portfolio({"name": "Sim B", "mode": "virtual", "tags": ["sim"]})
    assert userstore.get_portfolio(a)["tags"] == ["momentum a", "sim"]
    assert {t["tag"]: t["n"] for t in userstore.all_tags()} == {"momentum a": 1, "sim": 2}
    with pytest.raises(ValueError):
        userstore.set_tags(a, ["x" * 33])
    ask = userstore.portfolio_by_name("ASK")["id"]
    assert set(userstore.portfolio_ids()) == {ask, userstore.portfolio_by_name("frie midler")["id"]}
    assert userstore.portfolio_ids("virtual") == [a, b]
    assert userstore.portfolio_ids(tags=["SIM"]) == [a, b] and userstore.portfolio_ids(ids=[a]) == [a]
    userstore.save_portfolio({"archived": True}, ask)
    assert ask not in userstore.portfolio_ids() and ask in userstore.portfolio_ids(include_archived=True)


def test_only_real_portfolios_are_yours_unless_chosen(tmp_data):
    sim = userstore.save_portfolio({"name": "Sim", "mode": "virtual"})
    userstore.add_tx(_tx("R", "2026-01-05", "BUY", 1, 10, "ASK"))
    userstore.add_tx(_tx("V", "2026-01-05", "BUY", 1, 10, "Sim"))
    assert set(trades.holdings()["symbol"]) == {"R"}
    assert set(trades.holdings([sim])["symbol"]) == {"V"}
    assert "V" not in userstore.export_transactions_csv() and "V" in userstore.export_transactions_csv([sim])


def test_the_default_must_be_a_real_active_portfolio(tmp_data):
    sim = userstore.save_portfolio({"name": "Sim", "mode": "virtual"})
    with pytest.raises(ValueError):
        userstore.set_default_portfolio(sim)
    ask = userstore.portfolio_by_name("ASK")["id"]
    userstore.set_default_portfolio(ask)
    userstore.save_portfolio({"archived": True}, ask)
    assert userstore.default_portfolio() is None                             # archived: no longer the default


# ---------------- deleting, moving, importing ----------------

def test_a_real_portfolio_with_trades_is_archived_not_deleted(tmp_data):
    userstore.add_tx(_tx("A", "2026-01-05", "BUY", 1, 10, "ASK"))
    with pytest.raises(ValueError, match="move them first"):
        userstore.delete_portfolio(userstore.portfolio_by_name("ASK")["id"])
    sim = userstore.save_portfolio({"name": "Sim", "mode": "virtual"})
    userstore.add_tx(_tx("A", "2026-01-05", "BUY", 1, 10, "Sim"))
    assert userstore.delete_portfolio(sim)["n_tx"] == 1
    assert [t["portfolio"] for t in userstore.transactions()] == ["ASK"]


def test_moving_trades_is_checked_for_sales_left_without_their_buy(tmp_data):
    from radar.portfolios import checks

    userstore.add_tx(_tx("A", "2026-01-05", "BUY", 10, 10))                   # into Main
    userstore.add_tx(_tx("A", "2026-02-05", "SELL", 4, 12))
    main, ask = userstore.portfolio_by_name("Main")["id"], userstore.portfolio_by_name("ASK")["id"]
    sell_only = [t["id"] for t in userstore.transactions() if t["type"] == "SELL"]
    assert "sold 4" in checks.check_move(main, ask, ids=sell_only)[0]       # the sale without its buy
    assert checks.check_move(main, ask, symbols=["A"]) == []
    assert userstore.move_transactions(main, ask, symbols=["A"]) == 2
    assert {t["portfolio"] for t in userstore.transactions()} == {"ASK"}


def test_a_snapshot_import_replaces_only_its_portfolio_and_skips_moved_trades(tmp_data):
    userstore.add_import([_tx("Y", "2026-01-05", "BUY", 1, 10), _tx("Z", "2026-01-06", "BUY", 1, 10)],
                         "yahoo", replace_source=True)                        # into Main
    main, ask = userstore.portfolio_by_name("Main")["id"], userstore.portfolio_by_name("ASK")["id"]
    userstore.move_transactions(main, ask, symbols=["Y"])                     # Y really sits in ASK
    res = userstore.add_import([_tx("Y", "2026-01-05", "BUY", 1, 10), _tx("Z", "2026-01-06", "BUY", 1, 10)],
                               "yahoo", replace_source=True)
    assert (res["replaced"], res["added"], res["skipped"]) == (1, 1, 1)      # Y not imported twice
    assert sorted((t["symbol"], t["portfolio"]) for t in userstore.transactions()) == [("Y", "ASK"), ("Z", "Main")]
    sim = userstore.save_portfolio({"name": "Sim", "mode": "virtual"})
    res = userstore.add_import([_tx("Y", "2026-01-05", "BUY", 1, 10)], "csv", portfolio_id=sim)
    assert res["added"] == 1                                                  # a virtual copy is its own trade


def test_the_bundle_carries_kinds_and_tags_of_real_portfolios_only(tmp_data):
    pension = userstore.save_portfolio({"name": "Pension", "kind": "pension", "tags": ["long"]})
    userstore.save_portfolio({"name": "Sim", "mode": "virtual"})
    userstore.add_tx(_tx("A", "2026-01-05", "BUY", 1, 10, "Pension"))
    userstore.add_tx(_tx("V", "2026-01-05", "BUY", 1, 10, "Sim"))
    userstore.set_default_portfolio(pension)
    pf, tx = userstore.export_portfolios_json(), userstore.export_transactions_csv()
    assert "Sim" not in pf and "V," not in tx
    for f in (tmp_data / "userdata").iterdir():
        f.unlink() if f.is_file() else None
    userstore.import_portfolios_json(pf)
    userstore.import_transactions_csv(tx)
    p = userstore.portfolio_by_name("Pension")
    assert (p["kind"], p["tags"], p["is_default"], p["n_tx"]) == ("pension", ["long"], True, 1)
    assert userstore.portfolio_by_name("Sim") is None


def test_an_old_bundle_with_account_names_still_restores(tmp_data):
    old = ("symbol,date,type,quantity,price,fee,account,note,source,ext_ref\n"
           "A,2026-01-05,BUY,1,10,0,ASK,,manual,\nB,2026-01-05,BUY,1,10,0,,,manual,\n")
    assert userstore.import_transactions_csv(old) == 2
    assert sorted(t["portfolio"] for t in userstore.transactions()) == ["ASK", "Main"]


# ---------------- in the app: virtual portfolios stay out of "yours" ----------------

@pytest.fixture
def client(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers, progress=None: {})
    api.reset()
    dashboard.reset()
    return TestClient(api.app, base_url=LOCAL)


def _virtual_s2(client) -> int:
    sim = client.post("/api/portfolios", json={"name": "Sim", "mode": "virtual", "tags": ["test-a"]}).json()
    day, px = IDX[100].date().isoformat(), round(100 * 1.0010 ** 100, 4)
    r = client.post("/api/portfolio/transactions", json={"date": day, "type": "DEPOSIT", "amount": 10_000,
                                                         "portfolio_id": sim["id"]})
    assert r.status_code == 200, r.text
    r = client.post("/api/portfolio/transactions", json={"symbol": "S2", "date": day, "type": "BUY", "quantity": 5,
                                                         "price": px, "portfolio_id": sim["id"]})
    assert r.status_code == 200, r.text
    return sim["id"]


def test_a_virtual_holding_is_not_in_your_summary_holdings_or_markers(client, tmp_data):
    sim = _virtual_s2(client)
    report.build()
    me = json.loads((tmp_data / "reports" / "summary.json").read_text(encoding="utf-8"))["me"]
    assert "S1" in {r["symbol"] for r in me} and "S2" not in {r["symbol"] for r in me}
    assert "S2" not in {r["symbol"] for r in client.get("/api/me").json()["rows"]}
    assert "S2" not in {t["symbol"] for t in client.get("/api/context").json()["tickers"]}
    chosen = {r["symbol"]: r for r in client.get("/api/me", params={"portfolio": sim}).json()["rows"]}
    assert chosen["S2"]["status"] == "holding" and "S1" not in chosen
    by_tag = client.get("/api/portfolio/positions", params={"tag": "test-a"}).json()
    assert [p["symbol"] for p in by_tag["total"]] == ["S2"] and by_tag["by_portfolio"][0]["portfolio"] == "Sim"
    assert "S2" in universe.all_price_tickers(offline=True)                  # its prices are still updated


def test_compare_personal_uses_your_real_portfolios(client):
    from radar import profile

    _virtual_s2(client)
    out = profile.compare(["S3", "S4"], personal=True)
    assert "S1" in json.dumps(out["correlation"]) and "S2" not in json.dumps(out["correlation"])


def test_portfolio_api_crud_tags_default_and_move(client):
    sim = _virtual_s2(client)
    assert client.put(f"/api/portfolios/{sim}/tags", json={"tags": ["A/B", "test-a"]}).json()["tags"] == ["a/b", "test-a"]
    assert {t["tag"] for t in client.get("/api/portfolios/tags").json()} == {"a/b", "test-a"}
    assert client.post(f"/api/portfolios/{sim}/default").status_code == 422   # virtual: never the default
    ask = next(p["id"] for p in client.get("/api/portfolios").json() if p["name"] == "ASK")
    r = client.post(f"/api/portfolios/{sim}/move", json={"to": ask, "symbols": ["S2"]})
    assert r.status_code == 200 and r.json() == {"moved": 1}               # the buy; the deposit stays
    assert client.delete(f"/api/portfolios/{ask}").status_code == 409         # real, with a trade
    assert client.delete(f"/api/portfolios/{sim}").json()["name"] == "Sim"    # virtual, now empty
    edit = client.put(f"/api/portfolios/{ask}", json={"name": "ASK-renamed", "kind": "ask"}).json()
    assert edit["name"] == "ASK-renamed" and edit["n_tx"] == 1
