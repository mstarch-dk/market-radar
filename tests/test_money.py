"""money: pence quotes, basis points, the simulations' flat fee and an exchange rate on a day."""
import numpy as np
import pandas as pd
import pytest

from radar import money


def test_pence_belong_to_the_pound():
    assert money.is_pence("GBp") and not money.is_pence("GBP") and not money.is_pence(None)
    assert money.main_unit("GBp") == "GBP" and money.main_unit("USD") == "USD" and money.main_unit(None) is None


def test_basis_points_and_the_flat_fee():
    assert money.bps(25) == 0.0025
    assert money.fee_bps({"fee_bps": 10}) == 10.0 and money.fee_bps({}) == 0.0 and money.fee_bps(None) == 0.0


def test_a_rate_on_a_day_is_the_last_one_by_then():
    fx = pd.Series([7.0, np.nan, 7.2], index=pd.to_datetime(["2026-10-12", "2026-10-13", "2026-10-15"]))
    assert money.rate_on(fx, "2026-10-14") == 7.0                     # the gap and the day without a close
    assert money.rate_on(fx, "2026-10-15") == 7.2 and money.rate_on(fx) == 7.2
    assert money.rate_on(fx, "2026-10-01") is None                    # before the first rate


@pytest.mark.parametrize("fx", [None, pd.Series(dtype=float), pd.Series([np.nan]), pd.Series([0.0]), pd.Series([np.inf])])
def test_no_usable_rate_is_none(fx):
    if fx is not None:
        fx.index = pd.to_datetime(["2026-10-12"] * len(fx))
    assert money.rate_on(fx, "2026-10-12") is None
