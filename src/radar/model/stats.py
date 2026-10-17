"""Statistics the studies and the proposals share."""
from __future__ import annotations

import math

import numpy as np


def mean(values) -> float | None:
    """The mean of the finite values; None when there are none (a NaN or inf is missing, not a number)."""
    v = [x for x in values if x is not None and np.isfinite(x)]
    return float(np.mean(v)) if v else None


def nw_t(values, lag: int) -> float | None:
    """The mean's t-statistic with Newey-West (Bartlett) standard errors; None with fewer than 3 values."""
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)], dtype=float)
    n = len(v)
    if n < 3:
        return None
    e = v - v.mean()
    s = float(e @ e) / n
    for k in range(1, min(lag, n - 1) + 1):
        s += 2 * (1 - k / (lag + 1)) * float(e[k:] @ e[:-k]) / n
    if s <= 0:
        return None
    return float(v.mean() / math.sqrt(s / n))
