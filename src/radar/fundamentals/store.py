"""The fact store: statement values from SEC EDGAR and Yahoo in one long format, read and written here. The period
arithmetic on top (TTM, latest balance, fiscal years as known on a day) is pure and lives in signals/periods.py;
it is re-exported here. Where the data comes from: guide/brugervejledning/data-og-daekning.md (Regnskaber).
"""
from __future__ import annotations

import pandas as pd

from ..config import write_parquet
from ..paths import CACHE, HISTORY
from ..signals.periods import (  # noqa: F401 (re-exported: the store's readers use them as store.ttm etc.)
    KINDS,
    Row,
    Value,
    View,
    annual,
    as_known,
    instant,
    kind,
    latest_end,
    ttm,
    view,
)

EDGAR_FILE = CACHE / "fundamentals" / "edgar.parquet"       # can be fetched again from SEC: cache
YAHOO_FILE = HISTORY / "fundamentals" / "yahoo.parquet"     # Yahoo keeps ~4 years: what scrolls out is history

# One row per value as a source reported it. `start` is the first day of a flow's period (EDGAR only; Yahoo gives
# the period's end and its kind in `fp`: FY, Q or TTM). `known` is the first day the radar could have known the
# value: for EDGAR the filing date plus a day; for Yahoo the first day a fetch saw it, or an assumed date (`assumed`)
# for values seen in a ticker's first fetch, since Yahoo doesn't say when they were published; those never feed a
# test on past data. `tag` is the source's name for the item (items.py), `accn` EDGAR's filing number.
COLS = ["ticker", "source", "item", "start", "end", "value", "currency", "form", "fp", "filed", "known", "fetched",
        "tag", "accn", "assumed"]
DATES = ("start", "end", "filed", "known", "fetched")


def empty() -> pd.DataFrame:
    df = pd.DataFrame({c: pd.Series(dtype="object") for c in COLS})
    for c in DATES:
        df[c] = pd.Series(dtype="datetime64[ns]")
    df["value"] = pd.Series(dtype="float64")
    df["assumed"] = pd.Series(dtype="bool")
    return df


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """The columns in order with their types (missing columns added empty)."""
    out = df.reindex(columns=COLS).copy()
    for c in DATES:
        out[c] = pd.to_datetime(out[c])
    out["value"] = pd.to_numeric(out["value"], errors="coerce").astype("float64")
    out["assumed"] = out["assumed"].fillna(False).astype(bool)
    return out


def _read(path) -> pd.DataFrame:
    return normalize(pd.read_parquet(path)) if path.exists() else empty()


def load_edgar() -> pd.DataFrame:
    return _read(EDGAR_FILE)


def load_yahoo() -> pd.DataFrame:
    return _read(YAHOO_FILE)


def save(df: pd.DataFrame, path) -> None:
    out = normalize(df).sort_values(["ticker", "item", "end", "known"], kind="stable")
    write_parquet(out, path, index=False)
