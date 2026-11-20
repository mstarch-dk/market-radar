"""The Sector ETFs page (GET /api/sector-etfs): per sector of config/sector_etfs.yaml, the go-to UCITS ETF and its
peers from /sector-etfs' latest record, with returns in DKK and vs ACWI, costs, the Danish tax status and the
sector's rotation (sector_etf_view.py)."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Num, Quadrant, Strict

TaxListStatus = Literal["yes", "no", "no_sheet", "no_isin"]


class SectorEtfTax(Strict):
    """SKAT's positive list for the income year: aktiebaseret (lager-taxed share income, allowed on an
    aktiesparekonto), kapitalindkomst (off the list) or ukendt (no sheet for the year, or no ISIN); `next_year` when
    SKAT has published the next year's sheet."""
    status: TaxListStatus
    tax_class: Literal["aktiebaseret", "kapitalindkomst", "ukendt"]
    ask_ok: bool | None = None
    sheet_year: int | None = None
    next_year: TaxListStatus | None = None


class SectorEtfReturns(Strict):
    """Returns over trading sessions (1m 21, 3m 63, 6m 126, 1y 252) and YTD; None without the history."""
    r1m: Num = None
    r3m: Num = None
    r6m: Num = None
    r1y: Num = None
    ytd: Num = None


class SectorEtfRow(Strict):
    """One ETF as the record has it (unknown figures null) with what the page adds: returns in DKK and vs ACWI in
    DKK, a weekly sparkline (re-based to 1), Yahoo's cached TER, the tax status and its place in the ranking."""
    isin: str
    ticker: str
    name: str
    issuer: str | None = None
    index: str | None = None
    scope: Literal["world", "us", "europe", "other"]
    ter: Num = None
    distribution: Literal["acc", "dist"] | None = None
    domicile: str | None = None
    currency: str | None = None
    aum_musd: Num = None
    tracking_diff: Num = None
    sources: list[str] = []
    checked: str | None = None
    returns_dkk: SectorEtfReturns
    vs_acwi: SectorEtfReturns
    spark: list[float] = []
    last_close: str | None = None
    yahoo_ter: Num = None
    yahoo_fetched: str | None = None
    ter_mismatch: bool = False
    tax: SectorEtfTax
    rank: int
    reasons: list[str]
    pick: bool
    rejected: bool = False
    rejected_at: str | None = None
    rejected_reason: str | None = None


class SectorEtfFlag(Strict):
    """The sector's go-to you marked for replacement: the next /sector-etfs run picks another fund."""
    isin: str
    reason: str | None = None
    flagged_at: str


class SectorEtfReplaceIn(Strict):
    """Why the go-to should be replaced (optional): not traded at your broker, too expensive …"""
    reason: str | None = Field(default=None, max_length=200)


class SectorRotationRow(Strict):
    """A rotation ticker that stands for the sector, as the last `radar run` placed it."""
    ticker: str
    group: str
    group_label: str | None = None
    name: str | None = None
    quadrant: Quadrant | None = None
    rank: int | None = None
    rs_score: Num = None
    r3m: Num = None
    rel_r3m: Num = None


class SectorEtfSector(Strict):
    """A sector: GICS (parent null) or an EU supersector. `recheck`: the pick is no longer first in the ranking
    and the record gave no reason to override it. `replace`: you marked the go-to for replacement. No ETFs: not
    covered by a /sector-etfs run yet."""
    key: str
    label: str
    parent: str | None = None
    rotation: list[SectorRotationRow]
    pick: str | None = None
    reason: str | None = None
    rank_override: bool = False
    recheck: bool = False
    updated: str | None = None
    age_days: int | None = None
    replace: SectorEtfFlag | None = None
    etfs: list[SectorEtfRow]


class SectorEtfProblem(Strict):
    id: str
    problem: str


class SectorEtfRunScope(Strict):
    """The sectors /sector-etfs re-selects when run without arguments: every sector before the first record
    (first), the marked and the uncovered ones (replace), or none."""
    mode: Literal["first", "replace", "none"]
    sectors: list[str]
    marked: list[str]
    uncovered: list[str]


class SectorEtfsView(Strict):
    """The page. `as_of` null before the first /sector-etfs run (every sector then has no ETFs); `stale` once the
    record is older than `stale_days`; `prices` false when there is no price data yet (returns are then null)."""
    as_of: str | None = None
    record_id: str | None = None
    age_days: int | None = None
    stale: bool
    stale_days: int
    min_aum_musd: float
    tax_year: int
    tax_sheet: bool
    prices: bool
    note: str | None = None
    problems: list[SectorEtfProblem]
    run_scope: SectorEtfRunScope
    sectors: list[SectorEtfSector]
