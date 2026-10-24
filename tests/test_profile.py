"""profile.build() on the synthetic world: known returns, scores and sections, and honest gaps."""
import json

import numpy as np
import pandas as pd
import pytest

import world
from conftest import FIXTURES
from radar import api_models, profile
from radar.market import Market
from radar.sources import external, ingest


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


def test_refresh_asks_for_a_tracked_tickers_missing_sessions(env, monkeypatch):
    seen = []
    monkeypatch.setattr(profile, "ensure_prices", lambda t, m=None, refresh=False: seen.append(refresh) or m)
    profile.load_inputs("S1", Market.load(), refresh=True)
    assert seen == [True]                     # `radar info --refresh` and the app's refresh button alike


def test_legacy_info_keeps_the_old_keys(env):
    flat = profile.legacy_info(profile.build("S1"))
    for k in ("ticker", "last", "r1m", "r3m", "r6m", "r12_1", "from_high", "sma50", "sma200", "vol_surge", "above50",
              "above200", "trend_ok", "name", "currency", "rel_r1m", "rel_r3m", "rel_r6m", "region",
              "score_in_region", "rank_in_region", "region_size", "my_status", "analyst", "levels"):
        assert k in flat, k
    assert flat["region"] == "us" and flat["rank_in_region"] == 1 and flat["rel_r3m"] == flat["price"]["vs_acwi"]["r3m"]


def test_series(env):
    m = Market.load()
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
    s = profile.series("GAP.CO", Market.load(), days=30)
    assert gap not in s["dates"] and len(s["dates"]) == 30


def test_card_and_chart_agree(env):
    p = profile.build("S3")
    s = profile.series("S3", Market.load(), days=60)
    for key, w in (("1W", "r1w"), ("1M", "r1m"), ("3M", "r3m"), ("YTD", "ytd")):
        if p["price"]["returns"][w] is not None:
            assert s["ranges"][key]["ret"] == pytest.approx(p["price"]["returns"][w]), key
            assert s["ranges"][key]["vs_acwi"] == pytest.approx(p["price"]["vs_acwi"][w]), key
    assert s["ranges"]["5Y"]["short"] and s["ranges"]["5Y"]["start"] == world.IDX[0].strftime("%Y-%m-%d")
    assert not s["ranges"]["1M"]["short"]
    assert p["technicals"]["rsi14"] == pytest.approx(s["rsi"][-1])
    assert p["technicals"]["macd_hist"] == pytest.approx(s["macd_hist"][-1])
    assert p["price"]["last"] == pytest.approx(s["close"][-1])


def test_gauges_grade_the_readings(env):
    p = profile.build("S1")
    t, m, lv = p["technicals"]["gauges"], p["momentum"]["gauges"], p["levels"]["gauges"]
    # S1 rises steadily every day: RSI is pinned at 100, so it reads as extremely overbought, deep red
    assert t["rsi14"]["label"] == "extremely overbought" and t["rsi14"]["level"] == -4
    assert m["score"]["label"] == "leader" and m["score"]["level"] > 0           # rank 1 of its group
    assert m["from_high"]["label"] == "at 52w high"
    assert "stop_dist" in lv and lv["stop_dist"]["scale"] == "sequential"
    assert p["analyst"]["gauges"] == {}                                           # no analyst data: nothing graded
    keys = [w["key"] for w in p["context"]["watchouts"]]
    assert "rsi14" in keys and all(w["level"] <= -3 for w in p["context"]["watchouts"])


def test_risk_section_is_honest_about_flat_synthetic_prices(env):
    # the synthetic world grows at a constant rate, so ACWI never varies week to week: no beta exists
    r = profile.build("S1")["risk"]
    assert r["status"] == "missing" and r["windows"] == {} and r["factors"] is None
    assert r["currency"] == "DKK" and r["benchmark"] == "ACWI"


