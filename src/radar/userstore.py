"""Your own stateful data, kept locally in userdata/radar.db (SQLite; gitignored, never committed).

- **transactions**: every buy and sell (and cash row), the source of truth for the portfolios. Positions and average costs are
  derived from them (universe.holdings). Each row records where it came from (manual entry or an import).
- **imports**: one row per import run, so an import can be undone as a whole.
- **portfolios**: real ones (your accounts, e.g. ASK and frie midler) and virtual ones (simulations, A/B
  tests), each with a tax kind and free-form **portfolio_tags**. Every transaction belongs to one; only real
  portfolios count as "yours" unless others are chosen explicitly (portfolio_ids). **sim_runs** records
  simulated runs.
- **symbol_map**: broker identifiers (ISIN, names) the user has matched to Yahoo symbols, reused next time.
- **watchlist**: edits made in the app, an overlay on the watchlist ('add' / 'remove').
- **meta**: small key/value facts (e.g. the Yahoo watchlist from the last Yahoo import).
- **views**, **view_exposures**, **view_indicators**: your market views (subjective beliefs), what each helps or
  hurts, and which readings would confirm it (signals/views.py).

Schema changes are new entries in MIGRATIONS, never edits to old ones (a tuple of statements runs as one unit,
for rebuilding a table). A copy of the database is kept in
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
    """CREATE TABLE views (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         statement TEXT NOT NULL,
         conviction INTEGER NOT NULL DEFAULT 3 CHECK (conviction BETWEEN 1 AND 5),
         horizon TEXT NOT NULL DEFAULT '12m' CHECK (horizon IN ('3m', '6m', '12m', '3y')),
         rationale TEXT,
         falsifier TEXT,
         template TEXT,
         status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL)""",
    """CREATE TABLE view_exposures (
         view_id INTEGER NOT NULL REFERENCES views(id) ON DELETE CASCADE,
         kind TEXT NOT NULL CHECK (kind IN ('etf', 'sector', 'industry', 'region', 'ticker')),
         key TEXT NOT NULL,
         effect INTEGER NOT NULL CHECK (effect IN (-1, 1)))""",
    """CREATE TABLE view_indicators (
         view_id INTEGER NOT NULL REFERENCES views(id) ON DELETE CASCADE,
         indicator TEXT NOT NULL,
         expect TEXT NOT NULL CHECK (expect IN ('up', 'down')))""",
    # portfolios: the accounts become portfolios (real or virtual), with tags; trades without an account go to
    # a real portfolio "Main" (the default) so nothing is silently put in a tax account
    ("""CREATE TABLE portfolios (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         name TEXT NOT NULL UNIQUE CHECK (length(trim(name)) > 0),
         mode TEXT NOT NULL DEFAULT 'real' CHECK (mode IN ('real', 'virtual')),
         kind TEXT NOT NULL DEFAULT 'other' CHECK (kind IN ('ask', 'frie_midler', 'pension', 'other')),
         dividends TEXT NOT NULL DEFAULT 'reinvested' CHECK (dividends IN ('reinvested', 'cash')),
         origin TEXT NOT NULL DEFAULT 'manual' CHECK (origin IN ('manual', 'fork', 'sim')),
         parent_id INTEGER REFERENCES portfolios(id) ON DELETE SET NULL,
         forked_at TEXT,
         strategy TEXT,
         params TEXT,
         note TEXT,
         archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL)""",
     """INSERT INTO portfolios (name, kind, note, created_at, updated_at)
         SELECT name, kind, note, datetime('now'), datetime('now') FROM accounts ORDER BY rowid""",
     """INSERT INTO portfolios (name, kind, note, created_at, updated_at)
         SELECT 'Main', 'other', 'Trades from before portfolios: move them to the right account',
                datetime('now'), datetime('now')
         WHERE EXISTS (SELECT 1 FROM transactions WHERE account IS NULL OR account NOT IN (SELECT name FROM accounts))
           AND NOT EXISTS (SELECT 1 FROM portfolios WHERE name = 'Main')""",
     """INSERT OR REPLACE INTO meta (key, value)
         SELECT 'default_portfolio', CAST(id AS TEXT) FROM portfolios WHERE name = 'Main'""",
     """CREATE TABLE portfolio_tags (
         portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
         tag TEXT NOT NULL CHECK (tag = lower(trim(tag)) AND length(tag) BETWEEN 1 AND 32),
         PRIMARY KEY (portfolio_id, tag))""",
     "CREATE INDEX portfolio_tags_tag ON portfolio_tags (tag)",
     """CREATE TABLE sim_runs (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
         strategy TEXT NOT NULL,
         params TEXT NOT NULL DEFAULT '{}',
         start TEXT NOT NULL,
         "end" TEXT,
         data_asof TEXT,
         status TEXT NOT NULL CHECK (status IN ('ok', 'failed')),
         rows INTEGER NOT NULL DEFAULT 0,
         message TEXT,
         at TEXT NOT NULL)"""),
    # transactions belong to a portfolio, and may be cash rows (amount in DKK) besides buys and sells
    ("""CREATE TABLE transactions_new (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE RESTRICT,
         symbol TEXT,
         date TEXT NOT NULL,
         type TEXT NOT NULL CHECK (type IN ('BUY', 'SELL', 'DEPOSIT', 'WITHDRAW', 'DIVIDEND', 'FEE', 'INTEREST')),
         quantity REAL,
         price REAL,
         fee REAL NOT NULL DEFAULT 0 CHECK (fee >= 0),
         amount REAL,
         currency TEXT,
         fx_rate REAL CHECK (fx_rate IS NULL OR fx_rate > 0),
         note TEXT,
         source TEXT NOT NULL DEFAULT 'manual',
         import_id INTEGER REFERENCES imports(id),
         run_id INTEGER REFERENCES sim_runs(id) ON DELETE CASCADE,
         ext_ref TEXT,
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL,
         CHECK ((type IN ('BUY', 'SELL') AND symbol IS NOT NULL AND quantity > 0 AND price > 0 AND amount IS NULL)
             OR (type = 'DIVIDEND' AND symbol IS NOT NULL AND amount > 0 AND quantity IS NULL AND price IS NULL)
             OR (type IN ('DEPOSIT', 'WITHDRAW', 'FEE', 'INTEREST') AND amount > 0
                 AND quantity IS NULL AND price IS NULL)))""",
     """INSERT INTO transactions_new (id, portfolio_id, symbol, date, type, quantity, price, fee, note, source,
                                      import_id, ext_ref, created_at, updated_at)
         SELECT t.id, COALESCE(p.id, (SELECT id FROM portfolios WHERE name = 'Main')), t.symbol, t.date, t.type,
                t.quantity, t.price, t.fee, t.note, t.source, t.import_id, t.ext_ref, t.created_at, t.updated_at
         FROM transactions t LEFT JOIN portfolios p ON p.name = t.account""",
     "DROP TABLE transactions",
     "ALTER TABLE transactions_new RENAME TO transactions",
     "CREATE INDEX tx_symbol_date ON transactions (symbol, date)",
     "CREATE INDEX tx_portfolio_date ON transactions (portfolio_id, date)",
     "DROP TABLE accounts"),
    "ALTER TABLE imports ADD COLUMN portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE SET NULL",
]


def _connect() -> sqlite3.Connection:
    USERDATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(USERDATA / DB_NAME, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        _migrate(con)
    except BaseException:
        con.close()
        raise
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _migrate(con: sqlite3.Connection) -> None:
    """Bring the schema up to date. Each MIGRATIONS entry (one statement, or a tuple run as one unit) commits
    on its own, so a failing step leaves the database exactly as it was before that step. Foreign keys are
    off while migrating (so a table can be rebuilt) and checked before each commit. An existing database is
    backed up before its first upgrade step."""
    version = con.execute("PRAGMA user_version").fetchone()[0]
    if version >= len(MIGRATIONS):
        return
    if version > 0:
        _copy(con, f"before-schema-v{len(MIGRATIONS)}")
    con.isolation_level = None                    # explicit BEGIN/COMMIT: DDL included in the transaction
    con.execute("PRAGMA foreign_keys = OFF")      # only takes effect outside a transaction
    try:
        for i, step in enumerate(MIGRATIONS[version:], start=version + 1):
            con.execute("BEGIN")
            try:
                for sql in (step,) if isinstance(step, str) else step:
                    con.execute(sql)
                if con.execute("PRAGMA foreign_key_check").fetchone():
                    raise sqlite3.IntegrityError(f"schema step {i} would leave rows pointing at nothing")
                con.execute(f"PRAGMA user_version = {i}")
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
    finally:
        con.isolation_level = ""


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
    with closing(_connect()) as con:
        return _copy(con, reason)


def _copy(con: sqlite3.Connection, reason: str) -> str:
    d = USERDATA / "backups"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"radar-{datetime.now():%Y%m%d-%H%M%S-%f}-{reason}.db"
    with closing(sqlite3.connect(path)) as dst:
        con.backup(dst)                          # a consistent copy even while the app is writing
    for old in sorted(d.glob("radar-*.db"))[:-BACKUPS_KEPT]:
        old.unlink()
    return str(path)


# ---------------- portfolios ----------------

PORTFOLIO_KINDS = ("ask", "frie_midler", "pension", "other")          # the tax wrapper
PORTFOLIO_MODES = ("real", "virtual")                                  # virtual: simulated, never "yours"
DIVIDEND_POLICIES = ("reinvested", "cash")
PORTFOLIO_FIELDS = ("name", "mode", "kind", "dividends", "note", "archived")
SCOPES = ("real", "virtual", "all")


def norm_tag(tag: str) -> str:
    return " ".join(str(tag).split()).lower()


def _portfolio_rows(con, where: str = "", args: tuple = ()) -> list[dict]:
    default = _default_id(con)
    out = []
    for r in con.execute(
            "SELECT p.*, COUNT(t.id) AS n_tx, MIN(t.date) AS first_date, MAX(t.date) AS last_date "
            f"FROM portfolios p LEFT JOIN transactions t ON t.portfolio_id = p.id {where} "
            "GROUP BY p.id ORDER BY p.archived, p.mode, p.name COLLATE NOCASE", args):
        p = dict(r)
        p["archived"] = bool(p["archived"])
        p["params"] = json.loads(p["params"]) if p["params"] else None
        p["tags"] = [t["tag"] for t in con.execute(
            "SELECT tag FROM portfolio_tags WHERE portfolio_id = ? ORDER BY tag", (p["id"],))]
        p["is_default"] = p["id"] == default
        out.append(p)
    return out


def portfolios(include_archived: bool = True) -> list[dict]:
    """Every portfolio with its tags, number of rows and date range ([] without a database)."""
    if not _exists():
        return []
    with closing(_connect()) as con:
        return _portfolio_rows(con, "" if include_archived else "WHERE p.archived = 0")


def get_portfolio(pid: int) -> dict | None:
    if not _exists():
        return None
    with closing(_connect()) as con:
        rows = _portfolio_rows(con, "WHERE p.id = ?", (pid,))
        return rows[0] if rows else None


def portfolio_by_name(name: str | None) -> dict | None:
    if not _exists() or not name or not name.strip():
        return None
    with closing(_connect()) as con:
        rows = _portfolio_rows(con, "WHERE p.name = ?", (name.strip(),))
        return rows[0] if rows else None


def _write_tags(con, pid: int, tags) -> None:
    clean = sorted({norm_tag(t) for t in tags or [] if norm_tag(t)})
    for t in clean:
        if len(t) > 32:
            raise ValueError(f"tag too long (32 characters at most): {t!r}")
    con.execute("DELETE FROM portfolio_tags WHERE portfolio_id = ?", (pid,))
    con.executemany("INSERT INTO portfolio_tags (portfolio_id, tag) VALUES (?, ?)", [(pid, t) for t in clean])


def save_portfolio(p: dict, pid: int | None = None) -> int:
    """Add a portfolio, or update one (only the fields given; tags are replaced when `tags` is given)."""
    now = _now()
    vals = {k: p[k] for k in PORTFOLIO_FIELDS if k in p and (p[k] is not None or k == "note")}
    if "name" in vals:
        vals["name"] = (vals["name"] or "").strip()
        if not vals["name"]:
            raise ValueError("a portfolio needs a name")
    if "archived" in vals:
        vals["archived"] = int(bool(vals["archived"]))
    for k in ("origin", "parent_id", "forked_at", "strategy"):
        if k in p:
            vals[k] = p[k]
    if "params" in p:
        vals["params"] = json.dumps(p["params"]) if p["params"] is not None else None
    with closing(_connect()) as con, con:
        if "name" in vals and con.execute("SELECT 1 FROM portfolios WHERE name = ? AND id IS NOT ?",
                                          (vals["name"], pid)).fetchone():
            raise ValueError(f"there is already a portfolio called {vals['name']}")
        if pid is None:
            if "name" not in vals:
                raise ValueError("a portfolio needs a name")
            cols = list(vals) + ["created_at", "updated_at"]
            pid = con.execute(f"INSERT INTO portfolios ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                              (*vals.values(), now, now)).lastrowid
        elif vals:
            con.execute(f"UPDATE portfolios SET {', '.join(f'{k} = ?' for k in vals)}, updated_at = ? WHERE id = ?",
                        (*vals.values(), now, pid))
        if "tags" in p:
            _write_tags(con, pid, p["tags"])
        if vals.get("archived") or vals.get("mode") == "virtual":
            if _default_id(con) == pid:            # the default must stay a real, active portfolio
                con.execute("DELETE FROM meta WHERE key = 'default_portfolio'")
    return int(pid)


def set_tags(pid: int, tags) -> list[str]:
    with closing(_connect()) as con, con:
        _write_tags(con, pid, tags)
        return [r["tag"] for r in con.execute("SELECT tag FROM portfolio_tags WHERE portfolio_id = ? ORDER BY tag", (pid,))]


def all_tags() -> list[dict]:
    """Every tag in use, with how many portfolios carry it."""
    if not _exists():
        return []
    with closing(_connect()) as con:
        return [dict(r) for r in con.execute("SELECT tag, COUNT(*) AS n FROM portfolio_tags GROUP BY tag ORDER BY tag")]


def _default_id(con) -> int | None:
    r = con.execute("SELECT value FROM meta WHERE key = 'default_portfolio'").fetchone()
    if not r:
        return None
    pid = json.loads(r["value"])
    return pid if con.execute("SELECT 1 FROM portfolios WHERE id = ?", (pid,)).fetchone() else None


def default_portfolio() -> int | None:
    if not _exists():
        return None
    with closing(_connect()) as con:
        return _default_id(con)


def set_default_portfolio(pid: int) -> None:
    with closing(_connect()) as con, con:
        if not con.execute("SELECT 1 FROM portfolios WHERE id = ? AND mode = 'real' AND archived = 0", (pid,)).fetchone():
            raise ValueError("only a real, active portfolio can be the default")
        con.execute("INSERT INTO meta (key, value) VALUES ('default_portfolio', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (json.dumps(pid),))


def _target(con, row: dict, fallback: int | None = None, create: bool = False) -> int:
    """The portfolio a row goes into: its portfolio_id, else the portfolio named in `portfolio` (or the older
    `account`), else `fallback`, else the default portfolio ("Main", created on first use)."""
    if row.get("portfolio_id") is not None:
        return int(row["portfolio_id"])
    name = (row.get("portfolio") or row.get("account") or "").strip()
    if name:
        r = con.execute("SELECT id FROM portfolios WHERE name = ?", (name,)).fetchone()
        if r:
            return r["id"]
        if not create:
            raise ValueError(f"unknown portfolio {name!r}")
        now = _now()
        return con.execute("INSERT INTO portfolios (name, created_at, updated_at) VALUES (?, ?, ?)",
                           (name, now, now)).lastrowid
    if fallback is not None:
        return fallback
    pid = _default_id(con)
    if pid is None:
        r = con.execute("SELECT id FROM portfolios WHERE name = 'Main'").fetchone()
        now = _now()
        pid = r["id"] if r else con.execute(
            "INSERT INTO portfolios (name, note, created_at, updated_at) VALUES ('Main', ?, ?, ?)",
            ("Trades entered without choosing a portfolio", now, now)).lastrowid
        con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('default_portfolio', ?)", (json.dumps(pid),))
    return int(pid)


def portfolio_ids(scope: str = "real", ids=None, tags=None, include_archived: bool = False) -> list[int]:
    """The single resolver for "which portfolios": the ones named by id or carrying one of `tags` (an explicit
    choice: virtual and archived ones included), else every portfolio in `scope` (default: the real ones that
    aren't archived, i.e. yours)."""
    if not _exists():
        return []
    with closing(_connect()) as con:
        if ids or tags:
            out = {int(i) for i in ids or []}
            tags = [norm_tag(t) for t in tags or []]
            if tags:
                out |= {r[0] for r in con.execute(
                    f"SELECT portfolio_id FROM portfolio_tags WHERE tag IN ({', '.join('?' * len(tags))})", tags)}
            return sorted(out)
        where, args = ([] if include_archived else ["archived = 0"]), []
        if scope != "all":
            where.append("mode = ?")
            args.append(scope)
        sql = "SELECT id FROM portfolios" + (f" WHERE {' AND '.join(where)}" if where else "") + " ORDER BY id"
        return [r[0] for r in con.execute(sql, args)]


def delete_portfolio(pid: int) -> dict | None:
    """Delete a portfolio. A virtual one goes with its rows (a backup is taken first); a real one only when it
    has no rows left (archive it instead)."""
    p = get_portfolio(pid)
    if not p:
        return None
    if p["mode"] == "real" and p["n_tx"]:
        raise ValueError(f"{p['name']} has {p['n_tx']} transactions: move them first, or archive it")
    if p["n_tx"]:
        backup(f"before-delete-portfolio-{pid}")
    with closing(_connect()) as con, con:
        con.execute("DELETE FROM transactions WHERE portfolio_id = ?", (pid,))
        con.execute("DELETE FROM sim_runs WHERE portfolio_id = ?", (pid,))
        con.execute("DELETE FROM portfolios WHERE id = ?", (pid,))
        if _default_id(con) is None:
            con.execute("DELETE FROM meta WHERE key = 'default_portfolio'")
    return p


def move_transactions(from_id: int, to_id: int, ids=None, symbols=None) -> int:
    """Move rows to another portfolio (all of them, or only these ids / symbols). A backup is taken first."""
    where, args = ["portfolio_id = ?"], [from_id]
    if ids:
        where.append(f"id IN ({', '.join('?' * len(ids))})")
        args += list(ids)
    if symbols:
        where.append(f"symbol IN ({', '.join('?' * len(symbols))})")
        args += list(symbols)
    backup(f"before-move-{from_id}-to-{to_id}")
    with closing(_connect()) as con, con:
        return con.execute(f"UPDATE transactions SET portfolio_id = ?, updated_at = ? WHERE {' AND '.join(where)}",
                           [to_id, _now(), *args]).rowcount


BUNDLE_PORTFOLIO_KEYS = (*PORTFOLIO_FIELDS, "origin", "forked_at", "strategy", "params", "tags", "is_default")


def export_portfolios_json(scope: str = "real") -> str:
    """Portfolios with their kind, mode, tags and notes (the CI bundle; real ones by default)."""
    keep = set(portfolio_ids(scope, include_archived=True))
    rows = [{k: p[k] for k in BUNDLE_PORTFOLIO_KEYS} for p in portfolios() if p["id"] in keep]
    return json.dumps(rows, indent=1, ensure_ascii=False)


def import_portfolios_json(text: str) -> int:
    """Add or update portfolios by name from an export (their transactions come separately)."""
    rows = json.loads(text)
    _connect().close()                            # the schema (and its seeded portfolios) first: matched by name
    for p in rows:
        found = portfolio_by_name(p["name"])
        pid = save_portfolio({k: v for k, v in p.items() if k != "is_default"}, found["id"] if found else None)
        if p.get("is_default"):
            set_default_portfolio(pid)
    return len(rows)


# ---------------- transactions ----------------

TX_FIELDS = ("symbol", "date", "type", "quantity", "price", "fee", "amount", "currency", "fx_rate", "note", "ext_ref")
TRADE_TYPES = ("BUY", "SELL")
CASH_TYPES = ("DEPOSIT", "WITHDRAW", "DIVIDEND", "FEE", "INTEREST")


def transactions(symbol: str | None = None, portfolios: list[int] | None = None, types=None) -> list[dict]:
    """Stored rows, oldest first, each with its portfolio's name: every portfolio unless `portfolios` (ids) is
    given. Nothing is created just by reading."""
    if not _exists():
        return []
    where, args = [], []
    if symbol:
        where.append("t.symbol = ?")
        args.append(symbol)
    if portfolios is not None:
        where.append(f"t.portfolio_id IN ({', '.join('?' * len(portfolios))})" if portfolios else "0")
        args += list(portfolios)
    if types:
        where.append(f"t.type IN ({', '.join('?' * len(types))})")
        args += list(types)
    sql = ("SELECT t.*, p.name AS portfolio FROM transactions t JOIN portfolios p ON p.id = t.portfolio_id"
           + (f" WHERE {' AND '.join(where)}" if where else "") + " ORDER BY t.date, t.id")
    with closing(_connect()) as con:
        return [dict(r) for r in con.execute(sql, args)]


def get_tx(tx_id: int) -> dict | None:
    if not _exists():
        return None
    with closing(_connect()) as con:
        r = con.execute("SELECT t.*, p.name AS portfolio FROM transactions t JOIN portfolios p ON p.id = t.portfolio_id "
                        "WHERE t.id = ?", (tx_id,)).fetchone()
        return dict(r) if r else None


def transactions_version() -> str:
    """Changes whenever a row or a portfolio is added, edited, moved or deleted (for caching results)."""
    if not _exists():
        return "0"
    with closing(_connect()) as con:
        t = con.execute("SELECT COUNT(*), MAX(updated_at), TOTAL(id), TOTAL(portfolio_id * id) FROM transactions").fetchone()
        p = con.execute("SELECT COUNT(*), MAX(updated_at) FROM portfolios").fetchone()
        return ":".join(str(x) for x in (*t, *p))


def _insert(con: sqlite3.Connection, row: dict, source: str, import_id: int | None,
            tx_id: int | None = None, created: str | None = None, portfolio_id: int | None = None,
            run_id: int | None = None) -> int:
    now = _now()
    v = {k: row.get(k) for k in TX_FIELDS}
    pid = portfolio_id if portfolio_id is not None else _target(con, row)
    cur = con.execute(
        "INSERT INTO transactions (id, portfolio_id, symbol, date, type, quantity, price, fee, amount, currency, "
        "fx_rate, note, ext_ref, source, import_id, run_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (tx_id, pid, v["symbol"], str(v["date"])[:10], v["type"], v["quantity"], v["price"], v["fee"] or 0,
         v["amount"], v["currency"], v["fx_rate"], v["note"], v["ext_ref"], source, import_id, run_id,
         created or now, now))
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
    with closing(_connect()) as con, con:
        if any(row.get(k) is not None for k in ("portfolio_id", "portfolio", "account")):
            fields["portfolio_id"] = _target(con, row)
        if not fields:
            return False
        sets = ", ".join(f"{k} = ?" for k in fields) + ", updated_at = ?"
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
        pid = row.get("portfolio_id")
        if pid is not None and not con.execute("SELECT 1 FROM portfolios WHERE id = ?", (pid,)).fetchone():
            pid = None                            # its portfolio is gone: by name, else the default
        return _insert(con, {**row, "portfolio_id": pid}, row["source"], imp, row["id"], row.get("created_at"))


