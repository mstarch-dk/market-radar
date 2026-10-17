"""The trend exit and basket paths with it, once for the stop simulation, the proposal study and the follow-up on
frozen proposals.

The trend exit: a close below the `n`-day average of adjusted closes (missing until there are `n` closes) is the
trigger; the name is sold at the next session's close. The buy day itself is never a trigger: the check starts the
session after the buy. After the exit the money is parked in the benchmark."""
from __future__ import annotations

from collections.abc import Callable

import pandas as pd


def trend_level(closes, n: int):
    """The `n`-day average of the closes (Series or DataFrame); missing until there are `n` closes."""
    return closes.rolling(n, min_periods=n).mean()


def below_trend(closes, n: int):
    """True where the close is below its `n`-day average (False where the average is missing)."""
    return closes < trend_level(closes, n)


def exit_session(idx: pd.DatetimeIndex, below: pd.Series, signal: Callable[[pd.Timestamp], bool] | None = None
                 ) -> int | None:
    """The position in `idx` (idx[0] = the buy day) of the session the exit sells at: the one after the first
    trigger, a close below the level or `signal(day)`, checked from the session after the buy. None: no exit
    before the end of `idx`."""
    for i, d in enumerate(idx[1:-1], 1):
        if bool(below.get(d, False)) or (signal is not None and signal(d)):
            return i + 1
    return None


def park(leg: pd.Series, day: pd.Timestamp, bench: pd.Series, cost: float = 0.0) -> pd.Series:
    """A leg (value relative to the buy) sold at `day`'s close less `cost`, the proceeds then following `bench`."""
    return leg.where(leg.index <= day, leg.loc[day] * (1 - cost) * bench / bench.loc[day])
