"""Backups of everything that can't be downloaded again: radar.db, your folders (notes, briefs, research,
journal, exports, broker files) and the history the radar has built up. Never the market-data cache.

One zip per backup in `backups/` in the data folder, each with a `backup.json`: when and why, the app version, the
data and database format, row counts per table, and a SHA-256 per file, so a restore can prove the zip is whole.
A copy also goes to a second folder if one is set (`mirror`: a cloud-sync folder or a USB disk; a zip is safe to
sync, a database in use is not).

Taken: before a new app version first opens the data (kept 90 days), once a day (7 daily, 5 weekly, 12 monthly
kept), and on demand (the newest 20 kept). userstore's quick copies of radar.db before imports and undos stay
as they are (`radar-*.db`).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path

from . import home, paths

PREFIX = "market-radar-"
KINDS = ("manual", "daily", "upgrade", "restore")
KEEP_MANUAL, KEEP_DAILY, KEEP_WEEKLY, KEEP_MONTHLY, KEEP_UPGRADE_DAYS = 20, 7, 5, 12, 90


class BackupError(RuntimeError):
    pass


def _home() -> paths.Locations:
    """Backups are of a data folder (`radar setup`), not of the old layout inside the install folder."""
    loc = paths.locations()
    if not (loc.home / home.MANIFEST).exists():
        raise BackupError("backups need a data folder: run `radar setup` first")
    return loc


def is_home() -> bool:
    try:
        _home()
        return True
    except (BackupError, paths.NotSetUp):
        return False


def folder() -> Path:
    return paths.locations().userdata / "backups"


def mirror() -> Path | None:
    m = home.read_manifest(paths.locations().home) or {}
    return Path(m["backup_mirror"]) if m.get("backup_mirror") else None


def set_mirror(path: Path | None) -> Path | None:
    loc = _home()
    m = home.read_manifest(loc.home)
    if path:
        path = Path(path).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        if path.resolve() == folder().resolve() or loc.home.resolve() in path.resolve().parents:
            raise BackupError("the second backup folder must be outside the data folder")
    m["backup_mirror"] = str(path) if path else None
    home.write_manifest(loc.home, home.add_log(m, "backup_mirror", path=m["backup_mirror"]))
    return path


def _sources() -> list[tuple[str, Path]]:
    """(name in the zip, file) for every file that is backed up; the database is added separately."""
    loc = paths.locations()
    out = []
    for f in home.PERSONAL:
        out += [(f"{f}/{p.relative_to(loc.home / f).as_posix()}", p) for p in home.files_under(loc.home / f)]
    out += [(f"imports/{p.relative_to(loc.imports).as_posix()}", p)
            for p in home.files_under(loc.imports, home.APP_FILES["imports"])]
    for e in paths.REGISTRY["history"]:
        src = loc.history / e.rstrip("/")
        if e.endswith("/"):
            out += [(f"history/{e}{p.relative_to(src).as_posix()}", p) for p in home.files_under(src)]
        elif src.exists():
            out.append((f"history/{e}", src))
    return out


def create(reason: str = "manual", kind: str = "manual") -> Path:
    """Write one backup zip (and its mirror copy). Returns the zip."""
    if kind not in KINDS:
        raise ValueError(kind)
    loc = _home()
    d = folder()
    d.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() or c in "-." else "-" for c in reason)[:40]
    stem = f"{PREFIX}{datetime.now():%Y%m%d-%H%M%S}-{kind}-{slug}"
    out, n = d / f"{stem}.zip", 1
    while out.exists():                           # two in the same second
        n += 1
        out = d / f"{stem}-{n}.zip"
    files, meta = [], {"created": datetime.now().isoformat(timespec="seconds"), "kind": kind, "reason": reason,
                       "app_version": home.app_version(), "home_format": home.HOME_FORMAT}
    tmp = out.with_name(out.name + ".tmp")
    with tempfile.TemporaryDirectory() as t, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        db = loc.userdata / home.DB_NAME
        if db.exists():
            copy = Path(t) / home.DB_NAME
            home.copy_db(db, copy)
            meta["db_version"] = home.db_version(copy)
            meta["tables"] = home.table_counts(copy)
            files.append(_add(z, home.DB_NAME, copy))
        for name, p in _sources():
            files.append(_add(z, name, p))
        meta["files"] = files
        z.writestr("backup.json", json.dumps(meta, indent=1, ensure_ascii=False))
    tmp.replace(out)
    _mirror_copy(out)
    prune()
    return out


def _add(z: zipfile.ZipFile, name: str, p: Path) -> dict:
    z.write(p, name)
    return {"path": name, "size": p.stat().st_size, "sha256": home.file_sha256(p)}


def _mirror_copy(f: Path) -> None:
    m = mirror()
    if not m:
        return
    try:
        m.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, m / f.name)
    except OSError as e:                          # a disconnected USB disk must not stop the backup itself
        from . import ops

        ops.event("warn", "job", f"backup mirror {m}: {type(e).__name__}: {e}", source="backup")


def _when(f: Path) -> datetime | None:
    try:
        return datetime.strptime(f.name[len(PREFIX):len(PREFIX) + 15], "%Y%m%d-%H%M%S")
    except ValueError:
        return None


def _kind(f: Path) -> str:
    k = f.name[len(PREFIX) + 16:].split("-", 1)[0]
    return k if k in KINDS else "manual"


def listing(where: Path | None = None) -> list[dict]:
    d = where or folder()
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob(f"{PREFIX}*.zip"), reverse=True):
        when = _when(f)
        if when:
            out.append({"name": f.name, "path": str(f), "created": when.isoformat(timespec="seconds"),
                        "kind": _kind(f), "size": f.stat().st_size})
    return out


def prune(today: date | None = None) -> list[str]:
    """Thin out old backups in the data folder (the mirror is left to its owner). Returns the names removed."""
    today = today or date.today()
    zips = [(f, _when(f), _kind(f)) for f in folder().glob(f"{PREFIX}*.zip") if _when(f)]
    keep: set[Path] = set()
    for kind in ("manual", "restore"):
        keep |= {f for f, _, _ in sorted((x for x in zips if x[2] == kind), key=lambda x: x[1], reverse=True)[:KEEP_MANUAL]}
    keep |= {f for f, w, k in zips if k == "upgrade" and w.date() >= today - timedelta(days=KEEP_UPGRADE_DAYS)}
    daily = sorted((x for x in zips if x[2] == "daily"), key=lambda x: x[1], reverse=True)
    for key, n in ((lambda w: w.date(), KEEP_DAILY), (lambda w: w.isocalendar()[:2], KEEP_WEEKLY),
                   (lambda w: (w.year, w.month), KEEP_MONTHLY)):
        seen = []
        for f, w, _ in daily:                     # the newest backup of each day / week / month
            if key(w) not in seen:
                seen.append(key(w))
                if len(seen) <= n:
                    keep.add(f)
    gone = [f for f, _, _ in zips if f not in keep]
    for f in gone:
        f.unlink()
    return [f.name for f in gone]


def daily() -> Path | None:
    """Today's backup, unless there is one already."""
    if not is_home():
        return None
    today = date.today()
    if any(_when(f) and _when(f).date() == today and _kind(f) == "daily" for f in folder().glob(f"{PREFIX}*.zip")):
        return None
    return create("daily", kind="daily")


