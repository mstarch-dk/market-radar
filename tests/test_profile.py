"""profile.build() on the synthetic world: known returns, scores and sections, and honest gaps."""
import json

import numpy as np
import pandas as pd
import pytest

import world
from conftest import FIXTURES
from radar import api_models, external, ingest, profile


@pytest.fixture
def env(tmp_data, monkeypatch):
    extra = world.install(tmp_data, monkeypatch)

    def download(tickers):                         # a "Yahoo" that knows one extra Nordic stock and one fund
        for t in tickers:
            if t == "NEW.CO":
                extra[t] = world.bars(t, 50 * 1.0015 ** np.arange(200))
            elif t == "FUND.L":
                extra[t] = world.bars(t, 20 * 1.0006 ** np.arange(world.N))
        return {}
    monkeypatch.setattr(ingest, "update_prices", download)
    return extra


def _yahoo(monkeypatch, name, **info):
    raw = json.loads((FIXTURES / f"yahoo_{name}.json").read_text(encoding="utf-8"))
    raw["info"] |= info
    monkeypatch.setattr(external, "detail", lambda *a, **k: (raw, "ok"))
    return raw


def test_tracked_holding(env, monkeypatch):
    _yahoo(monkeypatch, "msft", currentPrice=float(world.closes()["S1"][-1]), industry="Software")
    p = profile.build("S1")
    api_models.Profile.model_validate(p)
    g, a = 1.0012, 1.0004
    assert p["price"]["returns"]["r3m"] == pytest.approx(g ** 63 - 1)
    assert p["price"]["vs_acwi"]["r3m"] == pytest.approx((g ** 63 - 1) - (a ** 63 - 1))
    assert p["price"]["returns_dkk"]["r3m"] == pytest.approx(g ** 63 - 1)          # constant USDDKK
    assert p["price"]["sector_etf"] == "LEAD"                                       # Technology → LEAD
    assert p["price"]["vs_sector"]["r3m"] == pytest.approx(
        (g ** 63 - 1) - (world.closes()["LEAD"][-1] / world.closes()["LEAD"][-64] - 1))
    assert p["momentum"]["rank"] == 1 and p["momentum"]["group_size"] == 6
    assert p["identity"]["my_status"] == "holding" and p["identity"]["my_position"]["quantity"] == 10
    assert p["identity"]["tracked"] and p["identity"]["region"] == "us"
    assert p["technicals"]["rsi_state"] == "overbought" and p["technicals"]["macd_state"] == "bullish"
    assert p["analyst"]["status"] == "ok" and p["analyst"]["calendar"]["next_earnings"] is not None
    assert p["fundamentals"]["forward_pe"] is not None
    assert p["levels"]["status"] == "ok" and p["levels"]["stop"] < p["price"]["last"]
    peers = p["peers"]["peers"]
    assert "S1" not in {x["ticker"] for x in peers} and len(peers) == 8              # same industry, all regions
    assert [x["score"] for x in peers] == sorted((x["score"] for x in peers), reverse=True)
    assert p["peers"]["rotation"]["ticker"] == "LEAD" and p["peers"]["rotation"]["quadrant"] == "Leading"
    assert p["etf"] is None and p["context"]["notes"] == []


def test_untracked_nordic_stock_is_scored_against_a_group_it_isnt_in(env):
    p = profile.build("NEW.CO")
    api_models.Profile.model_validate(p)
    assert "NEW.CO" in env                                                         # fetched on lookup
    assert p["identity"]["region"] == "nordic" and not p["identity"]["tracked"]
    assert p["momentum"]["rank"] is None and "not a member" in p["momentum"]["score_basis"]
    assert p["momentum"]["r12_1"] is None                                           # only 200 bars of history
    assert p["price"]["returns"]["r1y"] is None and p["price"]["returns"]["r6m"] is not None
    assert any("Not tracked" in n for n in p["context"]["notes"])


