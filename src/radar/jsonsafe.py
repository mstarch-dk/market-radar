"""Plain JSON values from pandas/numpy ones: NaN and inf as None, dates as YYYY-MM-DD (missing stays missing)."""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd


def clean(v):
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if isinstance(v, np.generic):
        v = v.item()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (pd.Timestamp, date)):
        return v.isoformat()[:10]
    if v is pd.NaT or v is pd.NA:
        return None
    return v
