"""SKAT's positive list (aktiebaserede investeringsselskaber), shipped with the app: the ISINs that are taxed as
shares in an aktiesparekonto and frie midler."""
from __future__ import annotations

import re

import pandas as pd

from .config import POSITIVE_LIST_FILE

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def load() -> pd.DataFrame | None:
    """SKAT's list of aktiebaserede investeringsselskaber – the latest year's sheet only.

    Older sheets are history; a fund deregistered this year must not count as listed.
    """
    if not POSITIVE_LIST_FILE.exists():
        return None
    sheets = pd.read_excel(POSITIVE_LIST_FILE, sheet_name=None, dtype=str)
    year = max(n for n in sheets if n.strip().isdigit())
    df = sheets[year]
    isin_col = next((c for c in df.columns if "isin" in str(c).lower()), None)  # by header: SKAT reorders columns
    if isin_col is None:
        raise ValueError(f"no ISIN column in the {year} sheet of {POSITIVE_LIST_FILE.name}")
    df = df.rename(columns={isin_col: "isin"})
    df["isin"] = df["isin"].str.strip().str.upper()
    df = df[df["isin"].str.match(ISIN_RE.pattern, na=False)]
    if df.empty:
        raise ValueError(f"no valid ISINs in the {year} sheet of {POSITIVE_LIST_FILE.name}")
    df.attrs["year"] = year
    return df


def isins() -> set[str] | None:
    df = load()
    return None if df is None else set(df["isin"])


def flag(isin: str | None, isins: set[str] | None) -> str:
    if not isinstance(isin, str) or not isin or isins is None:
        return "?"
    return "yes" if isin.upper() in isins else "no"
