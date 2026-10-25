"""The Danish tax rules per income year (config/tax_dk.yaml), checked on load. A year is used only when its block
is there and marked `verified`: a year without one raises NoRules, and nothing is borrowed from another year."""
from __future__ import annotations

from functools import cache

from ..config import load_yaml
from ..config_schema import TaxRules, TaxYear, check_tax


class NoRules(LookupError):
    """No verified rules for this income year in config/tax_dk.yaml."""

    def __init__(self, year: int):
        super().__init__(f"no rules for {year}")
        self.year = year


@cache
def load() -> TaxRules:
    return check_tax(load_yaml("tax_dk.yaml"))


def reset() -> None:
    load.cache_clear()


def rules(year: int) -> TaxYear:
    """The year's verified rules, or NoRules."""
    y = load().years.get(int(year))
    if y is None or y.verified is None:
        raise NoRules(int(year))
    return y


def years() -> list[int]:
    """The income years with verified rules, oldest first."""
    return sorted(y for y, r in load().years.items() if r.verified is not None)


def sources(year: int) -> list[str]:
    r = rules(year)
    return list(dict.fromkeys([r.share_income.source, r.ask.source, r.pension.source, r.losses.source]))
