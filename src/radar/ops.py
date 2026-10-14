"""The operations record: every external request, operational events (failed sources, parse errors, API errors,
throttling), job runs with their log, and per-host throttling state. Stored in `data/ops.db` (SQLite, WAL), which
can be deleted at any time: nothing here feeds a market reading. The Operations page and `radar ops` read it.

Recording never breaks the work it records: a write that fails (locked or broken database) is dropped with a
warning on the `radar.ops` logger.

Which source and job a request belongs to comes from `context(source=…, job=…)` (context variables), set by the
update steps, the discovery scan and the API. Work handed to threads keeps it when it goes through `net.pool`.
"""
from __future__ import annotations

import contextvars
import logging
import sqlite3
import statistics
import threading
import traceback
from contextlib import closing, contextmanager
from datetime import datetime, timedelta

from .config import DATA, settings

DB = DATA / "ops.db"
log = logging.getLogger("radar.ops")

_source: contextvars.ContextVar[str | None] = contextvars.ContextVar("ops_source", default=None)
_job: contextvars.ContextVar[int | None] = contextvars.ContextVar("ops_job", default=None)
# Threads that libraries start themselves (yf.download's) don't inherit context variables. For those, the source
# or job active anywhere in the process is used, but only when there is exactly one: ambiguity stays unattributed.
_active_lock = threading.Lock()
_active: dict[str, dict] = {"source": {}, "job": {}}

LEVELS = ("info", "warn", "error")
KINDS = ("source", "parse", "api", "job", "throttle", "doctor")
DETAIL_MAX = 4000  # characters of traceback kept per event

MIGRATIONS = [
    ("""CREATE TABLE requests (
        id INTEGER PRIMARY KEY, ts TEXT NOT NULL, job_id INTEGER, source TEXT, host TEXT NOT NULL,
        method TEXT NOT NULL, path TEXT NOT NULL, status INTEGER, ok INTEGER NOT NULL, duration_ms REAL,
        bytes INTEGER, attempt INTEGER NOT NULL DEFAULT 1, throttled INTEGER NOT NULL DEFAULT 0, error TEXT)""",
     "CREATE INDEX requests_ts ON requests(ts)",
     "CREATE INDEX requests_host_ts ON requests(host, ts)",
     """CREATE TABLE events (
        id INTEGER PRIMARY KEY, ts TEXT NOT NULL, level TEXT NOT NULL, kind TEXT NOT NULL, source TEXT,
        message TEXT NOT NULL, detail TEXT, job_id INTEGER)""",
     "CREATE INDEX events_ts ON events(ts)",
     """CREATE TABLE jobs (
        id INTEGER PRIMARY KEY, kind TEXT NOT NULL, started TEXT NOT NULL, finished TEXT, status TEXT NOT NULL,
        error TEXT, log TEXT)""",
     """CREATE TABLE host_state (
        host TEXT PRIMARY KEY, cooldown_until TEXT, reason TEXT, strikes INTEGER NOT NULL DEFAULT 0,
        updated TEXT NOT NULL)"""),
]


def now() -> datetime:
    return datetime.now()


def _ts(t: datetime | None = None) -> str:
    return (t or now()).isoformat(timespec="milliseconds")


def _connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode = WAL")     # job threads and API threads write at the same time
        con.execute("PRAGMA synchronous = NORMAL")   # an operations log may lose its last rows on a power cut
        _migrate(con)
    except BaseException:
        con.close()
        raise
    return con


def _migrate(con: sqlite3.Connection) -> None:
    """Same scheme as userstore: PRAGMA user_version, each step under the write lock (no backups: rebuildable)."""
    if con.execute("PRAGMA user_version").fetchone()[0] >= len(MIGRATIONS):
        return
    con.isolation_level = None
    try:
        for i, step in enumerate(MIGRATIONS, start=1):
            con.execute("BEGIN IMMEDIATE")
            if con.execute("PRAGMA user_version").fetchone()[0] >= i:
                con.execute("ROLLBACK")
                continue
            try:
                for sql in (step,) if isinstance(step, str) else step:
                    con.execute(sql)
                con.execute(f"PRAGMA user_version = {i}")
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
    finally:
        con.isolation_level = ""


