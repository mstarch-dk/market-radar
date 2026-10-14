"""The local user-data store and how its watchlist overlay combines with the Yahoo import."""
import sqlite3
from contextlib import closing

import pandas as pd

from radar import universe, userstore

HEADER = "symbol,status,quantity,avg_price,first_trade,last_sell_date,last_sell_price\n"


def _holdings(tmp_data, rows: str) -> None:
    (tmp_data / "holdings.csv").write_text(HEADER + rows, encoding="utf-8")


def _status(symbol: str):
    h = universe.holdings()
    st = h.loc[h["symbol"] == symbol, "status"]
    return st.iloc[0] if len(st) else None


def test_reading_creates_nothing(tmp_data):
    assert userstore.watchlist_overlay() == {}
    assert not (tmp_data / "userdata").exists()


def test_schema_is_versioned(tmp_data):
    userstore.watch("AAA")
    with closing(sqlite3.connect(tmp_data / "userdata" / userstore.DB_NAME)) as con:
        assert con.execute("PRAGMA user_version").fetchone()[0] == len(userstore.MIGRATIONS)
    userstore.watch("BBB")                               # reopening doesn't re-run migrations
    assert userstore.watchlist_overlay() == {"AAA": "add", "BBB": "add"}


def test_overlay_on_the_yahoo_import(tmp_data, monkeypatch):
    monkeypatch.setattr(universe, "universe_config", lambda: {"watchlist": ["CFG"]})
    _holdings(tmp_data, "H,holding,1,10,2026-01-02,,\nW,watch,,,,,\nS,sold,,,,2026-03-01,12\n")
    userstore.watch("NEW")
    userstore.watch("S")                                 # a sold position goes back on the watchlist ...
    userstore.unwatch("W")                               # ... a Yahoo watchlist entry comes off
    userstore.unwatch("CFG")                             # ... and so does one from universe.yaml
    userstore.unwatch("H")                               # a holding is never touched
    h = universe.holdings().set_index("symbol")
    assert h["status"].to_dict() == {"H": "holding", "S": "watch", "NEW": "watch"}
    assert h.loc["S", "last_sell_price"] == 12           # keeps its sale for "since sell"


def test_edits_survive_a_reimport_and_can_be_undone(tmp_data):
    _holdings(tmp_data, "W,watch,,,,,\nS,sold,,,,2026-03-01,12\n")
    userstore.unwatch("W")
    userstore.watch("S")
    _holdings(tmp_data, "W,watch,,,,,\nS,sold,,,,2026-03-01,12\nX,watch,,,,,\n")   # radar import-yahoo again
    assert (_status("W"), _status("S"), _status("X")) == (None, "watch", "watch")
    userstore.watch("W")
    userstore.unwatch("S")
    assert (_status("W"), _status("S")) == ("watch", "sold")


def test_export_and_import_for_the_ci_bundle(tmp_data):
    userstore.watch("A")
    userstore.unwatch("B")
    text = userstore.export_watchlist_csv()
    assert text == "symbol,action\nA,add\nB,remove\n"
    userstore.watch("C")
    assert userstore.import_watchlist_csv(text) == 2
    assert userstore.watchlist_overlay() == {"A": "add", "B": "remove"}


def test_holdings_without_any_file(tmp_data):
    userstore.watch("A")
    h = universe.holdings()
    assert list(h["symbol"]) == ["A"] and isinstance(h, pd.DataFrame)


def test_holdings_bundle_round_trip_carries_transactions_and_watchlists(tmp_data, monkeypatch):
    from typer.testing import CliRunner

    from radar import cli, config

    monkeypatch.setattr(config, "IMPORTS", tmp_data)
    _holdings(tmp_data, "W,watch,,,,,\nH,holding,2,10,2026-01-02,,\n")
    (tmp_data / "transactions.csv").write_text("symbol,date,type,quantity,price\nH,2026-01-02,BUY,2,10\n",
                                               encoding="utf-8")
    userstore.watch("A")
    userstore.unwatch("W")
    userstore.save_view({"statement": "AI is in a bubble", "conviction": 4,
                         "exposures": [{"kind": "etf", "key": "SMH", "effect": -1}],
                         "indicators": [{"indicator": "semis", "expect": "down"}]})
    bundle = CliRunner().invoke(cli.app, ["bundle-holdings"]).output.strip()

    for f in (tmp_data / "userdata").iterdir():                         # a fresh CI checkout
        f.unlink() if f.is_file() else None
    res = CliRunner().invoke(cli.app, ["unbundle-holdings"], env={"HOLDINGS_BUNDLE": bundle})
    assert res.exit_code == 0 and "1 transactions, 2 watchlist edits and 1 market views" in res.output
    h = universe.holdings().set_index("symbol")
    assert h["status"].to_dict() == {"H": "holding", "A": "watch"} and h.loc["H", "quantity"] == 2
    [v] = userstore.views()
    assert v["statement"] == "AI is in a bubble" and v["exposures"] == [{"kind": "etf", "key": "SMH", "effect": -1}]


def test_an_old_csv_bundle_still_restores(tmp_data, monkeypatch):
    import base64
    import io
    import zipfile

    from typer.testing import CliRunner

    from radar import cli, config

    monkeypatch.setattr(config, "IMPORTS", tmp_data)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("holdings.csv", HEADER + "H,holding,2,10,2026-01-02,,\n")
        z.writestr("transactions.csv", "symbol,date,type,quantity,price\nH,2026-01-02,BUY,2,10\n")
    res = CliRunner().invoke(cli.app, ["unbundle-holdings"], env={"HOLDINGS_BUNDLE": base64.b64encode(buf.getvalue()).decode()})
    assert res.exit_code == 0
    assert universe.holdings().set_index("symbol").loc["H", "quantity"] == 2