def before_upgrade() -> Path | None:
    """A backup the first time a new app version opens the data, before anything is changed."""
    if not is_home():
        return None
    m = home.read_manifest(paths.locations().home)
    if m.get("last_app_version") == home.app_version():
        return None
    return create(f"before-v{home.app_version()}", kind="upgrade")


# ---------------- restore ----------------

def verify(zf: Path) -> dict:
    """Read a backup's backup.json and check every file against it. Raises BackupError if it can't be restored."""
    try:
        with zipfile.ZipFile(zf) as z:
            meta = json.loads(z.read("backup.json"))
            for f in meta["files"]:
                h = hashlib.sha256(z.read(f["path"])).hexdigest()
                if h != f["sha256"]:
                    raise BackupError(f"{f['path']} in {zf.name} is damaged (checksum differs)")
    except (KeyError, zipfile.BadZipFile, ValueError) as e:
        raise BackupError(f"{zf.name} is not a Market Radar backup ({type(e).__name__}: {e})") from e
    if meta.get("home_format", 0) > home.HOME_FORMAT or (meta.get("db_version") or 0) > home.schema_known():
        raise BackupError(f"{zf.name} was made by Market Radar {meta.get('app_version')}, newer than this "
                          f"{home.app_version()}: restore it with that version or newer")
    return meta


def restore(zf: Path) -> dict:
    """Put a backup back: verify it, back up what is there now, unpack beside the data and swap it in. Only the
    parts a backup holds are replaced (radar.db, your folders, history); the cache is left alone."""
    zf = Path(zf)
    meta = verify(zf)
    loc = _home()
    before = create(f"before-restore-of-{zf.stem[len(PREFIX):len(PREFIX) + 15]}", kind="restore")
    staging, old = loc.home / ".restore-staging", loc.home / ".restore-old"
    for d in (staging, old):
        shutil.rmtree(d, ignore_errors=True)
    with zipfile.ZipFile(zf) as z:
        for f in meta["files"]:
            z.extract(f["path"], staging)
    db = staging / home.DB_NAME
    if db.exists():
        with closing(sqlite3.connect(db)) as con:
            ok = con.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != "ok":
            shutil.rmtree(staging, ignore_errors=True)
            raise BackupError(f"radar.db in {zf.name} failed its integrity check: {ok}")
    old.mkdir()
    parts = [home.DB_NAME, *home.PERSONAL, "imports", "history"]
    try:
        for p in parts:                           # same disk: renames, so each part swaps whole
            if (loc.home / p).exists():
                (loc.home / p).rename(old / p)
            if (staging / p).exists():
                (staging / p).rename(loc.home / p)
            elif p != home.DB_NAME:
                (loc.home / p).mkdir()
    except BaseException:
        for p in parts:                           # put back what was there
            if (old / p).exists():
                if (loc.home / p).exists():
                    shutil.rmtree(loc.home / p) if (loc.home / p).is_dir() else (loc.home / p).unlink()
                (old / p).rename(loc.home / p)
        raise
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(old, ignore_errors=True)        # it is in `before`
    m = home.read_manifest(loc.home)
    if m:
        home.write_manifest(loc.home, home.add_log(m, "restored", backup=zf.name, saved_first=before.name))
    return {"restored": zf.name, "created": meta["created"], "files": len(meta["files"]),
            "tables": meta.get("tables", {}), "saved_first": before.name}
