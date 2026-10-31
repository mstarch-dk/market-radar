"""Your market views in radar.db: subjective beliefs with conviction, horizon, rationale, what would prove
them wrong, their exposures and indicators (config/views.yaml has templates; market_views.py reads them against
the data)."""
from __future__ import annotations

import json
from contextlib import closing

from ..jsonsafe import dumps
from . import backup, connect, exists, timestamp

VIEW_FIELDS = ("statement", "conviction", "horizon", "rationale", "falsifier", "template", "status")
# set when a view is added (or restored) and never by an edit: where it came from (scout:<date>:<slug>), or None
ADDED_FIELDS = ("origin",)


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
    if not exists():
        return []
    with closing(connect()) as con:
        return _view_rows(con, "WHERE status = ?", (status,)) if status else _view_rows(con)


def get_view(view_id: int) -> dict | None:
    if not exists():
        return None
    with closing(connect()) as con:
        rows = _view_rows(con, "WHERE id = ?", (view_id,))
        return rows[0] if rows else None


def write_children(con, view_id: int, v: dict) -> None:
    con.execute("DELETE FROM view_exposures WHERE view_id = ?", (view_id,))
    con.execute("DELETE FROM view_indicators WHERE view_id = ?", (view_id,))
    con.executemany("INSERT INTO view_exposures (view_id, kind, key, effect) VALUES (?, ?, ?, ?)",
                    [(view_id, e["kind"], e["key"].strip(), int(e["effect"])) for e in v.get("exposures") or []])
    con.executemany("INSERT INTO view_indicators (view_id, indicator, expect) VALUES (?, ?, ?)",
                    [(view_id, i["indicator"], i["expect"]) for i in v.get("indicators") or []])


def save_view(v: dict, view_id: int | None = None) -> int:
    """Add a view, or replace one (statement, fields, exposures and indicators; an edit keeps its `origin`).
    Returns its id."""
    with closing(connect()) as con, con:
        return _save_view(con, v, view_id)


def _save_view(con, v: dict, view_id: int | None = None) -> int:
    now = timestamp()
    vals = {k: v.get(k) for k in VIEW_FIELDS}
    vals["status"] = vals["status"] or "active"
    vals["conviction"] = int(vals["conviction"] or 3)
    vals["horizon"] = vals["horizon"] or "12m"
    if view_id is None:
        cols = (*VIEW_FIELDS, *ADDED_FIELDS)
        cur = con.execute(f"INSERT INTO views ({', '.join(cols)}, created_at, updated_at) "
                          f"VALUES ({', '.join('?' * len(cols))}, ?, ?)",
                          (*vals.values(), *(v.get(k) for k in ADDED_FIELDS), v.get("created_at") or now, now))
        view_id = cur.lastrowid
    else:
        con.execute(f"UPDATE views SET {', '.join(f'{k} = ?' for k in VIEW_FIELDS)}, updated_at = ? WHERE id = ?",
                    (*vals.values(), now, view_id))
    write_children(con, view_id, v)
    return view_id


def delete_view(view_id: int) -> dict | None:
    """Delete a view; returns it (with its id), so restore_view can undo the delete."""
    v = get_view(view_id)
    if v:
        with closing(connect()) as con, con:
            con.execute("DELETE FROM views WHERE id = ?", (view_id,))
    return v


def restore_view(v: dict) -> int:
    cols = (*VIEW_FIELDS, *ADDED_FIELDS)
    with closing(connect()) as con, con:
        con.execute(f"INSERT INTO views (id, {', '.join(cols)}, created_at, updated_at) "
                    f"VALUES (?, {', '.join('?' * len(cols))}, ?, ?)",
                    (v["id"], *(v.get(k) for k in cols), v["created_at"], timestamp()))
        write_children(con, v["id"], v)
    return v["id"]


def views_version() -> str:
    """Changes whenever a view is added, edited or deleted (for caching alignment results)."""
    if not exists():
        return "0"
    with closing(connect()) as con:
        r = con.execute("SELECT COUNT(*) AS n, MAX(updated_at) AS t FROM views").fetchone()
        return f"{r['n']}:{r['t']}"


def export_views_json() -> str:
    return dumps([{k: v for k, v in x.items() if k != "id"} for x in views()], indent=1, ensure_ascii=False)


def import_views_json(text: str) -> int:
    """Replace all views with an exported set (restoring a holdings bundle). Returns the number of views.
    All or nothing: one transaction, with a copy of the database taken first."""
    rows = json.loads(text)
    backup("before-views-import")
    with closing(connect()) as con, con:
        con.execute("DELETE FROM views")
        for v in rows:
            _save_view(con, v)
    return len(rows)
