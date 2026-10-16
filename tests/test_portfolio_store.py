"""The transaction store as the portfolio's source of truth: the one-time move of the old CSV files, positions
derived with fees and per portfolio, import semantics (snapshot vs additive, duplicates, undo) and backups."""
import pandas as pd
import pytest

from radar import universe, userstore

HEADER = "symbol,status,quantity,avg_price,first_trade,last_sell_date,last_sell_price\n"


def _legacy(tmp_data, holdings: str, tx: str) -> None:
    (tmp_data / "holdings.csv").write_text(HEADER + holdings, encoding="utf-8")
    (tmp_data / "transactions.csv").write_text("symbol,date,type,quantity,price\n" + tx, encoding="utf-8")


def _tx(symbol, date, type_, qty, price, fee=0.0, portfolio=None, ext_ref=None):
    return {"symbol": symbol, "date": date, "type": type_, "quantity": qty, "price": price, "fee": fee,
            "portfolio": portfolio, "ext_ref": ext_ref}


def test_old_csv_files_move_into_the_store_unchanged(tmp_data):
    _legacy(tmp_data, "A,holding,15,450.0,2026-01-05,2026-06-01,600\nB,sold,,,,2026-03-01,20\nW,watch,,,,,\n",
            "A,2026-01-05,BUY,10,400\nA,2026-03-01,BUY,10,500\nA,2026-06-01,SELL,5,600\n"
            "B,2026-01-02,BUY,3,10\nB,2026-03-01,SELL,3,20\n")
    h = universe.holdings().set_index("symbol")
    assert h.loc["A", "quantity"] == 15 and h.loc["A", "avg_price"] == pytest.approx(450.0)
    assert h.loc["B", "status"] == "sold" and h.loc["W", "status"] == "watch"
    assert not (tmp_data / "holdings.csv").exists() and (tmp_data / "holdings.migrated.csv").exists()
    assert (tmp_data / "transactions.migrated.csv").exists()                 # renamed, never deleted
    assert userstore.meta_get("legacy_csv")["status"] == "migrated"
    assert len(universe.transactions()) == 5


def test_a_migration_that_would_change_a_position_is_undone(tmp_data):
    _legacy(tmp_data, "A,holding,3,400.0,2026-01-05,,\n", "A,2026-01-05,BUY,2,400\n")    # files disagree
    h = universe.holdings().set_index("symbol")
    assert h.loc["A", "quantity"] == 3                                       # still the old file's numbers
    assert (tmp_data / "holdings.csv").exists() and userstore.transactions() == []
    m = userstore.meta_get("legacy_csv")
    assert m["status"] == "failed" and "A: 3" in m["problems"][0]


def test_fees_are_part_of_the_cost_and_portfolios_are_kept_apart(tmp_data):
    userstore.add_tx(_tx("A", "2026-01-05", "BUY", 10, 100, fee=29, portfolio="ASK"))
    userstore.add_tx(_tx("A", "2026-02-05", "BUY", 10, 200, fee=0, portfolio="frie midler"))
    total = universe.holdings().set_index("symbol").loc["A"]
    assert total["quantity"] == 20 and total["avg_price"] == pytest.approx((1000 + 29 + 2000) / 20)
    per, _ = universe.positions(universe.transactions(), by_portfolio=True)
    per = per.set_index("portfolio")
    assert per.loc["ASK", "avg_price"] == pytest.approx(102.9) and per.loc["frie midler", "quantity"] == 10
    assert total["portfolios"] == "ASK, frie midler"


def test_an_oversold_position_is_reported_not_hidden(tmp_data):
    userstore.add_tx(_tx("A", "2026-01-05", "BUY", 2, 100))
    userstore.add_tx(_tx("A", "2026-02-05", "SELL", 5, 120))
    pos, warn = universe.positions(universe.transactions())
    assert pos.iloc[0]["status"] == "sold" and "sold 5" in warn["A"][0]


