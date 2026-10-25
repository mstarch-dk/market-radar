"""The discovery scan offline: the report, its price store, the DKK rates it needs and how one failed market is
handled while the universe is rebuilt."""
import json
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import world
from conftest import FIXTURES
from fakes import fake_yf
from radar import api, paths, sourcelog, universe
from radar.api_models import DiscoveryView
from radar.config import discovery_config
from radar.discovery import scan, sources
from radar.reporting import coverage
from radar.sources import fxrates, ingest

CFG = discovery_config() | {"markets": {
    "nordic": {"label": "Nordic", "kind": "stock"},
    "etfs": {"label": "UCITS ETFs", "kind": "etf"}}}


def _seed(tmp_data):
    scan.DIR.mkdir(parents=True, exist_ok=True)
    meta = pd.DataFrame({
        "ticker": ["S1", "S2", "NEW1", "NEW2", "THEME1"],
        "name": ["S1 name", "S2 name", "New one", "New two", "Theme one"],
        "market": ["nordic"] * 4 + ["etfs"], "kind": ["stock"] * 4 + ["etf"],
        "exchange": ["CPH"] * 4 + ["GER"], "country": ["Denmark"] * 4 + [""], "currency": ["DKK"] * 4 + ["EUR"],
        "market_cap_dkk": [6e10, 1e9, 2e9, None, None], "sector": ["Technology"] * 4 + [""],
        "industry": [""] * 5, "category": [""] * 4 + ["Global"], "isin": [""] * 4 + ["IE0000000001"]})
    meta.to_csv(scan.UNIVERSE_FILE, index=False)
    n = world.N
    new = pd.concat([world.bars("NEW1", 100 * 1.0015 ** np.arange(n)), world.bars("NEW2", 100 * 0.999 ** np.arange(n))])
    prices = pd.concat([world.prices(), new], ignore_index=True)
    prices.to_parquet(scan.PRICES_FILE, index=False)


