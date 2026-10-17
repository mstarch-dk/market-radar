"""jsonsafe: the one way the radar turns pandas/numpy values into JSON. Missing stays missing (None, never NaN
or "NaT"), and `dumps` can't write a NaN, which isn't JSON."""
import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from radar import jsonsafe


def test_clean_makes_numpy_dates_and_gaps_json_safe():
    v = jsonsafe.clean({1: [np.int64(3), np.float64("nan"), float("inf"), pd.Timestamp("2026-01-02 15:00")],
                        "d": date(2026, 3, 4), "na": pd.NA, "t": (np.bool_(True), "x")})
    assert v == {"1": [3, None, None, "2026-01-02"], "d": "2026-03-04", "na": None, "t": [True, "x"]}
    json.dumps(v, allow_nan=False)


@pytest.mark.parametrize("missing", [pd.NaT, pd.NA, None, float("nan"), np.float64("-inf"), np.datetime64("NaT", "D")])
def test_a_missing_value_is_none(missing):
    assert jsonsafe.clean(missing) is None


def test_a_numpy_datetime_is_an_iso_date():
    assert jsonsafe.clean(np.datetime64("2026-01-02")) == "2026-01-02"
    assert jsonsafe.clean(np.datetime64("2026-01-02T00:00:00.000000000")) == "2026-01-02"


def test_a_set_is_a_sorted_list():
    assert jsonsafe.clean({"b", "a"}) == ["a", "b"]


def test_dumps_never_writes_nan_and_stringifies_the_unknown():
    text = jsonsafe.dumps({"x": np.nan, "when": pd.Timestamp("2026-10-16"), "p": object.__new__(object)}, indent=1)
    assert "NaN" not in text
    out = json.loads(text)
    assert out["x"] is None and out["when"] == "2026-10-16" and out["p"].startswith("<object")
