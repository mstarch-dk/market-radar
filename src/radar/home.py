"""The data home: setting it up, moving old data into it, and guarding it against an older app.

- `status()`: is a home chosen and usable? (`unset`, `missing`, `newer`, `ok`), with the folders found that hold
  data from a version before the home existed (`find_legacy`).
- `create(home)`: a new, empty home. `migrate(src, home)`: copy an old install folder's data into a new home,
  verify the copy (SQLite integrity and row counts, a SHA-256 per file) and leave the old folder untouched, with a
  MOVED.txt that says where the data went. Nothing is ever moved or deleted.
- `market-radar.json` in the home records its format, the app versions that used it and what was done to it.
  A home (or a radar.db) from a newer app opens read-only (`read_only()`), so an old zip opened by mistake can't
  write over data it doesn't understand.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from . import paths
from .config import ROOT, write_text

# Changes to the data folder's layout (a folder renamed, a file moved between tiers): one function per step, taking
# the home Path; step i turns format i into i + 1. Append only, never edit a released step, never delete user data
# (copy or rename). They run after the backup a new version takes before its first use (`upgrade`).
HOME_MIGRATIONS: list = []
HOME_FORMAT = 1 + len(HOME_MIGRATIONS)
MANIFEST = "market-radar.json"
DB_NAME = "radar.db"
PERSONAL = ("notes", "briefs", "research", "journal", "exports")          # folders copied as they are
APP_FILES = {"imports": {"README.md", "positivliste.xlsx"}}                # shipped with the app, not yours
SYNC_MARKERS = ("onedrive", "icloud", "mobile documents", "dropbox", "google drive", "googledrive", "box sync")

README = """Market Radar: dine data
=======================

Denne mappe er dine egne data. Den ligger uden for programmappen, så du kan
skifte til en ny version af Market Radar uden at miste noget.

  radar.db        dine porteføljer, handler, markedssyn, watchlist og valg
  notes/          dine noter og investorprofil (til Claude-skills)
  briefs/         markedsbriefs
  research/       research-notater og sammenligninger
  journal/        beslutningsjournal
  exports/        eksporter og sammenligninger
  imports/        filer fra din bank/mægler
  history/        historik radaren har samlet over tid (kan ikke hentes igen)
  backups/        automatiske sikkerhedskopier
  market-radar.json   hvilken version der sidst brugte mappen

Markedsdata (kurser m.m.) ligger i en cache-mappe et andet sted; den kan
slettes og hentes igen. Kør "uv run radar paths" for at se hvor.

Tag backup af hele denne mappe. Læg den ikke direkte i OneDrive, iCloud eller
Dropbox: en database der synkroniseres mens den er i brug kan gå i stykker.
Læg i stedet backups der (se guiden: Dine data, backup og opdatering).
"""


def app_version() -> str:
    """From pyproject.toml beside the code (a release zip and a checkout both have it, and it can't be stale like an
    installed package's metadata), else the installed metadata."""
    import tomllib

    try:
        return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    except (OSError, KeyError, ValueError):
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("market-radar")
        except PackageNotFoundError:
            return "0.0.0"


def version_tuple(v: str) -> tuple:
    """A version as numbers, so versions compare right: "0.2.10" is (0, 2, 10); a part that isn't a number is 0."""
    return tuple(int(p) if p.isdigit() else 0 for p in v.split("."))


def schema_known() -> int:
    from . import userstore

    return len(userstore.MIGRATIONS)


# ---------------- manifest ----------------

def read_manifest(home: Path) -> dict | None:
    f = Path(home) / MANIFEST
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def write_manifest(home: Path, m: dict) -> None:
    """Write the data home's market-radar.json."""
    f = Path(home) / MANIFEST
    write_text(f, json.dumps(m, indent=1, ensure_ascii=False))


def add_log(m: dict, event: str, **kw) -> dict:
    """Append an event (with the time and this app version) to a manifest's log; returns the manifest."""
    m.setdefault("log", []).append({"at": datetime.now().isoformat(timespec="seconds"),
                                    "app_version": app_version(), "event": event} | kw)
    return m


def touch(home: Path) -> dict:
    """Record that this app version opened the home (once per version). Returns the manifest."""
    m = read_manifest(home)
    if m is None:
        return {}
    v = app_version()
    if m.get("last_app_version") != v and not _newer(m):
        m["last_app_version"] = v
        write_manifest(home, add_log(m, "opened"))
    return m


def upgrade(home: Path) -> list[int]:
    """Bring an older data folder's layout up to HOME_FORMAT, one recorded step at a time. Returns the steps run."""
    m = read_manifest(home)
    done = []
    while m and m.get("home_format", 1) < HOME_FORMAT:
        step = m.get("home_format", 1)
        HOME_MIGRATIONS[step - 1](Path(home))
        m["home_format"] = step + 1
        write_manifest(home, add_log(m, "upgraded", to_format=step + 1))
        done.append(step + 1)
    return done


def _newer(m: dict | None) -> bool:
    return bool(m) and (m.get("home_format", 0) > HOME_FORMAT)


# ---------------- status ----------------

def db_version(db: Path) -> int | None:
    if not db.exists():
        return None
    with closing(sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)) as con:
        return con.execute("PRAGMA user_version").fetchone()[0]


