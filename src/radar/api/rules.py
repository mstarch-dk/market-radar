"""Your trading rules, and whether an action (or what you hold now) breaks them: a mirror, never a gate."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..api_models import ActionIn, CheckResult, DecisionIn, ReplayResult, RuleIn, RuleRow, RulesPage, StandingResult
from ..userstore import rulestore
from . import state

router = APIRouter()


def _standing() -> dict | None:
    from .. import rulecheck

    if not rulestore.rules("active"):
        return None
    with state.lock:
        return rulecheck.standing(state.market())


def _page() -> dict:
    from .. import trading_rules as tr

    return {"disclaimer": tr.DISCLAIMER, "rules": rulestore.rules(), "templates": tr.templates(),
            "catalogue": tr.catalogue(), "standing": _standing()}


def _body(body: RuleIn) -> dict:
    from .. import trading_rules as tr

    return tr.validate(body.model_dump(exclude_none=False) | {"scope": body.scope.model_dump(exclude_none=True)})


@router.get("/api/rules", response_model=RulesPage)
def get_rules() -> dict:
    """Your trading rules (active and archived), the templates, the kinds and what you hold now against them."""
    return _page()


@router.post("/api/rules", response_model=RulesPage)
def add_rule(body: RuleIn) -> dict:
    rulestore.save_rule(_body(body))
    return _page()


@router.put("/api/rules/{rule_id}", response_model=RulesPage)
def edit_rule(rule_id: int, body: RuleIn) -> dict:
    if not rulestore.get_rule(rule_id):
        raise HTTPException(404, f"No rule {rule_id}.")
    rulestore.save_rule(_body(body), rule_id)
    return _page()


@router.delete("/api/rules/{rule_id}", response_model=RuleRow)
def delete_rule(rule_id: int) -> dict:
    """Delete a rule; the response is the deleted rule, which /restore puts back (undo)."""
    r = rulestore.delete_rule(rule_id)
    if not r:
        raise HTTPException(404, f"No rule {rule_id}.")
    return r


@router.post("/api/rules/restore", response_model=RulesPage)
def restore_rule(row: RuleRow) -> dict:
    if rulestore.get_rule(row.id):
        raise HTTPException(409, "That rule is already there.")
    from .. import trading_rules as tr

    r = tr.validate(row.model_dump() | {"scope": row.scope.model_dump(exclude_none=True)})
    rulestore.restore_rule(r)
    return _page()


@router.post("/api/rules/check", response_model=CheckResult)
def check_action(body: ActionIn) -> dict:
    """Every active rule against a proposed action: breaks, near, unknown, complies, not applicable, each with
    the numbers and the way to comply. `log` stores the check (when you go on to save the trade)."""
    from .. import rulecheck

    action = body.model_dump(exclude={"log"})
    with state.lock:
        return rulecheck.check(state.market(), action, log=body.log)


@router.get("/api/rules/standing", response_model=StandingResult)
def get_standing() -> dict:
    """What you hold now against the rules about holdings (name, theme and core weights, the number of names)."""
    from .. import rulecheck

    with state.lock:
        return rulecheck.standing(state.market())


@router.post("/api/rules/checks/{check_id}/decision", response_model=dict[str, bool])
def set_decision(check_id: int, body: DecisionIn) -> dict:
    """What you did after a logged check: went ahead (with the reason), changed it or dropped it."""
    if not rulestore.set_decision(check_id, body.decision, body.reason, body.transaction_id):
        raise HTTPException(404, f"No logged check {check_id}.")
    return {"ok": True}


@router.get("/api/rules/replay", response_model=ReplayResult)
def get_replay(start: str | None = None, end: str | None = None) -> dict:
    """Would your rules have helped? Your real trades from `start` to `end`, each checked against today's rules as
    of its own day, with what the name did afterwards against ACWI. Descriptive, no significance claimed."""
    from .. import rulecheck

    with state.lock:
        return rulecheck.replay(state.market(), start, end)
