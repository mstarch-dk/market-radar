"""Choosing and looking after the data folder: setup, the Data page (folders, backups, mirror, restore, export) and the update check."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from .. import paths
from ..api_models import (
    BackupRow,
    DataHome,
    HomeStatus,
    LegacyFound,
    MirrorIn,
    OpenIn,
    RestoreIn,
    RestoreResult,
    SetupIn,
    SetupResult,
    UpdateCheck,
    UpdateCheckIn,
)
from ..datahome import home
from . import state

router = APIRouter()


@router.get("/api/setup", response_model=HomeStatus)
def setup_status() -> dict:
    """Where the data is, whether it can be used, and (before setup) the old folders found with data in them."""
    return home.status()


@router.get("/api/setup/scan", response_model=LegacyFound)
def setup_scan(path: str = Query(..., min_length=1, max_length=1000)) -> dict:
    """What an old Market Radar folder the user points to holds (404 if nothing of theirs)."""
    found = home.legacy_summary(Path(path).expanduser())
    if found is None:
        raise HTTPException(404, f"No Market Radar data in {path}.")
    return found


@router.post("/api/setup", response_model=SetupResult)
def setup(body: SetupIn) -> dict:
    """Choose the data folder: copy an old version's data into it, start empty, or use one that exists. Refused
    once a folder is in use (409)."""
    if (state.gate or home.gate())[0] not in ("unset", "missing"):
        raise HTTPException(409, "A data folder is already in use.")
    target = Path(body.home).expanduser() if body.home else None
    files: dict[str, int] = {}
    try:
        if body.action == "migrate":
            if not body.source:
                raise HTTPException(422, "Choose the old folder to copy from.")
            files = home.migrate(Path(body.source), target, copy_cache=body.copy_cache)["files"]
        elif body.action == "create":
            home.create(target)
        else:
            if not target:
                raise HTTPException(422, "Choose the data folder to use.")
            home.use(target)
    except home.HomeError as e:
        raise HTTPException(422, str(e)) from e
    state.open_home()
    return {"status": home.status(), "files": files}


def _folders() -> list[dict]:
    from ..datahome import home as h

    loc = paths.locations()
    shown = ("data", "notes", "research", "journal", "briefs", "exports", "backups", "history", "cache")
    rows = {k: (k, label, d, tier) for k, label, d, tier in paths.folders(loc)}
    out = []
    for key, label, d, tier in (rows[k] for k in shown):
        fs = h.files_under(d) if key != "data" else ([loc.userdata / h.DB_NAME] if (loc.userdata / h.DB_NAME).exists() else [])
        out.append({"key": key, "label": label, "path": str(d), "tier": tier, "files": len(fs),
                    "mb": round(sum(f.stat().st_size for f in fs) / 1e6, 1)})
    return out


@router.get("/api/data-home", response_model=DataHome)
def data_home() -> dict:
    """Where your data, the history and the market data are; the backups and the second backup folder."""
    from ..datahome import backup

    m = backup.mirror() if backup.is_home() else None
    return {"status": home.status(), "folders": _folders(), "backups": backup.listing() if backup.is_home() else [],
            "mirror": str(m) if m else None, "mirror_backups": backup.listing(m) if m else []}


@router.post("/api/data-home/backup", response_model=BackupRow)
def data_home_backup() -> dict:
    from ..datahome import backup

    try:
        f = backup.create("manual")
    except backup.BackupError as e:
        raise HTTPException(409, str(e)) from e
    return next(r for r in backup.listing() if r["name"] == f.name)


@router.put("/api/data-home/mirror", response_model=DataHome)
def data_home_mirror(body: MirrorIn) -> dict:
    """Set (or clear) the second folder every backup is copied to."""
    from ..datahome import backup

    try:
        backup.set_mirror(Path(body.path) if body.path else None)
    except (backup.BackupError, OSError) as e:
        raise HTTPException(422, str(e)) from e
    return data_home()


@router.post("/api/data-home/restore", response_model=RestoreResult)
def data_home_restore(body: RestoreIn) -> dict:
    """Put one of the listed backups back (what is there now is backed up first)."""
    from ..datahome import backup

    m = backup.mirror()
    known = {r["name"]: r["path"] for r in [*backup.listing(), *(backup.listing(m) if m else [])]}
    if body.name not in known:
        raise HTTPException(404, f"No backup called {body.name}.")
    try:
        res = backup.restore(Path(known[body.name]))
    except backup.BackupError as e:
        raise HTTPException(422, str(e)) from e
    state.drop_prices()
    return res


@router.post("/api/data-home/open", response_model=bool)
def data_home_open(body: OpenIn) -> bool:
    """Show one of the folders in Explorer / Finder / the file manager (the app only runs on your own computer)."""
    import os
    import subprocess
    import sys

    path = next((f["path"] for f in _folders() if f["key"] == body.key), None)
    if path is None:
        raise HTTPException(404, f"No folder {body.key}.")
    Path(path).mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)                                    # noqa: S606 (a folder the app itself chose)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])
    return True


@router.get("/api/updates", response_model=UpdateCheck)
def get_updates() -> dict:
    """Is a newer Market Radar out? Asks GitHub at most once a day, and only when switched on."""
    from .. import updates

    return updates.status()


@router.put("/api/updates", response_model=UpdateCheck)
def put_updates(body: UpdateCheckIn) -> dict:
    from .. import updates

    updates.set_enabled(body.enabled)
    return updates.status()


@router.get("/api/data-home/export", include_in_schema=False)
def data_home_export() -> Response:
    """Everything of yours in open formats, as a zip download (export.py)."""
    from ..datahome import export

    name = f"market-radar-export-{date.today().isoformat()}.zip"
    return Response(export.build(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
