"""The Sector ETFs page: /sector-etfs' latest record with today's prices, positive list and rotation, and your marks
on a go-to you want replaced (userstore/sectorflags.py)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import sector_etf_view, sector_etfs
from ..api_models import SectorEtfReplaceIn, SectorEtfsView
from ..config import sector_etf_taxonomy
from ..userstore import sectorflags
from . import state

router = APIRouter()


def _view() -> dict:
    with state.lock:
        try:
            m = state.market()
        except SystemExit:                       # Market.load: no price data yet
            m = None
        return sector_etf_view.cached(m)


@router.get("/api/sector-etfs", response_model=SectorEtfsView)
def get_sector_etfs() -> dict:
    """Every sector of config/sector_etfs.yaml with the go-to UCITS ETF and its peers of the latest /sector-etfs
    run: returns in DKK and vs ACWI, TER (recorded and Yahoo's), size, the tax status, the ranking and your marks.
    Before the first run every sector comes back without ETFs (200, `as_of` null); without prices the returns are
    null."""
    return _view()


def _known(key: str) -> None:
    if key not in sector_etf_taxonomy().sectors:
        raise HTTPException(404, f"{key} is not a sector of config/sector_etfs.yaml.")


@router.put("/api/sector-etfs/{key}/replace", response_model=SectorEtfsView)
def mark_for_replacement(key: str, body: SectorEtfReplaceIn | None = None) -> dict:
    """Mark the sector's go-to for replacement (with an optional reason): it stays on the page, and the next
    /sector-etfs run picks another fund for this sector. 409 when the sector has no go-to yet."""
    _known(key)
    rec = sector_etfs.latest()
    s = next((s for s in (rec or {}).get("sectors", []) if s["key"] == key), None)
    if s is None:
        raise HTTPException(409, f"{key} has no go-to yet: run /sector-etfs first.")
    sectorflags.flag(key, s["pick"], body.reason if body else None)
    return _view()


@router.delete("/api/sector-etfs/{key}/flags/{isin}", response_model=SectorEtfsView)
def remove_flag(key: str, isin: str) -> dict:
    """Undo a mark for replacement, or allow a replaced fund as the sector's go-to again. 404 without such a mark."""
    _known(key)
    if not sectorflags.remove(key, isin.strip().upper()):
        raise HTTPException(404, f"No mark on {isin} for {key}.")
    return _view()
