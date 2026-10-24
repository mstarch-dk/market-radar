"""Property tests (Hypothesis) for the money and stats kernels: invariants that hold for every input, checked over
generated ones. A failure prints the smallest input that breaks the rule; pin it as an example test."""
import math

import pandas as pd
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from radar import money
from radar.model.stats import path_stats
from radar.portfolios import trades
from radar.signals.risk import deepest_drawdown, worst_window

# value paths: positive levels, as a price or a portfolio's value is
levels = st.lists(st.floats(0.01, 1e4, allow_nan=False), min_size=1, max_size=80).map(
    lambda xs: pd.Series(xs, index=pd.bdate_range("2026-01-01", periods=len(xs)), dtype=float))


# ---------------- drawdown, worst window, path stats ----------------

@given(levels)
def test_a_drawdown_is_never_positive_and_never_below_minus_one(level):
    dd = deepest_drawdown(level)
    assert -1 < dd <= 0


@given(levels, st.floats(0.01, 100))
def test_a_drawdown_does_not_depend_on_the_unit(level, k):
    assert deepest_drawdown(level * k) == pytest.approx(deepest_drawdown(level), abs=1e-12)


@given(levels)
def test_a_path_that_never_falls_has_no_drawdown(level):
    assert deepest_drawdown(level.cummax()) == 0


@given(levels, st.integers(1, 30))
def test_the_worst_window_is_missing_when_too_short_and_never_worse_than_the_drawdown(level, n):
    w = worst_window(level, n)
    if len(level) <= n:
        assert w is None                                     # missing, not 0
    else:
        assert w is not None and w > -1
        assert w >= deepest_drawdown(level) - 1e-12          # any fall over n sessions is a fall from a peak or less


@given(levels)
def test_path_stats_agree_with_their_parts(level):
    s = path_stats(level)
    assert s["ret"] == pytest.approx(level.iloc[-1] - 1)
    assert s["max_dd"] == deepest_drawdown(level) and s["worst20"] == worst_window(level, 20)


# ---------------- money: a rate on a day, an amount as people write it ----------------

rates = st.lists(st.one_of(st.floats(-2, 20, allow_nan=False), st.just(math.nan), st.just(math.inf)),
                 min_size=0, max_size=30).map(
    lambda xs: pd.Series(xs, index=pd.bdate_range("2026-01-01", periods=len(xs)), dtype=float))


@given(rates, st.integers(-5, 40))
def test_a_rate_is_positive_and_finite_or_missing_and_never_from_a_later_day(fx, offset):
    day = pd.Timestamp("2026-01-01") + pd.offsets.BDay(offset)
    r = money.rate_on(fx, day)
    assert r is None or (math.isfinite(r) and r > 0)
    assert r == money.rate_on(fx[fx.index <= day], None) or (r is None and fx[fx.index <= day].dropna().empty)
    if r is not None:
        assert r in set(fx[fx.index <= day])


@given(rates)
def test_the_latest_rate_is_the_last_known_one_when_positive(fx):
    known = fx.dropna()
    r = money.rate_on(fx)
    last = known.iloc[-1] if len(known) else None
    assert r == (last if last is not None and math.isfinite(last) and last > 0 else None)


def _thousands(v: int, sep: str) -> str:
    return f"{v:,}".replace(",", sep)


@given(st.integers(1, 10**9), st.sampled_from(["plain", ".", ",", " kr", " DKK", "k"]))
def test_an_amount_round_trips_in_the_ways_people_write_it(v, form):
    if form == "plain":
        text = str(v)
    elif form in (".", ","):
        text = _thousands(v, form)
    elif form == "k":
        assume(v % 1000 == 0)
        text = f"{v // 1000}k"
    else:
        text = f"{v}{form}"
    assert money.parse_amount(text) == v


@given(st.text(max_size=12))
def test_anything_parse_amount_accepts_is_a_positive_number(text):
    try:
        v = money.parse_amount(text)
    except ValueError:
        return
    assert v > 0


# ---------------- trades.replay: the average-cost method ----------------

trade = st.tuples(st.sampled_from(["BUY", "SELL"]), st.floats(0.5, 100), st.floats(1, 1000), st.floats(0, 50))


def _tx(rows) -> pd.DataFrame:
    return pd.DataFrame([{"date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=i), "type": k, "quantity": q,
                          "price": px, "fee": fee} for i, (k, q, px, fee) in enumerate(rows)])


def _held(rows) -> float:
    qty = 0.0
    for k, q, _px, _fee in rows:
        qty = qty + q if k == "BUY" else qty - min(q, qty)
    return qty


@given(st.lists(trade, min_size=1, max_size=25))
def test_a_replay_never_sells_more_than_it_holds_and_says_so(rows):
    pos, warnings = trades.replay(_tx(rows))
    held = _held(rows)
    if pos["status"] == "holding":
        assert pos["quantity"] > 0 and pos["quantity"] == pytest.approx(held, abs=1e-6)
    else:
        assert pos["quantity"] is None and pos["avg_price"] is None and held <= 1e-9 + 1e-6
    oversold, qty = False, 0.0
    for k, q, _px, _fee in rows:
        oversold |= k == "SELL" and q > qty + 1e-9
        qty = qty + q if k == "BUY" else qty - min(q, qty)
    assert bool(warnings) == oversold


@given(st.lists(st.tuples(st.floats(0.5, 100), st.floats(1, 1000), st.floats(0, 50)), min_size=1, max_size=10),
       st.floats(0.01, 0.99))
def test_the_average_cost_holds_the_fees_and_a_sale_does_not_move_it(buys, share):
    rows = [("BUY", q, px, fee) for q, px, fee in buys]
    before, _ = trades.replay(_tx(rows))
    cost = sum(q * px + fee for q, px, fee in buys)
    qty = sum(q for q, _px, _fee in buys)
    assert before["avg_price"] == pytest.approx(cost / qty)
    assert min(px for _q, px, _f in buys) - 1e-9 <= before["avg_price"] <= max(px + f / q for q, px, f in buys) + 1e-9
    after, warnings = trades.replay(_tx([*rows, ("SELL", qty * share, 1.0, 0.0)]))
    assert not warnings and after["avg_price"] == pytest.approx(before["avg_price"])
    assert after["quantity"] == pytest.approx(qty * (1 - share), abs=1e-6)

