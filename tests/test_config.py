"""The real config files: keys the code relies on, and identifiers that would silently mis-flag if mistyped."""
from collections import Counter

import pytest

from radar import config_schema, universe
from radar.config import index_funds, sector_etf_taxonomy, settings, universe_config
from radar.isin import valid as isin_valid
from radar.reporting import coverage
from radar.sources import constituents, fxrates, positive_list, tracked
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
    isins = [cfg["benchmark"].get("isin")] + [e.isin for e in tracked.etfs()]
    for isin in filter(None, isins):
        assert positive_list.ISIN_RE.match(isin) and _isin_ok(isin), isin


def test_no_duplicate_tickers():
    etf = [e.ticker for e in tracked.etfs()]
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
    for ccy, fx in fxrates.FX_DKK.items():
        assert fx is None or fx.endswith("DKK=X"), ccy
    for ccy, fx in fxrates.FX_VIA_USD.items():
        assert fx == f"USD{ccy}=X" and ccy not in fxrates.FX_DKK, ccy
    assert set(fxrates.FX_TICKERS) <= set(universe.all_price_tickers(offline=True))


def test_coverage_limits_cover_every_dated_source():
    max_age = settings()["coverage"]["max_age"]
    assert {"prices", "fred", "cftc", "factset", "oecd", "analyst"} <= set(max_age)
    assert set(max_age) <= set(coverage.SOURCES)


@pytest.mark.parametrize("section,test_cfg", [("stops", LEVELS_CFG), ("regime", REGIME_CFG)])
def test_test_thresholds_exist_in_settings(section, test_cfg):
    """The tests' copies of the thresholds must name real settings, so a rename can't leave them testing nothing."""
    real = settings()[section]
    assert set(test_cfg) <= set(real), set(test_cfg) - set(real)


# ---------------- settings.yaml's shape (config_schema) ----------------

def _raw() -> dict:
    import copy

    from radar.config import load_yaml
    return copy.deepcopy(load_yaml("settings.yaml"))


def test_the_shipped_settings_have_the_shape_the_code_reads():
    from radar import config_schema
    config_schema.check(_raw())
    assert settings()["propose"]["min_ticket_dkk"]           # settings() checks on load and returns the plain dict


@pytest.mark.parametrize("edit, says", [
    (lambda c: c["propose"]["caps"].update(sectr=0.3), "propose.caps.sectr: unknown key (a typo?)"),
    (lambda c: c["backtest"].pop("fee_bps"), "backtest.fee_bps: missing"),
    (lambda c: c["stops"].update(mode="sideways"), "stops.mode:"),
    (lambda c: c["propose"]["bootstrap"].update(draws="many"), "propose.bootstrap.draws:"),
    (lambda c: c["risk"].pop("factors"), "risk.factors: missing"),
    # the risk model's keys moved from propose: to risk:; a file with the old ones says which
    (lambda c: c["propose"].update(stress=[]), "propose.stress: unknown key"),
    (lambda c: c["propose"].update(look_through=[]), "propose.look_through: unknown key"),
    (lambda c: c["propose"].update(shrink=0.3), "propose.shrink: unknown key"),
    (lambda c: c["propose"].update(history_weeks=156), "propose.history_weeks: unknown key"),
])
def test_a_bad_setting_fails_at_load_naming_the_key(edit, says):
    from radar import config_schema
    c = _raw()
    edit(c)
    with pytest.raises(config_schema.SettingsError, match="config/settings.yaml is invalid") as e:
        config_schema.check(c)
    assert says in str(e.value)


def test_optional_and_nullable_settings_pass():
    from radar import config_schema
    c = _raw()
    c["stops"]["analyst_max_age_days"] = 21                  # read with a default, absent from the file
    c["attribution"]["nw_lag"] = None
    config_schema.check(c)
    c["other_section"] = {"anything": 1}                     # the whole file has a model: an unknown section is a typo
    with pytest.raises(config_schema.SettingsError, match="other_section: unknown key"):
        config_schema.check(c)



def test_typed_and_settings_read_the_same_file(monkeypatch):
    from conftest import with_settings
    from radar import config
    assert config.typed().backtest.fill == config.settings()["backtest"]["fill"]
    raw = with_settings(monkeypatch, backtest={"fee_bps": 3}, history_years=2)
    assert config.settings() is raw and raw["backtest"]["fill"] == "next"         # merged into the file's section
    assert config.typed().backtest.fee_bps == 3 and config.typed().history_years == 2


