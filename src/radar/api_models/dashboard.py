"""The dashboard (reports/dashboard.json, written by `radar run`): regime, rotation, momentum, quality,
discovery, source coverage and your own rows."""
from __future__ import annotations

from typing import Literal

from .common import (
    FundValuation,
    Gauge,
    MyStatus,
    Num,
    Quadrant,
    RegimeLabel,
    StockFundamentals,
    StockValuation,
    Strict,
)
from .profile import Breach, Reason, Watchout


class Outdated(Strict):
    """Why the readings are behind what is on disk (dashboard.outdated): `format` = built by an older version,
    `inputs` = a file they read has changed since (named in `changed`). A rebuild needs no downloads."""
    reason: Literal["format", "inputs"]
    changed: list[str]
    rebuilding: bool                       # the app's rebuild job is running


class Snapshot(Strict):
    asof: str
    generated: str
    age_days: int
    stale: bool
    outdated: Outdated | None = None


class Overall(Strict):
    label: RegimeLabel
    on: int
    off: int
    neutral: int
    na: int
    stale: int
    total: int                             # the rows that vote
    net: float
    not_voting: int = 0                    # rows in a group switched off (regime.votes), and context rows
    voting_groups: list[str] = []


class Indicator(Strict):
    name: str
    value: str
    status: str
    note: str
    source: str
    asof: str | None = None
    gauge: Gauge | None = None
    group: str | None = None               # a switchable set of rows (settings.yaml regime.votes); None = always votes,
                                           # "context" = shown for context, never votes
    votes: bool = True


class VoteOption(Strict):
    group: str
    label: str
    on: bool
    default: bool


class VotesIn(Strict):
    votes: dict[str, bool]


class SecContact(Strict):
    email: str | None = None       # sent to SEC in the User-Agent of each EDGAR request; None: EDGAR is skipped


class ChartSeries(Strict):
    name: str
    dates: list[str]
    values: list[float | None]             # None: a gap (unknown), never 0


class LineChart(Strict):
    title: str
    decimals: int
    hlines: list[float]
    series: list[ChartSeries]


class RegimeCounts(Strict):
    total: int
    current: int
    na: list[str]
    stale: list[str]


class OldestInput(Strict):
    name: str
    asof: str | None = None
    age_days: int | None = None


class RegimeCoverage(Strict):
    regime: RegimeCounts
    oldest: OldestInput | None = None
    failing: list[str]


class RegimeView(Snapshot):
    overall: Overall
    indicators: list[Indicator]
    votes: list[VoteOption] = []
    charts: list[LineChart]
    coverage: RegimeCoverage


class RotationRow(FundValuation):
    ticker: str
    name: str
    rank: int | None = None
    rank_change: int | None = None
    quadrant: Quadrant
    quadrant_local: Quadrant | None = None
    rel_r1m: Num = None
    rel_r3m: Num = None
    rel_r6m: Num = None
    r1m: Num = None
    r3m: Num = None
    r6m: Num = None
    above200: bool | None = None
    rs_ratio: Num = None
    rs_mom: Num = None
    rs_score: Num = None
    ucits: str | None = None
    ucits_name: str | None = None
    isin: str | None = None
    positive_list: str
    gauges: dict[str, Gauge] = {}


class RrgPoint(Strict):
    date: str
    x: float
    y: float


class RrgTrail(Strict):
    ticker: str
    name: str
    quadrant: Quadrant
    tail: list[RrgPoint]


class RotationGroup(Strict):
    key: str
    label: str
    local_benchmark: str | None = None
    rrg: list[RrgTrail]
    rrg_local: list[RrgTrail] | None = None
    rows: list[RotationRow]


class RotationView(Snapshot):
    prev: str | None = None
    tail_weeks: int
    positive_list_year: str | None = None
    groups: list[RotationGroup]


class MomentumRow(StockValuation, StockFundamentals):
    ticker: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    rank: int | None = None
    score: Num = None
    r1m: Num = None
    r3m: Num = None
    r6m: Num = None
    r12_1: Num = None
    from_high: Num = None
    vol_surge: Num = None
    trend_ok: bool | None = None
    new: bool
    gauges: dict[str, Gauge] = {}


class Cluster(Strict):
    level: str
    name: str
    count: int
    expected: float
    new: int
    tickers: list[str]


class MomentumRegion(Strict):
    key: str
    label: str
    rows: list[MomentumRow]
    entrants: list[str]
    dropped: list[str]
    clusters: list[Cluster]


class MomentumView(Snapshot):
    prev: str | None = None
    top_n: int
    regions: list[MomentumRegion]


