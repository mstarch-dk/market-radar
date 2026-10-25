"""What several routers share: the portfolio selection, the dashboard and its readings, lookups that answer 404."""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException, Query

from .. import updater, userstore
from ..config import typed
from ..portfolios import trades
from ..reporting import dashboard


def ticker_symbol(s: str) -> str:
    return s.strip().upper()


def selection(portfolio: list[int] | None, tag: list[str] | None, scope: str | None) -> list[int] | None:
    """Which portfolios a request is about: chosen ids and/or tags, else a scope (real | virtual | all); None
    means the default, your real portfolios."""
    if portfolio or tag:
        return userstore.portfolio_ids(ids=portfolio, tags=tag)
    if scope:
        if scope not in userstore.SCOPES:
            raise HTTPException(422, f"scope must be one of {', '.join(userstore.SCOPES)}")
        return userstore.portfolio_ids(scope)
    return None


PortfolioQ = Query(None, description="Portfolio ids (repeatable); default: your real portfolios")
TagQ = Query(None, description="Portfolios carrying any of these tags (repeatable)")
ScopeQ = Query(None, description="real | virtual | all (when no portfolio or tag is given)")



def dashboard_or_503() -> dict:
    d = dashboard.load()
    if d is None:
        raise HTTPException(503, "No dashboard yet: run `uv run radar run` (or `radar report`) first.")
    return d


def reading(key: str) -> dict:
    """One dashboard section, with how old its data is: stale once older than the price limit in settings."""
    d = dashboard_or_503()
    age = (date.today() - date.fromisoformat(d["asof"])).days
    limit = typed().coverage.max_age["prices"]
    return {"asof": d["asof"], "generated": d["generated"], "age_days": age, "stale": age > limit,
            "outdated": outdated(d), **d[key]}


def outdated(d: dict) -> dict | None:
    """Whether the readings are behind the data on disk, and whether a rebuild is running. While the update job
    runs they are behind by design: it rebuilds them when it finishes."""
    if updater.JOB.state["status"] == "running":
        return None
    o = dashboard.outdated(d)
    return o | {"rebuilding": updater.REPORT_JOB.state["status"] == "running"} if o else None



def my_status(symbol: str) -> str | None:
    h = trades.holdings()
    st = h.loc[h["symbol"] == symbol, "status"]
    return st.iloc[0] if len(st) else None



MAX_IMPORT_BYTES = 5_000_000


def portfolio_or_404(pid: int) -> dict:
    return found(userstore.get_portfolio(pid), f"No portfolio {pid}.")


def found(row: dict | None, missing: str) -> dict:
    """The row, or 404 with `missing` when it isn't there."""
    if not row:
        raise HTTPException(404, missing)
    return row




def sentence(e: Exception) -> str:
    s = str(e)
    return s[:1].upper() + s[1:] + ("" if s.endswith(".") else ".")
