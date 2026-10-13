"""The user's own stateful data, kept locally in userdata/radar.db (SQLite; gitignored, never committed).

Today it holds watchlist edits made in the web app. It is the home for more of the same kind later (ticker
notes, targets, alarms, peer comparisons): add a table with a new entry in MIGRATIONS, never edit an old one.

The watchlist table is an overlay on the Yahoo import (imports/holdings.csv), which `radar import-yahoo`
rewrites wholesale: 'add' puts a symbol on the watchlist, 'remove' takes a Yahoo-imported watchlist symbol
off it, and both survive the next import. universe.holdings() applies it.
"""
from __future__ import annotations

import csv
import io
import sqlite3
from contextlib import closing
from datetime import datetime

from .config import USERDATA

DB_NAME = "radar.db"

MIGRATIONS = [
    """CREATE TABLE watchlist (
         symbol TEXT PRIMARY KEY,
         action TEXT NOT NULL CHECK (action IN ('add', 'remove')),
         updated_at TEXT NOT NULL)""",
]


def _connect() -> sqlite3.Connection:
    USERDATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(USERDATA / DB_NAME, timeout=10)
    version = con.execute("PRAGMA user_version").fetchone()[0]
    for i, sql in enumerate(MIGRATIONS[version:], start=version + 1):
        with con:
            con.execute(sql)
            con.execute(f"PRAGMA user_version = {i}")
    return con


def _set(symbol: str, action: str) -> None:
    with closing(_connect()) as con, con:
        con.execute("INSERT INTO watchlist (symbol, action, updated_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(symbol) DO UPDATE SET action = excluded.action, updated_at = excluded.updated_at",
                    (symbol, action, datetime.now().isoformat(timespec="seconds")))


def watch(symbol: str) -> None:
    _set(symbol, "add")


def unwatch(symbol: str) -> None:
    _set(symbol, "remove")


def watchlist_overlay() -> dict[str, str]:
    """symbol -> 'add' | 'remove'. Empty when no database exists yet (nothing is created just by reading)."""
    if not (USERDATA / DB_NAME).exists():
        return {}
    with closing(_connect()) as con:
        return dict(con.execute("SELECT symbol, action FROM watchlist ORDER BY symbol").fetchall())


def export_watchlist_csv() -> str:
    """The overlay as CSV text (for the CI holdings bundle)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["symbol", "action"])
    w.writerows(watchlist_overlay().items())
    return buf.getvalue()


def import_watchlist_csv(text: str) -> int:
    """Load an exported overlay (replaces the current one). Returns the number of rows."""
    rows = [(r["symbol"], r["action"]) for r in csv.DictReader(io.StringIO(text))]
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_connect()) as con, con:
        con.execute("DELETE FROM watchlist")
        con.executemany("INSERT INTO watchlist (symbol, action, updated_at) VALUES (?, ?, ?)",
                        [(s, a, now) for s, a in rows])
    return len(rows)