def test_a_profile_the_app_cant_show_fails_naming_the_field():
    from radar import profile

    with pytest.raises(ValueError, match="the profile of X doesn't match api_models.Profile: generated"):
        profile.checked({"symbol": "X"})


# ---- the sections, each a pure function of hand-made inputs (no world installed, nothing stubbed)

def _inputs(ticker="S1", prices=None, raw=None, holdings=(), **over) -> profile.ProfileInputs:
    from radar import config
    from radar.portfolios import trades

    prices = world.prices() if prices is None else prices
    market = Market(prices, ingest.wide(prices), ingest.wide(prices, "high"), ingest.wide(prices, "low"),
                            ingest.wide(prices, "volume"))
    fields = dict(ticker=ticker, market=market, bench="ACWI", cfg=config.settings(), raw=raw,
                  raw_status="ok" if raw else "missing",
                  holdings=pd.DataFrame(list(holdings), columns=trades.HOLDING_COLS), etf=None, etfs=[],
                  region="us", sectors=None, name=f"{ticker} name", currency="USD", is_tracked=True,
                  stock_groups={}, group_labels={}, leaders=pd.DataFrame(), analyst_history=pd.DataFrame(),
                  regime={"label": None, "asof": None}, rotation_window=63, rotation_tail=10)
    return profile.ProfileInputs(**(fields | over))


def test_price_section_and_notes_for_a_stale_ticker_without_a_dkk_rate():
    old = world.bars("OLD", 50 * 1.001 ** np.arange(world.N - 10))           # stopped trading two weeks ago
    old["date"] = world.IDX[:-10]
    inp = _inputs("OLD", pd.concat([world.prices(), old], ignore_index=True), currency="SEK", sector_etf="LEAD")
    p = profile.section_price(inp)
    assert p["status"] == "stale" and p["asof"] == world.IDX[-11]
    assert p["returns"]["r1m"] == pytest.approx(1.001 ** 21 - 1)               # up to its own last bar
    assert p["returns_dkk"] is None and p["sector_etf"] == "LEAD" and p["vs_sector"]["r1m"] is not None
    assert p["last"] == pytest.approx(50 * 1.001 ** (world.N - 11)) and len(p["recent"]) == 20
    notes = profile.context_notes(inp)
    assert notes[0] == "Yahoo fundamentals and estimates: no data"
    assert "No DKK rate for currency SEK: DKK returns not shown" in notes
    assert notes[-1].startswith(f"Last price is from {world.IDX[-11].date()}, 14 days before")


def test_quality_section_says_missing_without_statements_and_skips_funds():
    assert profile.section_quality(_inputs(raw={"fetched": "2026-01-02", "info": {"quoteType": "ETF"}})) is None
    missing = profile.section_quality(_inputs())
    assert missing["status"] == "missing" and "No financial statements" in missing["notes"][0]
    card = {"fund_source": "edgar", "period_end": "2026-06-30", "quality": 80.0, "value": 40.0}
    q = profile.section_quality(_inputs(quality=card))
    assert q["status"] == "ok" and q["source"] == "SEC EDGAR" and q["asof"] == "2026-06-30" and q["quality"] == 80.0


def test_etf_section_overlap_is_only_what_you_hold():
    raw = json.loads((FIXTURES / "yahoo_iuit.json").read_text(encoding="utf-8"))
    raw["fund"]["top_holdings"][0]["symbol"] = "S1"
    assert profile.section_etf(_inputs("FUND")) is None                        # not a fund: no look-through
    holding = ("S1", "holding", 10, 100.0, "2026-01-02", None, None)
    held = profile.section_etf(_inputs("S2", raw=raw, holdings=[holding]))
    assert held["status"] == "ok" and held["asof"] == raw["fetched"][:10] and held["overlap"] == ["S1"]
    watched = profile.section_etf(_inputs("S2", raw=raw, holdings=[("S1", "watch", None, None, None, None, None)]))
    assert watched["overlap"] == [] and watched["expense_ratio"] == pytest.approx(0.0015)

