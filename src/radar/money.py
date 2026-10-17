"""Money conventions in one place: prices quoted in pence, basis points, the simulations' flat fee and an exchange
rate on a day."""
from __future__ import annotations

import math

import pandas as pd

from .values import num

PENCE = "GBp"      # Yahoo's code for a price quoted in pence (London listings); 100 pence to the pound


def is_pence(ccy) -> bool:
    return ccy == PENCE


def main_unit(ccy):
    """The currency a quote's unit belongs to: GBP for pence, else the code as it is (None stays None)."""
    return "GBP" if ccy == PENCE else ccy


def bps(x) -> float:
    """Basis points as a fraction (25 -> 0.0025)."""
    return float(x) / 1e4


def fee_bps(backtest: dict | None) -> float:
    """The flat fee in basis points a simulated trade pays without a fee schedule: settings.yaml backtest.fee_bps
    (pass that section), 0 when it isn't set."""
    return float((backtest or {}).get("fee_bps", 0))


def rate_on(fx: pd.Series | None, day=None) -> float | None:
    """An exchange rate on `day` (default: the latest), or the last one before it; None without a positive, finite
    rate."""
    if fx is None:
        return None
    s = fx.dropna()
    if s.empty:
        return None
    v = s.asof(pd.Timestamp(day)) if day is not None else s.iloc[-1]
    v = num(v)
    return v if v is not None and v > 0 else None


def parse_amount(text) -> float:
    """An amount in DKK as people write it: 50000, 50.000, 50,000, 50k, 1.5m, 12,5k ("kr"/"dkk" ignored).
    ValueError for anything else or an amount that isn't positive."""
    import re

    t = str(text).strip().lower().replace(" ", "").replace("dkk", "").replace("kr", "")
    mult = 1.0
    if t.endswith("k"):
        mult, t = 1e3, t[:-1]
    elif t.endswith("m"):
        mult, t = 1e6, t[:-1]
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", t):
        t = re.sub(r"[.,]", "", t)
    t = t.replace(",", ".")
    try:
        v = float(t) * mult
    except ValueError:
        raise ValueError(f"not an amount: {text}") from None
    if not math.isfinite(v):                     # float() reads "nan" and "inf" too
        raise ValueError(f"not an amount: {text}")
    if v <= 0:
        raise ValueError("the amount must be positive")
    return v
