"""The frozen picks file's contract (exports/proposals/*.json): what `freeze` writes and `evaluate`, `shadow`,
`review` and `check` read back, months later. Open models: the skill adds its own fields (a thesis, notes), and
only what the code reads is required. Every field the code reads is declared here, its default included, so the
readers take attributes from the checked model, not `.get(key, default)` from the raw file."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class _Open(BaseModel):
    model_config = ConfigDict(extra="allow")


class PickExit(_Open):
    review_level: dict | None = None
    signal: dict | None = None
    time_stop: date | None = None
    thesis: list = []


class Pick(_Open):
    ticker: str = Field(min_length=1)
    why: str | None = None
    exit: PickExit | None = None


class Meta(_Open):
    portfolio: str = Field(min_length=1)
    date: date
    amount: float
    settings_hash: str | None
    stops: dict
    frozen_at: str | None = None
    rule_basket: list[str] = []
    tilt: Literal["momentum", "value", "mix"] = "mix"           # rules.TILTS
    mode: Literal["conviction", "fill-gaps"] = "conviction"     # rules.MODES
    weighting: Literal["equal", "inverse-vol"] = "equal"        # rules.WEIGHTINGS
    horizon: int = 6
    max_position: float | None = None
    etf: bool = True


class PicksFile(_Open):
    type: Literal["propose-picks"]
    meta: Meta
    picks: list[Pick] = Field(min_length=1)
    filler: dict | None = None


def check(doc: dict, source: str = "the picks file") -> PicksFile:
    """`doc` as the checked model when it has the contract's shape and no ticker twice; ValueError naming the first
    problem. The raw dict stays the record (written, hashed); read its values from the model."""
    try:
        pf = PicksFile.model_validate(doc)
    except ValidationError as e:
        err = e.errors()[0]
        where = ".".join(str(x) for x in err["loc"])
        raise ValueError(f"{source} isn't a picks file: {where}: {err['msg']}") from None
    seen = set()
    for x in pf.picks:
        if x.ticker in seen:
            raise ValueError(f"{x.ticker} is picked twice")
        seen.add(x.ticker)
    return pf
