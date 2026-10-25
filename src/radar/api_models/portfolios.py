"""Portfolios: fees, simulations, the portfolio list, performance against ACWI, the comparison and the
A/B test."""
from __future__ import annotations

from typing import Any, Literal

from .common import Num, Strict
from .dashboard import LineChart

PortfolioKind = Literal["ask", "frie_midler", "pension", "other"]
PortfolioMode = Literal["real", "virtual"]


FeeMarket = Literal["DK", "NORDIC", "US", "EU", "UK", "OTHER"]


class FeeRule(Strict):
    """A market's commission: pct of the trade's value, at least `min` and at most `max` (in `currency`)."""
    market: FeeMarket
    pct: float
    min: float | None = None
    max: float | None = None
    currency: str = "DKK"


class FeeSchedule(Strict):
    """A portfolio's broker fees (fees.py), to estimate a trade's commission. `fx_pct`: the currency-exchange
    surcharge, shown apart from the fee."""
    preset: str | None = None
    as_of: str | None = None
    markets: list[FeeRule]
    fx_pct: float | None = None
    note: str | None = None


class FeePreset(Strict):
    id: str
    label: str
    as_of: str
    source_url: str
    note: str | None = None
    schedule: FeeSchedule


class FeeEstimate(Strict):
    """A trade's estimated commission in the quote currency, from its portfolio's fee schedule."""
    fee: float
    currency: str
    market: FeeMarket
    rule_market: FeeMarket                 # the rule used (OTHER when the schedule has none for the market)
    applied: Literal["pct", "min", "max"]
    basis: str                             # e.g. "0.1% (min 29 DKK)"
    fx_pct: float | None = None
    fx_fee: Num = None                     # the FX surcharge on the trade, not included in `fee`
    preset: str | None = None
    as_of: str | None = None


class SimRun(Strict):
    """One run that wrote a simulated portfolio's rows (the latest replaces the earlier ones)."""
    id: int
    portfolio_id: int
    strategy: str
    params: dict[str, Any]
    start: str
    end: str | None = None
    data_asof: str | None = None
    status: Literal["ok", "failed"]
    rows: int
    message: str | None = None
    at: str


class Portfolio(Strict):
    """A real portfolio (one of your accounts) or a virtual one (a simulation or an A/B test). Only real ones
    count as yours unless others are chosen; tags are free-form labels for grouping."""
    id: int
    name: str
    mode: PortfolioMode
    kind: PortfolioKind
    dividends: Literal["reinvested", "cash"]
    origin: Literal["manual", "fork", "sim"]
    parent_id: int | None = None
    forked_at: str | None = None
    strategy: str | None = None
    params: dict[str, Any] | None = None
    fee_schedule: FeeSchedule | None = None
    tax_person_id: int | None = None       # who owns the account for the tax estimate (none: no estimate)
    note: str | None = None
    archived: bool
    tags: list[str]
    is_default: bool
    n_tx: int
    first_date: str | None = None
    last_date: str | None = None
    created_at: str
    updated_at: str


class PortfolioIn(Strict):
    name: str
    mode: PortfolioMode = "real"
    kind: PortfolioKind = "other"
    dividends: Literal["reinvested", "cash"] = "reinvested"
    note: str | None = None
    archived: bool = False
    tags: list[str] = []
    fee_schedule: FeeSchedule | None = None    # left out: kept as it is; null: removed
    tax_person_id: int | None = None           # left out: kept as it is; null: nobody


class TagsIn(Strict):
    tags: list[str]


class TagCount(Strict):
    tag: str
    n: int


class MoveIn(Strict):
    to: int
    ids: list[int] | None = None           # only these rows (default: all of them)
    symbols: list[str] | None = None       # only these tickers


class MoveResult(Strict):
    moved: int


class ForkIn(Strict):
    name: str
    date: str                              # the copy is of the portfolio at that day's close
    extra_cash_dkk: float = 0.0
    tags: list[str] = []


class PortfolioRef(Strict):
    id: int
    name: str
    mode: PortfolioMode
    kind: PortfolioKind
    tags: list[str]
    archived: bool


class PeriodReturn(Strict):
    portfolio: Num = None
    acwi: Num = None


class PerfStats(Strict):
    """Returns in DKK. TWR: the investments' own return (cash-flow timing left out); MWR: the annual rate your
    actual flows earned (XIRR). ACWI: the same, given the same flows. Annualised figures need a year of history."""
    start: str | None = None
    days: int
    value_dkk: Num = None
    invested_dkk: Num = None
    twr_total: Num = None
    twr_ann: Num = None
    mwr_ann: Num = None
    acwi_twr_total: Num = None
    acwi_twr_ann: Num = None
    acwi_mwr_ann: Num = None
    excess_twr: Num = None
    max_drawdown: Num = None
    vol_ann: Num = None
    periods: dict[str, PeriodReturn]


class PerfSeries(Strict):
    dates: list[str]
    value_dkk: list[float | None]
    cash_dkk: list[float | None]
    invested_dkk: list[float | None]
    index: list[float | None]              # time-weighted, 100 at the start
    acwi_index: list[float | None]
    acwi_same_flows_dkk: list[float | None]


Funding = Literal["ledger", "implicit", "mixed"]


class Performance(Strict):
    portfolio: PortfolioRef
    asof: str
    funding: Funding
    dividends: str
    missing: list[str]
    notes: list[str]
    stats: PerfStats | None = None
    series: PerfSeries


class CompareRow(Strict):
    kind: Literal["portfolio", "tag"]
    label: str
    portfolio: PortfolioRef | None = None
    tag: str | None = None
    members: list[str] = []
    funding: Funding
    stats: PerfStats | None = None
    notes: list[str]
    missing: list[str]


class Comparison(Strict):
    asof: str
    start: str | None = None
    rows: list[CompareRow]
    chart: LineChart


class AbPortfolio(Strict):
    kind: Literal["ab-qv", "ab-momentum", "ab-blend"]
    label: str
    id: int
    name: str


class AbPick(Strict):
    ticker: str
    weight: float
    score: Num = None                      # the basket's score on the day it was picked (None in the blend)


class AbRebalance(Strict):
    kind: Literal["ab-qv", "ab-momentum", "ab-blend"]
    label: str
    date: str                              # the day the picks were recorded (bought at the next session)
    picks: list[AbPick]
    turnover: float                        # share of the basket traded (0–1)


class Correlation(Strict):
    symbols: list[str]
    weeks: int
    matrix: list[list[Num]]                # None where a pair has too few weeks


class AbTest(Strict):
    """The forward A/B test (abtest.py): three virtual baskets from their start on, against ACWI."""
    running: bool
    portfolios: list[AbPortfolio]
    params: dict[str, Any] | None = None
    comparison: Comparison | None = None
    correlation: Correlation | None = None
    rebalances: list[AbRebalance]
    next_due: str | None = None
    notes: list[str]


class AbStartIn(Strict):
    capital: float | None = None
    n: int | None = None
    max_per_sector: int | None = None
    value_score: Literal["qv", "value"] | None = None
