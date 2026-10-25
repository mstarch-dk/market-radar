"""The portfolio X-ray: what a selection of portfolios is exposed to and where its risk sits, against ACWI."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import xray
from ..api_models import XrayView
from ..portfolios import trades
from . import state
from .common import PortfolioQ, ScopeQ, TagQ, selection

router = APIRouter()


@router.get("/api/xray", response_model=XrayView)
def get_xray(portfolio: list[int] | None = PortfolioQ, tag: list[str] | None = TagQ,
             scope: str | None = ScopeQ) -> dict:
    """Exposure by sector, region and currency against ACWI, ex-ante and realised risk with each position's share,
    concentration, the stress windows and the factor tilts of the chosen portfolios (default: your real ones),
    computed now from the current prices. An empty selection is a view with empty tables and a note."""
    trades.ensure_migrated()
    sel = selection(portfolio, tag, scope)
    with state.lock:
        try:
            m = state.market()
        except SystemExit as e:                  # Market.load: no price data yet
            raise HTTPException(503, str(e)) from None
        return xray.cached(m, sel, scope)
