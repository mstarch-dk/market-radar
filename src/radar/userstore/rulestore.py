"""Your trading rules in radar.db: each rule in your words, its kind and numbers (config/rules.yaml has the kinds
and templates; trading_rules.py validates them, rulecheck.py checks an action against them), its scope, severity
and why you have it; and the checks you logged against them, with what you then did and why."""
from __future__ import annotations

import json
from contextlib import closing

from ..jsonsafe import dumps
from . import backup, connect, exists, new_id, timestamp

RULE_FIELDS = ("statement", "kind", "params", "scope", "severity", "rationale", "template", "status")
JSON_FIELDS = ("params", "scope")
DEFAULT_SCOPE = {"portfolios": "real"}
DECISIONS = ("went_ahead", "changed", "dropped")


def _row(r) -> dict:
    out = dict(r)
    for k in JSON_FIELDS:
        out[k] = json.loads(out[k]) if out[k] else ({} if k == "params" else dict(DEFAULT_SCOPE))
    return out


def _rule_rows(con, where: str = "", args: tuple = ()) -> list[dict]:
    order = "status, CASE severity WHEN 'hard' THEN 0 WHEN 'soft' THEN 1 ELSE 2 END, id"
    return [_row(r) for r in con.execute(f"SELECT * FROM trading_rules {where} ORDER BY {order}", args)]


def rules(status: str | None = None) -> list[dict]:
    """Your trading rules ([] without a database), hard ones first."""
    if not exists():
        return []
    with closing(connect()) as con:
        return _rule_rows(con, "WHERE status = ?", (status,)) if status else _rule_rows(con)


def get_rule(rule_id: int) -> dict | None:
    if not exists():
        return None
    with closing(connect()) as con:
        rows = _rule_rows(con, "WHERE id = ?", (rule_id,))
        return rows[0] if rows else None


def _values(r: dict) -> list:
    vals = {k: r.get(k) for k in RULE_FIELDS}
    vals["params"] = json.dumps(vals["params"] or {}, sort_keys=True)
    vals["scope"] = json.dumps(vals["scope"] or DEFAULT_SCOPE, sort_keys=True)
    vals["severity"] = vals["severity"] or "soft"
    vals["status"] = vals["status"] or "active"
    return list(vals.values())


def save_rule(r: dict, rule_id: int | None = None) -> int:
    """Add a rule, or replace one. Returns its id. Validate first (trading_rules.validate)."""
    with closing(connect()) as con, con:
        return _save_rule(con, r, rule_id)


def _save_rule(con, r: dict, rule_id: int | None = None) -> int:
    now = timestamp()
    if rule_id is None:
        cur = con.execute(f"INSERT INTO trading_rules ({', '.join(RULE_FIELDS)}, created_at, updated_at) "
                          f"VALUES ({', '.join('?' * len(RULE_FIELDS))}, ?, ?)",
                          (*_values(r), r.get("created_at") or now, now))
        return new_id(cur)
    con.execute(f"UPDATE trading_rules SET {', '.join(f'{k} = ?' for k in RULE_FIELDS)}, updated_at = ? WHERE id = ?",
                (*_values(r), now, rule_id))
    return rule_id


def delete_rule(rule_id: int) -> dict | None:
    """Delete a rule; returns it (with its id), so restore_rule can undo the delete."""
    r = get_rule(rule_id)
    if r:
        with closing(connect()) as con, con:
            con.execute("DELETE FROM trading_rules WHERE id = ?", (rule_id,))
    return r


def restore_rule(r: dict) -> int:
    with closing(connect()) as con, con:
        con.execute(f"INSERT INTO trading_rules (id, {', '.join(RULE_FIELDS)}, created_at, updated_at) "
                    f"VALUES (?, {', '.join('?' * len(RULE_FIELDS))}, ?, ?)",
                    (r["id"], *_values(r), r["created_at"], timestamp()))
    return r["id"]


def rules_version() -> str:
    """Changes whenever a rule is added, edited or deleted (stored with each logged check)."""
    if not exists():
        return "0"
    with closing(connect()) as con:
        r = con.execute("SELECT COUNT(*) AS n, MAX(updated_at) AS t FROM trading_rules").fetchone()
        return f"{r['n']}:{r['t']}"


def _named_scope(scope: dict, names: dict[int, str]) -> dict:
    """A scope with its portfolio ids as names (ids differ between computers; names don't)."""
    p = scope.get("portfolios")
    return {**scope, "portfolios": [names.get(i, str(i)) for i in p]} if isinstance(p, list) else scope


def _id_scope(con, scope: dict) -> dict:
    p = scope.get("portfolios")
    if not isinstance(p, list):
        return scope
    ids = []
    for x in p:
        if isinstance(x, int):
            ids.append(x)
            continue
        r = con.execute("SELECT id FROM portfolios WHERE name = ?", (str(x),)).fetchone()
        if not r:
            raise ValueError(f"a rule's scope names the portfolio {x!r}, which isn't there")
        ids.append(r["id"])
    return {**scope, "portfolios": ids}


def export_rules_json() -> str:
    """Every rule without its id, its scope's portfolios by name."""
    from . import portfolios

    names = {p["id"]: p["name"] for p in portfolios()}
    return dumps([{k: (_named_scope(v, names) if k == "scope" else v) for k, v in x.items() if k != "id"}
                  for x in rules()], indent=1, ensure_ascii=False)


def import_rules_json(text: str) -> int:
    """Replace all rules with an exported set (restoring a holdings bundle). Returns the number of rules.
    All or nothing: one transaction, with a copy of the database taken first."""
    rows = json.loads(text)
    if not isinstance(rows, list):
        raise ValueError("the rules file is not a list of rules")
    backup("before-rules-import")
    with closing(connect()) as con, con:
        con.execute("DELETE FROM trading_rules")
        for r in rows:
            _save_rule(con, {**r, "scope": _id_scope(con, r.get("scope") or DEFAULT_SCOPE)})
    return len(rows)


# ---------------- logged checks ----------------

def log_check(action: dict, verdicts: list[dict], version: str | None = None) -> int:
    """Store a check you asked for (from the app's save, the CLI's --log or a skill). Returns its id."""
    with closing(connect()) as con, con:
        cur = con.execute("INSERT INTO rule_checks (at, action, rules_version, verdicts) VALUES (?, ?, ?, ?)",
                          (timestamp(), dumps(action), version or rules_version(), dumps(verdicts)))
        return new_id(cur)


def set_decision(check_id: int, decision: str, reason: str | None = None,
                 transaction_id: int | None = None) -> bool:
    """What you did after a check: went ahead (with the reason, when against a rule), changed it, or dropped it."""
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {', '.join(DECISIONS)}")
    with closing(connect()) as con, con:
        cur = con.execute("UPDATE rule_checks SET decision = ?, reason = ?, transaction_id = ? WHERE id = ?",
                          (decision, (reason or "").strip() or None, transaction_id, check_id))
        return cur.rowcount > 0


def checks(limit: int = 200) -> list[dict]:
    """The logged checks, newest first."""
    if not exists():
        return []
    with closing(connect()) as con:
        out = []
        for r in con.execute("SELECT * FROM rule_checks ORDER BY id DESC LIMIT ?", (limit,)):
            row = dict(r)
            row["action"], row["verdicts"] = json.loads(row["action"]), json.loads(row["verdicts"])
            out.append(row)
        return out
