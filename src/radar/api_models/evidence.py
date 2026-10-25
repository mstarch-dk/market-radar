"""The Evidence page (evidence.py): the score studies, the long-run study, the rule studies' headers and the forward
scoreboard. A number a report doesn't have is None, never 0; a stale report's numbers are only in its own card."""
from __future__ import annotations

from typing import Literal

from .common import Num, Strict

ReportStatus = Literal["ok", "stale", "missing", "invalid"]     # model/artifacts.Status


class ReportHead(Strict):
    """A study report's header row. `stale`: it tested another rule than today's (`rule_hash` vs `rule_hash_now`),
    or recorded none; `old_data`: an ok report whose last day of data is older than `evidence.max_age_days`."""
    name: str
    signal: str | None = None
    label: str
    status: ReportStatus
    reason: str | None = None
    command: str
    created: str | None = None
    data_asof: str | None = None
    age_days: int | None = None
    old_data: bool
    rule_hash: str | None = None
    rule_hash_now: str | None = None
    legacy: bool


class ScoreRow(Strict):
    """The baseline over one split of formation dates; each mean next to its Newey-West t. `top_vs_acwi`: the top N
    in DKK minus ACWI (its t judges `top_dkk` too)."""
    dates: int | None = None
    ic_mean: Num = None
    ic_t: Num = None
    ic_pos: Num = None
    q: list[Num] | None = None
    monotone: bool | None = None
    spread: Num = None
    spread_t: Num = None
    top_excess: Num = None
    top_excess_t: Num = None
    top_dkk: Num = None
    acwi_dkk: Num = None
    top_vs_acwi: Num = None
    top_vs_acwi_t: Num = None
    top_beats_acwi: Num = None


class ScoreHorizon(Strict):
    h: int
    all: ScoreRow | None = None
    in_sample: ScoreRow | None = None
    holdout: ScoreRow | None = None


class VariantVerdict(Strict):
    h: int
    variant: str
    label: str | None = None
    in_sample_ic: Num = None
    holdout_ic: Num = None
    holdout_ic_t: Num = None
    holdout_diff_t: Num = None


class ScoreUniverse(Strict):
    tickers: int | None = None
    fund_names: int | None = None
    first: str | None = None
    last: str | None = None


class ScoreCard(Strict):
    head: ReportHead
    universe: ScoreUniverse | None = None
    us_only: bool
    baseline: str | None = None
    variants_tried: int | None = None
    n_top: int | None = None
    holdout_from: str | None = None
    horizons: list[ScoreHorizon]
    verdicts: list[VariantVerdict]
    turnover: Num = None
    momentum_corr: Num = None
    caveats: list[str]
    notes: list[str]


class LongrunRow(Strict):
    dates: int | None = None
    eff_n: Num = None
    ic_mean: Num = None
    ic_t: Num = None
    spread: Num = None
    spread_t: Num = None
    top_excess: Num = None
    top_excess_t: Num = None
    top_vs_market: Num = None
    top_vs_market_t: Num = None


class LongrunHorizon(Strict):
    h: int
    all: LongrunRow | None = None
    holdout: LongrunRow | None = None


class LongrunPart(Strict):
    """One split of the baseline (a decade, in or out of recession) at one horizon."""
    h: int
    part: str
    row: LongrunRow | None = None


class LongrunPanelCard(Strict):
    """A panel the long-run study ranks; `error`: why it wasn't studied (then everything else is empty)."""
    key: str
    label: str | None = None
    members: int | None = None
    n_top: int | None = None
    months: int | None = None
    first: str | None = None
    last: str | None = None
    baseline: str | None = None
    variants_tried: int | None = None
    horizons: list[LongrunHorizon]
    by_decade: list[LongrunPart]
    by_recession: list[LongrunPart]
    verdicts: list[VariantVerdict]
    error: str | None = None


class SurvivorshipGauge(Strict):
    implied_haircut: Num = None
    configured_haircut: Num = None
    first: str | None = None
    last: str | None = None
    study_top_quintile_excess_1m: Num = None
    survivorship_free_same_months: Num = None
    survivorship_free_since_1927: Num = None
    note: str | None = None


class BaseRateRow(Strict):
    label: str
    first: str | None = None
    last: str | None = None
    ann_return: Num = None
    t: Num = None
    last_10y_ann: Num = None
    share_neg_6m: Num = None
    share_neg_12m: Num = None
    max_dd: Num = None


class LongrunCard(Strict):
    head: ReportHead
    holdout_from: str | None = None
    panels: list[LongrunPanelCard]
    survivorship: SurvivorshipGauge | None = None
    base_rates: list[BaseRateRow]
    caveats: list[str]
    notes: list[str]


class ForwardRecord(Strict):
    """One forward line against ACWI over the same days. `too_short`: younger than its minimum, so listed but never
    ranked or averaged."""
    label: str
    start: str | None = None
    days: int | None = None
    ret: Num = None
    acwi: Num = None
    excess: Num = None
    max_dd: Num = None
    too_short: bool
    note: str | None = None


class ForwardCohort(Strict):
    """The mean excess and share ahead of ACWI over the records long enough to judge, once there are `need` of
    them (else None). No t: the windows overlap and the counts are small."""
    count: int
    need: int
    enough: bool
    mean_excess: Num = None
    beat_acwi: Num = None
    note: str | None = None


class ForwardGroup(Strict):
    running: bool
    records: list[ForwardRecord]
    cohort: ForwardCohort | None = None
    note: str | None = None


class EvidenceForward(Strict):
    abtest: ForwardGroup
    paper_trail: ForwardGroup
    proposals: ForwardGroup


class EvidenceView(Strict):
    """`forward` is None without prices (the study cards don't need them)."""
    generated: str
    holdout_from: str
    longrun_holdout_from: str | None = None
    scores: list[ScoreCard]
    longrun: LongrunCard
    rules: list[ReportHead]
    forward: EvidenceForward | None = None
    notes: list[str]
