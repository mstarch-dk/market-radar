"""Your market views (subjective beliefs) with the radar's evidence."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..api_models import (
    AlignCompact,
    AlignRequest,
    ViewIn,
    ViewRow,
    ViewsPage,
)
from ..userstore import viewstore
from . import state
from .common import (
    ticker_symbol,
)

router = APIRouter()


# ---------------- your market views (subjective beliefs) ----------------

def _views_page() -> dict:
    from .. import market_views as mv

    with state.lock:
        closes = state.market().closes
    return {"disclaimer": mv.DISCLAIMER, "views": mv.with_evidence(None, closes), "templates": mv.templates(),
            "catalogue": mv.catalogue()}


def _view_body(body: ViewIn) -> dict:
    from .. import market_views as mv

    return mv.validate(body.model_dump())


@router.get("/api/views", response_model=ViewsPage)
def get_views() -> dict:
    """Your market views (active and archived) with the radar's evidence, the templates and the vocabulary."""
    return _views_page()


@router.post("/api/views", response_model=ViewsPage)
def add_view(body: ViewIn) -> dict:
    viewstore.save_view(_view_body(body))
    return _views_page()


@router.put("/api/views/{view_id}", response_model=ViewsPage)
def edit_view(view_id: int, body: ViewIn) -> dict:
    if not viewstore.get_view(view_id):
        raise HTTPException(404, f"No view {view_id}.")
    viewstore.save_view(_view_body(body), view_id)
    return _views_page()


@router.delete("/api/views/{view_id}", response_model=ViewRow)
def delete_view(view_id: int) -> dict:
    """Delete a view; the response is the deleted view, which /restore puts back (undo)."""
    v = viewstore.delete_view(view_id)
    if not v:
        raise HTTPException(404, f"No view {view_id}.")
    return v


@router.post("/api/views/restore", response_model=ViewsPage)
def restore_view(row: ViewRow) -> dict:
    if viewstore.get_view(row.id):
        raise HTTPException(409, "That view is already there.")
    from .. import market_views as mv

    viewstore.restore_view(mv.validate(row.model_dump()))
    return _views_page()


@router.post("/api/views/align", response_model=dict[str, AlignCompact])
def align_views(body: AlignRequest) -> dict:
    """How each of `tickers` lines up with your active views (for table columns); {} without views."""
    from .. import market_views as mv

    with state.lock:
        return mv.align_many([ticker_symbol(t) for t in body.tickers][:5000], body.store)
