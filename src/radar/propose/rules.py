"""The rule's constants and settings: tilts, modes, weightings, the keys whose values make up the rule's
hash, and where proposals are kept."""
from __future__ import annotations

import hashlib
import json
import re

from ..config import settings
from ..paths import HOME

PROPOSALS = HOME / "exports" / "proposals"


MEMOS = HOME / "research" / "proposals"


TILTS = ("momentum", "value", "mix")


MODES = ("conviction", "fill-gaps")


WEIGHTINGS = ("equal", "inverse-vol")


RULE_KEYS = ("min_ticket_dkk", "max_names", "tilts", "require_trend_from", "penalties", "max_per_sector", "caps",
             "max_corr", "gates", "exit", "study_cost_bps", "study_ns", "horizons")


WEEKS_PER_MONTH = 52 / 12


def cfg() -> dict:
    return settings()["propose"]


def rule_hash(c: dict | None = None) -> str:
    c = c or cfg()
    blob = json.dumps({k: c.get(k) for k in RULE_KEYS}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:24] or "portfolio"
