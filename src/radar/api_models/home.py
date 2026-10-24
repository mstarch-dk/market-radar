"""The data home (home.py): setup, the data folders, backups, restore and the update check."""
from __future__ import annotations

from typing import Literal

from .common import Strict


class LegacyFound(Strict):
    """An install folder from before the data home that holds your data (home.legacy_summary)."""
    path: str
    is_this_install: bool
    database: bool
    counts: dict[str, int | str]
    personal: dict[str, int]
    imports: int
    history_files: int
    cache_mb: float
    newest: str | None = None
    moved: bool


class HomeStatus(Strict):
    """Where the data is and whether the app can use it: ok, unset (first start: choose), missing (chosen, not
    found) or newer (a newer version wrote it: read-only)."""
    state: Literal["ok", "unset", "missing", "newer"]
    source: str
    app_version: str
    pointer: str
    default_home: str
    default_cache: str
    home: str | None = None
    cache: str | None = None
    read_only: str | None = None
    warning: str | None = None
    found: list[LegacyFound]


class SetupIn(Strict):
    """migrate: copy an old folder's data (`source`) into a new home; create: an empty home; use: an existing one."""
    action: Literal["migrate", "create", "use"]
    source: str | None = None
    home: str | None = None
    copy_cache: bool = True


class SetupResult(Strict):
    status: HomeStatus
    files: dict[str, int] = {}


class DataFolder(Strict):
    """One place the app keeps things: your data (personal), history, or the market-data cache."""
    key: str
    label: str
    path: str
    tier: Literal["personal", "history", "cache"]
    files: int
    mb: float


class BackupRow(Strict):
    name: str
    path: str
    created: str
    kind: Literal["manual", "daily", "upgrade", "restore"]
    size: int


class DataHome(Strict):
    """The Data page's "Your data": where everything is, the backups here and in the second folder."""
    status: HomeStatus
    folders: list[DataFolder]
    backups: list[BackupRow]
    mirror: str | None = None
    mirror_backups: list[BackupRow]


class MirrorIn(Strict):
    path: str | None = None


class RestoreIn(Strict):
    name: str


class RestoreResult(Strict):
    restored: str
    created: str
    files: int
    tables: dict[str, int]
    saved_first: str


class OpenIn(Strict):
    key: str


class UpdateCheck(Strict):
    """Is a newer release out (updates.py)? Only when the user switched the check on and a repo is configured."""
    enabled: bool
    repo: str | None = None
    current: str
    latest: str | None = None
    newer: bool
    url: str | None = None
    published: str | None = None
    checked: str | None = None
    error: str | None = None


class UpdateCheckIn(Strict):
    enabled: bool