def _write(sql: str, args: tuple = ()) -> int | None:
    """Run one write; None (and a warning) if the database can't take it."""
    try:
        with closing(_connect()) as con, con:
            return con.execute(sql, args).lastrowid
    except sqlite3.Error as e:
        log.warning("ops record dropped (%s: %s)", type(e).__name__, e)
        return None


def _read(sql: str, args: tuple = ()) -> list[dict]:
    with closing(_connect()) as con:
        return [dict(r) for r in con.execute(sql, args)]


# ---------------- context ----------------

@contextmanager
def context(source: str | None = None, job: int | None = None):
    """Attribute what happens inside (requests, events) to a source and/or a job."""
    tokens, marks = [], []
    for name, var, val in (("source", _source, source), ("job", _job, job)):
        if val is not None:
            tokens.append((var, var.set(val)))
            mark = object()
            with _active_lock:
                _active[name][mark] = val
            marks.append((name, mark))
    try:
        yield
    finally:
        for var, tok in reversed(tokens):
            var.reset(tok)
        with _active_lock:
            for name, mark in marks:
                _active[name].pop(mark, None)


def _sole(name: str):
    with _active_lock:
        vals = set(_active[name].values())
    return vals.pop() if len(vals) == 1 else None


def current_source() -> str | None:
    """The source this request belongs to: this thread's context, else the only one active in the process."""
    s = _source.get()
    return s if s is not None else _sole("source")


def current_job() -> int | None:
    j = _job.get()
    return j if j is not None else _sole("job")


# ---------------- recording ----------------

def record_request(host: str, path: str, method: str, status: int | None, ok: bool, duration_ms: float | None,
                   size: int | None = None, attempt: int = 1, throttled: bool = False,
                   error: str | None = None) -> None:
    """One HTTP request. `path` must already be redacted (net.redact): no query string is ever stored."""
    _write("INSERT INTO requests (ts, job_id, source, host, method, path, status, ok, duration_ms, bytes, attempt,"
           " throttled, error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
           (_ts(), current_job(), current_source(), host, method.upper(), path, status, int(ok), duration_ms, size,
            attempt, int(throttled), error))


def event(level: str, kind: str, message: str, source: str | None = None, detail: str | None = None,
          exc: BaseException | None = None) -> None:
    """An operational event. With `exc`, its traceback is kept as the detail (capped)."""
    if exc is not None and detail is None:
        detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    if detail and len(detail) > DETAIL_MAX:
        detail = "…" + detail[-DETAIL_MAX:]
    _write("INSERT INTO events (ts, level, kind, source, message, detail, job_id) VALUES (?,?,?,?,?,?,?)",
           (_ts(), level, kind, source if source is not None else _source.get(), message, detail, current_job()))


def job_start(kind: str) -> int | None:
    return _write("INSERT INTO jobs (kind, started, status) VALUES (?,?,'running')", (kind, _ts()))


def job_finish(job_id: int | None, status: str, error: str | None = None, lines: list[str] | None = None) -> None:
    if job_id is None:
        return
    _write("UPDATE jobs SET finished = ?, status = ?, error = ?, log = ? WHERE id = ?",
           (_ts(), status, error, "\n".join(lines or []), job_id))


@contextmanager
def job(kind: str, lines: list[str] | None = None):
    """Record a job (start, end, status, log) around a block; its requests and events carry its id. `lines` is
    the job's log as it grows; the list is stored when the block ends."""
    jid = job_start(kind)
    try:
        with context(job=jid):
            yield jid
    except BaseException as e:
        job_finish(jid, "failed", f"{type(e).__name__}: {e}", lines)
        raise
    else:
        job_finish(jid, "done", None, lines)
    finally:
        prune()


# ---------------- throttling state (shared across processes) ----------------

def host_state(host: str) -> dict | None:
    try:
        rows = _read("SELECT * FROM host_state WHERE host = ?", (host,))
    except sqlite3.Error:
        return None
    return rows[0] if rows else None


