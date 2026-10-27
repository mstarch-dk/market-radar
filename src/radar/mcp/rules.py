"""Tools about the user's trading rules: the rules and what the holdings break now, a check of a proposed action,
and the two narrow writes (a rule the user has confirmed, what they did after a check). A mirror, never a gate:
nothing here blocks or sends a trade."""
from __future__ import annotations

from .. import errors, rulecheck
from .. import trading_rules as tr
from ..userstore import rulestore
from .common import market


def trading_rules(archived: bool = False) -> dict:
    """The user's trading rules (statement in their words, kind and numbers, scope, severity hard / soft /
    reminder, why they have it), what their holdings break or come close to now (`standing`), and the kinds and
    templates a new rule can use. Read the judgment rules (kind `judgment`) as questions to weigh yourself."""
    rs = rulestore.rules(None if archived else "active")
    return {"disclaimer": tr.DISCLAIMER, "rules": rs,
            "standing": rulecheck.standing(market()) if rulestore.rules("active") else None,
            "kinds": tr.catalogue()["kinds"], "templates": tr.templates()}


def rules_check(side: str, ticker: str, amount_dkk: float | None = None, quantity: float | None = None,
                fraction: float | None = None, portfolio: str | None = None, style: str | None = None,
                horizon: str | None = None, date: str | None = None, price: float | None = None,
                log: bool = False) -> dict:
    """Whether a proposed action breaks the user's active rules, rule by rule: `side` buy or sell; one of
    `amount_dkk`, `quantity` (shares) or, for a sale, `fraction` of the position (1 = all); `portfolio` by name
    (default: the default one); `style` momentum | value | core | tactical; `horizon` 1m | 3m | 6m | 12m | 3y;
    `date` YYYY-MM-DD (prices and trades as of then). Each verdict is breaks, near, unknown (an input is missing:
    never say it complies), complies, not_applicable or judgment (a question for the user), with the numbers and
    how to comply. `log` stores the check (do it when the user goes on to act, e.g. before a journal entry)."""
    action = {"side": side, "ticker": ticker, "amount_dkk": amount_dkk, "quantity": quantity, "fraction": fraction,
              "portfolio": portfolio, "style": style, "horizon": horizon, "date": date, "price": price}
    return rulecheck.check(market(), action, log=log)


def add_rule(statement: str, kind: str, params: dict | None = None, scope: dict | None = None,
             severity: str = "soft", rationale: str | None = None, template: str | None = None,
             confirm: bool = False) -> dict:
    """Add one trading rule: `statement` in the user's words, `kind` from trading_rules' kinds with its `params`,
    `scope` ({portfolios: real | all | [ids], kind, tag, style}), `severity` hard | soft | reminder, `rationale`
    (why they have it, in their words). Without `confirm` nothing is saved: it returns the rule as it would be
    stored (defaults filled in) or why it can't be. Show it to the user and call again with `confirm` only once
    they have agreed to this exact rule."""
    rule = tr.validate({"statement": statement, "kind": kind, "params": params or {}, "scope": scope,
                        "severity": severity, "rationale": rationale, "template": template})
    if not confirm:
        return {"saved": False, "rule": rule}
    rid = rulestore.save_rule(rule)
    return {"saved": True, "id": rid, "rule": rulestore.get_rule(rid)}


def rule_decision(check_id: int, decision: str, reason: str | None = None) -> dict:
    """What the user did after a logged check (`rules_check` with `log`): went_ahead (with their own reason when
    against a rule), changed or dropped."""
    if decision not in rulestore.DECISIONS:
        raise errors.Invalid(f"decision must be one of {', '.join(rulestore.DECISIONS)}")
    if not rulestore.set_decision(check_id, decision, reason):
        raise errors.NotFound(f"No logged check {check_id}.")
    return {"check_id": check_id, "decision": decision}


READS = (trading_rules,)
TOOLS = (trading_rules, rules_check, add_rule, rule_decision)
