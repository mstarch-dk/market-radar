"""The tools that write: a memo into the notebook's folders, one trade into a portfolio, and one market view.
Narrow on purpose: a memo goes only to a folder of its kind (all in the data folder's `home` tier, paths.REGISTRY),
written atomically and never over an existing one unless asked; a trade and a view are checked as the app checks
them and saved only on `confirm`."""
from __future__ import annotations

import re
from datetime import date as _date

from .. import errors, notebook, paths, profile, rulecheck, userstore
from .. import market_views as mv
from ..config import write_text
from ..portfolios import checks, trades
from ..signals import views as sv
from ..userstore import viewstore

FOLDERS = notebook.FOLDERS | {"hindsight": paths.HOME / "research" / "hindsight",   # the /hindsight memos
                             "listening": paths.HOME / "briefs" / "lyt"}             # a brief's NotebookLM version
NAME = re.compile(r"\w[\w.^+ -]{0,150}")      # a file name, no folders: NVDA, 2026-10-27_NVDA-AMD, NOVO-B.CO


def write_memo(kind: str, name: str, markdown: str, replace: bool = False) -> dict:
    """Write a skill's Markdown document into the data folder: `kind` research (research/<TICKER>), compare,
    proposals, proposal_reviews, hindsight, scout (a /scout report), briefs, listening (a brief's NotebookLM version),
    journal or reviews; `name` the file name without .md (e.g. NVDA, 2026-10-27_NVDA-AMD). An existing document is
    replaced only with `replace` (read it first with `read_document` and keep its content). Written whole or not at
    all; returns where it went."""
    if kind not in FOLDERS:
        raise errors.Invalid(f"kind must be one of {', '.join(FOLDERS)}")
    stem = name.removesuffix(".md").strip()
    if not NAME.fullmatch(stem) or ".." in stem:
        raise errors.Invalid(f"{name!r} isn't a file name: letters, digits, . _ - + ^ and spaces, no folders.")
    if not markdown.strip():
        raise errors.Invalid("The document is empty.")
    f = FOLDERS[kind] / f"{stem}.md"
    existed = f.is_file()
    if existed and not replace:
        raise errors.Conflict(f"{kind}/{stem} exists: read it with read_document, keep what it says, and write it "
                              f"again with replace=true.")
    f.parent.mkdir(parents=True, exist_ok=True)
    write_text(f, markdown if markdown.endswith("\n") else markdown + "\n")
    return {"kind": kind, "name": stem, "file": str(f), "replaced": existed}


def add_trade(type: str, symbol: str, quantity: float, price: float, date: str | None = None, fee: float = 0.0,
              portfolio: str | None = None, note: str | None = None, confirm: bool = False,
              rule_reason: str | None = None) -> dict:
    """Record one trade (`type` BUY or SELL; `price` and `fee` in the price's currency; `date` YYYY-MM-DD, default
    today) in `portfolio` (by name; default: the default portfolio). Without `confirm` nothing is saved: it returns
    the checks' issues (errors always block, warnings need the user's yes; the user's trading rules that the trade
    breaks or comes close to are warnings too, with the full check under `rules`) and the position before and
    after. Show them to the user, and call again with `confirm` only once the user has agreed to save this trade;
    when it breaks a rule, pass the user's own reason for going ahead as `rule_reason` (it is logged)."""
    trades.ensure_migrated()
    sym = symbol.strip().upper()
    row = {"symbol": sym, "date": date or _date.today().isoformat(), "type": type.strip().upper(),
           "quantity": quantity, "price": price, "fee": fee, "portfolio": portfolio, "note": note}
    m = profile.ensure_prices(sym)                     # an untracked ticker is downloaded, as in the app
    rc: dict = {}

    def rules(r: dict) -> list[dict]:
        rc["check"] = rulecheck.trade_check(m, r)
        return rulecheck.trade_issues(rc["check"])

    if not confirm:
        issues = checks.validate(row, m)
        if not any(i["level"] == "error" for i in issues):
            issues += rules(row)
        return {"saved": False, "trade": row, "issues": issues, "effect": checks.effect(row),
                "blocked": any(i["level"] == "error" for i in issues), "rules": rc.get("check")}
    issues = checks.checked(row, m, confirm=True, rule_issues=rules)   # Invalid (with the issues) on an error
    tx_id = userstore.add_tx(row)
    rulecheck.log_trade(rc.get("check"), tx_id, rule_reason)
    saved = userstore.get_tx(tx_id) or {}
    return {"saved": True, "id": tx_id, "portfolio": saved.get("portfolio"), "trade": row, "issues": issues,
            "effect": checks.effect(row, exclude_id=tx_id)}


