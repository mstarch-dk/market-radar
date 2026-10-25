"""Danish tax arithmetic (model/tax.py) against hand calculations: the textbook's worked examples in
guide/laerebog/skat.md are the golden tests, so the chapter and the engine can't disagree. The average-cost replay in
DKK over partial sales, lager with a purchase and a sale during the year, the aktiesparekonto over three years with a
losing year, a pension year at the PAL rate, the loss rules and the progression limit."""
from datetime import date

import pytest

from radar.model import tax


def T(day, kind, q, px, fee=0.0, rate=1.0):
    return tax.Trade(date.fromisoformat(day), kind, q, px, fee, rate)


def test_textbook_partial_sale_gains_145():
    # Køb 10 @ 100 + 20, køb 10 @ 130 + 20, salg 5 @ 150 − 20: gevinst 730 − 585 = 145 (skat.md, gennemsnitsmetoden)
    r = tax.replay_dkk([T("2026-01-10", "BUY", 10, 100, 20), T("2026-02-10", "BUY", 10, 130, 20),
                        T("2026-03-10", "SELL", 5, 150, 20)])
    (s,) = r.sales
    assert (s.proceeds, s.basis, s.gain) == pytest.approx((730, 585, 145))
    assert r.quantity == 15 and r.cost / r.quantity == pytest.approx(117)


def test_replay_in_dkk_at_each_trade_rate():
    # USD stock: bought 10 @ 100 + 1 at 6.50, 10 @ 110 + 1 at 7.00, sold 10 @ 120 − 1 at 6.80
    r = tax.replay_dkk([T("2026-01-02", "BUY", 10, 100, 1, 6.5), T("2026-02-02", "BUY", 10, 110, 1, 7.0),
                        T("2026-03-02", "SELL", 10, 120, 1, 6.8)])
    cost = 1001 * 6.5 + 1101 * 7.0                 # 6506.5 + 7707 = 14213.5
    (s,) = r.sales
    assert s.basis == pytest.approx(cost / 2)
    assert s.proceeds == pytest.approx(1199 * 6.8)
    assert s.gain == pytest.approx(1199 * 6.8 - cost / 2)


def test_oversold_is_capped_and_a_missing_rate_is_missing():
    r = tax.replay_dkk([T("2026-01-02", "BUY", 5, 10), T("2026-02-02", "SELL", 8, 12)])
    assert r.sales[0].quantity == 5 and r.warnings and "held 5" in r.warnings[0]
    r = tax.replay_dkk([T("2026-01-02", "BUY", 5, 10, rate=None), T("2026-02-02", "SELL", 2, 12)])
    assert r.sales[0].gain is None and r.cost is None
    r = tax.replay_dkk([T("2026-01-02", "BUY", 5, 10), T("2026-02-02", "SELL", 2, 12, rate=None)])
    assert r.sales[0].gain is None and r.sales[0].basis == pytest.approx(20)


def test_textbook_positive_list_lager_with_a_purchase_in_the_year():
    # Købt for 50.000 i løbet af året, 56.000 værd 31. december: 6.000 (skat.md, positivliste eller ej)
    assert tax.lager(0.0, 56_000, [50_000], []) == pytest.approx(6_000)
    # Next year: start 56.000, half sold for 30.000 in March, the rest worth 29.000 at year end: 3.000
    assert tax.lager(56_000, 29_000, [], [30_000]) == pytest.approx(3_000)
    assert tax.lager(56_000, None, [], []) is None and tax.lager(0.0, 1.0, [None], []) is None


def test_textbook_ask_three_years():
    # skat.md: 12.000 → 2.040; −5.000 carried; 8.000 − 5.000 → 510 (negative tax 850 carried, 1.360 − 850)
    y1 = tax.account_pool(100_000, 132_000, 20_000, 0, 0.0, 0.17)
    assert (y1.ret, y1.tax, y1.carried_out) == pytest.approx((12_000, 2_040, 0))
    y2 = tax.account_pool(129_960, 124_960, 0, 0, y1.carried_out, 0.17)
    assert (y2.ret, y2.tax, y2.carried_out) == pytest.approx((-5_000, 0, 850))
    y3 = tax.account_pool(124_960, 132_960, 0, 0, y2.carried_out, 0.17)
    assert (y3.ret, y3.used, y3.tax, y3.carried_out) == pytest.approx((8_000, 850, 510, 0))


def test_pension_at_the_pal_rate_with_carry_forward():
    y1 = tax.account_pool(500_000, 480_000, 10_000, 0, 0.0, 0.153)
    assert y1.ret == pytest.approx(-30_000) and y1.carried_out == pytest.approx(4_590) and y1.tax == 0
    y2 = tax.account_pool(480_000, 540_000, 0, 5_000, y1.carried_out, 0.153)
    assert y2.ret == pytest.approx(65_000)
    assert y2.tax == pytest.approx(65_000 * 0.153 - 4_590)


RULES = dict(low_rate=0.27, high_rate=0.42, limit=79_400, listed_offsets=["realised", "dividends", "pl_lager"])


@pytest.mark.parametrize("s, low, high", [(50_000, 13_500, 0), (79_400, 21_438, 0), (100_000, 21_438, 8_652)])
def test_progression_below_at_and_above_the_limit(s, low, high):
    r = tax.share_income([s], 0.0, [], listed_loss_in=0.0, negative_in=0.0, **RULES)
    assert (r.tax_low, r.tax_high, r.tax) == pytest.approx((low, high, low + high))


def test_listed_losses_offset_only_what_the_rules_allow_and_carry_forward():
    r = tax.share_income([10_000, -25_000], 3_000, [2_000], listed_loss_in=1_000, negative_in=0.0, **RULES)
    # 26.000 of losses against 15.000 of gains, dividends and positive-list lager: 11.000 carried, no tax
    assert r.listed_loss_used == pytest.approx(15_000) and r.listed_loss_out == pytest.approx(11_000)
    assert r.net == 0 and r.tax == 0 and r.negative_out == 0
    only = dict(RULES, listed_offsets=["realised"])
    r = tax.share_income([10_000, -25_000], 3_000, [2_000], listed_loss_in=0.0, negative_in=0.0, **only)
    assert r.listed_loss_used == pytest.approx(10_000) and r.net == pytest.approx(5_000)


def test_positive_list_lager_loss_is_deducted_and_a_negative_total_carries():
    r = tax.share_income([4_000], 0.0, [-10_000], listed_loss_in=0.0, negative_in=0.0, **RULES)
    assert r.net == 0 and r.negative_out == pytest.approx(6_000)
    r2 = tax.share_income([20_000], 0.0, [], listed_loss_in=0.0, negative_in=r.negative_out, **RULES)
    assert r2.net == pytest.approx(14_000) and r2.negative_out == 0


def test_capital_tax_needs_the_person_s_rate():
    assert tax.capital_tax(6_000, None) is None
    assert tax.capital_tax(6_000, 0.37) == pytest.approx(2_220)


def test_ask_headroom_from_last_year_end_value():
    # skat.dk's example: 105.000 on 31 Dec 2025 leaves 69.200 of the 174.200 cap for 2026
    assert tax.ask_headroom(174_200, 105_000, 0) == pytest.approx(69_200)
    assert tax.ask_headroom(174_200, 105_000, 80_000) == pytest.approx(-10_800)
