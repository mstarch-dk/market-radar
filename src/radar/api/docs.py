"""The notebook (briefs, research, journal) and the guide."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..api_models import (
    GuideChapter,
    GuideHit,
    GuideTree,
    NotebookDocument,
    NotebookListing,
)

router = APIRouter()


# ---------------- the notebook: briefs, research memos and the journal (notebook.py; read-only) ----------------

@router.get("/api/notebook", response_model=NotebookListing)
def notebook_listing() -> dict:
    from .. import notebook

    return notebook.listing()


@router.get("/api/notebook/{kind}/{name}", response_model=NotebookDocument)
def notebook_document(kind: str, name: str) -> dict:
    from .. import notebook

    try:
        return notebook.document(kind, name)
    except notebook.NotFound:
        raise HTTPException(404, f"No {kind} document {name}.") from None


# ---------------- the guide: Danish user guide and textbook (guide/, guide.py) ----------------

@router.get("/api/guide", response_model=GuideTree)
def guide_tree() -> dict:
    from .. import guide

    return guide.tree()


@router.get("/api/guide/search", response_model=list[GuideHit])
def guide_search(q: str = Query(..., min_length=2, max_length=80)) -> list[dict]:
    from .. import guide

    return guide.search(q)


@router.get("/api/guide/{book}/{slug}", response_model=GuideChapter)
def guide_chapter(book: str, slug: str) -> dict:
    from .. import guide

    try:
        return guide.chapter(book, slug)
    except guide.NotFound:
        raise HTTPException(404, f"No chapter {book}/{slug}.") from None
