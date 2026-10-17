"""A number or None: what every reading does with a value it didn't make itself (missing stays missing, never 0,
NaN or inf)."""
from __future__ import annotations

import math


def num(v) -> float | None:
    """`v` as a finite float; None for None, NaN, inf or anything that isn't a number."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def whole(v) -> int | None:
    """`v` as an int (an id, a count); None when it isn't a finite number."""
    f = num(v)
    return None if f is None else int(f)
