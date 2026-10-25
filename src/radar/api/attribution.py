"""Attribution vs ACWI: why a selection of portfolios beat or lagged ACWI, and whether what's left looks like skill."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import attribution
from ..api_models import AttributionView
from ..portfolios import trades
from . import state
from .common import PortfolioQ, ScopeQ, TagQ, selection

router = APIRouter()
DATE = r"^\d{4}-\d{2}-\d{2}$"


@router.get("/api/attribution", response_model=AttributionView)
def get_attribution(portfolio: list[int] | None = PortfolioQ, tag: list[str] | None = TagQ,
                    scope: str | None = ScopeQ,
                    start: str | None = Query(None, pattern=DATE, description="From this day (default: the start)"),
                    end: str | None = Query(None, pattern=DATE, description="To this day (default: the last close)")
                    ) -> dict:
    """Brinson–Fachler by sector and by region on local returns, the currency effect, linked to months and the
    period, the reconciliation with Returns, and the factor regression, of the chosen portfolios (default: your real
    ones), computed now from the current prices. Too short a history is a view with nulls and notes."""
    trades.ensure_migrated()
    sel = selection(portfolio, tag, scope)
    with state.lock:
        try:
            m = state.market()
        except SystemExit as e:                  # Market.load: no price data yet
            raise HTTPException(503, str(e)) from None
        return attribution.cached(m, sel, scope, start, end)
