"""Financial statements: parsing SEC EDGAR company facts and Yahoo statements, the period arithmetic (TTM, balances,
fiscal years) as known on a day, and the update steps (schedule, contact rule, never shrinking what is stored)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from fakes import Resp, fake_yf, serve, statements
from radar import sourcelog, universe, userstore, valuation
from radar.fundamentals import edgar, schedule, store, yahoo

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 16)


@pytest.fixture(scope="module")
def aapl_js() -> dict:
    return json.loads((FIX / "edgar_companyfacts_aapl.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def aapl(aapl_js) -> pd.DataFrame:
    return edgar.parse_companyfacts(aapl_js, "AAPL", TODAY)


def facts(**tags) -> dict:
    """A company-facts answer: tag -> list of (start, end, val, filed[, form]) in USD (dei: prefix for dei)."""
    out: dict = {"us-gaap": {}, "dei": {}}
    for tag, rows in tags.items():
        tax, name = ("dei", tag[4:]) if tag.startswith("dei__") else ("us-gaap", tag)
        unit = "shares" if "Shares" in name else "USD"
        out[tax][name] = {"units": {unit: [
            {k: v for k, v in {"start": r[0], "end": r[1], "val": r[2], "filed": r[3], "form": r[4] if len(r) > 4
             else "10-Q", "accn": f"a-{r[3]}", "fp": "FY" if len(r) > 4 and r[4] == "10-K" else "Q"}.items()
             if v is not None} for r in rows]}}
    return {"cik": 1, "entityName": "Test", "facts": out}


# ---------------- EDGAR ----------------

def test_apple_ttm_is_built_from_the_year_to_date(aapl):
    rev = store.ttm(aapl, "revenue")
    assert (rev.value, rev.end, rev.basis) == (466_823_000_000, pd.Timestamp("2026-06-27"), "ytd")
    cfo = store.ttm(aapl, "cfo")         # 10-Q cash flows are year to date only
    assert (cfo.value, cfo.basis) == (146_724_000_000, "ytd")
    assert store.ttm(aapl, "capex").value == 10_041_000_000
    fy = store.annual(aapl, "revenue")
    assert fy[pd.Timestamp("2025-09-27")] == 416_161_000_000


def test_a_value_counts_only_from_the_day_after_its_filing(aapl):
    before = store.ttm(aapl, "revenue", known_by=date(2026, 7, 31))   # the Q3 10-Q was filed 31 Jul
    assert before.end == pd.Timestamp("2026-03-28") and before.basis == "ytd"
    after = store.ttm(aapl, "revenue", known_by=date(2026, 8, 1))
    assert after.end == pd.Timestamp("2026-06-27")
    assert store.instant(aapl, "total_assets", known_by=date(2026, 7, 31)).end == pd.Timestamp("2026-03-28")


def test_the_recipe_that_finds_most_parts_wins(aapl):
    cash = store.instant(aapl, "cash")      # Apple reports marketable securities, not short-term investments
    assert cash.tag == "CashAndCashEquivalentsAtCarryingValue+MarketableSecuritiesCurrent"
    assert cash.value == 62_399_000_000
    assert store.instant(aapl, "debt_current").tag == "LongTermDebtCurrent+ShortTermBorrowings"


def test_a_share_count_is_the_latest_period_not_a_sum(aapl):
    sh = store.ttm(aapl, "diluted_shares")
    assert sh.basis == "latest" and 14e9 < sh.value < 15.5e9
    assert store.instant(aapl, "shares").tag == "dei:EntityCommonStockSharesOutstanding"


def test_a_restatement_is_kept_and_used_from_its_filing_day():
    js = facts(Revenues=[("2024-01-01", "2024-12-31", 100.0, "2025-02-10", "10-K"),
                         ("2024-01-01", "2024-12-31", 90.0, "2025-08-01", "10-K")])   # restated in a 10-K/A
    df = edgar.parse_companyfacts(js, "X", TODAY)
    assert len(df) == 2
    assert store.ttm(df, "revenue", known_by=date(2025, 7, 1)).value == 100
    assert store.ttm(df, "revenue").value == 90


def test_a_comparative_filed_again_keeps_its_first_filing_date():
    js = facts(Revenues=[("2024-01-01", "2024-12-31", 100.0, "2025-02-10", "10-K"),
                         ("2024-01-01", "2024-12-31", 100.0, "2026-02-10", "10-K")])
    df = edgar.parse_companyfacts(js, "X", TODAY)
    assert len(df) == 1 and df["filed"].iloc[0] == pd.Timestamp("2025-02-10")


def test_tags_are_tried_per_period_in_order():
    js = facts(SalesRevenueNet=[("2017-01-01", "2017-12-31", 50.0, "2018-02-10", "10-K"),
                                ("2018-01-01", "2018-12-31", 999.0, "2019-02-10", "10-K")],
               RevenueFromContractWithCustomerExcludingAssessedTax=[
                   ("2018-01-01", "2018-12-31", 60.0, "2019-02-10", "10-K")])
    df = edgar.parse_companyfacts(js, "X", date(2020, 1, 1))
    fy = store.annual(df, "revenue")
    assert fy.tolist() == [50.0, 60.0]       # ASC 606 tag preferred where both report the year
    assert set(df["tag"]) == {"SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax"}


def test_no_ttm_from_mismatched_pieces():
    """A 9-month year to date without last year's 9 months gives no TTM at that end: the fiscal year is used."""
    js = facts(Revenues=[("2025-01-01", "2025-12-31", 400.0, "2026-02-10", "10-K"),
                         ("2026-01-01", "2026-09-30", 330.0, "2026-10-30")])
    df = edgar.parse_companyfacts(js, "X", date(2026, 11, 15))
    v = store.ttm(df, "revenue")
    assert (v.value, v.basis, v.end) == (400.0, "fy", pd.Timestamp("2025-12-31"))


