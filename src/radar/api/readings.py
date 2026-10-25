"""The dashboard's readings from the last `radar run` (regime, rotation, momentum, quality, positioning, coverage) and
the settings the app changes (regime votes, the SEC contact)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import updater, userstore
from ..api_models import (
    CoverageView,
    MomentumView,
    PositioningView,
    QualityView,
    RegimeView,
    RotationView,
    SecContact,
    VoteOption,
    VotesIn,
)
from ..model import inputs
from ..reporting import dashboard
from .common import (
    dashboard_or_503,
    reading,
)

router = APIRouter()


@router.get("/api/regime", response_model=RegimeView)
def get_regime() -> dict:
    """The regime of the last `radar run`, voted with your current choice of indicator groups."""
    view = reading("regime")
    view["overall"], view["indicators"] = inputs.regime_now(dashboard_or_503())   # Regime(overall, indicators)
    return view | {"votes": dashboard.vote_options()}


@router.get("/api/settings/regime-votes", response_model=list[VoteOption])
def get_regime_votes() -> list[dict]:
    return dashboard.vote_options()


@router.put("/api/settings/regime-votes", response_model=list[VoteOption])
def put_regime_votes(body: VotesIn) -> list[dict]:
    """Which switchable indicator groups count in the regime vote (stored in userdata; the default is
    settings.yaml regime.votes). Takes effect at once here, and in summary.json from the next `radar report`."""
    inputs.choose_votes(body.votes)
    return dashboard.vote_options()


@router.get("/api/settings/sec-contact", response_model=SecContact)
def get_sec_contact() -> dict:
    return {"email": userstore.sec_contact()}


@router.put("/api/settings/sec-contact", response_model=SecContact)
def put_sec_contact(body: SecContact) -> dict:
    """The contact e-mail SEC asks for in the User-Agent of each EDGAR request (stored in userdata; null or empty
    removes it, and EDGAR is then skipped)."""
    try:
        return {"email": userstore.set_sec_contact(body.email)}
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/api/rotation", response_model=RotationView)
def get_rotation() -> dict:
    return reading("rotation")


@router.get("/api/momentum", response_model=MomentumView)
def get_momentum() -> dict:
    return reading("momentum")


@router.get("/api/quality", response_model=QualityView)
def get_quality() -> dict:
    """Kvalitetsscore and værdiscore per region, from the last `radar run`."""
    if "quality" not in dashboard_or_503():
        raise HTTPException(503, "The readings are being rebuilt for this version: reload in a minute."
                            if updater.REPORT_JOB.state["status"] == "running" else
                            "The last report was built by an older version: rebuild the readings on the Data page "
                            "(or run `uv run radar report`) to score the stocks.")
    return reading("quality")


@router.get("/api/positioning", response_model=PositioningView)
def get_positioning() -> dict:
    return reading("positioning")


@router.get("/api/coverage", response_model=CoverageView)
def get_coverage() -> dict:
    """The coverage section, with each source's last attempt and error read live from sources.json (a
    failure after the last report build shows at once)."""
    from ..reporting import coverage

    return coverage.live(reading("coverage"))
