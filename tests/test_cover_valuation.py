"""The weekly valuation snapshots: when one is due, how a run in the same ISO week replaces the last one (and
carries names it missed), the stock update with its screener and one-by-one lookups stubbed, and the coverage
rows read from stored snapshots."""
from datetime import date

import pandas as pd
import pytest

from radar import coverage, valuation
from radar.discovery import scan, sources

from fakes import fake_yf


def snap(day: str, tickers: list[str], pe=None, note=None) -> pd.DataFrame:
    """A stored stock snapshot: one row per ticker on `day`."""
    n = len(tickers)
    return pd.DataFrame({"date": pd.Timestamp(day), "ticker": tickers,
                         "pe_fy1": pe if pe is not None else [10.0] * n,
                         "note": note if note is not None else [None] * n}).reindex(columns=valuation.STOCK_COLS)


def new(tickers: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"ticker": tickers, "pe_fy1": [20.0] * len(tickers), "note": [None] * len(tickers)})


# ---------------- when a snapshot is due ----------------

def test_a_snapshot_is_due_when_there_is_none(tmp_path):
    due, old = valuation._snapshot_due(tmp_path / "none.parquet", 6, date(2026, 10, 16))
    assert due and old.empty


def test_a_snapshot_is_due_once_the_last_is_snapshot_days_old(tmp_path):
    path = tmp_path / "s.parquet"
    snap("2026-10-10", ["AAA"]).to_parquet(path, index=False)
    assert valuation._snapshot_due(path, 6, date(2026, 10, 16))[0]            # 6 days
    due, old = valuation._snapshot_due(path, 6, date(2026, 10, 15))          # 5 days
    assert not due and list(old["ticker"]) == ["AAA"]


# ---------------- one snapshot per ISO week ----------------

def test_a_run_in_the_next_week_appends(tmp_path):
    path = tmp_path / "s.parquet"
    old = snap("2026-10-09", ["AAA"])                                          # Fri, week 41
    assert valuation._store(path, old, new(["AAA"]), date(2026, 10, 12)) == 0   # Mon, week 42
    df = pd.read_parquet(path)
    assert sorted(df["date"].dt.strftime("%Y-%m-%d")) == ["2026-10-09", "2026-10-12"]


def test_a_second_run_in_the_same_week_replaces_it_and_carries_missed_names(tmp_path):
    path = tmp_path / "s.parquet"
    old = pd.concat([snap("2026-10-05", ["AAA"]),                              # week 41: kept
                     snap("2026-10-12", ["AAA", "BBB", "CCC"], note=[None, None, "odd EPS"])])   # week 42
    carried = valuation._store(path, old, new(["AAA"]), date(2026, 10, 15))    # Thu, week 42
    assert carried == 2
    df = pd.read_parquet(path)
    assert sorted(df["date"].dt.strftime("%Y-%m-%d").unique()) == ["2026-10-05", "2026-10-15"]
    wk = df[df["date"] == "2026-10-15"].set_index("ticker")
    assert sorted(wk.index) == ["AAA", "BBB", "CCC"]
    assert wk.loc["AAA", "pe_fy1"] == 20.0 and pd.isna(wk.loc["AAA", "note"])   # this run's row
    assert wk.loc["BBB", "pe_fy1"] == 10.0 and wk.loc["BBB", "note"] == "carried from 12 Oct"
    assert wk.loc["CCC", "note"] == "odd EPS; carried from 12 Oct"


def test_new_years_day_is_still_the_old_years_iso_week_53():
    assert date(2026, 12, 31).isocalendar()[:2] == (2026, 53)
    assert date(2027, 1, 1).isocalendar()[:2] == (2026, 53)
    assert date(2027, 1, 4).isocalendar()[:2] == (2027, 1)