def test_ytd_ttm_and_53_week_years():
    js = facts(Revenues=[("2024-01-01", "2024-09-30", 270.0, "2024-10-30"),
                         ("2024-01-01", "2025-01-05", 371.0, "2025-02-10", "10-K"),     # a 53-week year
                         ("2025-01-06", "2025-10-05", 300.0, "2025-10-30")])
    df = edgar.parse_companyfacts(js, "X", date(2025, 12, 1))
    v = store.ttm(df, "revenue")
    assert (v.value, v.basis) == (371 + 300 - 270, "ytd")
    assert store.kind("2024-01-01", "2025-01-05") == "FY" and store.kind("2025-01-01", "2025-02-28") is None


def test_an_ifrs_filer_is_left_to_yahoo():
    with pytest.raises(edgar.NotGaap):
        edgar.parse_companyfacts({"facts": {"ifrs-full": {"Revenue": {}}, "dei": {}}}, "NVO", TODAY)
    with pytest.raises(ValueError):
        edgar.parse_companyfacts(facts(SomethingElse=[("2024-01-01", "2024-12-31", 1.0, "2025-01-01")]), "X", TODAY)


def test_sec_ticker_list():
    df = edgar.parse_tickers({"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple"},
                              "1": {"cik_str": 1067983, "ticker": "BRK.B", "title": "Berkshire"}})
    assert dict(zip(df["ticker"], df["cik"])) == {"AAPL": 320193, "BRK-B": 1067983}
    with pytest.raises(ValueError):
        edgar.parse_tickers({})


# ---------------- Yahoo ----------------

def _yahoo(ticker: str, fetched=TODAY, old=None) -> pd.DataFrame:
    df = yahoo.parse_statements({tuple(k.split()): v for k, v in statements(ticker).items()}, ticker, "USD", fetched)
    return yahoo.merge(store.empty() if old is None else old, df, fetched, {"quarterly": 45, "annual": 75})


def test_yahoo_quarters_sum_to_the_ttm_and_agree_with_edgar(aapl):
    y = _yahoo("AAPL")
    for item in ("revenue", "operating_income", "cfo", "capex"):
        a, b = store.ttm(aapl, item), store.ttm(y, item)
        assert b.basis == "4q" and b.value == a.value, item
    assert store.ttm(y, "capex").value > 0          # Yahoo's negative cash out is stored as an amount
    assert store.instant(y, "cash").value == store.instant(aapl, "cash").value


def test_a_half_year_reporter_uses_yahoos_trailing_column():
    y = _yahoo("RR.L")
    v = store.ttm(y, "revenue")
    assert v.basis == "yahoo_ttm" and v.value > store.annual(y, "revenue").iloc[-1] * 0.8


def test_yahoo_values_are_dated_when_first_seen():
    first = _yahoo("AAPL", fetched=date(2026, 9, 1))
    assert first["assumed"].all()
    q = first[(first["item"] == "revenue") & (first["fp"] == "Q")]
    assert (q["known"] == (q["end"] + pd.Timedelta(days=45)).clip(upper=pd.Timestamp("2026-09-01"))).all()
    again = _yahoo("AAPL", fetched=date(2026, 10, 1), old=first)
    assert again.empty                                # nothing changed: nothing added
    df = yahoo.parse_statements({tuple(k.split()): v for k, v in statements("AAPL").items()}, "AAPL", "USD", TODAY)
    df.loc[(df["item"] == "revenue") & (df["fp"] == "FY"), "value"] *= 1.01   # restated years
    changed = yahoo.merge(first, df, TODAY, {"quarterly": 45, "annual": 75})
    assert len(changed) == (df["item"].eq("revenue") & df["fp"].eq("FY")).sum()
    assert (changed["known"] == pd.Timestamp(TODAY)).all() and not changed["assumed"].any()


