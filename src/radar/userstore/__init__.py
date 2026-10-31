"""Your own stateful data in radar.db in the data folder (SQLite; never committed): portfolios (real and virtual,
with tags), transactions (the source of truth), imports, sim_runs, symbol_map, watchlist edits, meta and market
views, and the tax estimate's persons, instruments and openings. It is the one place that decides which
portfolios count as yours.

The rules: docs/data-conventions.md, *Your portfolios*; the migrations: docs/architecture.md, *Where data lives*.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from ..errors import Conflict
from ..jsonsafe import dumps
from ..paths import USERDATA
from . import backups

DB_NAME = "radar.db"

# Append-only: a schema change is a new entry, never an edit to an old one. A tuple of statements runs as one unit
# (for rebuilding a table); see _migrate.
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
    # what a snapshot import replaced, and the copy taken before it: undoing it can't bring those rows back
    ("ALTER TABLE imports ADD COLUMN rows_replaced INTEGER NOT NULL DEFAULT 0",
     "ALTER TABLE imports ADD COLUMN backup TEXT"),
    # a broker fee schedule per portfolio (JSON; fees.py), to estimate a trade's commission while it is typed
    "ALTER TABLE portfolios ADD COLUMN fee_schedule TEXT",
    # the tax estimate (tax.py): who owns each real account (SKAT's average is per person over their frie midler),
    # each symbol's ISIN and tax class, and the losses carried in from before the history. "Me" owns every real
    # portfolio until told otherwise.
    ("""CREATE TABLE tax_persons (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         name TEXT NOT NULL UNIQUE CHECK (length(trim(name)) > 0),
         capital_income_rate REAL CHECK (capital_income_rate IS NULL OR (capital_income_rate >= 0
                                                                         AND capital_income_rate <= 1)),
         note TEXT,
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL)""",
     "ALTER TABLE portfolios ADD COLUMN tax_person_id INTEGER REFERENCES tax_persons(id) ON DELETE SET NULL",
     """INSERT INTO tax_persons (name, note, created_at, updated_at)
         VALUES ('Me', 'Owns every real account until you say otherwise', datetime('now'), datetime('now'))""",
     "UPDATE portfolios SET tax_person_id = (SELECT MIN(id) FROM tax_persons) WHERE mode = 'real'",
     """CREATE TABLE instruments (
         symbol TEXT PRIMARY KEY,
         isin TEXT,
         tax_class TEXT CHECK (tax_class IS NULL OR tax_class IN ('stock', 'pl_fund', 'fund', 'dk_distributing')),
         source TEXT NOT NULL CHECK (source IN ('manual', 'import', 'universe', 'discovery')),
         note TEXT,
         updated_at TEXT NOT NULL)""",
     """CREATE TABLE tax_openings (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         year INTEGER NOT NULL CHECK (year BETWEEN 1990 AND 2100),
         pool TEXT NOT NULL CHECK (pool IN ('ask_negative_tax', 'pension_negative_tax', 'listed_loss',
                                            'negative_share_income')),
         portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE CASCADE,
         tax_person_id INTEGER REFERENCES tax_persons(id) ON DELETE CASCADE,
         amount REAL NOT NULL CHECK (amount > 0),
         note TEXT,
         created_at TEXT NOT NULL,
         CHECK ((pool IN ('ask_negative_tax', 'pension_negative_tax') AND portfolio_id IS NOT NULL
                 AND tax_person_id IS NULL)
             OR (pool IN ('listed_loss', 'negative_share_income') AND tax_person_id IS NOT NULL
                 AND portfolio_id IS NULL)))"""),
    # an opening is the årsopgørelse's figure and anchors the carried chain from its year, so 0 ("nothing is
    # carried") is a real answer: the table is rebuilt to allow it, every row kept
    ("""CREATE TABLE tax_openings_new (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         year INTEGER NOT NULL CHECK (year BETWEEN 1990 AND 2100),
         pool TEXT NOT NULL CHECK (pool IN ('ask_negative_tax', 'pension_negative_tax', 'listed_loss',
                                            'negative_share_income')),
         portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE CASCADE,
         tax_person_id INTEGER REFERENCES tax_persons(id) ON DELETE CASCADE,
         amount REAL NOT NULL CHECK (amount >= 0),
         note TEXT,
         created_at TEXT NOT NULL,
         CHECK ((pool IN ('ask_negative_tax', 'pension_negative_tax') AND portfolio_id IS NOT NULL
                 AND tax_person_id IS NULL)
             OR (pool IN ('listed_loss', 'negative_share_income') AND tax_person_id IS NOT NULL
                 AND portfolio_id IS NULL)))""",
     """INSERT INTO tax_openings_new (id, year, pool, portfolio_id, tax_person_id, amount, note, created_at)
         SELECT id, year, pool, portfolio_id, tax_person_id, amount, note, created_at FROM tax_openings""",
     "DROP TABLE tax_openings",
     "ALTER TABLE tax_openings_new RENAME TO tax_openings"),
    # your trading rules (trading_rules.py; the kinds in config/rules.yaml) and the checks you logged against them,
    # with what you then did and why
    ("""CREATE TABLE trading_rules (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         statement TEXT NOT NULL CHECK (length(trim(statement)) > 0),
         kind TEXT NOT NULL,
         params TEXT NOT NULL DEFAULT '{}',
         scope TEXT NOT NULL DEFAULT '{"portfolios": "real"}',
         severity TEXT NOT NULL DEFAULT 'soft' CHECK (severity IN ('hard', 'soft', 'reminder')),
         rationale TEXT,
         template TEXT,
         status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL)""",
     """CREATE TABLE rule_checks (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         at TEXT NOT NULL,
         action TEXT NOT NULL,
         rules_version TEXT NOT NULL,
         verdicts TEXT NOT NULL,
         decision TEXT CHECK (decision IN ('went_ahead', 'changed', 'dropped')),
         reason TEXT,
         transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL)"""),
    # where a view came from when a skill wrote it (scout:<date>:<slug> for a /scout candidate you adopted); set
    # once when the view is added, kept through edits; NULL for views you wrote yourself
    "ALTER TABLE views ADD COLUMN origin TEXT",
]


def connect() -> sqlite3.Connection:
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
    backed up before its first upgrade step. Each step takes the write lock and re-reads the version, so
    connections opened at the same moment (the app's first page load) wait and skip what another one did."""
    version = con.execute("PRAGMA user_version").fetchone()[0]
    if version >= len(MIGRATIONS):
        return
    if version > 0:
        backups.copy(con, f"before-schema-v{len(MIGRATIONS)}")
    level = con.isolation_level
    con.isolation_level = None                    # explicit BEGIN/COMMIT: DDL included in the transaction
    con.execute("PRAGMA foreign_keys = OFF")      # only takes effect outside a transaction
    try:
        for i, step in enumerate(MIGRATIONS[version:], start=version + 1):
            con.execute("BEGIN IMMEDIATE")
            if con.execute("PRAGMA user_version").fetchone()[0] >= i:
                con.execute("ROLLBACK")           # another connection committed this step first
                continue
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
        con.isolation_level = level


