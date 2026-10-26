"""The tax estimate for a year (tax.py) on the synthetic world: one average per person across their frie midler
accounts, an ETF that leaves the positive list (share income, then capital income and an ASK warning), a fund the
radar can't classify (named with its value, in no estimate), the aktiesparekonto's pool from the book, a year
without rules (bases, no tax), openings carried in and anchoring the chain after a year without rules, dividends
the prices show but nobody booked (unknown, not 0), and the pre-tax numbers unchanged."""
from __future__ import annotations

import openpyxl
import pandas as pd
import pytest

import world
from radar import config, config_schema, tax, userstore
from radar.market import Market
from radar.portfolios import performance, taxrules
from world import IDX

HEADER = ["Skattemæssigt hjemsted/Tax residence", "ISIN-kode/-Code", "Navn andelsklasse/Name Shareclass"]
ISIN = "IE00B4L5Y983"
LAST = IDX[-1]
YEAR = LAST.year
PREV = YEAR - 1


def poslist(tmp_data, sheets: dict[str, list[str]]) -> None:
    wb = openpyxl.Workbook()
    wb.active.title = "Forside"
    for name, isins in sheets.items():
        ws = wb.create_sheet(name)
        ws.append(HEADER)
        for i in isins:
            ws.append(["IE", i, "A fund"])
    wb.save(tmp_data / "positivliste.xlsx")


