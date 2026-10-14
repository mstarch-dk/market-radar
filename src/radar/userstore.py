"""Your own stateful data, kept locally in userdata/radar.db (SQLite; gitignored, never committed).

- **transactions**: every buy and sell, the source of truth for the portfolio. Positions and average costs are
  derived from them (universe.holdings). Each row records where it came from (manual entry or an import).
- **imports**: one row per import run, so an import can be undone as a whole.
- **accounts**: e.g. ASK and frie midler; a transaction may name one.
- **symbol_map**: broker identifiers (ISIN, names) the user has matched to Yahoo symbols, reused next time.
- **watchlist**: edits made in the app, an overlay on the watchlist ('add' / 'remove').
- **meta**: small key/value facts (e.g. the Yahoo watchlist from the last Yahoo import).

Schema changes are new entries in MIGRATIONS, never edits to old ones. A copy of the database is kept in
userdata/backups/ before every import and every undo.
"""
from __future__ import annotations

import csv
import io
import json
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
    """CREATE TABLE accounts (
         name TEXT PRIMARY KEY,
         kind TEXT NOT NULL DEFAULT 'other' CHECK (kind IN ('ask', 'frie_midler', 'pension', 'other')),
         note TEXT)""",
    """INSERT INTO accounts (name, kind, note) VALUES
         ('ASK', 'ask', 'aktiesparekonto: 17% lager on everything; stocks and positive-list funds only'),
         ('frie midler', 'frie_midler', 'stocks taxed on realisation; positive-list funds lager')""",
    """CREATE TABLE imports (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         source TEXT NOT NULL,
         file_name TEXT,
         rows_added INTEGER NOT NULL DEFAULT 0,
         rows_skipped INTEGER NOT NULL DEFAULT 0,
         at TEXT NOT NULL)""",
    """CREATE TABLE transactions (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         symbol TEXT NOT NULL,
         date TEXT NOT NULL,
         type TEXT NOT NULL CHECK (type IN ('BUY', 'SELL')),
         quantity REAL NOT NULL CHECK (quantity > 0),
         price REAL NOT NULL CHECK (price > 0),
         fee REAL NOT NULL DEFAULT 0 CHECK (fee >= 0),
         account TEXT REFERENCES accounts(name) ON UPDATE CASCADE,
         note TEXT,
         source TEXT NOT NULL DEFAULT 'manual',
         import_id INTEGER REFERENCES imports(id),
         ext_ref TEXT,
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL)""",
    "CREATE INDEX tx_symbol_date ON transactions (symbol, date)",
    """CREATE TABLE symbol_map (
         ext TEXT PRIMARY KEY,
         symbol TEXT NOT NULL,
         updated_at TEXT NOT NULL)""",
    "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
]