ORIGIN = re.compile(r"scout:\d{4}-\d{2}-\d{2}:[a-z0-9-]{1,40}")    # where a skill's view came from


def _view_issues(v: dict) -> list[dict]:
    """What the user should see before saying yes: a view already adopted from the same candidate (error), active
    views it overlaps (same exposure, same direction) or contradicts (same exposure, the other way)."""
    out = []
    for o in viewstore.views("active"):
        if v.get("origin") and o.get("origin") == v["origin"]:
            out.append({"level": "error", "message": f"View #{o['id']} was already adopted from {v['origin']}."})
            continue
        mine = {(e["kind"], e["key"].strip().lower()): int(e["effect"]) for e in v.get("exposures") or []}
        theirs = {(e["kind"], e["key"].strip().lower()): int(e["effect"]) for e in o["exposures"]}
        same = sorted(k for k in mine.keys() & theirs.keys() if mine[k] == theirs[k])
        other = sorted(k for k in mine.keys() & theirs.keys() if mine[k] != theirs[k])
        if other:
            out.append({"level": "warning", "message": f"Contradicts view #{o['id']} ({o['statement']}) on "
                                                       f"{', '.join(f'{k}: {x}' for k, x in other)}."})
        elif same:
            out.append({"level": "warning", "message": f"Overlaps view #{o['id']} ({o['statement']}) on "
                                                       f"{', '.join(f'{k}: {x}' for k, x in same)}."})
    return out


def add_view(statement: str, conviction: int = 3, horizon: str = "12m", rationale: str | None = None,
             falsifier: str | None = None, exposures: list[dict] | None = None, indicators: list[dict] | None = None,
             origin: str | None = None, confirm: bool = False) -> dict:
    """Add one market view (a subjective belief, shown on the app's My market views page): `statement`,
    `conviction` 1-5, `horizon` 3m | 6m | 12m | 3y, `rationale`, `falsifier` (what would change the user's mind),
    `exposures` [{kind: etf | sector | industry | region | ticker, key, effect: 1 or -1}], `indicators`
    [{indicator: a key from market_views' catalogue, expect: up | down}], `origin` scout:<YYYY-MM-DD>:<slug> when it
    comes from a /scout candidate. Without `confirm` nothing is saved: it returns the view as it would be stored,
    the radar's evidence for it now, and issues (errors block: a view already adopted from the same `origin`;
    warnings: active views it overlaps or contradicts). Show them to the user, and call again with `confirm` only
    once the user has agreed to add this view."""
    if origin is not None and not ORIGIN.fullmatch(origin):
        raise errors.Invalid("origin is scout:<YYYY-MM-DD>:<slug> (lower-case letters, digits and -).")
    v = mv.validate({"statement": statement, "conviction": conviction, "horizon": horizon, "rationale": rationale,
                     "falsifier": falsifier, "template": None, "status": "active", "origin": origin,
                     "exposures": [{**e, "key": str(e.get("key") or "").strip()} for e in exposures or []],
                     "indicators": indicators or []})
    issues = _view_issues(v)
    blocked = any(i["level"] == "error" for i in issues)
    if not confirm or blocked:
        if confirm:
            raise errors.Invalid("Not saved: " + " ".join(i["message"] for i in issues if i["level"] == "error"))
        return {"saved": False, "view": v, "evidence": sv.evidence(v, mv.reads()), "issues": issues,
                "blocked": blocked, "disclaimer": mv.DISCLAIMER}
    view_id = viewstore.save_view(v)
    return {"saved": True, "id": view_id, "view": viewstore.get_view(view_id), "issues": issues}


TOOLS = (write_memo, add_trade, add_view)
