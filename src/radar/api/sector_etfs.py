"""The Sector ETFs page: /sector-etfs' latest record with today's prices, positive list and rotation."""
from __future__ import annotations

from fastapi import APIRouter

from .. import sector_etf_view
from ..api_models import SectorEtfsView
from . import state

router = APIRouter()


@router.get("/api/sector-etfs", response_model=SectorEtfsView)
def get_sector_etfs() -> dict:
    """Every sector of config/sector_etfs.yaml with the go-to UCITS ETF and its peers of the latest /sector-etfs
    run: returns in DKK and vs ACWI, TER (recorded and Yahoo's), size, the tax status and the ranking. Before the
    first run every sector comes back without ETFs (200, `as_of` null); without prices the returns are null."""
    with state.lock:
        try:
            m = state.market()
        except SystemExit:                       # Market.load: no price data yet
            m = None
        return sector_etf_view.cached(m)