def _connect() -> sqlite3.Connection:
    USERDATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(USERDATA / DB_NAME, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    version = con.execute("PRAGMA user_version").fetchone()[0]
    for i, sql in enumerate(MIGRATIONS[version:], start=version + 1):
        with con:
            con.execute(sql)
            con.execute(f"PRAGMA user_version = {i}")
    return con


def _exists() -> bool:
    return (USERDATA / DB_NAME).exists()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------- watchlist overlay ----------------

def _set(symbol: str, action: str) -> None:
    with closing(_connect()) as con, con:
        con.execute("INSERT INTO watchlist (symbol, action, updated_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(symbol) DO UPDATE SET action = excluded.action, updated_at = excluded.updated_at",
                    (symbol, action, _now()))


def watch(symbol: str) -> None:
    _set(symbol, "add")


def unwatch(symbol: str) -> None:
    _set(symbol, "remove")


def watchlist_overlay() -> dict[str, str]:
    """symbol -> 'add' | 'remove'. Empty when no database exists yet (nothing is created just by reading)."""
    if not _exists():
        return {}
    with closing(_connect()) as con:
        return {r["symbol"]: r["action"] for r in con.execute("SELECT symbol, action FROM watchlist ORDER BY symbol")}


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
    now = _now()
    with closing(_connect()) as con, con:
        con.execute("DELETE FROM watchlist")
        con.executemany("INSERT INTO watchlist (symbol, action, updated_at) VALUES (?, ?, ?)",
                        [(s, a, now) for s, a in rows])
    return len(rows)


# ---------------- backups ----------------

BACKUPS_KEPT = 20


def backup(reason: str) -> str | None:
    """Copy the database to userdata/backups/ (before imports and undos); keeps the newest BACKUPS_KEPT."""
    if not _exists():
        return None
    d = USERDATA / "backups"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"radar-{datetime.now():%Y%m%d-%H%M%S-%f}-{reason}.db"
    with closing(_connect()) as src, closing(sqlite3.connect(path)) as dst:
        src.backup(dst)                          # a consistent copy even while the app is writing
    for old in sorted(d.glob("radar-*.db"))[:-BACKUPS_KEPT]:
        old.unlink()
    return str(path)


# ---------------- transactions ----------------

TX_FIELDS = ("symbol", "date", "type", "quantity", "price", "fee", "account", "note", "ext_ref")


def transactions(symbol: str | None = None, account: str | None = None) -> list[dict]:
    """Stored transactions, oldest first. Nothing is created just by reading."""
    if not _exists():
        return []
    where, args = [], []
    if symbol:
        where.append("symbol = ?")
        args.append(symbol)
    if account:
        where.append("account = ?")
        args.append(account)
    sql = "SELECT * FROM transactions" + (f" WHERE {' AND '.join(where)}" if where else "") + " ORDER BY date, id"
    with closing(_connect()) as con:
        return [dict(r) for r in con.execute(sql, args)]


def get_tx(tx_id: int) -> dict | None:
    if not _exists():
        return None
    with closing(_connect()) as con:
        r = con.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        return dict(r) if r else None


def _insert(con: sqlite3.Connection, row: dict, source: str, import_id: int | None,
            tx_id: int | None = None, created: str | None = None) -> int:
    now = _now()
    v = {k: row.get(k) for k in TX_FIELDS}
    cur = con.execute(
        "INSERT INTO transactions (id, symbol, date, type, quantity, price, fee, account, note, ext_ref, source, "
        "import_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (tx_id, v["symbol"], str(v["date"])[:10], v["type"], v["quantity"], v["price"], v["fee"] or 0,
         v["account"], v["note"], v["ext_ref"], source, import_id, created or now, now))
    return int(cur.lastrowid)


def add_tx(row: dict, source: str = "manual") -> int:
    with closing(_connect()) as con, con:
        return _insert(con, row, source, None)


def update_tx(tx_id: int, row: dict) -> bool:
    fields = {k: row[k] for k in TX_FIELDS if k in row}
    if "fee" in fields:
        fields["fee"] = fields["fee"] or 0
    if "date" in fields:
        fields["date"] = str(fields["date"])[:10]
    if not fields:
        return False
    sets = ", ".join(f"{k} = ?" for k in fields) + ", updated_at = ?"
    with closing(_connect()) as con, con:
        return con.execute(f"UPDATE transactions SET {sets} WHERE id = ?", [*fields.values(), _now(), tx_id]).rowcount == 1


def delete_tx(tx_id: int) -> dict | None:
    """Delete one transaction; returns the deleted row so it can be restored (undo)."""
    row = get_tx(tx_id)
    if row:
        with closing(_connect()) as con, con:
            con.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    return row


def restore_tx(row: dict) -> int:
    """Put a deleted transaction back with its original id and provenance."""
    with closing(_connect()) as con, con:
        imp = row.get("import_id")
        if imp is not None and not con.execute("SELECT 1 FROM imports WHERE id = ?", (imp,)).fetchone():
            imp = None                            # its import was undone since: keep the row, drop the link
        return _insert(con, row, row["source"], imp, row["id"], row.get("created_at"))


def _key(r: dict) -> tuple:
    return (r["symbol"], str(r["date"])[:10], r["type"], round(float(r["quantity"]), 6), round(float(r["price"]), 6))


def add_import(rows: list[dict], source: str, file_name: str | None = None, replace_source: bool = False) -> dict:
    """Store an import as one unit. Rows already present (same broker trade id, or same symbol, date, type,
    quantity and price) are skipped. `replace_source` first removes every earlier row from this source (for a
    snapshot export such as Yahoo's, which always contains the full history). A backup is taken first."""
    backup(f"before-{source}-import")
    with closing(_connect()) as con, con:
        replaced = con.execute("DELETE FROM transactions WHERE source = ?", (source,)).rowcount if replace_source else 0
        existing = [dict(r) for r in con.execute("SELECT symbol, date, type, quantity, price, ext_ref FROM transactions")]
        keys = {_key(r) for r in existing}
        refs = {r["ext_ref"] for r in existing if r["ext_ref"]}
        imp = con.execute("INSERT INTO imports (source, file_name, at) VALUES (?, ?, ?)",
                          (source, file_name, _now())).lastrowid
        added = skipped = 0
        for r in rows:
            if r.get("account"):
                con.execute("INSERT OR IGNORE INTO accounts (name) VALUES (?)", (r["account"],))
            if (r.get("ext_ref") and r["ext_ref"] in refs) or _key(r) in keys:
                skipped += 1
                continue
            _insert(con, r, source, imp)   # only rows stored *before* this import count as duplicates:
            added += 1                      # two identical fills within one file are both real
        con.execute("UPDATE imports SET rows_added = ?, rows_skipped = ? WHERE id = ?", (added, skipped, imp))
    return {"id": int(imp), "added": added, "skipped": skipped, "replaced": replaced}