def read_only() -> str | None:
    """Why this app must not write to the current data (a newer app wrote it), or None."""
    try:
        loc = paths.locations()
    except paths.NotSetUp:
        return None
    m = read_manifest(loc.home)
    if _newer(m):
        return (f"Your data was last used by Market Radar {m.get('last_app_version', '?')} (data format "
                f"{m['home_format']}); this is {app_version()}. Start the newer version.")
    dv = db_version(loc.userdata / DB_NAME)
    if dv is not None and dv > schema_known():
        return (f"radar.db was upgraded by a newer Market Radar (schema {dv}; this version knows {schema_known()}). "
                "Start the newer version.")
    return None


def gate() -> tuple[str, str | None]:
    """The cheap part of `status()`, for every API request: (state, why read-only)."""
    src = paths.source()
    if src == "unset":
        return "unset", None
    loc = paths.locations()
    if src in ("pointer", "env", "portable", "option") and not (loc.home / MANIFEST).exists():
        return "missing", None                    # chosen once, now gone (another drive, renamed, deleted)
    ro = read_only()
    return ("newer" if ro else "ok"), ro


def status() -> dict:
    """What the app should do at start: run, ask where the data is, or refuse to write."""
    state, ro = gate()
    out = {"state": state, "source": paths.source(), "app_version": app_version(),
           "pointer": str(paths.pointer_file()), "default_home": str(paths.default_home()),
           "default_cache": str(paths.default_cache()), "home": None, "cache": None, "read_only": ro,
           "warning": None, "found": []}
    if state != "unset":
        loc = paths.locations()
        out |= {"home": str(loc.home), "cache": str(loc.cache), "warning": sync_warning(loc.home)}
    if state in ("unset", "missing"):
        out["found"] = find_legacy()
    return out


def sync_warning(home: Path) -> str | None:
    s = str(home).lower()
    hit = next((m for m in SYNC_MARKERS if m in s), None)
    if hit:
        return ("The data folder is inside a cloud-sync folder. A database synced while it is in use can be "
                "damaged: move it out, and send the backups to the cloud folder instead.")
    if str(home).startswith("\\\\"):
        return "The data folder is on a network drive; SQLite needs a local disk. Move it to this computer."
    return None


# ---------------- finding data from before the home ----------------

def files_under(d: Path, skip: set[str] = frozenset()) -> list[Path]:
    """Every file under `d`, leaving out the top-level folders in `skip` and half-written `.tmp` files."""
    if not d.is_dir():
        return []
    return [p for p in d.rglob("*") if p.is_file() and p.relative_to(d).parts[0] not in skip
            and not p.name.endswith(".tmp")]


