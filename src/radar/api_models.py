"""Response models for the web API. They mirror profile.py's dicts exactly (extra fields are an error), and
the TypeScript types in web/src/api/schema.ts are generated from them, so the two can't drift apart."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Status = Literal["ok", "stale", "missing"]
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


class Watchout(Strict):
    key: str
    label: str
    level: int
    text: str


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
    gauges: dict[str, Gauge] = {}


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
    gauges: dict[str, Gauge] = {}


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
    gauges: dict[str, Gauge] = {}


class RiskWindow(Strict):
    n_weeks: int
    return_ann: Num = None
    vol_ann: Num = None
    beta: Num = None
    beta_se: Num = None
    r2: Num = None
    corr: Num = None
    alpha_ann: Num = None
    alpha_t: Num = None
    alpha_basis: str
    idio_vol_ann: Num = None
    downside_beta: Num = None
    sharpe: Num = None
    sortino: Num = None
    max_dd: Num = None
    max_dd_weeks: int | None = None


class Loading(Strict):
    factor: str
    beta: Num = None
    t: Num = None


class Factors(Strict):
    n_weeks: int
    r2: Num = None
    alpha_ann: Num = None
    alpha_t: Num = None
    loadings: list[Loading]


class Risk(Section):
    currency: str
    benchmark: str
    windows: dict[str, RiskWindow]
    factors: Factors | None = None
    budget: Num = None
    budget_risk: Num = None
    notes: list[str] = []


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
    gauges: dict[str, Gauge] = {}


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
    watchouts: list[Watchout] = []


class Profile(Strict):
    symbol: str
    generated: str
    identity: Identity
    price: Price
    momentum: Momentum
    technicals: Technicals
    levels: Levels
    risk: Risk | None = None
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


class TickerSummary(Strict):
    symbol: str
    name: str | None = None
    kind: Literal["stock", "etf"] | None = None
    group: str | None = None
    currency: str | None = None
    last: Num = None
    change_1d: Num = None
    r1m: Num = None
    r3m: Num = None
    score: Num = None
    quadrant: str | None = None
    spark: list[float]
    asof: str | None = None
    my_status: MyStatus | None = None


class WatchState(Strict):
    symbol: str
    my_status: MyStatus | None = None


# ---------------- dashboard (reports/dashboard.json, written by `radar run`) ----------------

class Snapshot(Strict):
    asof: str
    generated: str
    age_days: int
    stale: bool


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
    gauge: Gauge | None = None


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
    gauges: dict[str, Gauge] = {}


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


class DiscoveryRow(Strict):
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
    quadrant: str | None = None
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
    gauge: Gauge | None = None


class CotRow(Strict):
    market: str
    group: str
    asof: str
    net_pct_oi: float
    chg_4w: Num = None
    percentile: float
    flag: str | None = None
    gauge: Gauge | None = None


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
    gauges: dict[str, Gauge] = {}
    watchouts: list[Watchout] = []


class MeView(Strict):
    asof: str
    generated: str
    regime: str | None = None
    rows: list[MyRow]


class UpdateProgress(Strict):
    done: int
    total: int
    label: str


class UpdateStatus(Strict):
    status: Literal["idle", "running", "done", "failed"]
    started: str | None = None
    finished: str | None = None
    log: list[str]
    progress: UpdateProgress | None = None
    error: str | None = None


class ImportResult(Strict):
    holdings: int
    sold: int
    watch: int
    warnings: dict[str, list[str]]


# ---------------- portfolio editor ----------------

class TxIn(Strict):
    symbol: str
    date: str
    type: Literal["BUY", "SELL"]
    quantity: float
    price: float
    fee: float = 0.0
    account: str | None = None
    note: str | None = None
    confirm: bool = False                  # save despite warnings (errors always block)


class TxRow(Strict):
    id: int
    symbol: str
    date: str
    type: Literal["BUY", "SELL"]
    quantity: float
    price: float
    fee: float
    account: str | None = None
    note: str | None = None
    source: str
    import_id: int | None = None
    ext_ref: str | None = None
    created_at: str
    updated_at: str


class Issue(Strict):
    level: Literal["error", "warning"]
    field: str
    message: str


class PositionState(Strict):
    quantity: float
    avg_price: Num = None


class Effect(Strict):
    symbol: str
    before: PositionState
    after: PositionState


class PriceCheck(Strict):
    symbol: str
    currency: str | None = None
    close: Num = None
    close_date: str | None = None
    verdict: Literal["ok", "x100", "div100", "far", "no_data"]
    message: str | None = None


class TxCheck(Strict):
    issues: list[Issue]
    effect: Effect | None = None
    price: PriceCheck | None = None


class TxResult(Strict):
    tx: TxRow
    issues: list[Issue]


class PositionRow(Strict):
    symbol: str
    name: str | None = None
    currency: str | None = None
    account: str | None = None
    accounts: str | None = None
    quantity: float
    avg_price: float
    first_trade: str | None = None
    last: Num = None
    value: Num = None
    unrealized: Num = None


class PositionsView(Strict):
    total: list[PositionRow]
    by_account: list[PositionRow]
    warnings: dict[str, list[str]]
    transactions: int


class Account(Strict):
    name: str
    kind: Literal["ask", "frie_midler", "pension", "other"]
    note: str | None = None


class AccountIn(Account):
    old_name: str | None = None


class ImportRow(Strict):
    row: int
    ident: str
    symbol_in: str | None = None
    isin: str | None = None
    name: str | None = None
    date: str | None = None
    type: Literal["BUY", "SELL"] | None = None
    quantity: Num = None
    price: Num = None
    fee: float = 0.0
    currency: str | None = None
    account: str | None = None
    ext_ref: str | None = None
    skip: str | None = None
    symbol: str | None = None
    issues: list[Issue] = []
    duplicate: bool = False


class SymbolCandidate(Strict):
    symbol: str
    how: str
    name: str | None = None
    exchange: str | None = None


class SymbolMatch(Strict):
    ident: str
    isin: str | None = None
    name: str | None = None
    candidates: list[SymbolCandidate]
    chosen: str | None = None
    certain: bool


class ImportCounts(Strict):
    rows: int
    new: int
    duplicates: int
    skipped: int
    errors: int
    warnings: int


class ImportPreview(Strict):
    preset: str | None = None
    preset_label: str | None = None
    verified: bool | None = None
    snapshot: bool
    columns: list[str]
    mapping: dict[str, str]
    rows: list[ImportRow]
    symbols: list[SymbolMatch]
    watch: list[str]
    counts: ImportCounts


class ImportCommitResult(Strict):
    id: int
    added: int
    skipped: int
    replaced: int
    source: str


class ImportRecord(Strict):
    id: int
    source: str
    file_name: str | None = None
    rows_added: int
    rows_skipped: int
    at: str
    rows_now: int


class Preset(Strict):
    key: str
    label: str
    verified: bool
