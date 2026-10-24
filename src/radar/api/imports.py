"""Importing trades from broker exports: presets, preview, commit, undo."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .. import (
    trades,
    userstore,
)
from ..api_models import (
    ImportCommitResult,
    ImportPreview,
    ImportRecord,
    Preset,
)
from . import state
from .common import (
    MAX_IMPORT_BYTES,
)

router = APIRouter()


# ---------------- importing trades from broker exports ----------------




def _preview(body: bytes, filename: str, preset: str | None, mapping: str | None, symbols: str | None,
             portfolio: int | None) -> dict:
    import json

    from .. import importers

    if not body.strip():
        raise HTTPException(400, "The file is empty.")
    if len(body) > MAX_IMPORT_BYTES:
        raise HTTPException(413, "That file is too large for a transaction export.")
    try:
        with state.lock:
            return importers.preview(body, filename, state.market, state.has_prices, preset or None,
                                     json.loads(mapping) if mapping else None, portfolio,
                                     json.loads(symbols) if symbols else None)
    except (ValueError, KeyError, UnicodeDecodeError) as e:
        raise HTTPException(400, f"Couldn't read this file as a table of trades ({type(e).__name__}: {e}).") from e


@router.get("/api/portfolio/import/presets", response_model=list[Preset])
def import_presets() -> list[dict]:
    from .. import importers

    return [{"key": k, "label": p["label"], "verified": bool(p.get("verified"))} for k, p in importers.presets().items()]


@router.post("/api/portfolio/import/preview", response_model=ImportPreview)
async def import_preview(request: Request, filename: str = "", preset: str | None = None, mapping: str | None = None,
                         symbols: str | None = None, portfolio: int | None = None) -> dict:
    """What importing this file would do, without saving: format, column mapping, symbol matches, each row with
    its issues. `mapping` and `symbols` (JSON) override the detected columns and the suggested symbols; rows go
    into `portfolio` (default: the default portfolio) unless the file names one."""
    trades.ensure_migrated()
    return _preview(await request.body(), filename, preset, mapping, symbols, portfolio)


@router.post("/api/portfolio/import/commit", response_model=ImportCommitResult)
async def import_commit(request: Request, filename: str = "", preset: str | None = None, mapping: str | None = None,
                        symbols: str | None = None, portfolio: int | None = None, confirm: bool = False) -> dict:
    """Save the import exactly as the same preview shows it (re-run here, so nothing unchecked gets in)."""
    from .. import importers

    trades.ensure_migrated()
    pv = _preview(await request.body(), filename, preset, mapping, symbols, portfolio)
    try:
        return importers.commit(pv, filename, confirm)
    except ValueError as e:
        raise HTTPException(422, {"message": f"Not imported: {e}.", "issues": []}) from e


@router.get("/api/portfolio/imports", response_model=list[ImportRecord])
def list_imports() -> list[dict]:
    return userstore.imports()


@router.delete("/api/portfolio/imports/{import_id}", response_model=int)
def undo_import(import_id: int) -> int:
    """Remove every trade an import added (a backup of the database is taken first)."""
    if not any(i["id"] == import_id for i in userstore.imports()):
        raise HTTPException(404, f"No import {import_id}.")
    return userstore.undo_import(import_id)