def _r6(v) -> float | None:
    return None if v is None else round(float(v), 6)


def _key(r: dict) -> tuple:
    """What makes two rows the same trade, whichever portfolio they are in."""
    return (r.get("symbol"), str(r["date"])[:10], r["type"], _r6(r.get("quantity")), _r6(r.get("price")),
            _r6(r.get("amount")))


def add_import(rows: list[dict], source: str, file_name: str | None = None, replace_source: bool = False,
               portfolio_id: int | None = None) -> dict:
    """Store an import as one unit, into `portfolio_id` (default: the default portfolio) unless a row names its
    own portfolio (created as a real one if new). Rows already stored (same broker trade id, or same symbol,
    date, type, quantity and price) are skipped: in any real portfolio when importing into a real one, so trades
    moved to another account aren't imported twice; in the target only when importing into a virtual one. `replace_source` first removes the target's earlier rows from this source
    (for a snapshot export such as Yahoo's, which always contains the full history). A backup is taken first."""
    backup(f"before-{source}-import")
    with closing(_connect()) as con, con:
        target = _target(con, {}, portfolio_id)
        replaced = con.execute("DELETE FROM transactions WHERE source = ? AND portfolio_id = ?",
                               (source, target)).rowcount if replace_source else 0
        existing = [dict(r) for r in con.execute(
            "SELECT t.symbol, t.date, t.type, t.quantity, t.price, t.amount, t.ext_ref FROM transactions t "
            "JOIN portfolios p ON p.id = t.portfolio_id WHERE t.portfolio_id = ? OR (p.mode = 'real' AND "
            "(SELECT mode FROM portfolios WHERE id = ?) = 'real')", (target, target))]
        keys = {_key(r) for r in existing}
        refs = {r["ext_ref"] for r in existing if r["ext_ref"]}
        imp = con.execute("INSERT INTO imports (source, file_name, at, portfolio_id) VALUES (?, ?, ?, ?)",
                          (source, file_name, _now(), target)).lastrowid
        added = skipped = 0
        for r in rows:
            if (r.get("ext_ref") and r["ext_ref"] in refs) or _key(r) in keys:
                skipped += 1
                continue
            pid = _target(con, r, target, create=True)
            _insert(con, r, source, imp, portfolio_id=pid)   # only rows stored *before* this import count as
            added += 1                                       # duplicates: two identical fills in one file are real
        con.execute("UPDATE imports SET rows_added = ?, rows_skipped = ? WHERE id = ?", (added, skipped, imp))
    return {"id": int(imp), "added": added, "skipped": skipped, "replaced": replaced}


