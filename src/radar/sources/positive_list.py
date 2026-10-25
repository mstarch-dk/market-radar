"""SKAT's positive list (aktiebaserede investeringsselskaber), shipped with the app: the ISINs that are taxed as
shares in an aktiesparekonto and frie midler. The flag on the ETF pages uses the latest year's sheet; the tax
estimate uses the sheet of each income year."""
from __future__ import annotations

import re

import pandas as pd

from ..config import POSITIVE_LIST_FILE

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def _sheet(df: pd.DataFrame, year: str) -> pd.DataFrame:
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


def _sheets() -> dict[str, pd.DataFrame] | None:
    if not POSITIVE_LIST_FILE.exists():
        return None
    sheets = pd.read_excel(POSITIVE_LIST_FILE, sheet_name=None, dtype=str)
    return {n.strip(): df for n, df in sheets.items() if n.strip().isdigit()}


def load() -> pd.DataFrame | None:
    """SKAT's list of aktiebaserede investeringsselskaber – the latest year's sheet only.

    Older sheets are history; a fund deregistered this year must not count as listed.
    """
    sheets = _sheets()
    if sheets is None:
        return None
    year = max(sheets, key=int)
    return _sheet(sheets[year], year)


def load_years() -> dict[int, set[str]] | None:
    """Every year's sheet as a set of ISINs, by calendar year: the sheet named for a year ("Kalenderåret 2026" on
    SKAT's cover sheet) lists the funds that are aktiebaserede for that income year. None without the file; a sheet
    that parses to no ISINs raises, as load() does."""
    sheets = _sheets()
    if sheets is None:
        return None
    return {int(y): set(_sheet(df, y)["isin"]) for y, df in sheets.items()}


def status(isin: str | None, year: int, years: dict[int, set[str]] | None) -> str:
    """A fund's place on the list for an income year: yes, no, no_sheet (the file has no sheet for that year, or
    there is no file) or no_isin. Never borrowed from another year."""
    if not isinstance(isin, str) or not isin.strip():
        return "no_isin"
    if years is None or year not in years:
        return "no_sheet"
    return "yes" if isin.strip().upper() in years[year] else "no"


def isins() -> set[str] | None:
    df = load()
    return None if df is None else set(df["isin"])


def flag(isin: str | None, isins: set[str] | None) -> str:
    if not isinstance(isin, str) or not isin or isins is None:
        return "?"
    return "yes" if isin.upper() in isins else "no"