def set_cooldown(host: str, until: datetime, reason: str, strikes: int) -> None:
    _write("INSERT INTO host_state (host, cooldown_until, reason, strikes, updated) VALUES (?,?,?,?,?) "
           "ON CONFLICT(host) DO UPDATE SET cooldown_until = excluded.cooldown_until, reason = excluded.reason, "
           "strikes = excluded.strikes, updated = excluded.updated", (host, _ts(until), reason, strikes, _ts()))


def clear_cooldown(host: str) -> bool:
    """End a host's cooldown now (strikes are kept, so a repeat still escalates). False if it had none."""
    st = host_state(host)
    if not st or not st["cooldown_until"]:
        return False
    _write("UPDATE host_state SET cooldown_until = NULL, updated = ? WHERE host = ?", (_ts(), host))
    return True


def cooldowns() -> list[dict]:
    """Hosts paused right now."""
    return _read("SELECT * FROM host_state WHERE cooldown_until > ? ORDER BY host", (_ts(),))


def count_requests(host: str, since: datetime, status: int | None = None) -> int:
    sql, args = "SELECT COUNT(*) AS n FROM requests WHERE host = ? AND ts >= ?", [host, _ts(since)]
    if status is not None:
        sql += " AND status = ?"
        args.append(status)
    return _read(sql, tuple(args))[0]["n"]


# ---------------- housekeeping ----------------

def _cfg() -> dict:
    return {"keep_requests_days": 30, "keep_events_days": 180} | (settings().get("ops") or {})


def prune() -> None:
    """Drop requests and events/jobs older than settings.yaml `ops:` keeps them."""
    cfg = _cfg()
    t = now()
    try:
        with closing(_connect()) as con, con:
            con.execute("DELETE FROM requests WHERE ts < ?", (_ts(t - timedelta(days=cfg["keep_requests_days"])),))
            old = _ts(t - timedelta(days=cfg["keep_events_days"]))
            con.execute("DELETE FROM events WHERE ts < ?", (old,))
            con.execute("DELETE FROM jobs WHERE started < ? AND status != 'running'", (old,))
    except sqlite3.Error as e:
        log.warning("ops prune skipped (%s: %s)", type(e).__name__, e)


SERVER_KINDS = ("update", "discover")   # the jobs the server runs; CLI runs (cli_*) are other processes


def mark_interrupted() -> None:
    """The server's own jobs still 'running' from an earlier server can't be: a new one starts with none. A CLI
    run in another process is left alone."""
    _write("UPDATE jobs SET status = 'interrupted', finished = COALESCE(finished, started) "
           f"WHERE status = 'running' AND kind IN ({','.join('?' * len(SERVER_KINDS))})", SERVER_KINDS)


# ---------------- queries for the page and `radar ops` ----------------

def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return round(values[0], 1)
    return round(statistics.quantiles(values, n=100, method="inclusive")[int(q) - 1], 1)


