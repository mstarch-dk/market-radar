"""The real config files: keys the code relies on, and identifiers that would silently mis-flag if mistyped."""
from collections import Counter

import pytest

from radar import coverage, universe
from radar.config import settings, universe_config
from test_levels import CFG as LEVELS_CFG
from test_signals import CFG as REGIME_CFG


def _isin_ok(isin: str) -> bool:
    """ISO 6166 check digit (Luhn over the letters-as-numbers expansion)."""
    digits = "".join(str(int(c, 36)) for c in isin[:-1])
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d) * (2 if i % 2 == 0 else 1)
        total += n // 10 + n % 10
    return (10 - total % 10) % 10 == int(isin[-1])


def test_isin_check_digit_helper():
    assert _isin_ok("IE00B6R52259") and _isin_ok("US0378331005")
    assert not _isin_ok("IE00B6R52258")


def test_etf_isins_are_valid():
    cfg = universe_config()
    isins = [cfg["benchmark"].get("isin")] + [e.isin for e in universe.etfs()]
    for isin in filter(None, isins):
        assert universe.ISIN_RE.match(isin) and _isin_ok(isin), isin


def test_no_duplicate_tickers():
    etf = [e.ticker for e in universe.etfs()]
    assert not [t for t, n in Counter(etf).items() if n > 1]
    for key, g in universe_config()["stock_groups"].items():
        tickers = g.get("tickers") or []
        assert len(tickers) == len(set(tickers)), key


def test_every_group_has_what_the_report_needs():
    cfg = universe_config()
    for key, g in cfg["etf_groups"].items():
        assert g.get("label") and g.get("region") and g.get("items"), key
        if g.get("benchmark"):
            assert g["benchmark"].get("ticker") and g["benchmark"].get("name"), key
    for key, g in cfg["stock_groups"].items():
        assert g.get("label") and (g.get("tickers") or g.get("source") == "spy_holdings"), key


def test_macro_and_external_keys_the_regime_reads():
    cfg = universe_config()
    assert {"VIX", "VIX3M", "Copper", "Gold", "Oil (WTI)"} <= set(cfg["macro"]["yahoo"])
    assert {"BAMLH0A0HYM2", "T10Y2Y", "DGS10", "DTWEXBGS"} <= set(cfg["macro"]["fred"])
    assert next(iter(cfg["external"]["oecd_cli"])) == "G20"     # the first area carries the regime vote
    for report, markets in cfg["external"]["cot"].items():
        assert report in ("tff", "disagg")
        assert all(isinstance(code, str) for code in markets.values()), report   # "043602" must not become 43602


def test_every_currency_used_has_a_dkk_rate():
    for ccy, fx in universe.FX_DKK.items():
        assert fx is None or fx.endswith("DKK=X"), ccy


def test_coverage_limits_cover_every_dated_source():
    max_age = settings()["coverage"]["max_age"]
    assert {"prices", "fred", "cftc", "factset", "oecd", "analyst"} <= set(max_age)
    assert set(max_age) <= set(coverage.SOURCES)


@pytest.mark.parametrize("section,test_cfg", [("stops", LEVELS_CFG), ("regime", REGIME_CFG)])
def test_test_thresholds_exist_in_settings(section, test_cfg):
    """The tests' copies of the thresholds must name real settings, so a rename can't leave them testing nothing."""
    real = settings()[section]
    assert set(test_cfg) <= set(real), set(test_cfg) - set(real)
