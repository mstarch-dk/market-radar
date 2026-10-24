"""The dashboard's positioning view: FactSet earnings, the OECD CLI, COT, market valuation, estimate
revisions, sentiment and rates."""
from __future__ import annotations

from typing import Literal

from .common import Gauge, Num, Strict
from .dashboard import LineChart, Snapshot


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


class CapeReading(Strict):
    value: float
    asof: str
    pct_all: Num = None
    pct_1990: Num = None
    median: float
    since: str
    gauge: Gauge | None = None


class ErpReading(Strict):
    value: float
    asof: str
    pct: Num = None
    median: float
    since: str
    gauge: Gauge | None = None


class YieldGap(Strict):
    earnings_yield: float
    real_yield: float
    value: float
    asof: str
    fwd_pe: float
    gauge: Gauge | None = None


class MarketValuation(Strict):
    cape: CapeReading | None = None
    erp: ErpReading | None = None
    yield_gap: YieldGap | None = None
    charts: list[LineChart] = []


class RevisionRow(Strict):
    group: str
    label: str
    scope: Literal["radar", "discover"]
    names: int
    up: float
    down: float
    net: float
    median: float
    gauge: Gauge | None = None


class RevisionWindow(Strict):
    weeks: int
    base: str | None = None                # the snapshot compared with; None while the history is shorter
    rows: list[RevisionRow]


class Revisions(Strict):
    weeks_stored: int
    asof: str | None = None
    windows: list[RevisionWindow]


class AaiiPoint(Strict):
    date: str
    spread: float


class Aaii(Strict):
    asof: str
    bullish: float
    neutral: float
    bearish: float
    spread: float
    spread_8w: float
    pct: Num = None
    flag: str | None = None
    gauge: Gauge | None = None
    history: list[AaiiPoint]


class PutCall(Strict):
    asof: str
    total: Num = None
    equity: Num = None
    index: Num = None
    equity_10d: float
    pct: Num = None
    days: int
    gauge: Gauge | None = None


class Sentiment(Strict):
    aaii: Aaii | None = None
    putcall: PutCall | None = None


class RateLatest(Strict):
    value: float
    asof: str


class Rates(Strict):
    latest: dict[str, RateLatest]
    chart: LineChart | None = None


class PositioningView(Snapshot):
    factset: FactSet | None = None
    cli: list[CliRow]
    cot: list[CotRow]
    valuation: MarketValuation | None = None
    revisions: Revisions | None = None
    sentiment: Sentiment | None = None
    rates: Rates | None = None
