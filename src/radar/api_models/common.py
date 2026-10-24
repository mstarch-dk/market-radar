"""The pieces every area's response models share: the Strict base (extra fields are an error), Num and
Status, the graded Gauge, and the valuation and fundamentals fields that profile rows and dashboard rows both carry."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Status = Literal["ok", "stale", "missing"]
Quadrant = Literal["Leading", "Weakening", "Lagging", "Improving", "n/a"]   # signals/rotation.py quadrant()
RegimeLabel = Literal["Risk-on", "Risk-off", "Mixed"]                      # signals/regime.py overall()
Num = float | None


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Gauge(Strict):
    """A reading graded between its thresholds: score in [-1, 1] (+ green/good, - red/warning), level -4..4,
    a word, and the axis (ticks, lo, hi) to draw it on. See signals/gauges.py."""
    value: float
    score: float
    level: int
    label: str
    scale: Literal["diverging", "sequential"]
    unit: Literal["pct", "num"] = "num"
    ticks: list[float]
    lo: float
    hi: float


class StockValuation(Strict):
    """A stock's valuation from the weekly snapshot (valuation.py): P/E on trailing, this-year and next-year
    consensus EPS, against its sector's median among the same peers, and the change in the next-year EPS estimate
    over 4 and 12 weeks (None until the snapshots go back that far)."""
    pe_fy1: Num = None
    pe_cy: Num = None
    pe_ttm: Num = None
    pb: Num = None
    div_yield: Num = None
    pe_vs_sector: Num = None
    eps_rev_4w: Num = None
    eps_rev_12w: Num = None
    earnings_date: str | None = None
    val_gauges: dict[str, Gauge] = {}      # graded pe_vs_sector and eps_rev (kept apart from the momentum gauges)


class FundValuation(Strict):
    """A fund's multiples from Yahoo fund data: P/E, relative to ACWI's and its percentile in its own stored history."""
    pe: Num = None
    pe_vs_acwi: Num = None
    pe_pct: Num = None
    val_gauges: dict[str, Gauge] = {}


class StockFundamentals(Strict):
    """A stock's kvalitetsscore and værdiscore (signals/fundamentals.py), 0–100 among its sector's peers, with
    how many of the four quality pillars and four value metrics they rest on (None: too few to score)."""
    quality: Num = None
    value: Num = None
    qv: Num = None                         # the mean of the two, only when both exist
    q_n: int | None = None
    v_n: int | None = None
    fund_set: Literal["standard", "financial"] | None = None
    fund_source: Literal["edgar", "yahoo"] | None = None
    fund_period_end: str | None = None
    fcf_yield: Num = None
    ev_ebit: Num = None
    roic: Num = None
    fund_gauges: dict[str, Gauge] = {}


MyStatus = Literal["holding", "watch", "sold"]