class QualityRow(StockFundamentals):
    """One stock on the Quality & value page: its scores, ranks within the region, pillars and headline metrics."""
    ticker: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    region: str
    rank_qv: int | None = None
    rank_q: int | None = None
    rank_v: int | None = None
    fcf_margin: Num = None
    gm_stability: Num = None
    rev_stability: Num = None
    rev_cagr: Num = None
    nd_ebitda: Num = None
    interest_cover: Num = None
    div_years: int | None = None
    shareholder_yield: Num = None
    ey_vs_history: Num = None
    roe: Num = None
    pb: Num = None
    q_profitability: Num = None
    q_durability: Num = None
    q_balance: Num = None
    q_record: Num = None
    momentum: Num = None                   # the momentum score in its region, for reading the two together
    new: bool
    notes: list[str] = []


class QualityCoverage(Strict):
    stocks: int                            # in the region's list
    quality: int                           # with a kvalitetsscore
    value: int
    edgar: int                             # scored from SEC EDGAR / from Yahoo
    yahoo: int


class QualityRegion(Strict):
    key: str
    label: str
    rows: list[QualityRow]                 # every stock with statements, best K+V first
    entrants: list[str]
    dropped: list[str]
    coverage: QualityCoverage


class QualityView(Snapshot):
    prev: str | None = None
    top_n: int
    regions: list[QualityRegion]


class DiscoveryRow(StockValuation, FundValuation):
    ticker: str
    name: str | None = None
    kind: Literal["stock", "etf"]
    exchange: str | None = None
    country: str | None = None
    currency: str | None = None
    sector: str | None = None
    industry: str | None = None
    category: str | None = None
    isin: str | None = None
    positive_list: str | None = None
    market_cap_dkk: Num = None
    size: Literal["large", "mid", "small"] | None = None
    liquidity_dkk: Num = None
    thin: bool | None = None
    score: Num = None
    score_prev: Num = None
    d_score: Num = None
    r1w: Num = None
    r1m: Num = None
    r3m: Num = None
    r6m: Num = None
    r12_1: Num = None
    from_high: Num = None
    vol_surge: Num = None
    trend_ok: bool | None = None
    new_high: bool | None = None
    trend_turn: bool | None = None
    rs_high: bool | None = None
    quadrant: Quadrant | None = None
    off_radar: bool
    check_data: bool | None = None
    stale: bool | None = None
    spark: list[float]


class DiscoveryMarket(Strict):
    key: str
    label: str
    kind: Literal["stock", "etf"]
    names: int
    scored: int
    rows: list[DiscoveryRow]


class DiscoveryThresholds(Strict):
    size_large_dkk: float
    size_mid_dkk: float
    liquidity_floor_dkk: float


class DiscoveryView(Snapshot):
    universe_asof: str
    markets: list[DiscoveryMarket]
    thresholds: DiscoveryThresholds


class Source(Strict):
    key: str
    name: str
    provider: str
    official: bool
    cadence: str
    feeds: str
    coverage: str
    detail: str
    asof: str | None = None
    age_days: int | None = None
    max_age: int | None = None
    status: str
    last_attempt: str | None = None
    last_success: str | None = None
    error: str | None = None


class CoverageView(Snapshot):
    sources: list[Source]
    regime: RegimeCounts
    oldest: OldestInput | None = None
    failing: list[str]
    stale_sources: list[str]
    missing_tickers: list[str]
    stale_tickers: list[str]
    behind_tickers: list[str] = []  # no bar on the as-of session: holiday, or not on Yahoo yet
    blind_spots: list[str]


class MyAnalyst(Strict):
    fetched: str | None = None
    rec_key: str | None = None
    n_analysts: Num = None
    target_low: Num = None
    target_high: Num = None
    target_mean: Num = None
    upside: Num = None
    stale: bool | None = None


class MyLevels(Strict):
    stop: Num = None
    stop_pct: Num = None
    take_profit: Num = None
    tp_pct: Num = None
    tp_source: str | None = None
    k: Num = None
    anchor: Num = None
    atr: Num = None
    anchor_basis: str | None = None
    mode: Literal["trend", "atr"] | None = None
    action: Literal["review", "sell"] | None = None
    reasons: list[Reason]
    flags: list[str]
    breaches: list[Breach]
    analyst: MyAnalyst | None = None


class MyRow(StockValuation, FundValuation, StockFundamentals):
    symbol: str
    name: str | None = None
    status: MyStatus
    quantity: Num = None
    avg_price: Num = None
    first_trade: str | None = None
    last_sell_date: str | None = None
    last_sell_price: Num = None
    last: Num = None
    r1m: Num = None
    r3m: Num = None
    r6m: Num = None
    r12_1: Num = None
    from_high: Num = None
    sma50: Num = None
    sma200: Num = None
    vol_surge: Num = None
    history: int | None = None
    above50: bool | None = None
    above200: bool | None = None
    trend_ok: bool | None = None
    rel_r3m: Num = None
    score: Num = None
    since_buy: Num = None
    bench_since_buy: Num = None
    since_sell: Num = None
    flags: list[str]
    levels: MyLevels | None = None
    gauges: dict[str, Gauge] = {}
    watchouts: list[Watchout] = []


class MeView(Strict):
    asof: str
    generated: str
    regime: RegimeLabel | None = None
    rows: list[MyRow]
