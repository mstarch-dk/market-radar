"""The rule's constants and settings: tilts, modes, weightings, the keys whose values make up the rule's
hash, and where proposals are kept."""
from __future__ import annotations

import hashlib
import json
import re

from ..config import settings, typed
from ..config_schema import Propose
from ..paths import HOME

PROPOSALS = HOME / "exports" / "proposals"


MEMOS = HOME / "research" / "proposals"


TILTS = ("momentum", "value", "mix")


MODES = ("conviction", "fill-gaps")


WEIGHTINGS = ("equal", "inverse-vol")


RULE_KEYS = ("min_ticket_dkk", "max_names", "tilts", "require_trend_from", "penalties", "max_per_sector", "caps",
             "max_corr", "gates", "exit", "study_cost_bps", "study_ns", "horizons")


WEEKS_PER_MONTH = 52 / 12


def cfg() -> Propose:
    """settings.yaml `propose:` as the checked model: read the rule's values through this."""
    return typed().propose


def rule_settings(section: dict | None = None) -> dict:
    """The values that make up the rule, as written in settings.yaml (`section`: a raw `propose:` section)."""
    section = section if section is not None else settings()["propose"]
    return {k: section.get(k) for k in RULE_KEYS}


def rule_hash(section: dict | None = None) -> str:
    """The rule's fingerprint, frozen with every proposal and study. Taken of the raw YAML values, not the model:
    the model writes 10000 as 10000.0, which would change every hash already stored."""
    blob = json.dumps(rule_settings(section), sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:24] or "portfolio"
