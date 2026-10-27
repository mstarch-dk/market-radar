"""Trading rules: your rules, their catalogue and templates, and a check of an action (or of what you hold now)
against them. A mirror, never a gate."""
from __future__ import annotations

from typing import Any, Literal

from .common import Num, Strict

Severity = Literal["hard", "soft", "reminder"]
RuleStatus = Literal["breaks", "near", "complies", "not_applicable", "unknown", "judgment"]
Style = Literal["momentum", "value", "core", "tactical"]
Horizon = Literal["1m", "3m", "6m", "12m", "3y"]


class RuleExposure(Strict):
    kind: Literal["etf", "sector", "industry", "region", "ticker"]
    key: str


class RuleScope(Strict):
    """Which portfolios a rule covers: real, all, or a list of ids; narrowed by account kind, tag and style."""
    portfolios: Literal["real", "all"] | list[int] = "real"
    kind: Literal["ask", "frie_midler", "pension", "other"] | None = None
    tag: str | None = None
    style: Style | None = None


class RuleIn(Strict):
    statement: str
    kind: str
    params: dict[str, Any] = {}
    scope: RuleScope = RuleScope()
    severity: Severity = "soft"
    rationale: str | None = None
    template: str | None = None
    status: Literal["active", "archived"] = "active"


class RuleRow(RuleIn):
    id: int
    created_at: str
    updated_at: str


class RuleParamSpec(Strict):
    key: str
    type: Literal["pct", "dkk", "int", "days", "choice", "tickers", "exposures"]
    label: str
    min: Num = None
    max: Num = None
    default: Any = None
    choices: list[Any] | None = None


class RuleKind(Strict):
    key: str
    label: str
    when: Literal["action", "state", "both"]
    sides: list[Literal["buy", "sell"]]
    needs: str | None = None
    params: list[RuleParamSpec]


class RuleTemplate(Strict):
    key: str
    kind: str
    statement: str
    params: dict[str, Any]
    scope: RuleScope
    severity: Severity
    rationale: str | None = None


class RulesCatalogue(Strict):
    kinds: list[RuleKind]
    styles: list[Style]
    horizons: list[Horizon]
    severities: list[Severity]
    account_kinds: list[str]
    exposure_kinds: list[str]
    etfs: list[dict[str, str]]
    sectors: list[str]
    regions: list[str]


class RuleVerdict(Strict):
    """One rule's reading of an action (or of a holding, when standing). Weights are shares of the invested DKK
    value of the rule's portfolios; the message says of what."""
    rule_id: int
    statement: str
    kind: str
    kind_label: str
    severity: Severity
    rationale: str | None = None
    status: RuleStatus
    value: Num = None
    limit: Num = None
    unit: str | None = None
    message: str
    comply: str | None = None
    symbol: str | None = None
    symbols: list[str] | None = None


class RuleCounts(Strict):
    by_status: dict[RuleStatus, dict[Severity, int]]
    total: dict[RuleStatus, int]


class StandingFlag(Strict):
    rule_id: int
    statement: str
    severity: Severity
    status: RuleStatus


class StandingResult(Strict):
    """What you hold now against the rules about holdings."""
    disclaimer: str
    asof: str
    rows: list[RuleVerdict]
    summary: RuleCounts
    flags: dict[str, list[StandingFlag]]
    notes: list[str]


class RulesPage(Strict):
    disclaimer: str
    rules: list[RuleRow]
    templates: list[RuleTemplate]
    catalogue: RulesCatalogue
    standing: StandingResult | None = None


class ActionIn(Strict):
    """A proposed action: one of amount_dkk, quantity or (a sale) fraction of the position."""
    side: Literal["buy", "sell"]
    ticker: str
    portfolio: str | int | None = None
    amount_dkk: Num = None
    quantity: Num = None
    fraction: Num = None
    price: Num = None
    date: str | None = None
    style: Style | None = None
    horizon: Horizon | None = None
    note: str | None = None
    log: bool = False


class ResolvedAction(Strict):
    side: Literal["buy", "sell"]
    symbol: str
    name: str | None = None
    portfolio: str
    portfolio_id: int
    portfolio_kind: str
    portfolio_mode: str
    date: str
    price: Num = None
    currency: str | None = None
    rate: Num = None
    quantity: Num = None
    amount_dkk: Num = None
    fraction: Num = None
    style: str | None = None
    style_from: Literal["action", "journal"] | None = None
    horizon: str | None = None
    note: str | None = None


class CheckResult(Strict):
    disclaimer: str
    asof: str
    action: ResolvedAction
    verdicts: list[RuleVerdict]
    summary: RuleCounts
    notes: list[str]
    check_id: int | None = None


class DecisionIn(Strict):
    decision: Literal["went_ahead", "changed", "dropped"]
    reason: str | None = None
    transaction_id: int | None = None


class ReplayVerdict(Strict):
    rule_id: int
    status: RuleStatus
    message: str
    severity: Severity


class ReplayAfter(Strict):
    """What the name did from the trade day's close to the last close, in DKK, and ACWI over the same days."""
    ret: Num = None
    acwi: Num = None
    rel: Num = None
    days: int | None = None


class ReplayTrade(Strict):
    id: int
    date: str
    side: Literal["buy", "sell"]
    symbol: str
    portfolio: str
    amount_dkk: Num = None
    error: str | None = None
    verdicts: list[ReplayVerdict]
    after: ReplayAfter | None = None


class ReplayFlag(Strict):
    id: int
    date: str
    symbol: str
    status: RuleStatus
    rel: Num = None


class ReplayRule(Strict):
    rule_id: int
    statement: str
    severity: Severity
    side: Literal["buy", "sell"]
    n_flagged: int
    n_passed: int
    n_unknown: int
    flagged_rel: Num = None
    passed_rel: Num = None
    flagged: list[ReplayFlag]


class ReplayResult(Strict):
    """Would your rules have helped? Today's rules on your past real trades, each as of its own day. Descriptive."""
    disclaimer: str
    asof: str
    start: str | None = None
    end: str | None = None
    n_trades: int
    rules: list[ReplayRule]
    trades: list[ReplayTrade]
    note: str
