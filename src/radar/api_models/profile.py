"""The ticker profile (profile.py) and its series, search hits, the ticker list and the app's context."""
from __future__ import annotations

from typing import Literal

from .common import Gauge, MyStatus, Num, Quadrant, RegimeLabel, Status, Strict
from .views import ViewAlignment


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
    mode: Literal["trend", "atr"] | None = None      # trend: the level is a moving average to review at; atr: a trailing stop
    action: Literal["review", "sell"] | None = None
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
    alpha_basis: str
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
    earnings_start: str | None = None
    earnings_end: str | None = None
    is_range: bool = False
    eps_estimate: Num = None
    eps_low: Num = None
    eps_high: Num = None
    revenue_estimate: Num = None
    revenue_low: Num = None
    revenue_high: Num = None
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


class PePoint(Strict):
    date: str
    pe: float


class ValuationSnapshot(Strict):
    """This ticker in the weekly valuation snapshot (stocks: P/E on next year's EPS vs its sector; funds: Yahoo
    fund P/E vs ACWI)."""
    kind: Literal["stock", "fund"]
    asof: str | None = None
    weeks: int
    pe: Num = None
    pe_vs_sector: Num = None
    pe_vs_acwi: Num = None
    pe_pct: Num = None
    eps_rev_4w: Num = None
    eps_rev_12w: Num = None
    sector: str | None = None
    gauges: dict[str, Gauge] = {}
    history: list[PePoint]


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
    snapshot: ValuationSnapshot | None = None


class FundMetric(Strict):
    key: str
    label: str
    value: Num = None
    pct: Num = None                        # percentile among the peers (0–100, higher = better for the score)
    basis: Literal["sector", "universe"] | None = None
    peers: int | None = None
    pillar: str                            # profitability | durability | balance | record | value


class FundYear(Strict):
    year: str                              # the fiscal year's end
    revenue: Num = None
    gross_margin: Num = None
    fcf_margin: Num = None


class QualityCard(Section):
    """The ticker page's kvalitetsscore and værdiscore: scores, every metric with its percentile, the years."""
    quality: Num = None
    value: Num = None
    qv: Num = None
    q_n: int | None = None
    v_n: int | None = None
    fund_set: Literal["standard", "financial"] | None = None
    fund_source: Literal["edgar", "yahoo"] | None = None
    period_end: str | None = None          # the latest period the figures reach
    filed: str | None = None               # EDGAR: the latest filing date
    currency: str | None = None            # the reporting currency of the figures
    ttm_basis: str | None = None           # how the last twelve months were built (fy, ytd, 4q, yahoo_ttm)
    ev_ebit: Num = None
    market_cap: Num = None                 # in the reporting currency
    pillars: dict[str, Num] = {}
    metrics: list[FundMetric] = []
    history: list[FundYear] = []
    notes: list[str] = []
    gauges: dict[str, Gauge] = {}


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
    quadrant: Quadrant
    rs_ratio: Num = None
    rs_mom: Num = None
    rel_r3m: Num = None


class Peers(Section):
    industry: str | None = None
    peers: list[Peer]
    rotation: Rotation | None = None


class Regime(Strict):
    label: RegimeLabel | None = None
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
    quality: QualityCard | None = None     # stocks only; status "missing" without stored statements
    etf: Etf | None = None
    peers: Peers
    context: Context
    views: ViewAlignment | None = None   # your market views; left out of anonymous profiles


class SeriesRange(Strict):
    start: str                   # base date: the close the return is measured from
    short: bool                  # the stored history is shorter than the range: it runs from the first close
    ret: Num
    acwi: Num
    vs_acwi: Num                 # percentage points
    high: Num
    low: Num


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
    ranges: dict[str, SeriesRange]


class SearchHit(Strict):
    symbol: str
    name: str | None = None
    exchange: str | None = None
    quote_type: str | None = None
    tracked: bool


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
    quadrant: Quadrant | None = None
    spark: list[float]
    asof: str | None = None
    my_status: MyStatus | None = None


class WatchState(Strict):
    symbol: str
    my_status: MyStatus | None = None
