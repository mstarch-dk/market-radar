"""Attribution vs ACWI (attribution.py): why a selection of portfolios beat or lagged ACWI, by sector, region and
currency, tied to Returns by the reconciliation, and the factor regression. Missing figures are None, never 0."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Num, Strict
from .xray import FundClass

SegmentDim = Literal["sector", "region"]             # segments.DIMS


class AttributionSelection(Strict):
    ids: list[int]
    names: list[str]
    scope: str | None = None


class AttributionPeriod(Strict):
    """The book's valued history inside the period asked for; `months` from start to end."""
    start: str
    end: str
    months: float


class Reconciliation(Strict):
    """TWR − ACWI = trading and fees (TWR minus the buy-and-hold return of the daily weights) + benchmark proxies vs
    ACWI + the attributed active return. None where a leg has no data."""
    twr: float
    acwi: Num = None
    active: Num = None
    trading_fees: Num = None
    proxy_vs_acwi: Num = None
    attributed: Num = None


class EffectTotals(Strict):
    allocation: float
    selection: float
    interaction: float
    currency: float
    cross: float


class SegmentRow(Strict):
    """One segment over the period: average weights, compounded returns on the days held (None: never held), and
    its effects linked with Carino. `cash` is a segment whose benchmark return is 0: the cash drag."""
    key: str
    w_p: Num = None
    w_b: Num = None
    r_p: Num = None
    r_b: Num = None
    allocation: float
    selection: float
    interaction: float
    total: float


class AttributionMonth(Strict):
    """One month's effects linked over its days; `basis` back-drifted when any day's ACWI weights were rolled back
    from the first weekly snapshot."""
    month: str
    allocation: float
    selection: float
    interaction: float
    currency: float
    cross: float
    active: float
    days: int
    basis: Literal["snapshot", "back-drifted"]


class AttributionDim(Strict):
    """One dimension (sector or region): segments largest |total| first, the months, the period's totals, the
    portfolio's and the proxies' returns over the days used, the days left out and the linking error."""
    rows: list[SegmentRow]
    months: list[AttributionMonth]
    totals: EffectTotals
    rp: Num = None
    rb: Num = None
    days: int
    days_missing: int
    linking_error: float
    proxy_notes: list[str]
    reconciliation: Reconciliation


class CurrencyRow(Strict):
    currency: str
    w_p: Num = None
    w_b: Num = None
    fx_return: Num = None
    effect: float


class CurrencyEffect(Strict):
    """The currency effect (the same in both dimensions) and the sector dimension's cross term, by currency;
    `unknown` holds value whose currency isn't known (its whole return counted as local)."""
    effect: float
    cross: float
    rows: list[CurrencyRow]


class AttributionBenchmark(Strict):
    """The first weekly record of ACWI's weights (None: none yet) and the months whose weights are back-drifted."""
    first_snapshot: str | None = None
    back_drifted_months: list[str]


class Unclassified(Strict):
    """A holding that can't be placed by sector: its own segment with its own return, never a 0 % return."""
    symbol: str
    class_: FundClass = Field(alias="class")         # `class` on the wire; a Python keyword
    avg_weight: Num = None


class FactorLoading(Strict):
    factor: str
    beta: Num = None
    t: Num = None


class FactorRegression(Strict):
    """Weekly excess returns in DKK on French's developed factors with Newey-West t: alpha p.a. with its t and n,
    and the weeks and months of data it would take to reach t = 2 (None once |t| ≥ 2 or without a t)."""
    n_weeks: int
    start: str
    end: str
    nw_lag: int
    r2: Num = None
    alpha_ann: Num = None
    alpha_t: Num = None
    alpha_se_ann: Num = None
    reached: bool
    weeks_to_t2: Num = None
    months_to_t2: Num = None
    loadings: list[FactorLoading]
    factors_to: str


class AttributionView(Strict):
    """GET /api/attribution: the attribution of a selection of portfolios (default: your real ones) vs ACWI,
    computed live. Too short a history or no ACWI weights yet: nulls and notes, not an error."""
    asof: str | None = None
    generated: str
    selection: AttributionSelection
    period: AttributionPeriod | None = None
    reconciliation: Reconciliation | None = None
    dims: dict[SegmentDim, AttributionDim]
    currency: CurrencyEffect | None = None
    benchmark: AttributionBenchmark
    unclassified: list[Unclassified]
    regression: FactorRegression | None = None
    notes: list[str]