def exists() -> bool:
    return (USERDATA / DB_NAME).exists()


def new_id(cur: sqlite3.Cursor) -> int:
    """The id of the row an INSERT just added."""
    if cur.lastrowid is None:
        raise sqlite3.DatabaseError("the insert added no row")
    return cur.lastrowid


def timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------- watchlist overlay ----------------

def _set(symbol: str, action: str) -> None:
    with closing(connect()) as con, con:
        con.execute("INSERT INTO watchlist (symbol, action, updated_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(symbol) DO UPDATE SET action = excluded.action, updated_at = excluded.updated_at",
                    (symbol, action, timestamp()))


def watch(symbol: str) -> None:
    _set(symbol, "add")


def unwatch(symbol: str) -> None:
    _set(symbol, "remove")


def watchlist_overlay() -> dict[str, str]:
    """symbol -> 'add' | 'remove'. Empty when no database exists yet (nothing is created just by reading)."""
    if not exists():
        return {}
    with closing(connect()) as con:
        return {r["symbol"]: r["action"] for r in con.execute("SELECT symbol, action FROM watchlist ORDER BY symbol")}


def export_watchlist_csv() -> str:
    """The overlay as CSV text (for the holdings bundle)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["symbol", "action"])
    w.writerows(watchlist_overlay().items())
    return buf.getvalue()


def import_watchlist_csv(text: str) -> int:
    """Load an exported overlay (replaces the current one). Returns the number of rows."""
    rows = [(r["symbol"], r["action"]) for r in csv.DictReader(io.StringIO(text))]
    now = timestamp()
    with closing(connect()) as con, con:
        con.execute("DELETE FROM watchlist")
        con.executemany("INSERT INTO watchlist (symbol, action, updated_at) VALUES (?, ?, ?)",
                        [(s, a, now) for s, a in rows])
    return len(rows)


def backup(reason: str) -> str | None:
    """Copy the database to backups/ (before imports and undos); keeps the newest BACKUPS_KEPT."""
    if not exists():
        return None
    with closing(connect()) as con:
        return backups.copy(con, reason)


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
        p["fee_schedule"] = json.loads(p["fee_schedule"]) if p["fee_schedule"] else None
        p["tags"] = [t["tag"] for t in con.execute(
            "SELECT tag FROM portfolio_tags WHERE portfolio_id = ? ORDER BY tag", (p["id"],))]
        p["is_default"] = p["id"] == default
        out.append(p)
    return out


def portfolios(include_archived: bool = True) -> list[dict]:
    """Every portfolio with its tags, number of rows and date range ([] without a database)."""
    if not exists():
        return []
    with closing(connect()) as con:
        return _portfolio_rows(con, "" if include_archived else "WHERE p.archived = 0")


def get_portfolio(pid: int) -> dict | None:
    if not exists():
        return None
    with closing(connect()) as con:
        rows = _portfolio_rows(con, "WHERE p.id = ?", (pid,))
        return rows[0] if rows else None


def portfolio_by_name(name: str | None) -> dict | None:
    if not exists() or not name or not name.strip():
        return None
    with closing(connect()) as con:
        rows = _portfolio_rows(con, "WHERE p.name = ?", (name.strip(),))
        return rows[0] if rows else None


def _write_tags(con, pid: int, tags) -> None:
    clean = sorted({norm_tag(t) for t in tags or [] if norm_tag(t)})
    for t in clean:
        if len(t) > 32:
            raise ValueError(f"tag too long (32 characters at most): {t!r}")
    con.execute("DELETE FROM portfolio_tags WHERE portfolio_id = ?", (pid,))
    con.executemany("INSERT INTO portfolio_tags (portfolio_id, tag) VALUES (?, ?)", [(pid, t) for t in clean])


class NameTaken(Conflict):
    """Another portfolio already has that name."""


def save_portfolio(p: dict, pid: int | None = None) -> int:
    """Add a portfolio, or update one (only the fields given; tags are replaced when `tags` is given). Refuses an
    unknown kind, mode or dividend policy, a name another portfolio has (NameTaken) and making a simulated
    portfolio real: its trades never happened."""
    now = timestamp()
    for key, allowed in (("kind", PORTFOLIO_KINDS), ("mode", PORTFOLIO_MODES), ("dividends", DIVIDEND_POLICIES)):
        if p.get(key) is not None and p[key] not in allowed:
            raise ValueError(f"{key} must be one of {', '.join(allowed)}")
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
    if "fee_schedule" in p:                        # None clears it
        vals["fee_schedule"] = json.dumps(p["fee_schedule"]) if p["fee_schedule"] else None
    if "tax_person_id" in p:                       # None: nobody (no tax estimate for the account)
        vals["tax_person_id"] = p["tax_person_id"]
    with closing(connect()) as con, con:
        if vals.get("tax_person_id") is not None and not con.execute(
                "SELECT 1 FROM tax_persons WHERE id = ?", (vals["tax_person_id"],)).fetchone():
            raise ValueError(f"no tax person with id {vals['tax_person_id']}")
        if "name" in vals and con.execute("SELECT 1 FROM portfolios WHERE name = ? AND id IS NOT ?",
                                          (vals["name"], pid)).fetchone():
            raise NameTaken(f"there is already a portfolio called {vals['name']}")
        if pid is not None and vals.get("mode") == "real" and (con.execute(
                "SELECT origin FROM portfolios WHERE id = ?", (pid,)).fetchone() or {"origin": None})["origin"] == "sim":
            raise ValueError("a simulated portfolio stays virtual: its trades never happened")
        if pid is None:
            if "name" not in vals:
                raise ValueError("a portfolio needs a name")
            if "tax_person_id" not in p and vals.get("mode", "real") == "real":
                first = con.execute("SELECT MIN(id) AS id FROM tax_persons").fetchone()
                vals["tax_person_id"] = first["id"] if first else None
            cols = list(vals) + ["created_at", "updated_at"]
            pid = new_id(con.execute(f"INSERT INTO portfolios ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                              (*vals.values(), now, now)))
        elif vals:
            con.execute(f"UPDATE portfolios SET {', '.join(f'{k} = ?' for k in vals)}, updated_at = ? WHERE id = ?",
                        (*vals.values(), now, pid))
        if "tags" in p:
            _write_tags(con, pid, p["tags"])
        # the default must stay a real, active portfolio
        if (vals.get("archived") or vals.get("mode") == "virtual") and _default_id(con) == pid:
            con.execute("DELETE FROM meta WHERE key = 'default_portfolio'")
    return int(pid)


def set_tags(pid: int, tags) -> list[str]:
    with closing(connect()) as con, con:
        _write_tags(con, pid, tags)
        return [r["tag"] for r in con.execute("SELECT tag FROM portfolio_tags WHERE portfolio_id = ? ORDER BY tag", (pid,))]


def compared_ids() -> list[int]:
    """What a comparison shows when nothing is chosen: each of your active real portfolios that has rows."""
    return [p["id"] for p in portfolios(include_archived=False) if p["mode"] == "real" and p["n_tx"]]


def all_tags() -> list[dict]:
    """Every tag in use, with how many portfolios carry it."""
    if not exists():
        return []
    with closing(connect()) as con:
        return [dict(r) for r in con.execute("SELECT tag, COUNT(*) AS n FROM portfolio_tags GROUP BY tag ORDER BY tag")]


def _default_id(con) -> int | None:
    r = con.execute("SELECT value FROM meta WHERE key = 'default_portfolio'").fetchone()
    if not r:
        return None
    pid = json.loads(r["value"])
    return pid if con.execute("SELECT 1 FROM portfolios WHERE id = ?", (pid,)).fetchone() else None


def default_portfolio() -> int | None:
    if not exists():
        return None
    with closing(connect()) as con:
        return _default_id(con)


def set_default_portfolio(pid: int) -> None:
    with closing(connect()) as con, con:
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
        now = timestamp()
        return new_id(con.execute("INSERT INTO portfolios (name, created_at, updated_at) VALUES (?, ?, ?)",
                           (name, now, now)))
    if fallback is not None:
        return fallback
    pid = _default_id(con)
    if pid is None:
        r = con.execute("SELECT id FROM portfolios WHERE name = 'Main'").fetchone()
        now = timestamp()
        pid = r["id"] if r else new_id(con.execute(
            "INSERT INTO portfolios (name, note, created_at, updated_at) VALUES ('Main', ?, ?, ?)",
            ("Trades entered without choosing a portfolio", now, now)))
        con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('default_portfolio', ?)", (json.dumps(pid),))
    return int(pid)


def portfolio_ids(scope: str = "real", ids=None, tags=None, include_archived: bool = False) -> list[int]:
    """The single resolver for "which portfolios": the ones named by id or carrying one of `tags` (an explicit
    choice: virtual and archived ones included), else every portfolio in `scope` (default: the real ones that
    aren't archived, i.e. yours)."""
    if not exists():
        return []
    with closing(connect()) as con:
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
        raise Conflict(f"{p['name']} has {p['n_tx']} transactions: move them first, or archive it")
    if p["n_tx"]:
        backup(f"before-delete-portfolio-{pid}")
    with closing(connect()) as con, con:
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
    with closing(connect()) as con, con:
        return con.execute(f"UPDATE transactions SET portfolio_id = ?, updated_at = ? WHERE {' AND '.join(where)}",
                           [to_id, timestamp(), *args]).rowcount


BUNDLE_PORTFOLIO_KEYS = (*PORTFOLIO_FIELDS, "origin", "forked_at", "strategy", "params", "fee_schedule", "tags",
                         "is_default")


def export_portfolios_json(scope: str = "real") -> str:
    """Portfolios with their kind, mode, tags and notes (the holdings bundle; real ones by default)."""
    keep = set(portfolio_ids(scope, include_archived=True))
    rows = [{k: p[k] for k in BUNDLE_PORTFOLIO_KEYS} for p in portfolios() if p["id"] in keep]
    return dumps(rows, indent=1, ensure_ascii=False)


def import_portfolios_json(text: str) -> int:
    """Add or update portfolios by name from an export (their transactions come separately)."""
    rows = json.loads(text)
    connect().close()                            # the schema (and its seeded portfolios) first: matched by name
    for p in rows:
        found = portfolio_by_name(p["name"])
        pid = save_portfolio({k: v for k, v in p.items() if k != "is_default"}, found["id"] if found else None)
        if p.get("is_default"):
            set_default_portfolio(pid)
    return len(rows)


# ---------------- tax: persons, instruments, openings ----------------

TAX_CLASSES = ("stock", "pl_fund", "fund", "dk_distributing")
INSTRUMENT_SOURCES = ("manual", "import", "universe", "discovery")   # a manual row is never overwritten by the rest
OPENING_POOLS = {"ask_negative_tax": "portfolio", "pension_negative_tax": "portfolio",
                 "listed_loss": "person", "negative_share_income": "person"}
ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")


def tax_persons() -> list[dict]:
    """The tax persons with the portfolios each owns ([] without a database)."""
    if not exists():
        return []
    with closing(connect()) as con:
        out = [dict(r) for r in con.execute("SELECT * FROM tax_persons ORDER BY id")]
        for p in out:
            p["portfolio_ids"] = [r[0] for r in con.execute(
                "SELECT id FROM portfolios WHERE tax_person_id = ? ORDER BY id", (p["id"],))]
        return out


def save_tax_person(p: dict, pid: int | None = None) -> int:
    """Add a tax person or update one (name, capital_income_rate as a fraction or None, note)."""
    vals = {k: p[k] for k in ("name", "capital_income_rate", "note") if k in p}
    if "name" in vals:
        vals["name"] = (vals["name"] or "").strip()
        if not vals["name"]:
            raise ValueError("a tax person needs a name")
    rate = vals.get("capital_income_rate")
    if rate is not None and not 0 <= float(rate) <= 1:
        raise ValueError("capital_income_rate is a fraction between 0 and 1 (0.37 for 37 %)")
    now = timestamp()
    with closing(connect()) as con, con:
        if "name" in vals and con.execute("SELECT 1 FROM tax_persons WHERE name = ? AND id IS NOT ?",
                                          (vals["name"], pid)).fetchone():
            raise NameTaken(f"there is already a tax person called {vals['name']}")
        if pid is None:
            if "name" not in vals:
                raise ValueError("a tax person needs a name")
            cols = list(vals) + ["created_at", "updated_at"]
            return new_id(con.execute(f"INSERT INTO tax_persons ({', '.join(cols)}) VALUES "
                                      f"({', '.join('?' * len(cols))})", (*vals.values(), now, now)))
        if vals:
            con.execute(f"UPDATE tax_persons SET {', '.join(f'{k} = ?' for k in vals)}, updated_at = ? WHERE id = ?",
                        (*vals.values(), now, pid))
        return int(pid)


def instruments() -> dict[str, dict]:
    """symbol -> {isin, tax_class, source, note} ({} without a database)."""
    if not exists():
        return {}
    with closing(connect()) as con:
        return {r["symbol"]: dict(r) for r in con.execute("SELECT * FROM instruments ORDER BY symbol")}


def save_instrument(symbol: str, source: str = "manual", **fields) -> bool:
    """Set a symbol's `isin`, `tax_class` (None = decided automatically) or `note`. A row set by hand (`manual`) is
    never overwritten by an automatic fill. True when something was written."""
    if source not in INSTRUMENT_SOURCES:
        raise ValueError(f"source must be one of {', '.join(INSTRUMENT_SOURCES)}")
    sym = symbol.strip().upper()
    vals = {k: fields[k] for k in ("isin", "tax_class", "note") if k in fields}
    if vals.get("tax_class") is not None and vals["tax_class"] not in TAX_CLASSES:
        raise ValueError(f"tax_class must be one of {', '.join(TAX_CLASSES)}")
    if vals.get("isin"):
        vals["isin"] = vals["isin"].strip().upper()
        if not ISIN.fullmatch(vals["isin"]):
            raise ValueError(f"{vals['isin']} isn't an ISIN (two letters, nine letters or digits, a check digit)")
    with closing(connect()) as con, con:
        row = con.execute("SELECT source FROM instruments WHERE symbol = ?", (sym,)).fetchone()
        if row and row["source"] == "manual" and source != "manual":
            return False
        if row:
            sets = [f"{k} = ?" for k in vals] + ["source = ?", "updated_at = ?"]
            con.execute(f"UPDATE instruments SET {', '.join(sets)} WHERE symbol = ?",
                        (*vals.values(), source, timestamp(), sym))
        else:
            cols = ["symbol", *vals, "source", "updated_at"]
            con.execute(f"INSERT INTO instruments ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                        (sym, *vals.values(), source, timestamp()))
        return True


def symbol_isins() -> dict[str, str]:
    """symbol -> ISIN from the symbol map: what a broker import matched (an ISIN key mapped to a symbol)."""
    if not exists():
        return {}
    with closing(connect()) as con:
        return {r["symbol"]: r["ext"] for r in con.execute("SELECT ext, symbol FROM symbol_map ORDER BY updated_at")
                if ISIN.fullmatch(r["ext"])}


def tax_openings() -> list[dict]:
    if not exists():
        return []
    with closing(connect()) as con:
        return [dict(r) for r in con.execute("SELECT * FROM tax_openings ORDER BY year, pool, id")]


def add_tax_opening(row: dict) -> int:
    """What the årsopgørelse for `year` - 1 carries into `year`, in DKK: an ASK's or pension account's negative tax
    (by `portfolio_id`), or a person's listed-share loss or negative share income (by `tax_person_id`). It replaces
    the radar's own chain from that year; 0 says nothing is carried."""
    pool = row.get("pool")
    if pool not in OPENING_POOLS:
        raise ValueError(f"pool must be one of {', '.join(OPENING_POOLS)}")
    owner = "portfolio_id" if OPENING_POOLS[pool] == "portfolio" else "tax_person_id"
    if row.get(owner) is None:
        raise ValueError(f"a {pool} opening needs {owner}")
    if row.get("amount") is None or float(row["amount"]) < 0:
        raise ValueError("an opening is an amount in DKK, 0 or more")
    with closing(connect()) as con, con:
        return new_id(con.execute(
            f"INSERT INTO tax_openings (year, pool, {owner}, amount, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (int(row["year"]), pool, int(row[owner]), float(row["amount"]), row.get("note"), timestamp())))


def delete_tax_opening(oid: int) -> bool:
    with closing(connect()) as con, con:
        return con.execute("DELETE FROM tax_openings WHERE id = ?", (oid,)).rowcount > 0


def export_tax_json() -> str:
    """Tax persons (with the portfolios they own, by name), instruments and openings, for the export."""
    names = {p["id"]: p["name"] for p in portfolios()}
    persons = tax_persons()
    pname = {p["id"]: p["name"] for p in persons}
    return dumps({
        "persons": [{"name": p["name"], "capital_income_rate": p["capital_income_rate"], "note": p["note"],
                     "portfolios": [names[i] for i in p["portfolio_ids"] if i in names]} for p in persons],
        "instruments": [{k: v for k, v in r.items() if k != "updated_at"} for r in instruments().values()],
        "openings": [{"year": o["year"], "pool": o["pool"], "amount": o["amount"], "note": o["note"],
                      "portfolio": names.get(o["portfolio_id"]), "person": pname.get(o["tax_person_id"])}
                     for o in tax_openings()],
    }, indent=1, ensure_ascii=False)


def import_tax_json(text: str) -> int:
    """An export's tax.json read back: persons by name (and the portfolios they own), instruments, openings (one
    already there isn't added twice). Returns the number of rows read."""
    d = json.loads(text)
    by_name = {p["name"]: p["id"] for p in tax_persons()}
    for p in d.get("persons", []):
        pid = save_tax_person({k: p.get(k) for k in ("name", "capital_income_rate", "note")}, by_name.get(p["name"]))
        by_name[p["name"]] = pid
        for name in p.get("portfolios", []):
            found = portfolio_by_name(name)
            if found:
                save_portfolio({"tax_person_id": pid}, found["id"])
    for r in d.get("instruments", []):
        save_instrument(r["symbol"], r.get("source") or "manual", **{k: r.get(k) for k in ("isin", "tax_class", "note")})
    have = {(o["year"], o["pool"], o["portfolio_id"], o["tax_person_id"], o["amount"]) for o in tax_openings()}
    for o in d.get("openings", []):
        pf = portfolio_by_name(o.get("portfolio")) if o.get("portfolio") else None
        row = {"year": o["year"], "pool": o["pool"], "amount": o["amount"], "note": o.get("note"),
               "portfolio_id": pf["id"] if pf else None, "tax_person_id": by_name.get(o.get("person") or "")}
        if (row["year"], row["pool"], row["portfolio_id"], row["tax_person_id"], row["amount"]) not in have:
            add_tax_opening(row)
    return len(d.get("persons", [])) + len(d.get("instruments", [])) + len(d.get("openings", []))


# ---------------- transactions ----------------

TX_FIELDS = ("symbol", "date", "type", "quantity", "price", "fee", "amount", "currency", "fx_rate", "note", "ext_ref")
TRADE_TYPES = ("BUY", "SELL")
CASH_TYPES = ("DEPOSIT", "WITHDRAW", "DIVIDEND", "FEE", "INTEREST")
# every row type there is; the schema's CHECK (a migration, never edited) and api_models.TxType list the same
# (tests/test_userstore.py holds them to it)
TYPES = TRADE_TYPES + CASH_TYPES


def transactions(symbol: str | None = None, portfolios: list[int] | None = None, types=None) -> list[dict]:
    """Stored rows, oldest first, each with its portfolio's name: every portfolio unless `portfolios` (ids) is
    given. Nothing is created just by reading."""
    if not exists():
        return []
    where: list[str] = []
    args: list = []
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
    with closing(connect()) as con:
        return [dict(r) for r in con.execute(sql, args)]


def get_tx(tx_id: int) -> dict | None:
    if not exists():
        return None
    with closing(connect()) as con:
        r = con.execute("SELECT t.*, p.name AS portfolio FROM transactions t JOIN portfolios p ON p.id = t.portfolio_id "
                        "WHERE t.id = ?", (tx_id,)).fetchone()
        return dict(r) if r else None


def transactions_version() -> str:
    """Changes whenever a row or a portfolio is added, edited, moved or deleted (for caching results)."""
    if not exists():
        return "0"
    with closing(connect()) as con:
        t = con.execute("SELECT COUNT(*), MAX(updated_at), TOTAL(id), TOTAL(portfolio_id * id) FROM transactions").fetchone()
        p = con.execute("SELECT COUNT(*), MAX(updated_at) FROM portfolios").fetchone()
        return ":".join(str(x) for x in (*t, *p))


def _insert(con: sqlite3.Connection, row: dict, source: str, import_id: int | None,
            tx_id: int | None = None, created: str | None = None, portfolio_id: int | None = None,
            run_id: int | None = None) -> int:
    now = timestamp()
    v = {k: row.get(k) for k in TX_FIELDS}
    pid = portfolio_id if portfolio_id is not None else _target(con, row)
    cur = con.execute(
        "INSERT INTO transactions (id, portfolio_id, symbol, date, type, quantity, price, fee, amount, currency, "
        "fx_rate, note, ext_ref, source, import_id, run_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (tx_id, pid, v["symbol"], str(v["date"])[:10], v["type"], v["quantity"], v["price"], v["fee"] or 0,
         v["amount"], v["currency"], v["fx_rate"], v["note"], v["ext_ref"], source, import_id, run_id,
         created or now, now))
    return new_id(cur)


def add_tx(row: dict, source: str = "manual") -> int:
    with closing(connect()) as con, con:
        return _insert(con, row, source, None)


def update_tx(tx_id: int, row: dict) -> bool:
    fields = {k: row[k] for k in TX_FIELDS if k in row}
    if "fee" in fields:
        fields["fee"] = fields["fee"] or 0
    if "date" in fields:
        fields["date"] = str(fields["date"])[:10]
    with closing(connect()) as con, con:
        if any(row.get(k) is not None for k in ("portfolio_id", "portfolio", "account")):
            fields["portfolio_id"] = _target(con, row)
        if not fields:
            return False
        sets = ", ".join(f"{k} = ?" for k in fields) + ", updated_at = ?"
        return con.execute(f"UPDATE transactions SET {sets} WHERE id = ?", [*fields.values(), timestamp(), tx_id]).rowcount == 1


def delete_tx(tx_id: int) -> dict | None:
    """Delete one transaction; returns the deleted row so it can be restored (undo)."""
    row = get_tx(tx_id)
    if row:
        with closing(connect()) as con, con:
            con.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    return row


def restore_tx(row: dict) -> int:
    """Put a deleted transaction back with its original id and provenance."""
    with closing(connect()) as con, con:
        imp = row.get("import_id")
        if imp is not None and not con.execute("SELECT 1 FROM imports WHERE id = ?", (imp,)).fetchone():
            imp = None                            # its import was undone since: keep the row, drop the link
        pid = row.get("portfolio_id")
        if pid is not None and not con.execute("SELECT 1 FROM portfolios WHERE id = ?", (pid,)).fetchone():
            pid = None                            # its portfolio is gone: by name, else the default
        return _insert(con, {**row, "portfolio_id": pid}, row["source"], imp, row["id"], row.get("created_at"))


def _r6(v) -> float | None:
    return None if v is None else round(float(v), 6)


def trade_key(r: dict) -> tuple:
    """What makes two rows the same trade, whichever portfolio they are in."""
    return (r.get("symbol"), str(r["date"])[:10], r["type"], _r6(r.get("quantity")), _r6(r.get("price")),
            _r6(r.get("amount")))


def add_import(rows: list[dict], source: str, file_name: str | None = None, replace_source: bool = False,
               portfolio_id: int | None = None) -> dict:
    """Store an import as one unit, into `portfolio_id` (default: the default portfolio) unless a row names its
    own portfolio (created as a real one if new). Rows already stored (same broker trade id, or same symbol,
    date, type, quantity and price) are skipped: in any real portfolio when importing into a real one, so trades
    moved to another account aren't imported twice; in the target only when importing into a virtual one.
    `replace_source` first removes the target's earlier rows from this source (for a snapshot export such as
    Yahoo's, which always contains the full history). A backup is taken first."""
    copy = backup(f"before-{source}-import")
    with closing(connect()) as con, con:
        target = _target(con, {}, portfolio_id)
        replaced = con.execute("DELETE FROM transactions WHERE source = ? AND portfolio_id = ?",
                               (source, target)).rowcount if replace_source else 0
        existing = [dict(r) for r in con.execute(
            "SELECT t.symbol, t.date, t.type, t.quantity, t.price, t.amount, t.ext_ref FROM transactions t "
            "JOIN portfolios p ON p.id = t.portfolio_id WHERE t.portfolio_id = ? OR (p.mode = 'real' AND "
            "(SELECT mode FROM portfolios WHERE id = ?) = 'real')", (target, target))]
        keys = {trade_key(r) for r in existing}
        refs = {r["ext_ref"] for r in existing if r["ext_ref"]}
        imp = new_id(con.execute("INSERT INTO imports (source, file_name, at, portfolio_id, rows_replaced, backup) "
                          "VALUES (?, ?, ?, ?, ?, ?)",
                          (source, file_name, timestamp(), target, replaced, Path(copy).name if copy else None)))
        added = skipped = 0
        for r in rows:
            if (r.get("ext_ref") and r["ext_ref"] in refs) or trade_key(r) in keys:
                skipped += 1
                continue
            pid = _target(con, r, target, create=True)
            _insert(con, r, source, imp, portfolio_id=pid)   # only rows stored *before* this import count as
            added += 1                                       # duplicates: two identical fills in one file are real
        con.execute("UPDATE imports SET rows_added = ?, rows_skipped = ? WHERE id = ?", (added, skipped, imp))
    return {"id": int(imp), "added": added, "skipped": skipped, "replaced": replaced}


def imports() -> list[dict]:
    """Past imports, newest first, with how many of their rows are still in the store."""
    if not exists():
        return []
    with closing(connect()) as con:
        out = []
        for r in con.execute("SELECT i.*, p.name AS portfolio FROM imports i "
                             "LEFT JOIN portfolios p ON p.id = i.portfolio_id ORDER BY i.id DESC").fetchall():
            n = con.execute("SELECT COUNT(*) FROM transactions WHERE import_id = ?", (r["id"],)).fetchone()[0]
            out.append(dict(r) | {"rows_now": n})
        return out


def undo_import(import_id: int) -> int:
    """Remove every transaction an import added (a backup is taken first). Returns the number removed. An import
    that replaced earlier rows (a snapshot such as Yahoo's) is refused: removing its rows wouldn't bring back the
    ones it replaced, so the way back is the copy of the database taken before it."""
    with closing(connect()) as con:
        imp = con.execute("SELECT rows_replaced, backup, at FROM imports WHERE id = ?", (import_id,)).fetchone()
    if imp and imp["rows_replaced"]:
        raise Conflict(f"This import replaced {imp['rows_replaced']} earlier rows, which undoing it can't bring "
                         f"back. Restore the copy taken just before it instead: {imp['backup'] or 'see backups/'} "
                         "(in backups/ in the data folder; the newest copies are kept), or import the earlier file "
                         "again.")
    backup(f"before-undo-import-{import_id}")
    with closing(connect()) as con, con:
        n = con.execute("DELETE FROM transactions WHERE import_id = ?", (import_id,)).rowcount
        con.execute("DELETE FROM imports WHERE id = ?", (import_id,))
    return n


def create_with_rows(p: dict, rows: list[dict], source: str) -> int:
    """A new portfolio and its first rows, as one unit (a fork). Returns its id."""
    now = timestamp()
    vals = {k: p.get(k) for k in (*PORTFOLIO_FIELDS, "origin", "parent_id", "forked_at", "strategy") if p.get(k) is not None}
    vals["params"] = json.dumps(p["params"]) if p.get("params") is not None else None
    if p.get("fee_schedule"):
        vals["fee_schedule"] = json.dumps(p["fee_schedule"])
    with closing(connect()) as con, con:
        cols = list(vals) + ["created_at", "updated_at"]
        pid = new_id(con.execute(f"INSERT INTO portfolios ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                          (*vals.values(), now, now)))
        _write_tags(con, pid, p.get("tags"))
        for r in rows:
            _insert(con, r, source, None, portfolio_id=pid)
    return int(pid)


def replace_sim_run(pid: int, run: dict, rows: list[dict]) -> int:
    """Replace a simulated portfolio's rows with one run's, as one unit: the earlier runs and every row in the
    portfolio go, the run is recorded and its rows stored with it. Returns the run id."""
    with closing(connect()) as con, con:
        p = con.execute("SELECT mode, origin FROM portfolios WHERE id = ?", (pid,)).fetchone()
        if not p or p["mode"] != "virtual" or p["origin"] != "sim":
            raise ValueError("simulated runs go only into a virtual portfolio made for simulations")
        con.execute("DELETE FROM transactions WHERE portfolio_id = ?", (pid,))
        con.execute("DELETE FROM sim_runs WHERE portfolio_id = ?", (pid,))
        run_id = new_id(con.execute(
            'INSERT INTO sim_runs (portfolio_id, strategy, params, start, "end", data_asof, status, rows, message, at) '
            "VALUES (?, ?, ?, ?, ?, ?, 'ok', ?, ?, ?)",
            (pid, run["strategy"], json.dumps(run.get("params") or {}), str(run["start"])[:10],
             str(run["end"])[:10] if run.get("end") else None, run.get("data_asof"), len(rows), run.get("message"),
             timestamp())))
        for i, r in enumerate(rows):
            _insert(con, r | {"ext_ref": r.get("ext_ref") or f"sim:{run['strategy']}:{i}"}, "sim", None,
                    portfolio_id=pid, run_id=run_id)
    return int(run_id)


def sim_runs(pid: int) -> list[dict]:
    if not exists():
        return []
    with closing(connect()) as con:
        return [dict(r) | {"params": json.loads(r["params"])} for r in
                con.execute("SELECT * FROM sim_runs WHERE portfolio_id = ? ORDER BY id", (pid,))]


# ---------------- symbol map, meta ----------------

def mapped_symbol(ext: str) -> str | None:
    if not exists():
        return None
    with closing(connect()) as con:
        r = con.execute("SELECT symbol FROM symbol_map WHERE ext = ?", (ext.strip().upper(),)).fetchone()
        return r["symbol"] if r else None


def map_symbol(ext: str, symbol: str) -> None:
    with closing(connect()) as con, con:
        con.execute("INSERT INTO symbol_map (ext, symbol, updated_at) VALUES (?, ?, ?) ON CONFLICT(ext) DO UPDATE "
                    "SET symbol = excluded.symbol, updated_at = excluded.updated_at", (ext.strip().upper(), symbol, timestamp()))


def meta_get(key: str, default=None):
    if not exists():
        return default
    with closing(connect()) as con:
        r = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return json.loads(r["value"]) if r else default


def meta_set(key: str, value) -> None:
    with closing(connect()) as con, con:
        con.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, json.dumps(value)))



# ---------------- SEC's contact address (the User-Agent EDGAR asks for) ----------------

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def sec_contact() -> str | None:
    return meta_get("sec_contact")


def set_sec_contact(email: str | None) -> str | None:
    """Store (or with None/"" remove) the contact e-mail sent to SEC; raises ValueError for a malformed one."""
    email = (email or "").strip() or None
    if email is not None and not EMAIL.match(email):
        raise ValueError(f"{email!r} doesn't look like an e-mail address")
    meta_set("sec_contact", email)
    return email

# ---------------- CSV round trip (backup download, holdings bundle) ----------------

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


def _cell_float(v) -> float | None:
    """A CSV cell as a float; an empty one is None."""
    return float(v) if v not in (None, "") else None


def import_transactions_csv(text: str) -> int:
    """Load an exported set (restoring a holdings bundle): each portfolio it names (the older `account` column too;
    empty means the default portfolio) gets exactly these rows. Returns the number of rows."""
    rows = [{**r, "quantity": _cell_float(r.get("quantity")), "price": _cell_float(r.get("price")), "fee": _cell_float(r.get("fee")) or 0.0,
             "amount": _cell_float(r.get("amount")), "fx_rate": _cell_float(r.get("fx_rate")), "currency": r.get("currency") or None,
             "portfolio": r.get("portfolio") or r.get("account") or None, "note": r.get("note") or None,
             "ext_ref": r.get("ext_ref") or None}
            for r in csv.DictReader(io.StringIO(text))]
    with closing(connect()) as con, con:
        pids = [_target(con, r, create=True) for r in rows]
        for pid in set(pids):
            con.execute("DELETE FROM transactions WHERE portfolio_id = ?", (pid,))
        for r, pid in zip(rows, pids):
            _insert(con, r, str(r.get("source") or "bundle"), None, portfolio_id=pid)
    return len(rows)