def legacy_summary(root: Path) -> dict | None:
    """What an install folder from before the data home holds, or None when it holds nothing of yours."""
    root = Path(root)
    loc = paths.Locations.legacy(root)
    db = loc.userdata / DB_NAME
    personal = {f: len(files_under(root / f)) for f in PERSONAL}
    imports = len(files_under(loc.imports, APP_FILES["imports"]))
    history = sum(len(files_under(loc.history / e)) if e.endswith("/") else int((loc.history / e).exists())
                  for e in paths.REGISTRY["history"])
    counts = {}
    if db.exists():
        try:
            with closing(sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)) as con:
                tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                          for t in ("portfolios", "transactions", "views", "watchlist") if t in tables}
        except sqlite3.Error as e:
            counts = {"error": f"{type(e).__name__}: {e}"}
    if not db.exists() and not any(personal.values()) and not imports:
        return None
    newest = max((p.stat().st_mtime for p in [db] + [x for f in PERSONAL for x in files_under(root / f)] if p.exists()),
                 default=None)
    return {"path": str(root), "is_this_install": root.resolve() == ROOT.resolve(), "database": db.exists(),
            "counts": counts, "personal": personal, "imports": imports, "history_files": history,
            "cache_mb": round(sum(p.stat().st_size for p in files_under(loc.cache)) / 1e6, 1) if loc.cache.is_dir() else 0,
            "newest": datetime.fromtimestamp(newest).isoformat(timespec="minutes") if newest else None,
            "moved": (root / "MOVED.txt").exists()}


def find_legacy(root: Path = ROOT) -> list[dict]:
    """This install folder and its siblings (a new version unzipped next to the old one), newest data first.
    Only the parent folder is looked in: a wider search would trip macOS's privacy prompts."""
    cands = [root]
    try:
        cands += sorted(p for p in root.parent.iterdir() if p.is_dir() and p != root and _looks_like_install(p))
    except OSError:
        pass
    found = [s for s in (legacy_summary(c) for c in cands) if s]
    return sorted(found, key=lambda s: (s["moved"], -(datetime.fromisoformat(s["newest"]).timestamp()
                                                      if s["newest"] else 0)))


def _looks_like_install(p: Path) -> bool:
    return (p / "pyproject.toml").exists() and (p / "src" / "radar").is_dir()


# ---------------- creating and migrating ----------------

class HomeError(RuntimeError):
    pass


def file_sha256(p: Path) -> str:
    """The file's SHA-256 (hex), read in 1 MB blocks."""
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix == ".db":
        copy_db(src, dst)
        return
    shutil.copy2(src, dst)
    if file_sha256(src) != file_sha256(dst):
        raise HomeError(f"copy of {src} differs from the original")


def copy_db(src: Path, dst: Path) -> None:
    """SQLite's backup API: a consistent copy even while the old app has the database open."""
    with closing(sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)) as s, closing(sqlite3.connect(dst)) as d:
        s.backup(d)


def _copy_tree(src: Path, dst: Path, skip: set[str] = frozenset()) -> int:
    n = 0
    for f in files_under(src, skip):
        _copy_file(f, dst / f.relative_to(src))
        n += 1
    return n


def table_counts(db: Path) -> dict[str, int]:
    with closing(sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)) as con:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                            "AND name NOT LIKE 'sqlite_%'")]
        return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}


def _check_target(home: Path) -> None:
    if (home / MANIFEST).exists() or (home / DB_NAME).exists():
        raise HomeError(f"{home} already holds Market Radar data: choose it as your folder, or pick another one")
    if home.exists() and any(home.iterdir()):
        raise HomeError(f"{home} is not empty: choose an empty or new folder")


def _init(home: Path, m: dict) -> None:
    home.mkdir(parents=True, exist_ok=True)
    for f in (*PERSONAL, "imports", "history", "backups"):
        (home / f).mkdir(exist_ok=True)
    (home / "README.txt").write_text(README, encoding="utf-8")
    write_manifest(home, m)


def _manifest(event: str, **kw) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    return add_log({"home_format": HOME_FORMAT, "created": now, "created_by": app_version(),
                 "last_app_version": app_version()}, event, **kw)


def create(home: Path | None = None, cache: Path | None = None, pointer: bool = True) -> paths.Locations:
    """A new, empty data home (a first start with nothing to move). Remembered on this computer."""
    home = Path(home).expanduser() if home else paths.default_home()
    pointer = pointer and paths.remembers()
    _check_target(home)
    _init(home, _manifest("created"))
    loc = paths.Locations.at(home, cache)
    if pointer:
        paths.write_pointer(home, cache)
    paths.configure(loc, source="pointer" if pointer else "option")
    return loc


