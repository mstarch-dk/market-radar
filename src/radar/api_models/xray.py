"""The portfolio X-ray (xray.py): a selection's exposure against ACWI, where its risk sits, concentration, the stress
windows and the factor tilts. Missing figures are None, never 0."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Num, Strict
from .profile import Factors

FundClass = Literal["world", "sector_fund", "fund_sectors", "fund", "stock", "unknown"]   # exposure.CLASSES


class XraySelection(Strict):
    ids: list[int]
    names: list[str]
    scope: str | None = None


class Unvalued(Strict):
    """A position without a DKK value (no price, or no DKK rate): left out of every weight, never valued at 0."""
    symbol: str
    quantity: float
    reason: Literal["no price", "no DKK rate"]


class XrayTotals(Strict):
    """`cash_dkk`: summed over the portfolios that keep a cash ledger; None when none does (unknown, not 0)."""
    invested_dkk: float
    cash_dkk: Num = None
    unvalued: list[Unvalued]


class ExposureRow(Strict):
    """One key's weight, ACWI's and the active weight; `acwi` and `active` are None for a key that isn't a real
    place (a fund not looked through, unknown) or without ACWI's weights."""
    key: str
    weight: float
    acwi: Num = None
    active: Num = None


class ExposureDim(Strict):
    """Rows sorted by the size of the active weight, then the weight. `coverage`: the share of the value with a
    real key."""
    rows: list[ExposureRow]
    coverage: Num = None
    note: str | None = None


class XrayExposure(Strict):
    sector: ExposureDim
    region: ExposureDim
    currency: ExposureDim


class XrayClass(Strict):
    """How a held name is classified for the exposure (a fund looked through, a world fund, a stock …)."""
    symbol: str
    class_: FundClass = Field(alias="class")         # `class` on the wire; a Python keyword
    value_dkk: float
    weight: float
    detail_asof: str | None = None


class RiskPosition(Strict):
    """A position's share of the total risk and of the active risk (both sum to 1 with the ACWI leg; a hedge is
    negative) and its marginal contribution to the total risk, annualised."""
    symbol: str
    weight: float
    share_total: Num = None
    share_active: Num = None
    mctr_ann: Num = None


class RiskExcluded(Strict):
    symbol: str
    weight: Num = None
    reason: str


class XrayRisk(Strict):
    """Ex-ante risk of today's weights (shrunk weekly covariance over `window_weeks`), and the realised figures of
    what was actually held over the last year. `warn`: the risk model covers less than the warning level."""
    vol_ann: float
    beta: Num = None
    te_ann: Num = None
    div_ratio: Num = None
    coverage: float
    warn: bool
    realised_vol_1y: Num = None
    realised_max_dd_1y: Num = None
    positions: list[RiskPosition]
    acwi_leg_share_active: Num = None
    excluded: list[RiskExcluded]
    window_weeks: int
    shrink: float


class Largest(Strict):
    symbol: str
    weight: float


class LargestRisk(Strict):
    symbol: str
    share: float


class CorrelatedPair(Strict):
    """Two holdings whose weekly returns correlated above the threshold, and their combined weight."""
    a: str
    b: str
    corr: float
    weight: float


class Concentration(Strict):
    """Effective N (1/Σw²), the top-5 share, the largest position and the largest share of total risk. A world fund
    counts as one position, so `world_fund_weight` says how much that understates the spread."""
    effective_n: Num = None
    top5_share: Num = None
    largest: Largest | None = None
    largest_ctr: LargestRisk | None = None
    world_fund_weight: Num = None
    pairs: list[CorrelatedPair]


class StressWindow(Strict):
    """Today's weights replayed through a past window, where the price history covers at least half the value."""
    key: str
    label: str
    start: str
    end: str
    coverage: Num = None
    ret: Num = None
    max_dd: Num = None
    acwi_ret: Num = None
    acwi_max_dd: Num = None
    missing: list[str]
    note: str | None = None


class XrayView(Strict):
    """GET /api/xray: the X-ray of a selection of portfolios (default: your real ones), computed live."""
    asof: str | None = None
    generated: str
    selection: XraySelection
    totals: XrayTotals
    exposure: XrayExposure
    classes: list[XrayClass]
    risk: XrayRisk | None = None
    concentration: Concentration
    stress: list[StressWindow]
    factors: Factors | None = None
    notes: list[str]
