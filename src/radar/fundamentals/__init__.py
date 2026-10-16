"""Company fundamentals from financial statements: SEC EDGAR for US companies (with filing dates, so a past day can
be scored on what was public then) and Yahoo for every tracked stock. Both land in one long fact format
(store.py); the period arithmetic (TTM, balances, fiscal years) is done there, for now or for any past day.

- items.py: the canonical items and their names in each source
- edgar.py / yahoo.py: fetching, parsing and the update steps
- schedule.py: which tickers are due on a run (statements change quarterly; the backfill is spread over runs)
"""
from __future__ import annotations

import pandas as pd

from . import store

# the items a ticker's EDGAR facts must hold for the scores to use EDGAR rather than Yahoo
CORE = ("revenue", "operating_income", "cfo", "capex", "total_assets")


def facts(ticker: str, edgar: pd.DataFrame | None = None, yahoo: pd.DataFrame | None = None) -> pd.DataFrame:
    """One ticker's facts from one source: EDGAR when it has the core items, else Yahoo (never mixed)."""
    e = (store.load_edgar() if edgar is None else edgar)
    e = e[e["ticker"] == ticker]
    if not e.empty and set(CORE) <= set(e["item"]):
        return e
    y = (store.load_yahoo() if yahoo is None else yahoo)
    return y[y["ticker"] == ticker]