def test_index_funds_name_real_countries_currencies_and_isins():
    cfg = index_funds()
    known = set(constituents.COUNTRY_EN.values())
    for key, d in cfg.indexes.items():
        listed = [*([] if d.countries == "all" else d.countries), *d.exclude]
        assert listed or d.countries == "all", key
        assert set(listed) <= known, (key, set(listed) - known)   # a misspelt country would silently drop out
    world = set(settings()["risk"]["world_funds"])
    for t, f in cfg.funds.items():
        assert t not in world, t                                   # one fund, one way of counting it
        assert f.hedged is None or f.hedged in fxrates.FX_DKK, t
        assert f.isin is None or (positive_list.ISIN_RE.match(f.isin) and _isin_ok(f.isin)), t
    isins = [f.isin for f in cfg.funds.values() if f.isin]
    assert len(isins) == len(set(isins))


# ---------------- config/sector_etfs.yaml (plans/F13-sector-etfs.md) ----------------

def test_isin_valid_checks_shape_and_check_digit():
    assert isin_valid("IE00B6R52259") and isin_valid("DE000A0F5UJ7")
    assert not isin_valid("IE00B6R52258") and not isin_valid("ie00b6r52259") and not isin_valid(None)


def test_every_rotation_sector_ticker_has_exactly_one_sector():
    tax = sector_etf_taxonomy()
    groups = universe_config()["etf_groups"]
    tickers = [i["ticker"] for g in ("us_sectors", "eu_sectors") for i in groups[g]["items"]]
    counts = Counter(t for d in tax.sectors.values() for t in d.rotation)
    assert {t: counts[t] for t in tickers} == dict.fromkeys(tickers, 1)
    assert set(counts) == set(tickers)                     # nothing in the map the rotation doesn't show
    assert tax.for_ticker("XLK") == "Technology" and tax.for_ticker("EXV1.DE") == "Banks"
    assert tax.for_ticker("SPY") is None


def test_gics_sectors_are_the_sector_names_the_radar_uses():
    tax = sector_etf_taxonomy()
    cfg = universe_config()
    assert set(tax.gics()) == set(cfg["sector_etfs"]["us"]) == set(cfg["attribution"]["sectors"])
    for key, d in tax.sectors.items():
        assert d.label and d.seeds, key
        assert d.parent is None or d.parent in tax.gics(), key


def test_sector_seeds_are_on_the_latest_positive_list():
    listed = positive_list.isins()
    assert listed is not None
    for key, d in sector_etf_taxonomy().sectors.items():
        for s in d.seeds:
            assert s.isin in listed, (key, s.isin)          # a seed is a fund a Danish investor can hold as shares


def test_sector_taxonomy_refuses_what_would_mislead():
    seed = {"isin": "DE000A0F5UJ7", "ticker": "EXV1.DE", "name": "x", "scope": "europe"}
    ok = {"sectors": {"Financial Services": {"label": "Finans", "rotation": ["XLF"]},
                      "Banks": {"label": "Banker", "parent": "Financial Services", "rotation": ["EXV1.DE"],
                                "seeds": [seed]}}}
    assert config_schema.check_sector_etfs(ok).for_ticker("EXV1.DE") == "Banks"
    bad = [
        ({"Banks": {"label": "B", "parent": "Nowhere"}}, "parent Nowhere"),
        ({"A": {"label": "A", "parent": "B"}, "B": {"label": "B", "parent": "C"}, "C": {"label": "C"}}, "A: parent B"),
        ({"A": {"label": "A", "rotation": ["XLF"]}, "B": {"label": "B", "rotation": ["XLF"]}}, "XLF stands for both"),
        ({"A": {"label": "A", "seeds": [{**seed, "isin": "DE000A0F5UJ8"}]}}, "not a valid ISIN"),
        ({"A": {"label": "A", "seeds": [seed, seed]}}, "listed twice"),
        ({"A": {"label": "A", "seeds": [{**seed, "scope": "asia"}]}}, "scope"),
        ({"A": {"label": "A", "colour": "red"}}, "unknown key"),
    ]
    for sectors, match in bad:
        with pytest.raises(config_schema.SettingsError, match=match):
            config_schema.check_sector_etfs({"sectors": sectors})


def test_sector_etf_settings_have_their_defaults():
    s = config_schema.SectorEtfsSettings()
    assert (s.stale_days, s.min_aum_musd) == (180, 100)
    raw = dict(settings())
    assert config_schema.check({k: v for k, v in raw.items() if k != "sector_etfs"}).sector_etfs == s
    with pytest.raises(config_schema.SettingsError, match="sector_etfs.stale_days"):
        config_schema.check({**raw, "sector_etfs": {"stale_days": 0}})
