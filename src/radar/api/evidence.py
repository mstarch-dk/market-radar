"""The Evidence page: the studies of the scores and the forward record, read from the reports and the portfolios."""
from __future__ import annotations

from fastapi import APIRouter

from .. import evidence
from ..api_models import EvidenceView
from ..portfolios import trades
from . import state

router = APIRouter()


@router.get("/api/evidence", response_model=EvidenceView)
def get_evidence() -> dict:
    """A card per score study (momentum, quality, value, K+V) and the long-run study, the rule studies' headers, and
    the forward scoreboard (A/B test, paper trail, frozen proposals vs ACWI). Missing reports are cards that say so;
    without prices the scoreboard is null and the study cards still come back."""
    trades.ensure_migrated()
    with state.lock:
        try:
            m = state.market()
        except SystemExit:                       # Market.load: no price data yet
            m = None
        return evidence.cached(m)