def test_across_new_year_the_iso_week_decides_replace_or_append(tmp_path):
    path = tmp_path / "s.parquet"
    valuation._store(path, pd.DataFrame(), new(["AAA", "BBB"]), date(2026, 12, 31))   # Thu, 2026-W53
    carried = valuation._store(path, pd.read_parquet(path), new(["AAA"]), date(2027, 1, 1))  # Fri, 2026-W53
    df = pd.read_parquet(path)
    assert carried == 1 and list(df["date"].dt.strftime("%Y-%m-%d").unique()) == ["2027-01-01"]
    assert sorted(df["ticker"]) == ["AAA", "BBB"]
    valuation._store(path, df, new(["AAA"]), date(2027, 1, 4))                          # Mon, 2027-W01
    df = pd.read_parquet(path)
    assert df.groupby(df["date"].dt.strftime("%Y-%m-%d"))["ticker"].apply(sorted).to_dict() == {
        "2027-01-01": ["AAA", "BBB"], "2027-01-04": ["AAA"]}


def test_the_same_week_number_a_year_later_is_not_the_same_week(tmp_path):
    path = tmp_path / "s.parquet"
    old = snap("2025-10-13", ["AAA", "BBB"])                                   # 2025-W42
    assert valuation._store(path, old, new(["AAA"]), date(2026, 10, 12)) == 0  # 2026-W42: appended
    assert len(pd.read_parquet(path)) == 3


# ---------------- update_stocks ----------------

def quote(sym, eps_fwd=5.0, kind="EQUITY"):
    return {"symbol": sym, "quoteType": kind, "currency": "USD", "financialCurrency": "USD",
            "regularMarketPrice": 100.0, "epsForward": eps_fwd}


@pytest.fixture
def stocks_world(monkeypatch):
    """Two exchanges (min 2 names each), four tracked stocks; returns the screener's answers per exchange."""
    answers = {"XA": [quote("AAA"), quote("BBB", eps_fwd=None), quote("ETF1", kind="ETF")],
               "XB": [quote("CCC"), quote("DDD")]}
    monkeypatch.setattr(valuation, "_screen_codes",
                        lambda: {"XA": {"min_cap": 1, "min_count": 2}, "XB": {"min_cap": 1, "min_count": 2}})
    monkeypatch.setattr(sources, "screen_exchange", lambda code, min_cap=0, **kw: answers[code])
    monkeypatch.setattr(scan, "fx_rates", lambda: {"DKK": 1.0, "USD": 6.4})
    monkeypatch.setattr(valuation, "tracked_stocks", lambda: ["AAA", "BAD", "FUND", "LOOK"])
    return answers


def test_a_normal_run_stores_todays_snapshot_and_counts_what_it_got(monkeypatch, stocks_world):
    yf = fake_yf(monkeypatch, info={"LOOK": {"quoteType": "EQUITY", "currency": "USD", "currentPrice": 50.0,
                                             "trailingEps": 2.5, "forwardEps": 2.5},
                                    "FUND": {"quoteType": "ETF"}, "BAD": RuntimeError("Yahoo said no")})
    msg = valuation.update_stocks(today=date(2026, 10, 16))
    # AAA, BBB, CCC, DDD from the screener (ETF1 left out) + LOOK; BBB has no forward EPS
    assert msg == "5 names, 4 with a forward P/E; 2 of 4 tracked stocks (1 looked up one by one, 1 lookups failed)"
    assert sorted(t for k, t in yf.asked) == ["BAD", "FUND", "LOOK"]
    df = valuation.load_stocks()
    assert list(df.columns) == valuation.STOCK_COLS
    assert set(df["date"]) == {pd.Timestamp("2026-10-16")}
    assert sorted(df["ticker"]) == ["AAA", "BBB", "CCC", "DDD", "LOOK"]
    assert df.set_index("ticker").loc["LOOK", "pe_fy1"] == pytest.approx(20.0)