def imports() -> list[dict]:
    """Past imports, newest first, with how many of their rows are still in the store."""
    if not _exists():
        return []
    with closing(_connect()) as con:
        out = []
        for r in con.execute("SELECT i.*, p.name AS portfolio FROM imports i "
                             "LEFT JOIN portfolios p ON p.id = i.portfolio_id ORDER BY i.id DESC").fetchall():
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


def create_with_rows(p: dict, rows: list[dict], source: str) -> int:
    """A new portfolio and its first rows, as one unit (a fork). Returns its id."""
    now = _now()
    vals = {k: p.get(k) for k in (*PORTFOLIO_FIELDS, "origin", "parent_id", "forked_at", "strategy") if p.get(k) is not None}
    vals["params"] = json.dumps(p["params"]) if p.get("params") is not None else None
    with closing(_connect()) as con, con:
        cols = list(vals) + ["created_at", "updated_at"]
        pid = con.execute(f"INSERT INTO portfolios ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                          (*vals.values(), now, now)).lastrowid
        _write_tags(con, pid, p.get("tags"))
        for r in rows:
            _insert(con, r, source, None, portfolio_id=pid)
    return int(pid)


def replace_sim_run(pid: int, run: dict, rows: list[dict]) -> int:
    """Replace a simulated portfolio's rows with one run's, as one unit: the earlier runs and every row in the
    portfolio go, the run is recorded and its rows stored with it. Returns the run id."""
    with closing(_connect()) as con, con:
        p = con.execute("SELECT mode, origin FROM portfolios WHERE id = ?", (pid,)).fetchone()
        if not p or p["mode"] != "virtual" or p["origin"] != "sim":
            raise ValueError("simulated runs go only into a virtual portfolio made for simulations")
        con.execute("DELETE FROM transactions WHERE portfolio_id = ?", (pid,))
        con.execute("DELETE FROM sim_runs WHERE portfolio_id = ?", (pid,))
        run_id = con.execute(
            'INSERT INTO sim_runs (portfolio_id, strategy, params, start, "end", data_asof, status, rows, message, at) '
            "VALUES (?, ?, ?, ?, ?, ?, 'ok', ?, ?, ?)",
            (pid, run["strategy"], json.dumps(run.get("params") or {}), str(run["start"])[:10],
             str(run["end"])[:10] if run.get("end") else None, run.get("data_asof"), len(rows), run.get("message"),
             _now())).lastrowid
        for i, r in enumerate(rows):
            _insert(con, r | {"ext_ref": r.get("ext_ref") or f"sim:{run['strategy']}:{i}"}, "sim", None,
                    portfolio_id=pid, run_id=run_id)
    return int(run_id)


def sim_runs(pid: int) -> list[dict]:
    if not _exists():
        return []
    with closing(_connect()) as con:
        return [dict(r) | {"params": json.loads(r["params"])} for r in
                con.execute("SELECT * FROM sim_runs WHERE portfolio_id = ? ORDER BY id", (pid,))]


# ---------------- symbol map, meta ----------------

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

EXPORT_COLS = ["symbol", "date", "type", "quantity", "price", "fee", "amount", "currency", "fx_rate", "portfolio",
               "note", "source", "ext_ref"]


def export_transactions_csv(portfolios: list[int] | None = None) -> str:
    """Rows as CSV: your real portfolios (archived ones too) unless `portfolios` (ids) is given."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=EXPORT_COLS, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    w.writerows(transactions(portfolios=portfolio_ids("real", include_archived=True) if portfolios is None
                             else portfolios))
    return buf.getvalue()


def _num(v) -> float | None:
    return float(v) if v not in (None, "") else None


def import_transactions_csv(text: str) -> int:
    """Load an exported set (restoring the CI bundle): each portfolio it names (the older `account` column too;
    empty means the default portfolio) gets exactly these rows. Returns the number of rows."""
    rows = [{**r, "quantity": _num(r.get("quantity")), "price": _num(r.get("price")), "fee": _num(r.get("fee")) or 0.0,
             "amount": _num(r.get("amount")), "fx_rate": _num(r.get("fx_rate")), "currency": r.get("currency") or None,
             "portfolio": r.get("portfolio") or r.get("account") or None, "note": r.get("note") or None,
             "ext_ref": r.get("ext_ref") or None}
            for r in csv.DictReader(io.StringIO(text))]
    with closing(_connect()) as con, con:
        pids = [_target(con, r, create=True) for r in rows]
        for pid in set(pids):
            con.execute("DELETE FROM transactions WHERE portfolio_id = ?", (pid,))
        for r, pid in zip(rows, pids):
            _insert(con, r, r.get("source") or "bundle", None, portfolio_id=pid)
    return len(rows)


# ---------------- market views (your subjective beliefs; config/views.yaml has templates) ----------------

VIEW_FIELDS = ("statement", "conviction", "horizon", "rationale", "falsifier", "template", "status")


def _view_rows(con, where: str = "", args: tuple = ()) -> list[dict]:
    out = []
    for r in con.execute(f"SELECT * FROM views {where} ORDER BY status, conviction DESC, id", args):
        v = dict(r)
        v["exposures"] = [dict(e) for e in con.execute(
            "SELECT kind, key, effect FROM view_exposures WHERE view_id = ? ORDER BY effect DESC, kind, key", (v["id"],))]
        v["indicators"] = [dict(i) for i in con.execute(
            "SELECT indicator, expect FROM view_indicators WHERE view_id = ? ORDER BY indicator", (v["id"],))]
        out.append(v)
    return out


def views(status: str | None = None) -> list[dict]:
    """Your market views with their exposures and indicators ([] without a database)."""
    if not _exists():
        return []
    with closing(_connect()) as con:
        return _view_rows(con, "WHERE status = ?", (status,)) if status else _view_rows(con)


def get_view(view_id: int) -> dict | None:
    if not _exists():
        return None
    with closing(_connect()) as con:
        rows = _view_rows(con, "WHERE id = ?", (view_id,))
        return rows[0] if rows else None


def _write_children(con, view_id: int, v: dict) -> None:
    con.execute("DELETE FROM view_exposures WHERE view_id = ?", (view_id,))
    con.execute("DELETE FROM view_indicators WHERE view_id = ?", (view_id,))
    con.executemany("INSERT INTO view_exposures (view_id, kind, key, effect) VALUES (?, ?, ?, ?)",
                    [(view_id, e["kind"], e["key"].strip(), int(e["effect"])) for e in v.get("exposures") or []])
    con.executemany("INSERT INTO view_indicators (view_id, indicator, expect) VALUES (?, ?, ?)",
                    [(view_id, i["indicator"], i["expect"]) for i in v.get("indicators") or []])


def save_view(v: dict, view_id: int | None = None) -> int:
    """Add a view, or replace one (statement, fields, exposures and indicators). Returns its id."""
    now = _now()
    vals = {k: v.get(k) for k in VIEW_FIELDS}
    vals["status"] = vals["status"] or "active"
    vals["conviction"] = int(vals["conviction"] or 3)
    vals["horizon"] = vals["horizon"] or "12m"
    with closing(_connect()) as con, con:
        if view_id is None:
            cur = con.execute(f"INSERT INTO views ({', '.join(VIEW_FIELDS)}, created_at, updated_at) "
                              f"VALUES ({', '.join('?' * len(VIEW_FIELDS))}, ?, ?)",
                              (*vals.values(), v.get("created_at") or now, now))
            view_id = cur.lastrowid
        else:
            con.execute(f"UPDATE views SET {', '.join(f'{k} = ?' for k in VIEW_FIELDS)}, updated_at = ? WHERE id = ?",
                        (*vals.values(), now, view_id))
        _write_children(con, view_id, v)
    return view_id


def delete_view(view_id: int) -> dict | None:
    """Delete a view; returns it (with its id), so restore_view can undo the delete."""
    v = get_view(view_id)
    if v:
        with closing(_connect()) as con, con:
            con.execute("DELETE FROM views WHERE id = ?", (view_id,))
    return v


def restore_view(v: dict) -> int:
    with closing(_connect()) as con, con:
        con.execute(f"INSERT INTO views (id, {', '.join(VIEW_FIELDS)}, created_at, updated_at) "
                    f"VALUES (?, {', '.join('?' * len(VIEW_FIELDS))}, ?, ?)",
                    (v["id"], *(v.get(k) for k in VIEW_FIELDS), v["created_at"], _now()))
        _write_children(con, v["id"], v)
    return v["id"]


def views_version() -> str:
    """Changes whenever a view is added, edited or deleted (for caching alignment results)."""
    if not _exists():
        return "0"
    with closing(_connect()) as con:
        r = con.execute("SELECT COUNT(*) AS n, MAX(updated_at) AS t FROM views").fetchone()
        return f"{r['n']}:{r['t']}"


def export_views_json() -> str:
    return json.dumps([{k: v for k, v in x.items() if k != "id"} for x in views()], indent=1, ensure_ascii=False)


def import_views_json(text: str) -> int:
    """Replace all views with an exported set (restoring the CI bundle). Returns the number of views."""
    rows = json.loads(text)
    with closing(_connect()) as con, con:
        con.execute("DELETE FROM views")
    for v in rows:
        save_view(v)
    return len(rows)