def test_report_validates_and_marks_what_the_radar_already_tracks(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(scan, "discovery_config", lambda: CFG)
    _seed(tmp_data)
    out = scan.build_report(set(universe.all_price_tickers(offline=True)))
    assert out["names"] == 5
    d = json.loads(scan.REPORT_FILE.read_text(encoding="utf-8"))
    DiscoveryView.model_validate({"age_days": 0, "stale": False, **d})
    nordic = {r["ticker"]: r for r in d["markets"][0]["rows"]}
    assert d["markets"][0]["scored"] == 4
    assert nordic["S1"]["off_radar"] is False and nordic["NEW1"]["off_radar"] is True
    assert nordic["NEW1"]["score"] > nordic["NEW2"]["score"]
    assert nordic["NEW2"]["market_cap_dkk"] is None and nordic["NEW2"]["size"] is None   # unknown, not 0
    assert nordic["S1"]["size"] == "large" and len(nordic["S1"]["spark"]) == 26
    etf = d["markets"][1]["rows"][0]
    assert etf["kind"] == "etf" and etf["category"] == "Global" and etf["positive_list"] == "?"
    assert etf["sector"] is None                                                       # blank means unknown


def test_api_says_when_no_scan_has_run(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(scan, "discovery_config", lambda: CFG)
    client = TestClient(api.app)
    r = client.get("/api/discover")
    assert r.status_code == 503 and "radar discover" in r.json()["detail"]["message"]
    _seed(tmp_data)
    scan.build_report(set(universe.all_price_tickers(offline=True)))
    r = client.get("/api/discover")
    assert r.status_code == 200 and r.json()["markets"][0]["label"] == "Nordic"


def test_discovery_stays_out_of_the_daily_radar(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(scan, "discovery_config", lambda: CFG)
    _seed(tmp_data)
    scan.build_report(set(universe.all_price_tickers(offline=True)))
    assert "NEW1" not in universe.all_price_tickers(offline=True)
    rows = {r["key"]: r for r in coverage.discovery_rows(pd.Timestamp.today().date(),
                                                           {"discovery_universe": 45, "discovery_prices": 10}, {})}
    assert rows["discovery_universe"]["coverage"] == "5 names"
    assert rows["discovery_prices"]["status"] == "ok"


def test_prices_refused_by_yahoo_are_asked_for_again(tmp_data, monkeypatch):
    from radar.sources import ingest

    tickers = [f"T{i}" for i in range(10)]
    calls = []

    def download(ts, start, progress=None):
        calls.append(list(ts))
        got = ts[:4] if len(calls) == 1 else ts            # the first pass is rate-limited after 4 names
        return pd.concat([world.bars(t, [1.0, 2.0]) for t in got], ignore_index=True)
    monkeypatch.setattr(ingest, "download_bars", download)
    waits = []
    res = scan.update_prices(tickers, log=lambda m: None, sleep=waits.append, waits=(1, 2))
    assert res["got"] == 10 and res["missing"] == []
    assert calls[1] == tickers[4:] and waits == [1]


def test_us_market_keeps_only_sp500_members_with_caps_and_index_sectors(monkeypatch):
    members = sources.parse_sp500((FIXTURES / "ishares_cspx_holdings.csv").read_text(encoding="utf-8"), min_rows=5)
    q = lambda sym, name, cap: {"symbol": sym, "longName": name, "currency": "USD", "financialCurrency": "USD",
                                "marketCap": cap, "quoteType": "EQUITY"}
    screens = {"NMS": [q("NVDA", "NVIDIA Corporation", 4e12), q("GOOGL", "Alphabet Inc.", 3e12),
                       q("GOOG", "Alphabet Inc.", 3e12), q("PLTR", "Palantir", 3e11)],
               "NYQ": [q("BRK-B", "Berkshire Hathaway Inc.", 1e12), q("BF-B", "Brown-Forman", 1e10)]}
    calls = []
    monkeypatch.setattr(sources, "screen_exchange", lambda code, min_cap=5e7, **kw: calls.append(min_cap) or screens[code])
    monkeypatch.setattr(sources, "fetch_index", lambda key: members)
    monkeypatch.setattr(sources, "screen_sectors", lambda codes: pytest.fail("no sector screen for the US"))
    mk = {"label": "US (S&P 500)", "kind": "stock", "index": "sp500", "members_only": True,
          "exchanges": ["NMS", "NYQ"], "screen_min_cap": 2e9}
    df = scan.stock_market("us", mk, {"DKK": 1.0, "USD": 6.5}, log=lambda s: None).set_index("ticker")
    assert calls == [2e9, 2e9]
    assert "PLTR" not in df.index                                   # not a member
    assert ("GOOGL" in df.index) != ("GOOG" in df.index)            # one row per company, not re-added as extra
    assert df.loc["NVDA", "market_cap_dkk"] == 4e12 * 6.5 and df.loc["NVDA", "sector"] == "Technology"
    assert {"AMZN", "CBOE"} <= set(df.index)                        # members the screen missed are kept…
    assert pd.isna(df.loc["AMZN", "market_cap_dkk"])                # …with their size unknown, not 0
    assert df.loc["BRK-B", "sector"] == "Financial Services" and (df["kind"] == "stock").all()


# ---------------- FX ----------------

RATES = {"USDDKK=X": 6.5, "EURDKK=X": 7.46, "GBPDKK=X": 8.6, "SEKDKK=X": 0.65, "NOKDKK=X": 0.62,
         "CHFDKK=X": 8.0}


def _store_fx(days_ago: int, rates=RATES):
    d = pd.Timestamp(date.today() - timedelta(days=days_ago))
    df = pd.DataFrame([{"date": d, "ticker": t, "high": v, "low": v, "close": v, "raw_close": v, "volume": 0.0}
                       for t, v in rates.items()], columns=ingest.COLUMNS)
    paths.PRICES_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(paths.PRICES_FILE, index=False)


def _yahoo_fx(rates):
    def download(tickers, start):
        idx = pd.date_range(end=pd.Timestamp(date.today()), periods=2)
        cols = pd.MultiIndex.from_tuples([(t, "Close") for t in rates])
        return pd.DataFrame([[rates[t] for t in rates]] * 2, index=idx, columns=cols)
    return download


def test_fx_from_a_recent_price_store_does_not_ask_yahoo(monkeypatch):
    _store_fx(days_ago=2)
    fake = fake_yf(monkeypatch, download=lambda t, s: pytest.fail("asked Yahoo"))
    out = scan.fx_rates()
    assert out["DKK"] == 1.0 and out["EUR"] == 7.46 and out["CHF"] == 8.0 and fake.asked == []


@pytest.mark.parametrize("days_ago, rates", [(30, RATES),                         # stale store
                                              (1, {k: v for k, v in RATES.items() if k != "CHFDKK=X"})])
def test_fx_from_a_stale_or_incomplete_store_falls_back_to_yahoo(monkeypatch, days_ago, rates):
    _store_fx(days_ago, rates)
    fake = fake_yf(monkeypatch, download=_yahoo_fx(RATES | {"CHFDKK=X": 8.1}))
    out = scan.fx_rates()
    assert out["CHF"] == 8.1 and [k for k, _ in fake.asked] == ["download"]


def test_fx_without_a_store_uses_yahoo(monkeypatch):
    fake_yf(monkeypatch, download=_yahoo_fx(RATES))
    assert scan.fx_rates()["SEK"] == pytest.approx(RATES["SEKDKK=X"])


def test_fx_a_rate_yahoo_misses_comes_from_the_store_at_any_age(monkeypatch):
    _store_fx(days_ago=40)                                         # too old to use as a whole
    fake_yf(monkeypatch, download=_yahoo_fx({k: v for k, v in RATES.items() if k != "SEKDKK=X"}))
    assert scan.fx_rates()["SEK"] == pytest.approx(RATES["SEKDKK=X"])


def test_fx_a_needed_rate_missing_everywhere_raises_rather_than_dropping_a_market(monkeypatch):
    fake_yf(monkeypatch, download=_yahoo_fx({"USDDKK=X": 6.5, "EURDKK=X": 7.46, "GBPDKK=X": 8.6}))
    with pytest.raises(RuntimeError, match="no DKK rate for CHF, NOK, SEK"):
        scan.fx_rates()


def test_fx_with_too_few_rates_from_yahoo_raises(monkeypatch):
    fake_yf(monkeypatch, download=_yahoo_fx({"USDDKK=X": 6.5, "EURDKK=X": 7.46}))
    with pytest.raises(RuntimeError, match="no FX rates"):
        scan.fx_rates()


# ---------------- build_universe ----------------

MARKETS = {"nordic": {"label": "Nordic", "kind": "stock", "exchanges": ["CPH"]},
           "europe": {"label": "Europe", "kind": "stock", "exchanges": ["GER"]}}


def _q(sym, name, ccy, cap):
    return {"symbol": sym, "longName": name, "currency": ccy, "financialCurrency": ccy, "marketCap": cap,
            "quoteType": "EQUITY"}


SCREENS = {"CPH": [_q("NOVO-B.CO", "Novo Nordisk A/S", "DKK", 1e12)],
           "GER": [_q("SIE.DE", "Siemens AG", "EUR", 2e11), _q("NOV.DE", "Novo Nordisk A/S", "EUR", 1.3e11)]}


def _setup(monkeypatch, failing=()):
    monkeypatch.setattr(scan, "discovery_config", lambda: {"markets": MARKETS})
    monkeypatch.setattr(scan, "fx_rates", lambda: {"DKK": 1.0, "EUR": 7.46})
    monkeypatch.setattr(scan, "INDEX_KEEP", set())

    def screen(code, min_cap=5e7, **kw):
        if code in failing:
            raise ValueError(f"screener broke for {code}")
        return SCREENS[code]
    monkeypatch.setattr(sources, "screen_exchange", screen)
    monkeypatch.setattr(sources, "screen_sectors", lambda codes: {})
    monkeypatch.setattr(sources, "fetch_index", lambda key: pytest.fail("no index in these markets"))
    monkeypatch.setattr(fxrates, "currencies", lambda t: pytest.fail(f"currency lookup for {t}"))


def _cached(rows):
    scan.DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).reindex(columns=scan.UNIVERSE_COLS).to_csv(scan.UNIVERSE_FILE, index=False)


def _row(ticker, name, market, exchange, ccy):
    return {"ticker": ticker, "name": name, "market": market, "kind": "stock", "exchange": exchange,
            "currency": ccy, "market_cap_dkk": 1e9, "sector": ""}


def test_a_failed_market_keeps_its_cached_names_and_the_others_are_rebuilt(monkeypatch):
    _setup(monkeypatch, failing={"GER"})
    _cached([_row("OLD.CO", "Old Nordic A/S", "nordic", "CPH", "DKK"),       # rebuilt away
             _row("BAS.DE", "BASF SE", "europe", "GER", "EUR"),               # kept (market failed)
             _row("NOV.DE", "Novo Nordisk A/S", "europe", "GER", "EUR")])     # kept, but already in Nordic
    logs = []
    with pytest.raises(sourcelog.PartialFailure, match=r"Europe \(ValueError: screener broke for GER\)"):
        scan.build_universe(logs.append)
    df = scan.load_universe().set_index("ticker")
    assert dict(df["market"]) == {"NOVO-B.CO": "nordic", "BAS.DE": "europe"}
    assert any("Europe: FAILED" in m and "keeping 2 cached names" in m for m in logs)


def test_a_company_in_two_markets_stays_only_in_the_first(monkeypatch):
    _setup(monkeypatch)
    df = scan.build_universe(lambda m: None).set_index("ticker")
    assert dict(df["market"]) == {"NOVO-B.CO": "nordic", "SIE.DE": "europe"}
    assert df.loc["SIE.DE", "market_cap_dkk"] == pytest.approx(2e11 * 7.46)


def test_all_markets_failing_still_keep_cached_rows_and_with_none_cached_raise(monkeypatch):
    _setup(monkeypatch, failing={"CPH", "GER"})
    _cached([_row("BAS.DE", "BASF SE", "europe", "GER", "EUR")])
    with pytest.raises(sourcelog.PartialFailure):          # the cached Europe rows still make a universe
        scan.build_universe(lambda m: None)
    assert list(scan.load_universe()["ticker"]) == ["BAS.DE"]
    scan.UNIVERSE_FILE.unlink()
    with pytest.raises(RuntimeError, match="no market could be built"):
        scan.build_universe(lambda m: None)
    assert not scan.UNIVERSE_FILE.exists()