def test_an_exchange_with_too_few_names_raises_and_keeps_the_last_snapshot(monkeypatch, stocks_world):
    stocks_world["XB"] = [quote("CCC")]
    old = snap("2026-10-05", ["OLD"])
    valuation.write_parquet(old, valuation.STOCKS_FILE, index=False)
    before = valuation.STOCKS_FILE.read_bytes()
    yf = fake_yf(monkeypatch)
    with pytest.raises(ValueError, match=r"XB 1 < 2"):
        valuation.update_stocks(today=date(2026, 10, 16))
    assert valuation.STOCKS_FILE.read_bytes() == before and yf.asked == []


def test_not_due_is_up_to_date_without_asking_anyone(monkeypatch, stocks_world):
    valuation.write_parquet(snap("2026-10-14", ["AAA"]), valuation.STOCKS_FILE, index=False)

    def asked(*a, **kw):
        raise AssertionError("nothing should be asked")
    monkeypatch.setattr(sources, "screen_exchange", asked)
    monkeypatch.setattr(scan, "fx_rates", asked)
    yf = fake_yf(monkeypatch)
    assert valuation.update_stocks(today=date(2026, 10, 16)) == "up to date (snapshot of 14 Oct)"
    assert yf.asked == []


def test_a_forced_run_in_the_same_week_says_how_many_it_carried(monkeypatch, stocks_world):
    valuation.write_parquet(snap("2026-10-14", ["AAA", "GONE"]), valuation.STOCKS_FILE, index=False)
    fake_yf(monkeypatch, info={"LOOK": {"quoteType": "EQUITY", "currency": "USD", "currentPrice": 50.0,
                                        "forwardEps": 2.5}})
    msg = valuation.update_stocks(force=True, today=date(2026, 10, 16))
    assert msg.endswith("; 1 carried from this week's earlier snapshot")
    df = valuation.load_stocks()
    assert set(df["date"]) == {pd.Timestamp("2026-10-16")} and "GONE" in set(df["ticker"])


# ---------------- coverage rows ----------------

MAX_AGE = {"valuation_stocks": 10, "valuation_etfs": 10}


def test_coverage_rows_read_the_stored_snapshots():
    stocks = pd.concat([snap("2026-10-05", ["AAA", "BBB"]),
                        snap("2026-10-12", ["AAA", "BBB", "CCC"], pe=[20.0, None, 15.0])])
    valuation.write_parquet(stocks, valuation.STOCKS_FILE, index=False)
    etfs = pd.DataFrame({"date": pd.Timestamp("2026-10-01"), "ticker": ["ACWI", "XLK", "XLE"],
                         "pe": [20.0, 30.0, None]}).reindex(columns=valuation.ETF_COLS)
    valuation.write_parquet(etfs, valuation.ETFS_FILE, index=False)
    rows = {r["key"]: r for r in coverage._valuation_rows(date(2026, 10, 16), MAX_AGE, {}, ["AAA", "BBB", "ZZZ"])}
    st = rows["valuation_stocks"]
    assert (st["status"], st["age_days"], st["asof"]) == ("ok", 4, "2026-10-12")
    assert st["coverage"] == "1 of 3 tracked stocks with a forward P/E; 3 names in all"
    assert st["detail"].startswith("2 weekly snapshots;")
    et = rows["valuation_etfs"]
    assert (et["status"], et["age_days"], et["asof"]) == ("stale", 15, "2026-10-01")
    assert et["coverage"] == "2 ETFs with a P/E"
    assert rows["cape"]["status"] == "missing" and rows["cape"]["coverage"] == "not loaded"


def test_coverage_rows_without_snapshots_are_missing_not_zero():
    rows = {r["key"]: r for r in coverage._valuation_rows(date(2026, 10, 16), MAX_AGE, {}, ["AAA"])}
    for key in ("valuation_stocks", "valuation_etfs"):
        assert (rows[key]["status"], rows[key]["age_days"], rows[key]["coverage"]) == ("missing", None, "no snapshot yet")
    assert rows["valuation_stocks"]["detail"].startswith("0 weekly snapshots;")