def test_without_yahoo_detail_sections_say_missing(env):
    p = profile.build("S2")
    api_models.Profile.model_validate(p)
    assert p["analyst"]["status"] == p["fundamentals"]["status"] == "missing"
    assert p["fundamentals"]["forward_pe"] is None and p["analyst"]["eps"] == []
    assert any("no data" in n for n in p["context"]["notes"])
    assert p["price"]["status"] == "ok" and p["momentum"]["status"] == "ok"        # price-based parts still work


def test_fund_look_through_and_sector(env, monkeypatch):
    raw = _yahoo(monkeypatch, "iuit")
    raw["fund"]["top_holdings"][0]["symbol"] = "S1"                                 # holds the user's position
    p = profile.build("FUND.L")
    api_models.Profile.model_validate(p)
    assert p["identity"]["quote_type"] == "ETF" and p["identity"]["sector"] == "Technology"
    assert p["etf"]["status"] == "ok" and p["etf"]["overlap"] == ["S1"]
    assert p["etf"]["expense_ratio"] == pytest.approx(0.0015)
    assert p["price"]["sector_etf"] == "LEAD"                                       # dominant sector's ETF
    assert p["analyst"]["status"] == "missing"                                      # funds have no estimates


def test_unknown_ticker(env):
    with pytest.raises(profile.TickerNotFound):
        profile.build("NOPE")


def test_legacy_info_keeps_the_old_keys(env):
    flat = profile.legacy_info(profile.build("S1"))
    for k in ("ticker", "last", "r1m", "r3m", "r6m", "r12_1", "from_high", "sma50", "sma200", "vol_surge", "above50",
              "above200", "trend_ok", "name", "currency", "rel_r1m", "rel_r3m", "rel_r6m", "region",
              "score_in_region", "rank_in_region", "region_size", "my_status", "analyst", "levels"):
        assert k in flat, k
    assert flat["region"] == "us" and flat["rank_in_region"] == 1 and flat["rel_r3m"] == flat["price"]["vs_acwi"]["r3m"]


def test_series(env):
    m = profile.Market.load()
    s = profile.series("S1", m, days=100)
    api_models.Series.model_validate(s)
    assert len(s["dates"]) == len(s["close"]) == len(s["rsi"]) == 100
    assert s["rel_acwi"][0] == pytest.approx(100.0) and s["rel_acwi"][-1] == pytest.approx(100 * (1.0012 / 1.0004) ** 99)
    assert s["sma200"][-1] == pytest.approx(np.mean(world.closes()["S1"][-200:]))
    assert pd.Timestamp(s["dates"][-1]) == world.IDX[-1]


def test_missing_yahoo_bars_are_not_shown_as_sessions(env):
    full = world.bars("GAP.CO", 80 * 1.001 ** np.arange(world.N))
    env["GAP.CO"] = full.drop(full.index[-2])                    # Yahoo has no bar for the second-last day
    p = profile.build("GAP.CO")
    dates = [b["date"] for b in p["price"]["recent"]]
    gap = world.IDX[-2].date().isoformat()
    assert gap not in dates and dates[0] == world.IDX[-1].date().isoformat()
    assert p["price"]["change_1d"] == pytest.approx(1.001 ** 2 - 1)   # vs the last real close, two days back
    assert p["price"]["recent"][0]["change"] == pytest.approx(1.001 ** 2 - 1)
    s = profile.series("GAP.CO", profile.Market.load(), days=30)
    assert gap not in s["dates"] and len(s["dates"]) == 30


def test_card_and_chart_agree(env):
    p = profile.build("S3")
    s = profile.series("S3", profile.Market.load(), days=60)
    assert p["technicals"]["rsi14"] == pytest.approx(s["rsi"][-1])
    assert p["technicals"]["macd_hist"] == pytest.approx(s["macd_hist"][-1])
    assert p["price"]["last"] == pytest.approx(s["close"][-1])
