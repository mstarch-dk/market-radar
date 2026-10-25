"""The shape of config/settings.yaml, checked when it is loaded: a typo, a missing key or a wrong type fails at once
with the key's path, not as a KeyError deep in a study or a proposal. Every section has a model; a key the code
reads with a default is optional here too, with that default. `config.typed()` gives the checked `Settings`,
`config.settings()` the file as written (for what records or hashes it, and the readings that take a section as a
dict)."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Stops(_Section):
    mode: Literal["trend", "atr"]
    trend_sma: int
    action: str
    take_profit: bool
    atr_days: int
    k_base: float
    k_min: float
    k_max: float
    k_step: float
    strong_score: float
    extended_vs_sma50: float
    reward_risk: float
    near_atr: float
    min_analysts: int
    target_cut: float
    info_anchor_days: int
    include: list[str]
    analyst_max_age_days: int | None = None


class Backtest(_Section):
    warmup_days: int
    max_years: int
    fill: Literal["next", "same"]
    park: str
    fred_lag_days: int
    oecd_lag_days: int
    valuation_lag_days: int
    fundamentals_lag_days: int
    fee_bps: float
    study_holdout_from: date
    study_min_names: int
    random_baskets: int


class StressWindow(_Section):
    key: str
    label: str
    start: date
    end: date


class _Covariance(_Section):
    history_weeks: int
    min_weeks: int
    shrink: float


class _Xray(_Section):
    min_coverage: float
    warn_coverage: float
    pair_corr: float


class Risk(_Section):
    windows: dict[str, int]
    min_weeks: int
    factors: list[str]
    budget: float
    covariance: _Covariance
    world_funds: list[str]
    stress: list[StressWindow]
    xray: _Xray


class _Tilt(_Section):
    momentum: float
    qv: float


class _Penalties(_Section):
    vol: float
    stretch: float
    corr: float


class _Caps(_Section):
    sector: float
    region: float
    currency: float


class _Gates(_Section):
    max_stale_days: int
    min_history_weeks: int
    min_adv_dkk: float


class _Exit(_Section):
    min_score: float
    min_qv: float
    weakening: float


class _Spread(_Section):
    min_adv_dkk: float
    bps: float


class _Prior(_Section):
    region: str
    report_regions: list[str]
    since: date
    components: dict[str, list[str]]
    qv: dict[str, float]
    tau_annual: float
    trend_months: int
    min_trend_eff_n: int


class _Bootstrap(_Section):
    draws: int
    block_weeks: int
    seed: int
    ewma_lambda: float


class _Filler(_Section):
    ticker: str
    model: str
    name: str
    isin: str
    min_dkk: float


class Propose(_Section):
    min_ticket_dkk: float
    max_names: int
    tilts: dict[str, _Tilt]
    require_trend_from: float
    penalties: _Penalties
    fill_gaps_bonus: float
    max_per_sector: int
    caps: _Caps
    max_corr: float
    gates: _Gates
    exit: _Exit
    spread_bps: list[_Spread]
    study_cost_bps: float
    horizons: list[int]
    study_ns: list[int]
    min_weeks: int
    acwi_drift_annual: float
    survivorship_haircut: float
    haircut_from_gauge: bool
    prior: _Prior
    bootstrap: _Bootstrap
    min_edge: float
    min_regime_dates: int
    max_swaps: int
    frontier_knee: float
    ask_deposit_cap: float | None
    ask_cap_year: int | None
    etf_filler: _Filler
    review_min: int


class Rotation(_Section):
    window: int
    tail: int


class Momentum(_Section):
    top_n: int
    min_history_days: int


class Regime(_Section):
    vix_calm: float
    vix_stress: float
    breadth_strong: float
    breadth_weak: float
    highs_lows_band: float
    vix_term_calm: float
    rates_shock: float
    copper_gold_band: float
    oil_shock: float
    revisions_band: float
    cape_rich_pct: float
    cape_cheap_pct: float
    erp_low_pct: float
    erp_high_pct: float
    momentum_payoff_band: float
    dispersion_low_pct: float
    dispersion_high_pct: float
    crash_rebound: float
    votes: dict[str, bool] = {}


class Positioning(_Section):
    lookback_weeks: int
    extreme_pct: float


class Sectors(_Section):
    cluster_min: int
    cluster_ratio: float


class Abtest(_Section):
    n: int
    max_per_sector: int
    capital: float
    value_score: Literal["qv", "value"]


class EvidenceAge(_Section):
    score: int
    longrun: int
    rules: int


class Evidence(_Section):
    max_age_days: EvidenceAge
    forward_min_months: int
    cohort_age_months: int
    cohort_min: int


class Analyst(_Section):
    max_age_days: int


class Coverage(_Section):
    max_age: dict[str, int]                     # source -> days behind the report's as-of date before it is stale
    blind_spots: list[str]


class Limits(_Section):
    rate: int | float | None = None
    burst: int | None = None
    concurrency: int | None = None
    retries: int | None = None
    backoff: int | float | None = None
    max_wait: int | float | None = None
    budget: int | None = None


class Cooldown(_Section):
    trip: int | None = None
    window_min: int | float | None = None
    cooldown_min: int | float | None = None
    max_cooldown_min: int | float | None = None


class Network(_Section):
    default: Limits = Limits()
    hosts: dict[str, Limits] = {}               # glob pattern -> limits, the first match wins
    cooldown: Cooldown = Cooldown()


class _FrenchFile(_Section):
    file: str
    block: str | None = None


class _JkpSet(_Section):
    region: str
    theme: str
    weighting: str
    series: str = "location"
    name: str | None = None


class _JkpPortfolios(_Section):
    weighting: str = "vw_cap"
    regions: list[str]
    characteristics: list[str]


class Factors(_Section):
    max_age_days: int = 30
    french: dict[str, str | _FrenchFile] = {}
    jkp: dict[str, _JkpSet] = {}
    jkp_portfolios: _JkpPortfolios | None = None


class _Panel(_Section):
    label: str | None = None
    data: str
    market: str = "us"
    excess: bool = False
    n_top: int = 10
    min_names: int = 20
    members: list[str] | None = None


class Longrun(_Section):
    holdout_from: date | None = None
    horizons: list[int] = [1, 3, 6, 12]
    regime_months: int = 10
    panels: dict[str, _Panel] = {}
    factors: dict[str, tuple[str, str]] = {}    # label -> (dataset, series)


class Updates(_Section):
    repo: str | None = None


class Ops(_Section):
    keep_requests_days: int = 30
    keep_events_days: int = 180


class Valuation(_Section):
    snapshot_days: int
    fallback_max: int
    pe_range: tuple[float, float]
    fund_pe_range: tuple[float, float]
    rel_band: float
    min_peers: int
    revision_band: float
    etf_history_weeks: int
    etf_min_share: float = 0.8


class Edgar(_Section):
    refresh_days: int
    after_period_days: int
    max_per_run: int
    tickers_max_age_days: int
    max_fail_share: float
    years: int


class _Lags(_Section):
    quarterly: int
    annual: int


class YahooFundamentals(_Section):
    refresh_days: int
    after_earnings_days: int
    max_per_run: int
    min_ok_share: float
    assumed_lag_days: _Lags


class _QualityScore(_Section):
    weights: dict[str, float]
    min_pillars: int
    required: list[str]


class _ValueScore(_Section):
    weights: dict[str, float]
    min_components: int
    required_any: list[str]


class Fundamentals(_Section):
    edgar: Edgar
    yahoo: YahooFundamentals
    top_n: int
    min_sector_peers: int
    financial_industries: list[str]
    ttm_max_age_days: int
    annual_max_age_days: int
    stability_years: int
    min_fy_points: int
    ey_history_years: int
    ey_history_min_points: int
    interest_cover_cap: float
    shares_low: float
    shares_high: float
    mcap_check: float
    ranges: dict[str, tuple[float, float]]
    quality: _QualityScore
    value: _ValueScore
    financial_value: _ValueScore


class Sentiment(_Section):
    putcall_backfill_days: int
    putcall_retry_days: int = 10
    putcall_lookback_days: int
    aaii_extreme_pct: float


class Gauge(_Section):
    scale: Literal["diverging", "sequential"] = "diverging"
    unit: Literal["num", "pct"] = "num"
    anchors: list[tuple[float, float]]          # (value, score): +1 good / bullish / cheap, -1 a warning
    labels: list[tuple[float | None, str]]      # (upper bound, word); the last bound is None
    ticks: list[float] = []
    range: tuple[float, float] | None = None
    abs_from: float | None = None


class Settings(_Section):
    """The whole of config/settings.yaml."""
    history_years: int
    constituents_max_age_days: int
    snapshot_min_gap_days: int
    rotation: Rotation
    momentum: Momentum
    regime: Regime
    positioning: Positioning
    sectors: Sectors
    stops: Stops
    backtest: Backtest
    abtest: Abtest
    evidence: Evidence
    propose: Propose
    risk: Risk
    analyst: Analyst
    coverage: Coverage
    network: Network
    factors: Factors
    longrun: Longrun
    updates: Updates = Updates()
    ops: Ops = Ops()
    valuation: Valuation
    fundamentals: Fundamentals
    sentiment: Sentiment
    gauges: dict[str, Gauge]


class SettingsError(ValueError):
    """config/settings.yaml doesn't have the shape the code reads."""


def check(raw: dict, source: str = "config/settings.yaml") -> Settings:
    """The checked settings; SettingsError naming every key that is missing, unknown (a typo?) or of the wrong type."""
    try:
        return Settings.model_validate(raw)
    except ValidationError as e:
        problems = []
        for err in e.errors():
            where = ".".join(str(p) for p in err["loc"])
            what = {"missing": "missing", "extra_forbidden": "unknown key (a typo?)"}.get(err["type"], err["msg"])
            problems.append(f"{where}: {what}")
        raise SettingsError(f"{source} is invalid: " + "; ".join(problems)) from None
