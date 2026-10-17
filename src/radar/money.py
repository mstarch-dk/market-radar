"""Money conventions in one place: prices quoted in pence, basis points, the simulations' flat fee and an exchange
rate on a day."""
from __future__ import annotations

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
