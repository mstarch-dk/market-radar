"""Market views: the views you hold, their evidence and catalogue, and how holdings align with them."""
from __future__ import annotations

from typing import Literal

from .common import Num, Strict


class ViewExposure(Strict):
    kind: Literal["etf", "sector", "industry", "region", "ticker"]
    key: str
    effect: Literal[-1, 1]


class ViewIndicator(Strict):
    indicator: str
    expect: Literal["up", "down"]


class ViewIn(Strict):
    statement: str
    conviction: int = 3
    horizon: Literal["3m", "6m", "12m", "3y"] = "12m"
    rationale: str | None = None
    falsifier: str | None = None
    template: str | None = None
    status: Literal["active", "archived"] = "active"
    exposures: list[ViewExposure] = []
    indicators: list[ViewIndicator] = []


class EvidenceItem(Strict):
    indicator: str
    label: str
    kind: str | None = None
    expect: Literal["up", "down"]
    value: Num = None
    asof: str | None = None
    state: Literal["supports", "contradicts", "flat", "no data"]


class Evidence(Strict):
    items: list[EvidenceItem]
    counts: dict[str, int]
    verdict: Literal["supported", "contradicted", "mixed", "unclear", "no data"]


class ViewRow(ViewIn):
    id: int
    created_at: str
    updated_at: str
    evidence: Evidence | None = None


class ViewTemplate(Strict):
    key: str
    area: str
    pair: str | None = None
    statement: str
    falsifier: str | None = None
    exposures: list[ViewExposure]
    indicators: list[ViewIndicator]


class CatalogueIndicator(Strict):
    key: str
    label: str
    kind: str


class CatalogueEtf(Strict):
    ticker: str
    name: str
    group: str


class ViewsCatalogue(Strict):
    indicators: list[CatalogueIndicator]
    etfs: list[CatalogueEtf]
    sectors: list[str]
    regions: list[str]
    horizons: list[str]


class ViewsPage(Strict):
    disclaimer: str
    views: list[ViewRow]
    templates: list[ViewTemplate]
    catalogue: ViewsCatalogue


class AlignReason(Strict):
    effect: Literal[-1, 1]
    text: str


AlignLabel = Literal["aligned", "conflicts", "mixed", "unrelated"]


class ViewAlignmentRow(Strict):
    id: int | None = None
    statement: str
    conviction: int
    label: AlignLabel
    score: float
    reasons: list[AlignReason]
    evidence: str | None = None


class ViewAlignment(Strict):
    """How a name lines up with your market views (your subjective beliefs)."""
    label: AlignLabel
    score: float
    views: list[ViewAlignmentRow]


class AlignRequest(Strict):
    tickers: list[str]
    store: Literal["main", "discovery"] = "main"


class AlignCompactView(Strict):
    id: int | None = None
    label: AlignLabel
    reasons: list[str]


class AlignCompact(Strict):
    label: AlignLabel
    score: float
    views: list[AlignCompactView]