def imports() -> list[dict]:
    """Past imports, newest first, with how many of their rows are still in the store."""
    if not _exists():
        return []
    with closing(_connect()) as con:
        out = []
        for r in con.execute("SELECT * FROM imports ORDER BY id DESC").fetchall():
            n = con.execute("SELECT COUNT(*) FROM transactions WHERE import_id = ?", (r["id"],)).fetchone()[0]
            out.append(dict(r) | {"rows_now": n})
        return out


def undo_import(import_id: int) -> int:
    """Remove every transaction an import added (a backup is taken first). Returns the number removed."""
    backup(f"before-undo-import-{import_id}")
    with closing(_connect()) as con, con:
        n = con.execute("DELETE FROM transactions WHERE import_id = ?", (import_id,)).rowcount
        con.execute("DELETE FROM imports WHERE id = ?", (import_id,))
    return n


# ---------------- accounts, symbol map, meta ----------------

ACCOUNT_KINDS = ("ask", "frie_midler", "pension", "other")


def accounts() -> list[dict]:
    with closing(_connect()) as con:
        return [dict(r) for r in con.execute("SELECT name, kind, note FROM accounts ORDER BY name")]


def save_account(name: str, kind: str = "other", note: str | None = None, old_name: str | None = None) -> None:
    """Add an account, or rename/update one (its transactions follow a rename)."""
    with closing(_connect()) as con, con:
        if old_name and old_name != name:
            con.execute("UPDATE accounts SET name = ?, kind = ?, note = ? WHERE name = ?", (name, kind, note, old_name))
        else:
            con.execute("INSERT INTO accounts (name, kind, note) VALUES (?, ?, ?) ON CONFLICT(name) DO UPDATE SET "
                        "kind = excluded.kind, note = excluded.note", (name, kind, note))


def mapped_symbol(ext: str) -> str | None:
    if not _exists():
        return None
    with closing(_connect()) as con:
        r = con.execute("SELECT symbol FROM symbol_map WHERE ext = ?", (ext.strip().upper(),)).fetchone()
        return r["symbol"] if r else None


def map_symbol(ext: str, symbol: str) -> None:
    with closing(_connect()) as con, con:
        con.execute("INSERT INTO symbol_map (ext, symbol, updated_at) VALUES (?, ?, ?) ON CONFLICT(ext) DO UPDATE "
                    "SET symbol = excluded.symbol, updated_at = excluded.updated_at", (ext.strip().upper(), symbol, _now()))


def meta_get(key: str, default=None):
    if not _exists():
        return default
    with closing(_connect()) as con:
        r = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return json.loads(r["value"]) if r else default


def meta_set(key: str, value) -> None:
    with closing(_connect()) as con, con:
        con.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, json.dumps(value)))


# ---------------- CSV round trip (backup download, CI holdings bundle) ----------------

EXPORT_COLS = ["symbol", "date", "type", "quantity", "price", "fee", "account", "note", "source", "ext_ref"]


def export_transactions_csv() -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=EXPORT_COLS, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    w.writerows(transactions())
    return buf.getvalue()


def import_transactions_csv(text: str) -> int:
    """Replace all transactions with an exported set (restoring the CI bundle). Returns the number of rows."""
    rows = [{**r, "quantity": float(r["quantity"]), "price": float(r["price"]), "fee": float(r.get("fee") or 0),
             "account": r.get("account") or None, "note": r.get("note") or None, "ext_ref": r.get("ext_ref") or None}
            for r in csv.DictReader(io.StringIO(text))]
    with closing(_connect()) as con, con:
        con.execute("DELETE FROM transactions")
        for r in rows:
            if r["account"]:
                con.execute("INSERT OR IGNORE INTO accounts (name) VALUES (?)", (r["account"],))
            _insert(con, r, r.get("source") or "bundle", None)
    return len(rows)
