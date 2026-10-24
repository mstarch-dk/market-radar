"""The one rule for a value the radar didn't make itself: a finite number, or None (values.num), and a mean
over what is there (model.stats.mean)."""
import numpy as np
import pandas as pd
import pytest

from radar.model.stats import mean, split_holdout
from radar.values import num, whole


@pytest.mark.parametrize("v, want", [(1, 1.0), ("2.5", 2.5), (np.float32(0.5), 0.5), (True, 1.0), (-0.0, 0.0)])
def test_a_number_is_a_float(v, want):
    assert num(v) == want and isinstance(num(v), float)


@pytest.mark.parametrize("v", [None, float("nan"), float("inf"), -np.inf, pd.NA, "", "x", [1]])
def test_anything_else_is_missing(v):
    assert num(v) is None


def test_mean_leaves_out_what_is_missing():
    assert mean([1.0, None, np.nan, 3.0, np.inf]) == 2.0
    assert mean([None, np.nan]) is None and mean([]) is None


def test_whole_is_an_int_or_missing():
    assert whole(np.int64(3)) == 3 and isinstance(whole(3.0), int)
    assert whole(None) is None and whole(np.nan) is None and whole(pd.NA) is None


def test_the_holdout_split_is_by_date_and_none_means_all_in_sample():
    recs = [{"date": pd.Timestamp(d)} for d in ("2020-01-31", "2021-12-31", "2022-01-31", "2023-06-30")]
    parts = split_holdout(recs, pd.Timestamp("2022-01-31"))
    assert [len(parts[k]) for k in ("all", "in_sample", "holdout")] == [4, 2, 2]      # the holdout starts on its day
    assert split_holdout(recs, None) == {"all": recs, "in_sample": recs, "holdout": []}
