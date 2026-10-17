"""Copies of radar.db in backups/ in the data folder: taken before imports, undos, moves, deletes and schema
upgrades (userstore.backup), the newest BACKUPS_KEPT kept."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime

from ..paths import USERDATA

BACKUPS_KEPT = 20


def copy(con: sqlite3.Connection, reason: str) -> str:
    """A consistent copy of the open database `con`, named by time and `reason`; returns its path."""
    d = USERDATA / "backups"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"radar-{datetime.now():%Y%m%d-%H%M%S-%f}-{reason}.db"
    with closing(sqlite3.connect(path)) as dst:
        con.backup(dst)                          # a consistent copy even while the app is writing
    for old in sorted(d.glob("radar-*.db"))[:-BACKUPS_KEPT]:
        old.unlink()
    return str(path)
