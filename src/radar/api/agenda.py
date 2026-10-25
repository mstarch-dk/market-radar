"""The calendar: what is coming for the names you hold and watch, and which of it to look at first."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import agenda
from ..api_models import AgendaView
from ..portfolios import trades
from . import state
from .common import PortfolioQ, ScopeQ, TagQ, dashboard_or_503, selection

router = APIRouter()


@router.get("/api/calendar", response_model=AgendaView)
def get_calendar(portfolio: list[int] | None = PortfolioQ, tag: list[str] | None = TagQ,
                 scope: str | None = ScopeQ,
                 days: int | None = Query(None, ge=1, le=366, description="Window in days; default calendar.days")
                 ) -> dict:
    """Earnings and ex-dividend dates of the held and watched stocks of the chosen portfolios (default: your real
    ones), your open journal reviews and the proposals' time stops, each with the reasons it is highlighted and a
    level, counted from the last close. Stocks with no known date are listed; funds are counted."""
    trades.ensure_migrated()
    sel = selection(portfolio, tag, scope)
    d = dashboard_or_503()
    with state.lock:
        try:
            m = state.market()
        except SystemExit as e:                  # Market.load: no price data yet
            raise HTTPException(503, str(e)) from None
        return agenda.cached(m, d, sel, scope, days)
