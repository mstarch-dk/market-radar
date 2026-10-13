"""Yahoo portfolio export → holdings.csv / transactions.csv (average-cost method)."""
import pandas as pd
import pytest

from radar import universe

HEADER = ("Symbol,Current Price,Date,Time,Change,Open,High,Low,Volume,Trade Date,Purchase Price,Quantity,"
          "Commission,High Limit,Low Limit,Comment,Transaction Type")


def _row(sym, trade="", price="", qty="", kind=""):
    return f"{sym},100,2026/10/13,17:30 CEST,0,100,101,99,1000,{trade},{price},{qty},,,,,{kind}"


@pytest.fixture
def imported(tmp_data, monkeypatch):
    monkeypatch.setattr(universe, "universe_config", lambda: {"watchlist": ["EXTRA"]})

    def run(*rows):
        path = tmp_data / "export.csv"
        path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
        df, warnings = universe.import_yahoo_csv(str(path))
        return df.set_index("symbol"), warnings
    return run


def test_average_cost_survives_a_partial_sell(imported):
    df, warn = imported(_row("NOVO-B.CO", 20260105, 400, 10, "BUY"),
                        _row("NOVO-B.CO", 20260301, 500, 10, "BUY"),
                        _row("NOVO-B.CO", 20260601, 600, 5, "SELL"))
    r = df.loc["NOVO-B.CO"]
    assert r["status"] == "holding" and r["quantity"] == 15
    assert r["avg_price"] == pytest.approx(450.0)              # a sale doesn't change the average cost
    assert r["first_trade"] == "2026-01-05" and r["last_sell_date"] == "2026-06-01" and r["last_sell_price"] == 600
    assert not warn


def test_close_and_reopen_restarts_first_trade_and_cost(imported):
    df, _ = imported(_row("AAPL", 20250105, 100, 10, "BUY"),
                     _row("AAPL", 20250601, 150, 10, "SELL"),
                     _row("AAPL", 20260201, 200, 4, "BUY"))
    r = df.loc["AAPL"]
    assert r["first_trade"] == "2026-02-01" and r["avg_price"] == pytest.approx(200.0) and r["quantity"] == 4


def test_fully_sold_and_oversold_positions(imported):
    df, warn = imported(_row("SOLD", 20250105, 10, 5, "BUY"), _row("SOLD", 20250205, 12, 5, "SELL"),
                        _row("OVER", 20250105, 10, 5, "BUY"), _row("OVER", 20250205, 12, 8, "SELL"))
    assert df.loc["SOLD", "status"] == "sold" and pd.isna(df.loc["SOLD", "quantity"])
    assert df.loc["OVER", "status"] == "sold"
    assert "sold 8 on 2025-02-05 but held 5" in warn["OVER"][0]


def test_watchlist_market_rows_and_transactions_file(imported, tmp_data):
    df, _ = imported(_row("WATCH"), _row("^VIX"), _row("EURUSD=X"), _row("$$CASH", 20260105, 1, 100, "BUY"),
                     _row("MSFT", 20260105, 400, 2, ""))       # older exports: no type means BUY
    assert df.loc["WATCH", "status"] == "watch"
    assert not {"^VIX", "EURUSD=X", "$$CASH"} & set(df.index)
    assert df.loc["MSFT", "status"] == "holding"
    tx = pd.read_csv(tmp_data / "transactions.csv", parse_dates=["date"])
    assert tx.to_dict("records") == [{"symbol": "MSFT", "date": pd.Timestamp("2026-01-05"), "type": "BUY",
                                      "quantity": 2.0, "price": 400.0}]
    h = universe.holdings().set_index("symbol")                # + watchlist from universe.yaml
    assert h.loc["EXTRA", "status"] == "watch"


def test_unknown_transaction_types_are_skipped_with_a_warning(imported, tmp_data):
    df, warn = imported(_row("KO", 20260105, 60, 10, "BUY"), _row("KO", 20260301, 0.5, 10, "DIVIDEND"))
    assert df.loc["KO", "quantity"] == 10 and df.loc["KO", "avg_price"] == pytest.approx(60.0)
    assert "skipped a DIVIDEND" in warn["KO"][0]
    assert pd.read_csv(tmp_data / "transactions.csv")["type"].tolist() == ["BUY"]