def summary(days: int = 7, hosts_cfg=None) -> dict:
    """Request statistics per host and source over the last `days`, plus the headline tiles. `hosts_cfg(host)`
    gives a host's limits (net.limits) for its daily budget."""
    t = now()
    since, day_ago = t - timedelta(days=days), t - timedelta(days=1)
    today = t.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = _read("SELECT host, source, ts, status, ok, duration_ms, error FROM requests WHERE ts >= ? ORDER BY ts",
                 (_ts(since),))
    groups: dict[tuple[str, str | None], list[dict]] = {}
    for r in rows:
        groups.setdefault((r["host"], r["source"]), []).append(r)
    paused = {c["host"]: c for c in cooldowns()}
    dates = [(since + timedelta(days=i + 1)).date().isoformat() for i in range(days)]
    out_rows = []
    today_by_host: dict[str, int] = {}
    for r in rows:
        if r["ts"] >= _ts(today):
            today_by_host[r["host"]] = today_by_host.get(r["host"], 0) + 1
    for (host, source), rs in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        durs = [r["duration_ms"] for r in rs if r["duration_ms"] is not None]
        errors = [r for r in rs if not r["ok"]]
        last_err = errors[-1] if errors else None
        per_day = {d: 0 for d in dates}
        for r in rs:
            d = r["ts"][:10]
            if d in per_day:
                per_day[d] += 1
        lim = hosts_cfg(host) if hosts_cfg else {}
        budget = lim.get("budget")
        cd = paused.get(host)
        out_rows.append({
            "host": host, "source": source, "requests": len(rs), "errors": len(errors),
            "error_pct": round(100 * len(errors) / len(rs), 1),
            "throttled": sum(1 for r in rs if r["status"] == 429),
            "p50_ms": _pct(durs, 50), "p95_ms": _pct(durs, 95),
            "last": rs[-1]["ts"], "last_error": (last_err["error"] or f"HTTP {last_err['status']}") if last_err else None,
            "last_error_at": last_err["ts"] if last_err else None,
            "today": today_by_host.get(host, 0), "budget": budget,
            "cooldown_until": cd["cooldown_until"] if cd else None,
            "daily": [per_day[d] for d in dates],
        })
    recent = [r for r in rows if r["ts"] >= _ts(day_ago)]
    ev = _read("SELECT COUNT(*) AS n FROM events WHERE level = 'error' AND ts >= ?", (_ts(day_ago),))[0]["n"]
    last_update = _read("SELECT * FROM jobs WHERE kind IN ('update', 'cli_run', 'cli_update') ORDER BY id DESC LIMIT 1")
    over = sorted({r["host"] for r in out_rows if r["budget"] and r["today"] > r["budget"]})
    return {
        "days": days, "dates": dates, "generated": _ts(t),
        "requests_24h": len(recent), "errors_24h": sum(1 for r in recent if not r["ok"]),
        "error_events_24h": ev,
        "last_update": _job_row(last_update[0]) if last_update else None,
        "cooldowns": [{"host": c["host"], "until": c["cooldown_until"], "reason": c["reason"],
                       "strikes": c["strikes"]} for c in paused.values()],
        "over_budget": over, "rows": out_rows,
    }


def _job_row(r: dict, with_log: bool = False) -> dict:
    dur = None
    if r["finished"]:
        dur = round((datetime.fromisoformat(r["finished"]) - datetime.fromisoformat(r["started"])).total_seconds(), 1)
    out = {"id": r["id"], "kind": r["kind"], "started": r["started"], "finished": r["finished"],
           "status": r["status"], "error": r["error"], "duration_s": dur}
    if with_log:
        out["log"] = (r["log"] or "").splitlines() if r["log"] else []
    return out


def jobs(limit: int = 50) -> list[dict]:
    return [_job_row(r) for r in _read("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,))]


def job_detail(job_id: int) -> dict | None:
    rows = _read("SELECT * FROM jobs WHERE id = ?", (job_id,))
    if not rows:
        return None
    out = _job_row(rows[0], with_log=True)
    out["requests"] = _read("SELECT COUNT(*) AS n FROM requests WHERE job_id = ?", (job_id,))[0]["n"]
    out["errors"] = _read("SELECT COUNT(*) AS n FROM requests WHERE job_id = ? AND ok = 0", (job_id,))[0]["n"]
    return out


def _filtered(table: str, filters: dict, limit: int, before: int | None) -> list[dict]:
    where, args = [], []
    for col, val in filters.items():
        if val is not None:
            where.append(f"{col} = ?")
            args.append(val)
    if before is not None:
        where.append("id < ?")
        args.append(before)
    sql = f"SELECT * FROM {table}" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id DESC LIMIT ?"
    return _read(sql, (*args, limit))


def events(level: str | None = None, kind: str | None = None, source: str | None = None, limit: int = 200,
           before: int | None = None) -> list[dict]:
    return _filtered("events", {"level": level, "kind": kind, "source": source}, limit, before)


def requests(host: str | None = None, source: str | None = None, status: int | None = None, limit: int = 200,
             before: int | None = None) -> list[dict]:
    rows = _filtered("requests", {"host": host, "source": source, "status": status}, limit, before)
    for r in rows:
        r["ok"], r["throttled"] = bool(r["ok"]), bool(r["throttled"])
    return rows
