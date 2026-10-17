"""The shape of config/settings.yaml, checked when it is loaded: a typo, a missing key or a wrong type fails at once
with the key's path, not as a KeyError deep in a study or a proposal. The models cover the sections the
simulations and proposals depend on (stops, backtest, risk, propose); a key the code reads with a default is
optional here too. settings() still returns the plain dict."""
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


class Risk(_Section):
    windows: dict[str, int]
    min_weeks: int
    factors: list[str]
    budget: float


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


class _Stress(_Section):
    key: str
    label: str
    start: date
    end: date


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
    history_weeks: int
    min_weeks: int
    shrink: float
    acwi_drift_annual: float
    survivorship_haircut: float
    haircut_from_gauge: bool
    prior: _Prior
    bootstrap: _Bootstrap
    stress: list[_Stress]
    min_edge: float
    min_regime_dates: int
    max_swaps: int
    frontier_knee: float
    ask_deposit_cap: float | None
    ask_cap_year: int | None
    etf_filler: _Filler
    look_through: list[str]
    review_min: int


class Settings(BaseModel):
    """The checked sections; the others pass through as they are."""
    model_config = ConfigDict(extra="allow")
    stops: Stops
    backtest: Backtest
    risk: Risk
    propose: Propose


class SettingsError(ValueError):
    """config/settings.yaml doesn't have the shape the code reads."""


def check(raw: dict, source: str = "config/settings.yaml") -> None:
    """Raise SettingsError naming every key that is missing, unknown (a typo?) or of the wrong type."""
    try:
        Settings.model_validate(raw)
    except ValidationError as e:
        problems = []
        for err in e.errors():
            where = ".".join(str(p) for p in err["loc"])
            what = {"missing": "missing", "extra_forbidden": "unknown key (a typo?)"}.get(err["type"], err["msg"])
            problems.append(f"{where}: {what}")
        raise SettingsError(f"{source} is invalid: " + "; ".join(problems)) from None
