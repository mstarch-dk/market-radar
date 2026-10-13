"""Response models for the web API. They mirror profile.py's dicts exactly (extra fields are an error), and
the TypeScript types in web/src/api/schema.ts are generated from them, so the two can't drift apart."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Status = Literal["ok", "stale", "missing"]
Num = float | None


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Section(Strict):
    status: Status
    source: str
    asof: str | None = None


class Position(Strict):
    quantity: Num = None
    avg_price: Num = None
    first_trade: str | None = None


class Identity(Section):
    symbol: str
    name: str | None = None
    quote_type: str | None = None
    currency: str | None = None
    exchange: str | None = None
    country: str | None = None
    sector: str | None = None
    industry: str | None = None
    website: str | None = None
    summary: str | None = None
    employees: int | None = None
    region: str
    tracked: bool
    stock_group: str | None = None
    etf_group: str | None = None
    ucits: str | None = None
    isin: str | None = None
    positive_list: str | None = None
    my_status: MyStatus | None = None
    my_position: Position | None = None


class Windows(Strict):
    r1w: Num = None
    r1m: Num = None
    r3m: Num = None
    r6m: Num = None
    r1y: Num = None
    ytd: Num = None


class Bar(Strict):
    date: str
    close: float
    change: Num = None
    volume: Num = None


class Price(Section):
    last: float
    traded_last: Num = None
    change_1d: Num = None
    currency: str | None = None
    returns: Windows
    returns_dkk: Windows | None = None
    vs_acwi: Windows
    sector_etf: str | None = None
    vs_sector: Windows | None = None
    high_52w: float
    low_52w: float
    from_high: float
    from_low: float
    recent: list[Bar]


class Momentum(Section):
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
    score: Num = None
    rank: int | None = None
    group_size: int
    score_basis: str
    region_label: str | None = None


class Technicals(Section):
    rsi14: Num = None
    rsi_state: Literal["overbought", "oversold", "neutral"] | None = None
    macd: Num = None
    macd_signal: Num = None
    macd_hist: Num = None
    macd_state: Literal["bullish", "bearish"] | None = None
    bb_pct_b: Num = None
    bb_upper: Num = None
    bb_lower: Num = None
    atr: Num = None
    atr_pct: Num = None
    vol_3m: Num = None
    max_drawdown_1y: Num = None
    beta_acwi: Num = None
    corr_acwi: Num = None


class Reason(Strict):
    signal: str
    effect: float
    detail: str


class Breach(Strict):
    date: str
    close: float
    stop: float


class Levels(Section):
    stop: Num = None
    stop_pct: Num = None
    take_profit: Num = None
    tp_pct: Num = None
    tp_source: str | None = None
    k: Num = None
    anchor: Num = None
    atr: Num = None
    anchor_basis: str | None = None
    reasons: list[Reason] = []
    flags: list[str] = []
    breaches: list[Breach] = []
    regime: str | None = None


class Recommendation(Strict):
    period: str | None = None
    strong_buy: int
    buy: int
    hold: int
    sell: int
    strong_sell: int
    n: int
    mean: Num = None


class Eps(Strict):
    period: str
    label: str
    eps: Num = None
    currency: str | None = None
    chg_7d: Num = None
    chg_30d: Num = None
    chg_90d: Num = None
    up_30d: int | None = None
    down_30d: int | None = None
    growth: Num = None
    index_growth: Num = None


class Calendar(Strict):
    next_earnings: str | None = None
    eps_estimate: Num = None
    revenue_estimate: Num = None
    ex_dividend: str | None = None
    dividend_date: str | None = None


class Analyst(Section):
    fetched: str | None = None
    quote_type: str | None = None
    n_analysts: Num = None
    rec_key: str | None = None
    rec_mean: Num = None
    stale: bool | None = None
    max_age_days: int | None = None
    target_mean: Num = None
    target_median: Num = None
    target_high: Num = None
    target_low: Num = None
    upside: Num = None
    target_change: Num = None
    recommendations: list[Recommendation]
    eps: list[Eps]
    calendar: Calendar


class Fundamentals(Section):
    market_cap: Num = None
    market_cap_dkk: Num = None
    enterprise_value: Num = None
    currency: str | None = None
    financial_currency: str | None = None
    trailing_pe: Num = None
    forward_pe: Num = None
    peg: Num = None
    price_to_book: Num = None
    ev_ebitda: Num = None
    ev_revenue: Num = None
    gross_margin: Num = None
    operating_margin: Num = None
    profit_margin: Num = None
    revenue_growth: Num = None
    earnings_growth: Num = None
    return_on_equity: Num = None
    debt_to_equity: Num = None
    dividend_yield: Num = None
    payout_ratio: Num = None
    beta: Num = None
    short_pct_float: Num = None
    employees: int | None = None
    beta_radar: Num = None
    notes: list[str] = []


class Holding(Strict):
    symbol: str
    name: str | None = None
    weight: Num = None


class SectorWeight(Strict):
    sector: str
    weight: float


class Etf(Section):
    top_holdings: list[Holding]
    sector_weights: list[SectorWeight]
    asset_classes: dict[str, float]
    expense_ratio: Num = None
    total_assets: Num = None
    family: str | None = None
    legal_type: str | None = None
    notes: list[str] = []
    overlap: list[str]


class Peer(Strict):
    ticker: str
    name: str | None = None
    region: str
    score: Num = None
    r3m: Num = None
    r6m: Num = None
    trend_ok: bool | None = None
    from_high: Num = None


class Rotation(Strict):
    ticker: str
    name: str
    quadrant: str
    rs_ratio: Num = None
    rs_mom: Num = None
    rel_r3m: Num = None


class Peers(Section):
    industry: str | None = None
    peers: list[Peer]
    rotation: Rotation | None = None


class Regime(Strict):
    label: str | None = None
    asof: str | None = None
    net: Num = None


class Context(Strict):
    regime: Regime
    notes: list[str]
    errors: dict[str, str]


class Profile(Strict):
    symbol: str
    generated: str
    identity: Identity
    price: Price
    momentum: Momentum
    technicals: Technicals
    levels: Levels
    analyst: Analyst
    fundamentals: Fundamentals
    etf: Etf | None = None
    peers: Peers
    context: Context


class Series(Strict):
    symbol: str
    dates: list[str]
    close: list[Num]
    high: list[Num]
    low: list[Num]
    volume: list[Num]
    sma50: list[Num]
    sma200: list[Num]
    rsi: list[Num]
    macd: list[Num]
    macd_signal: list[Num]
    macd_hist: list[Num]
    bb_upper: list[Num]
    bb_lower: list[Num]
    rel_acwi: list[Num]


class SearchHit(Strict):
    symbol: str
    name: str | None = None
    exchange: str | None = None
    quote_type: str | None = None
    tracked: bool


MyStatus = Literal["holding", "watch", "sold"]


class ListedTicker(Strict):
    symbol: str
    name: str | None = None
    status: MyStatus


class AppContext(Strict):
    regime: Regime
    tickers: list[ListedTicker]


class WatchState(Strict):
    symbol: str
    my_status: MyStatus | None = None


# ---------------- dashboard (reports/dashboard.json, written by `radar run`) ----------------

class Snapshot(Strict):
    asof: str
    generated: str


class Overall(Strict):
    label: str
    on: int
    off: int
    neutral: int
    na: int
    stale: int
    total: int
    net: float


class Indicator(Strict):
    name: str
    value: str
    status: str
    note: str
    source: str
    asof: str | None = None


class ChartSeries(Strict):
    name: str
    dates: list[str]
    values: list[float]


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
    charts: list[LineChart]
    coverage: RegimeCoverage


class RotationRow(Strict):
    ticker: str
    name: str
    rank: int | None = None
    rank_change: int | None = None
    quadrant: str
    quadrant_local: str | None = None
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


class RrgPoint(Strict):
    date: str
    x: float
    y: float


class RrgTrail(Strict):
    ticker: str
    name: str
    quadrant: str
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


class MomentumRow(Strict):
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


class FactSetPoint(Strict):
    report_date: str
    quarter: str | None = None
    growth_now: Num = None
    fwd_pe: Num = None


class FactSet(Strict):
    quarter: str | None = None
    growth_now: Num = None
    growth_start: Num = None
    guidance_neg: Num = None
    guidance_pos: Num = None
    fwd_pe: Num = None
    fwd_pe_5y: Num = None
    fwd_pe_10y: Num = None
    cy_next_growth: Num = None
    rev_up_sectors: str | None = None
    rev_down_sectors: str | None = None
    report_date: str
    history: list[FactSetPoint]


class CliRow(Strict):
    area: str
    label: str
    asof: str
    cli: float
    chg_3m: float
    phase: str


class CotRow(Strict):
    market: str
    group: str
    asof: str
    net_pct_oi: float
    chg_4w: Num = None
    percentile: float
    flag: str | None = None


class PositioningView(Snapshot):
    factset: FactSet | None = None
    cli: list[CliRow]
    cot: list[CotRow]


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
    reasons: list[Reason]
    flags: list[str]
    breaches: list[Breach]
    analyst: MyAnalyst | None = None


class MyRow(Strict):
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


class MeView(Strict):
    asof: str
    generated: str
    regime: str | None = None
    rows: list[MyRow]