@pytest.fixture
def market(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    poslist(tmp_data, {str(PREV): [ISIN], str(YEAR): ["IE00B6R52259"]})   # THEME1 leaves the list this year
    return Market.load()


def pid(name: str) -> int:
    """A seeded portfolio's id (the store seeds ASK and frie midler on creation)."""
    userstore.connect().close()
    return userstore.portfolio_by_name(name)["id"]


def day(year: int, n: int) -> pd.Timestamp:
    return [d for d in IDX if d.year == year][n]


def px(market, sym, d) -> float:
    return float(market.closes[sym].loc[d])


def buy(portfolio, sym, d, q, market, fee=0.0, kind="BUY"):
    userstore.add_tx({"symbol": sym, "date": d.date().isoformat(), "type": kind, "quantity": q,
                      "price": px(market, sym, d), "fee": fee, "portfolio_id": portfolio})


def test_one_average_per_person_across_frie_midler_accounts(market):
    a = userstore.save_portfolio({"name": "Depot A", "kind": "frie_midler"})
    b = userstore.save_portfolio({"name": "Depot B", "kind": "frie_midler"})
    ask = pid("ASK")
    d1, d2, d3 = day(PREV, 5), day(PREV, 20), day(YEAR, 30)
    buy(a, "S2", d1, 10, market, fee=1)
    buy(b, "S2", d2, 10, market, fee=1)
    buy(ask, "S2", d2, 50, market)                             # the ASK's own: not in the average
    buy(a, "S2", d3, 5, market, fee=1, kind="SELL")
    r = tax.year_report(market, YEAR)
    acc = next(x for x in r["accounts"] if x["name"] == "Depot A")
    (sale,) = acc["realised"]
    cost = (10 * px(market, "S2", d1) + 1 + 10 * px(market, "S2", d2) + 1) * 6.5
    assert sale["basis"] == pytest.approx(cost / 20 * 5)
    assert sale["gain"] == pytest.approx((5 * px(market, "S2", d3) - 1) * 6.5 - cost / 4)
    me = next(p for p in r["persons"] if p["name"] == "Me")
    assert me["share_income"]["realised_gains"] == pytest.approx(sale["gain"])
    lim = taxrules.rules(YEAR).share_income.progression_limit
    assert me["share_income"]["tax"] == pytest.approx(0.27 * min(sale["gain"], lim) + 0.42 * max(0, sale["gain"] - lim))


def test_an_etf_that_leaves_the_positive_list(market):
    fm = pid("frie midler")
    ask = pid("ASK")
    userstore.save_instrument("THEME1", isin=ISIN)
    buy(fm, "THEME1", day(PREV, 3), 20, market)
    buy(ask, "THEME1", day(PREV, 3), 5, market)
    before = tax.year_report(market, PREV)
    (row,) = next(a for a in before["accounts"] if a["name"] == "frie midler")["lager"]
    assert row["tax_class"] == "pl_fund" and row["v_start"] == 0
    assert before["persons"][0]["bases"]["pl_gains"] == pytest.approx(row["gain"])
    assert before["persons"][0]["bases"]["capital_base"] == 0
    now = tax.year_report(market, YEAR)
    (row,) = next(a for a in now["accounts"] if a["name"] == "frie midler")["lager"]
    assert row["tax_class"] == "fund"
    assert now["persons"][0]["bases"]["capital_base"] == pytest.approx(row["gain"])
    assert now["persons"][0]["capital_income"]["tax"] is None                     # no rate given: no guess
    assert any("THEME1: not on the" in w for w in next(a for a in now["accounts"] if a["name"] == "ASK")["warnings"])


def test_a_fund_without_an_isin_is_named_and_left_out(market):
    fm = pid("frie midler")
    buy(fm, "THEME2", day(PREV, 3), 10, market)
    r = tax.year_report(market, YEAR)
    (u,) = r["unknown"]
    assert u["symbol"] == "THEME2" and u["value_dkk"] > 0 and "ISIN" in u["reason"]
    acc = next(a for a in r["accounts"] if a["name"] == "frie midler")
    me = r["persons"][0]
    assert acc["lager"] == [] and me["bases"]["capital_base"] is None                # it could be capital income
    assert me["capital_income"]["base"] is None and me["capital_income"]["tax"] is None and not me["complete"]
    assert any("THEME2 at the end of" in n for n in me["notes"])


def test_the_ask_pool_from_the_book(market):
    ask = pid("ASK")
    userstore.add_tx({"date": day(PREV, 1).date().isoformat(), "type": "DEPOSIT", "amount": 100_000, "portfolio_id": ask})
    buy(ask, "S1", day(PREV, 2), 100, market)
    userstore.add_tx({"date": day(YEAR, 10).date().isoformat(), "type": "DEPOSIT", "amount": 5_000, "portfolio_id": ask})
    r = tax.year_report(market, YEAR)
    pool = next(a for a in r["accounts"] if a["name"] == "ASK")["pool"]
    b = performance.book(userstore.transactions(portfolios=[ask]), market, "cash")
    v0 = float(b.value[b.value.index <= pd.Timestamp(PREV, 12, 31)].iloc[-1])
    v1 = float(b.value.iloc[-1])
    assert pool["v_start"] == pytest.approx(v0) and pool["v_end"] == pytest.approx(v1)
    assert pool["deposits"] == pytest.approx(5_000)
    assert pool["ret"] == pytest.approx(v1 - v0 - 5_000)
    assert pool["tax"] == pytest.approx(max(0.0, pool["ret"]) * 0.17)
    assert not r["complete_year"] and any("isn't over" in n for n in r["notes"])


def test_a_year_without_rules_shows_bases_and_no_tax(market, monkeypatch):
    no_rules_for(YEAR, monkeypatch)
    fm = pid("frie midler")
    buy(fm, "S2", day(PREV, 5), 10, market)
    buy(fm, "S2", day(YEAR, 5), 4, market, kind="SELL")
    r = tax.year_report(market, YEAR)
    assert r["rules"] is None and any(f"no rules for {YEAR}" in n for n in r["notes"])
    me = r["persons"][0]
    assert me["share_income"] is None and me["bases"]["realised_gains"] > 0 and not me["complete"]


def test_openings_are_carried_in(market):
    fm = pid("frie midler")
    buy(fm, "S2", day(PREV, 5), 10, market)
    buy(fm, "S2", day(YEAR, 5), 10, market, kind="SELL")
    gain = tax.year_report(market, YEAR)["persons"][0]["share_income"]["realised_gains"]
    me = userstore.tax_persons()[0]["id"]
    userstore.add_tax_opening({"year": PREV, "pool": "listed_loss", "tax_person_id": me, "amount": gain + 100})
    si = tax.year_report(market, YEAR)["persons"][0]["share_income"]
    assert si["listed_loss_in"] == pytest.approx(gain + 100)
    assert si["net"] == 0 and si["listed_loss_out"] == pytest.approx(100)


def no_rules_for(year: int, monkeypatch) -> None:
    raw = config.load_yaml("tax_dk.yaml")
    raw["years"].pop(year, None)
    monkeypatch.setattr(taxrules, "load", lambda: config_schema.check_tax(raw))


def test_an_opening_anchors_the_chain_after_a_year_without_rules(market, monkeypatch):
    no_rules_for(PREV, monkeypatch)
    fm, ask = pid("frie midler"), pid("ASK")
    buy(fm, "S2", day(PREV, 5), 10, market)
    buy(fm, "S2", day(YEAR, 5), 10, market, kind="SELL")
    userstore.add_tx({"date": day(PREV, 1).date().isoformat(), "type": "DEPOSIT", "amount": 50_000, "portfolio_id": ask})
    buy(ask, "S1", day(PREV, 2), 50, market)
    r = tax.year_report(market, YEAR)
    me, pool = r["persons"][0], next(a for a in r["accounts"] if a["name"] == "ASK")["pool"]
    assert me["share_income"] is None and pool["tax"] is None                          # the chain broke in PREV
    assert any(f"({PREV} has no estimate)" in n and f"årsopgørelse for {PREV}" in n for n in me["notes"])
    person = userstore.tax_persons()[0]["id"]
    userstore.add_tax_opening({"year": YEAR, "pool": "listed_loss", "tax_person_id": person, "amount": 0})
    userstore.add_tax_opening({"year": YEAR, "pool": "ask_negative_tax", "portfolio_id": ask, "amount": 300})
    r = tax.year_report(market, YEAR)
    si, pool = r["persons"][0]["share_income"], next(a for a in r["accounts"] if a["name"] == "ASK")["pool"]
    assert si is not None and si["listed_loss_in"] == 0 and si["negative_in"] == 0      # the pool not entered: 0
    assert pool["carried_in"] == 300 and pool["tax"] is not None


def test_an_opening_replaces_a_known_chain(market):
    fm = pid("frie midler")
    buy(fm, "S2", day(PREV, 5), 10, market)
    buy(fm, "S2", day(PREV, 40), 10, market, kind="SELL")
    loss = tax.year_report(market, PREV)["persons"][0]["share_income"]
    chained = tax.year_report(market, YEAR)["persons"][0]["share_income"]
    assert chained["listed_loss_in"] == pytest.approx(loss["listed_loss_out"])
    me = userstore.tax_persons()[0]["id"]
    userstore.add_tax_opening({"year": YEAR, "pool": "listed_loss", "tax_person_id": me, "amount": 1234})
    assert tax.year_report(market, YEAR)["persons"][0]["share_income"]["listed_loss_in"] == 1234   # the årsopgørelse wins


def test_a_dividend_the_prices_show_but_nobody_booked(market):
    fm = pid("frie midler")
    ex = day(YEAR, 20)
    raw = market.closes.copy()
    raw.loc[raw.index < ex, "S2"] = raw.loc[raw.index < ex, "S2"] / 0.98             # a 2 % dividend on `ex`
    market._raw = raw
    buy(fm, "S2", day(PREV, 5), 10, market)
    r = tax.year_report(market, YEAR)
    me = r["persons"][0]
    assert me["bases"]["dividends"] is None and not me["complete"]
    assert any(f"S2 in frie midler: ex-dividend {ex.date()}" in n for n in me["notes"])
    userstore.add_tx({"symbol": "S2", "date": (ex + pd.Timedelta(days=3)).date().isoformat(), "type": "DIVIDEND",
                      "amount": 25.0, "portfolio_id": fm})
    me = tax.year_report(market, YEAR)["persons"][0]
    assert me["bases"]["dividends"] == pytest.approx(25.0) and not any("ex-dividend" in n for n in me["notes"])


def test_the_payment_window_matches_the_guide():
    assert tax.PAY_DAYS == 45            # quoted as "45 dage" in guide/brugervejledning/skat.md


def test_a_dividend_before_the_holding_is_not_missing(market):
    fm = pid("frie midler")
    ex = day(YEAR, 20)
    raw = market.closes.copy()
    raw.loc[raw.index < ex, "S2"] = raw.loc[raw.index < ex, "S2"] / 0.98
    market._raw = raw
    buy(fm, "S2", ex, 10, market)                                                      # bought on the ex-day: no dividend
    assert tax.year_report(market, YEAR)["persons"][0]["bases"]["dividends"] == 0


def test_pretax_numbers_are_unchanged(market):
    fm = pid("frie midler")
    buy(fm, "S2", day(PREV, 5), 10, market)
    p = userstore.get_portfolio(fm)
    before = performance.analyze(performance.portfolio_book(p, market), market)
    userstore.save_instrument("S2", isin="US0000000002", tax_class="stock")
    userstore.add_tax_opening({"year": PREV, "pool": "listed_loss", "tax_person_id": p["tax_person_id"], "amount": 1})
    tax.year_report(market, YEAR)
    performance.reset()
    assert performance.analyze(performance.portfolio_book(userstore.get_portfolio(fm), market), market) == before
