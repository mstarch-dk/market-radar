"""The tax rules file (config/tax_dk.yaml): checked on load, a year used only when verified, nothing borrowed from
another year, every number with a source, and the guide quoting it with {{tax:…}}."""
import pytest

from radar import config, config_schema, guide
from radar.portfolios import taxrules


def test_the_shipped_rules_load_with_sources():
    years = taxrules.years()
    assert 2025 in years and 2026 in years
    r = taxrules.rules(2026)
    assert r.ask.rate == 0.17 and r.share_income.progression_limit > 0
    assert all(s.startswith("https://") for s in taxrules.sources(2026))


def test_a_year_without_verified_rules_raises(monkeypatch):
    raw = config.load_yaml("tax_dk.yaml")
    raw["years"][2027] = dict(raw["years"][2026], verified=None)
    monkeypatch.setattr(taxrules, "load", lambda: config_schema.check_tax(raw))
    with pytest.raises(taxrules.NoRules, match="no rules for 2027"):
        taxrules.rules(2027)
    with pytest.raises(taxrules.NoRules, match="no rules for 2031"):
        taxrules.rules(2031)
    assert 2027 not in taxrules.years()


def test_a_misspelt_key_fails_with_its_path():
    raw = config.load_yaml("tax_dk.yaml")
    raw["years"][2026]["ask"]["deposit_kap"] = 1
    with pytest.raises(config_schema.SettingsError, match=r"years\.2026\.ask\.deposit_kap: unknown key"):
        config_schema.check_tax(raw)


def test_the_guide_quotes_the_rules():
    assert guide.fill("{{tax:2026.ask.rate|pct}}") == "17 %"
    assert guide.fill("{{tax:2026.share_income.progression_limit}}") == "79.400"
    with pytest.raises(KeyError, match="tax has no 2026.ask.nope"):
        guide.fill("{{tax:2026.ask.nope}}")