def use(home: Path, cache: Path | None = None, pointer: bool = True) -> paths.Locations:
    """Point this computer at an existing data home (moved, or set up by another version)."""
    home = Path(home).expanduser()
    if not (home / MANIFEST).exists():
        raise HomeError(f"{home} is not a Market Radar data folder (no {MANIFEST} in it)")
    pointer = pointer and paths.remembers()
    loc = paths.Locations.at(home, cache)
    if pointer:
        paths.write_pointer(home, cache)
    paths.configure(loc, source="pointer" if pointer else "option")
    touch(home)
    return loc


def migrate(src_root: Path, home: Path | None = None, cache: Path | None = None, copy_cache: bool = True,
            pointer: bool = True, progress=lambda msg: None) -> dict:
    """Copy an old install folder's data into a new home and verify it. The old folder is left as it was, plus a
    MOVED.txt. Returns what was copied."""
    src_root = Path(src_root).expanduser().resolve()
    summary = legacy_summary(src_root)
    if summary is None:
        raise HomeError(f"no Market Radar data found in {src_root}")
    home = Path(home).expanduser() if home else paths.default_home()
    pointer = pointer and paths.remembers()
    _check_target(home)
    old, new = paths.Locations.legacy(src_root), paths.Locations.at(home, cache)
    staging = home.with_name(home.name + ".incoming")       # built aside, renamed into place when verified
    if staging.exists():
        shutil.rmtree(staging)
    stage = paths.Locations.at(staging, new.cache)
    report = {"from": str(src_root), "home": str(home), "cache": str(new.cache), "files": {}}
    try:
        progress("Copying your folders")
        for f in PERSONAL:
            report["files"][f] = _copy_tree(src_root / f, staging / f)
        report["files"]["imports"] = _copy_tree(old.imports, stage.imports, APP_FILES["imports"])
        db = old.userdata / DB_NAME
        if db.exists():
            progress("Copying radar.db")
            copy_db(db, stage.userdata / DB_NAME)
            before, after = table_counts(db), table_counts(stage.userdata / DB_NAME)
            if before != after:
                raise HomeError(f"radar.db copy differs: {before} vs {after}")
            with closing(sqlite3.connect(stage.userdata / DB_NAME)) as con:
                ok = con.execute("PRAGMA integrity_check").fetchone()[0]
            if ok != "ok":
                raise HomeError(f"radar.db copy failed its integrity check: {ok}")
            report["tables"] = after
            report["files"]["backups"] = _copy_tree(old.userdata / "backups", stage.userdata / "backups")
        progress("Copying history")
        report["files"]["history"] = _copy_entries(old.history, stage.history, paths.REGISTRY["history"])
        if copy_cache:
            progress("Copying market data")
            report["files"]["cache"] = _copy_entries(old.cache, new.cache, paths.REGISTRY["cache"], skip_existing=True)
            report["files"]["reports"] = _copy_tree(old.reports, new.reports)
        _init(staging, _manifest("migrated", source=str(src_root), files=report["files"]))
        staging.rename(home) if not home.exists() else _move_into(staging, home)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    (src_root / "MOVED.txt").write_text(_moved_note(home, new.cache), encoding="utf-8")
    if pointer:
        paths.write_pointer(home, cache)
    paths.configure(new, source="pointer" if pointer else "option")
    return report


def _move_into(staging: Path, home: Path) -> None:
    """`home` exists but is empty (checked): move the staged contents in, then drop the staging folder."""
    for p in staging.iterdir():
        p.rename(home / p.name)
    staging.rmdir()


def _copy_entries(src: Path, dst: Path, entries, skip_existing: bool = False) -> int:
    n = 0
    for e in entries:
        s = src / e.rstrip("/")
        if e.endswith("/"):
            n += _copy_tree(s, dst / e.rstrip("/"))
        elif s.exists() and not (skip_existing and (dst / e).exists()):
            _copy_file(s, dst / e)
            n += 1
    return n


def _moved_note(home: Path, cache: Path) -> str:
    return (f"Market Radar: your data was copied to a data folder of its own on "
            f"{datetime.now():%Y-%m-%d %H:%M}.\n\n  Your data:   {home}\n  Market data: {cache}\n\n"
            "Newer versions of Market Radar use that folder, wherever you unzip them. This folder is the old "
            "version with the old copy of your data: once the new version shows your portfolios, notes and "
            "research, you can delete it.\n")