# ---------------- schedule ----------------

def test_due_order_and_reasons():
    log = pd.DataFrame({"ticker": ["OLD", "FRESH", "FAILED", "REPORTED"],
                        "fetched": pd.to_datetime(["2026-08-01", "2026-10-10", "2026-10-14", "2026-10-01"]),
                        "ok": [True, True, False, True], "last_end": pd.NaT, "n": 1, "error": None})
    got = schedule.due(["NEW", "OLD", "FRESH", "FAILED", "REPORTED"], log, TODAY, 30,
                       {"REPORTED": pd.Timestamp("2026-10-12"), "FRESH": pd.Timestamp("2026-10-01")})
    assert got == ["NEW", "OLD", "REPORTED", "FAILED"]


# ---------------- the update steps ----------------

@pytest.fixture
def us(monkeypatch):
    monkeypatch.setattr(universe, "stock_groups", lambda **kw: {"us": ["AAPL", "MSFT"]})
    monkeypatch.setattr(valuation, "tracked_stocks", lambda: ["AAPL", "MSFT"])


TICKERS = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple"},
           "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft"}}


def test_edgar_needs_a_contact_and_sends_nothing_without_one(us, monkeypatch):
    calls = serve(monkeypatch, {})
    with pytest.raises(edgar.NoContact):
        edgar.update_edgar(today=TODAY)
    assert calls == []
    with pytest.raises(ValueError):
        edgar.set_contact("not an address")


def test_edgar_update_stores_and_keeps_more_than_a_shorter_answer(us, monkeypatch, aapl_js):
    edgar.set_contact("someone@example.com")
    seen = {}

    def facts_for(url):
        return Resp(json=aapl_js) if "0000320193" in url else Resp(404)
    calls = serve(monkeypatch, {"company_tickers": Resp(json=TICKERS), "companyfacts": facts_for})
    monkeypatch.setattr(edgar.net, "get", _capture_headers(edgar.net.get, seen))
    msg = edgar.update_edgar(today=TODAY)
    assert "1 of 2 due companies stored" in msg and "without us-gaap" in msg
    assert seen["User-Agent"].endswith("someone@example.com")
    n = len(store.load_edgar())
    assert n > 300 and any("companyfacts" in c for c in calls)

    short = json.loads(json.dumps(aapl_js))          # the next answer is missing the latest 10-Q
    for node in short["facts"]["us-gaap"].values():
        for u in node["units"]:
            node["units"][u] = [r for r in node["units"][u] if r["end"] < "2026-06-01"]
    serve(monkeypatch, {"company_tickers": Resp(json=TICKERS), "companyfacts": lambda u: Resp(json=short)
                        if "0000320193" in u else Resp(404)})
    with pytest.raises(sourcelog.PartialFailure):
        edgar.update_edgar(today=TODAY, tickers=["AAPL"])
    assert len(store.load_edgar()) == n
    log = schedule.load_log(edgar.LOG_FILE).set_index("ticker")
    assert not log.at["AAPL", "ok"] and "kept the stored values" in log.at["AAPL", "error"]


def _capture_headers(get, seen):
    def wrapped(url, **kw):
        seen.update(kw.get("headers") or {})
        return get(url, **kw)
    return wrapped


def test_a_ticker_list_that_maps_too_few_us_stocks_fails(us, monkeypatch):
    edgar.set_contact("someone@example.com")
    serve(monkeypatch, {"company_tickers": Resp(json={"0": TICKERS["0"]})})
    with pytest.raises(ValueError, match="maps only 1 of 2"):
        edgar.update_edgar(today=TODAY)


def test_yahoo_update_appends_and_fails_loudly_on_nothing(us, monkeypatch):
    fake_yf(monkeypatch, statements={"AAPL": statements("AAPL"), "MSFT": RuntimeError("Yahoo")})
    msg = yahoo.update_yahoo(today=TODAY)
    assert msg.startswith("1 of 2 due stocks answered")
    before = len(store.load_yahoo())
    assert before > 100
    fake_yf(monkeypatch, statements={"AAPL": {}, "MSFT": {}})
    with pytest.raises(ValueError, match="no statements from Yahoo"):
        yahoo.update_yahoo(today=TODAY, force=True)
    assert len(store.load_yahoo()) == before


def test_userstore_keeps_the_contact():
    assert edgar.contact() is None
    edgar.set_contact("  a@b.dk ")
    assert edgar.contact() == "a@b.dk" and userstore.meta_get("sec_contact") == "a@b.dk"
    edgar.set_contact("")
    assert edgar.contact() is None
