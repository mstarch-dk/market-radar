"""The one rule for a value the radar didn't make itself: a finite number, or None (values.num), and a mean
over what is there (model.stats.mean)."""
import numpy as np
import pandas as pd
import pytest

from radar.model.stats import mean
from radar.values import num


@pytest.mark.parametrize("v, want", [(1, 1.0), ("2.5", 2.5), (np.float32(0.5), 0.5), (True, 1.0), (-0.0, 0.0)])
def test_a_number_is_a_float(v, want):
    assert num(v) == want and isinstance(num(v), float)


@pytest.mark.parametrize("v", [None, float("nan"), float("inf"), -np.inf, pd.NA, "", "x", [1]])
def test_anything_else_is_missing(v):
    assert num(v) is None


def test_mean_leaves_out_what_is_missing():
    assert mean([1.0, None, np.nan, 3.0, np.inf]) == 2.0
    assert mean([None, np.nan]) is None and mean([]) is None
