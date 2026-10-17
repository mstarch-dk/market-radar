import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import world
from conftest import FIXTURES
from radar import api, coverage, universe
from radar.api_models import DiscoveryView
from radar.config import discovery_config
from radar.discovery import scan, sources

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
    out = scan.build_report()
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
    assert r.status_code == 503 and "radar discover" in r.json()["detail"]
    _seed(tmp_data)
    scan.build_report()
    r = client.get("/api/discover")
    assert r.status_code == 200 and r.json()["markets"][0]["label"] == "Nordic"


def test_discovery_stays_out_of_the_daily_radar(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(scan, "discovery_config", lambda: CFG)
    _seed(tmp_data)
    scan.build_report()
    assert "NEW1" not in universe.all_price_tickers(offline=True)
    rows = {r["key"]: r for r in coverage._discovery_rows(pd.Timestamp.today().date(),
                                                           {"discovery_universe": 45, "discovery_prices": 10}, {})}
    assert rows["discovery_universe"]["coverage"] == "5 names"
    assert rows["discovery_prices"]["status"] == "ok"


def test_prices_refused_by_yahoo_are_asked_for_again(tmp_data, monkeypatch):
    from radar import ingest

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
    df = scan._stocks("us", mk, {"DKK": 1.0, "USD": 6.5}, log=lambda s: None).set_index("ticker")
    assert calls == [2e9, 2e9]
    assert "PLTR" not in df.index                                   # not a member
    assert ("GOOGL" in df.index) != ("GOOG" in df.index)            # one row per company, not re-added as extra
    assert df.loc["NVDA", "market_cap_dkk"] == 4e12 * 6.5 and df.loc["NVDA", "sector"] == "Technology"
    assert {"AMZN", "CBOE"} <= set(df.index)                        # members the screen missed are kept…
    assert pd.isna(df.loc["AMZN", "market_cap_dkk"])                # …with their size unknown, not 0
    assert df.loc["BRK-B", "sector"] == "Financial Services" and (df["kind"] == "stock").all()
