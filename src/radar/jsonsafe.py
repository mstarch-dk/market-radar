"""Plain JSON values from pandas/numpy ones: NaN and inf as None, dates as YYYY-MM-DD (missing stays missing).
`dumps` is the one way the radar writes JSON: what `clean` leaves can't be NaN, and anything else unknown is str()."""
from __future__ import annotations

import json
import math
from datetime import date

import numpy as np
import pandas as pd


def clean(v):
    if v is pd.NaT or v is pd.NA:                   # before the date check: NaT is a datetime and would become "NaT"
        return None
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return [clean(x) for x in sorted(v)]
    if isinstance(v, np.datetime64):
        v = pd.Timestamp(v)
        return None if v is pd.NaT else v.isoformat()[:10]
    if isinstance(v, np.generic):
        v = v.item()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (pd.Timestamp, date)):
        return v.isoformat()[:10]
    return v


def dumps(obj, **kw) -> str:
    """JSON text of `clean(obj)` (json.dumps' keywords pass through, e.g. indent)."""
    return json.dumps(clean(obj), allow_nan=False, default=str, **kw)