def test_broker_imports_add_skip_known_rows_and_can_be_undone(tmp_data):
    userstore.add_tx(_tx("A", "2026-01-05", "BUY", 10, 100))                      # entered by hand
    first = userstore.add_import([_tx("A", "2026-01-05", "BUY", 10, 100),          # the same trade: skipped
                                  _tx("B", "2026-02-01", "BUY", 1, 50, ext_ref="T1"),
                                  _tx("B", "2026-02-01", "BUY", 1, 50, ext_ref="T2")], "saxo", "trades.csv")
    assert (first["added"], first["skipped"]) == (2, 1)                           # two identical fills both kept
    again = userstore.add_import([_tx("B", "2026-02-01", "BUY", 1, 50, ext_ref="T1")], "saxo")
    assert (again["added"], again["skipped"]) == (0, 1)
    assert userstore.undo_import(first["id"]) == 2
    assert [t["symbol"] for t in userstore.transactions()] == ["A"]
    backups = list((tmp_data / "userdata" / "backups").glob("radar-*.db"))
    assert len(backups) >= 3                                                      # before each import and the undo


def test_a_yahoo_import_replaces_the_previous_yahoo_rows_only(tmp_data):
    userstore.add_tx(_tx("M", "2026-01-05", "BUY", 1, 10))                        # manual: kept
    userstore.add_import([_tx("Y", "2026-01-05", "BUY", 1, 10)], "yahoo", replace_source=True)
    userstore.add_import([_tx("Z", "2026-01-06", "BUY", 1, 10)], "yahoo", replace_source=True)
    assert sorted(t["symbol"] for t in userstore.transactions()) == ["M", "Z"]


def test_delete_and_restore_a_transaction(tmp_data):
    tx_id = userstore.add_tx(_tx("A", "2026-01-05", "BUY", 10, 100, portfolio="ASK"))
    row = userstore.delete_tx(tx_id)
    assert userstore.transactions() == [] and row["portfolio"] == "ASK"
    assert userstore.restore_tx(row) == tx_id and userstore.get_tx(tx_id)["price"] == 100


def test_accounts_are_seeded_as_portfolios_and_renames_carry_the_transactions(tmp_data):
    tx_id = userstore.add_tx(_tx("A", "2026-01-05", "BUY", 1, 1, portfolio="ASK"))
    assert {(p["name"], p["kind"], p["mode"]) for p in userstore.portfolios()} == {
        ("ASK", "ask", "real"), ("frie midler", "frie_midler", "real")}
    userstore.save_portfolio({"name": "ASK Danske"}, userstore.portfolio_by_name("ASK")["id"])
    assert userstore.get_tx(tx_id)["portfolio"] == "ASK Danske"


def test_without_any_data_nothing_is_created(tmp_data):
    assert universe.transactions().empty and universe.holdings().empty
    assert not (tmp_data / "userdata").exists()


def test_undoing_an_import_that_replaced_rows_is_refused_with_its_backup(tmp_data):
    import pytest
    first = userstore.add_import([_tx("Y", "2026-01-05", "BUY", 1, 10)], "yahoo", replace_source=True)
    second = userstore.add_import([_tx("Z", "2026-01-06", "BUY", 1, 10)], "yahoo", replace_source=True)
    rec = {i["id"]: i for i in userstore.imports()}[second["id"]]
    assert rec["rows_replaced"] == 1 and rec["backup"].startswith("radar-") and "before-yahoo-import" in rec["backup"]
    with pytest.raises(ValueError, match="replaced 1") as e:
        userstore.undo_import(second["id"])           # would leave Y gone and Z gone: neither file's state
    assert rec["backup"] in str(e.value)
    assert sorted(t["symbol"] for t in userstore.transactions()) == ["Z"]      # nothing changed
    assert userstore.undo_import(first["id"]) == 0    # an import that replaced nothing can still be undone
