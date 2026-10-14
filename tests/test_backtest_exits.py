"""The stop-loss / take-profit rule replayed on your trades (backtest/), on the synthetic world: inputs as known on
each day (parity with the live functions, no look-ahead), the exits themselves, the overlay / rules-only
variants, funding, and the runs written into simulated portfolios."""
import json

import numpy as np
import pandas as pd
import pytest

import world
from radar import mine, performance, profile, simulate, userstore
from radar.backtest import exits, pit
from radar.signals import momentum, regime
from world import IDX, N

FX = 6.5
UP, DOWN = 200, 30                        # CRASH: rises 0.3% a bar for 200 bars, then falls 1% a bar for 30
c1 = lambda i: 100 * 1.0012 ** i          # noqa: E731


def crash() -> np.ndarray:
    up = 100 * 1.003 ** np.arange(UP)
    down = up[-1] * 0.99 ** np.arange(1, DOWN + 1)
    flat = down[-1] * 1.0005 ** np.arange(1, N - UP - DOWN + 1)
    return np.r_[up, down, flat]


@pytest.fixture
def market(tmp_data, monkeypatch):
    extra = world.install(tmp_data, monkeypatch)
    extra["CRASH"] = world.bars("CRASH", crash())
    monkeypatch.setattr(performance, "_cache", {})
    monkeypatch.setattr(exits, "REPORTS", tmp_data / "reports")
    return profile.Market.load()


def context(market, *held):
    ctx = pit.Context.build(market, set(held) | {"ACWI"})
    ctx.eligible |= {"CRASH"}                                    # a stock, as far as the rule is concerned
    return ctx


def buy(sym, i, qty, price=None, fx=None):
    return {"symbol": sym, "date": IDX[i].date().isoformat(), "type": "BUY", "quantity": qty,
            "price": price if price is not None else float(world.prices().query("ticker == @sym").iloc[i]["close"])
            if sym != "CRASH" else float(crash()[i]), "fee": 0.0, "fx_rate": fx}


def sell(sym, i, qty, price):
    return {"symbol": sym, "date": IDX[i].date().isoformat(), "type": "SELL", "quantity": qty, "price": price,
            "fee": 0.0, "fx_rate": None}


# ---------------- inputs as known on the day ----------------

def test_metrics_panel_matches_metrics_cut_at_each_day(market):
    tickers = ["S1", "S2", "E1", "CRASH"]
    panel = momentum.metrics_panel(market.closes, tickers, 200)
    for i in (100, 220, N - 1):
        d = IDX[i]
        m = momentum.metrics(market.closes.loc[:d], market.volumes.loc[:d], tickers, 200).set_index("ticker")
        for col in ("last", "r1m", "r3m", "r6m", "r12_1", "from_high", "sma50", "sma200", "history"):
            pd.testing.assert_series_equal(panel[col].loc[d].rename(None), m[col].astype(float).rename(None),
                                           check_names=False, check_index_type=False)
        for col in ("above50", "above200", "trend_ok"):
            assert list(panel[col].loc[d].astype(object).where(panel[col].loc[d].notna(), None)) == \
                   list(m[col].astype(object).where(m[col].notna(), None))


def test_score_is_the_percentile_against_the_universe_that_day(market):
    ctx = context(market, "S3")
    d = IDX[260]
    lead = momentum.leaders(market.closes.loc[:d], market.volumes.loc[:d], {"us": world.UNIVERSE["stock_groups"]["us"]["tickers"],
                            "europe": world.UNIVERSE["stock_groups"]["europe"]["tickers"]}, 200)
    row = momentum.metrics(market.closes.loc[:d], market.volumes.loc[:d], ["S3"], 200).iloc[0]
    assert ctx.score("S3", d) == mine._pct_vs(lead, row) is not None


def test_the_regime_reads_enough_rows_to_equal_the_full_history(market):
    d = IDX[280]
    full = market.closes.loc[:d]
    args = (world.fred().loc[:d], "ACWI", {k: g["tickers"] for k, g in world.UNIVERSE["stock_groups"].items()},
            {"us": "US", "europe": "Europe"}, world.UNIVERSE["macro"]["yahoo"], pit.settings()["regime"])
    a, _ = regime.indicators(full, *args)
    b, _ = regime.indicators(full.iloc[-pit.REGIME_ROWS:], *args)
    assert [(i["name"], i["status"], i["value"]) for i in a] == [(i["name"], i["status"], i["value"]) for i in b]


def test_the_regime_holds_for_the_week_and_is_missing_without_history(market):
    ctx = context(market)
    assert ctx.regime(IDX[100])["label"] is None and "200 sessions" in ctx.regime(IDX[100])["missing"]
    fri = next(d for d in IDX[250:] if d.weekday() == 4)
    mon_after = fri + pd.Timedelta(days=3)
    assert ctx.regime(mon_after)["asof"] == ctx.regime(fri)["asof"] == fri.date().isoformat()
    assert ctx.regime(fri)["label"] in ("Risk-on", "Mixed", "Risk-off")


def test_nothing_after_the_day_is_read(market, tmp_data, monkeypatch):
    d = IDX[240]
    before = context(market, "CRASH").levels("CRASH", d, float(crash()[:241].max()))
    extra = world.install(tmp_data, monkeypatch)                    # the same world, but the future changes
    future = crash()
    future[241:] *= 0.5
    extra["CRASH"] = world.bars("CRASH", future)
    after = context(profile.Market.load(), "CRASH").levels("CRASH", d, float(crash()[:241].max()))
    assert {k: before[k] for k in ("stop", "take_profit", "k")} == {k: after[k] for k in ("stop", "take_profit", "k")}
    assert before["context"] == after["context"]


def test_missing_inputs_move_nothing_and_are_named(market):
    lv = context(market, "CRASH").levels("CRASH", IDX[120], float(crash()[:121].max()))
    assert {"Momentum score", "Macro regime", "Analyst data"} <= set(lv["context"]["missing"])
    assert lv["context"]["score"] is None and lv["context"]["regime"] is None
    assert all(r["effect"] == 0 for r in lv["reasons"] if "no adjustment" in r["detail"])


# ---------------- the exits ----------------

def test_a_stop_sells_at_the_next_close_and_parks_the_money(market):
    ctx = context(market, "CRASH")
    rep = exits.replay([buy("CRASH", 190, 10)], ctx, "rules")
    [e] = rep["exits"]
    assert e["trigger"] == "stop" and UP <= IDX.get_loc(pd.Timestamp(e["trigger_date"])) < UP + DOWN
    t = IDX.get_loc(pd.Timestamp(e["trigger_date"]))
    assert e["close_adj"] <= e["stop"]
    assert e["fill_date"] == IDX[t + 1].date().isoformat() and e["fill_price"] == pytest.approx(crash()[t + 1])
    assert e["proceeds_dkk"] == pytest.approx(10 * crash()[t + 1] * FX)
    acwi = lambda i: 100 * 1.0004 ** i      # noqa: E731
    assert e["park_units"] == pytest.approx(e["proceeds_dkk"] / (acwi(t + 1) * FX))
    end = e["after"]["end"]
    assert end["position_dkk"] == pytest.approx(10 * crash()[N - 1] * FX)
    assert end["parked_dkk"] == pytest.approx(e["park_units"] * acwi(N - 1) * FX)
    assert end["saved_dkk"] == pytest.approx(end["parked_dkk"] - end["position_dkk"]) and end["saved_dkk"] > 0
    assert simulate.check_rows(rep["rows"], market) == []
    same = exits.replay([buy("CRASH", 190, 10)], ctx, "rules", fill="same")["exits"][0]
    assert same["fill_date"] == same["trigger_date"]


def test_take_profit_is_fixed_at_the_buy_and_triggers_on_the_cross(market):
    ctx = context(market, "S1")
    rep = exits.replay([buy("S1", 50, 10, c1(50))], ctx, "rules")
    [e] = rep["exits"]
    at_buy = ctx.levels("S1", IDX[50], float(market.closes.at[IDX[50], "S1"]))
    assert e["trigger"] == "take_profit" and e["level"] == pytest.approx(at_buy["take_profit"])
    t = IDX.get_loc(pd.Timestamp(e["trigger_date"]))
    assert c1(t) >= e["level"] > c1(t - 1)
    # recomputed every day, the target would stay ahead of the price and never be reached
    assert all(ctx.levels("S1", IDX[i], c1(i))["take_profit"] > c1(i) for i in range(60, N, 20))


def test_an_add_sets_the_target_again_but_keeps_the_high(market):
    ctx = context(market, "S1")
    rep = exits.replay([buy("S1", 50, 10, c1(50)), buy("S1", 120, 5, c1(120))], ctx, "rules")
    e = rep["exits"][0]
    assert e["tp_set"]["set"] == IDX[120].date().isoformat() and e["quantity"] == 15
    assert e["episode_start"] == IDX[50].date().isoformat()


def test_overlay_skips_a_sale_the_rule_already_made_and_rules_ignore_yours(market):
    ctx = context(market, "CRASH")
    real = [buy("CRASH", 190, 10), sell("CRASH", 260, 10, float(crash()[260]))]
    over = exits.replay(real, ctx, "overlay")
    assert [ev["kind"] for ev in over["events"]] == ["real sell skipped"]
    assert "your_sale" in over["exits"][0]["after"] and over["exits"][0]["after"]["your_sale"]["date"] == IDX[260].date().isoformat()
    rules = exits.replay(real, ctx, "rules")
    assert [ev["kind"] for ev in rules["events"]] == ["real sell ignored"]
    early = exits.replay([buy("CRASH", 190, 10), sell("CRASH", 195, 4, float(crash()[195]))], ctx, "overlay")
    assert early["events"] == [] and early["exits"][0]["quantity"] == 6                 # the rest goes on the stop


def test_a_buy_after_an_exit_uses_the_parked_money_first(market):
    ctx = context(market, "CRASH", "S2")
    rep = exits.replay([buy("CRASH", 190, 10), buy("S2", 280, 1, 100 * 1.001 ** 280)], ctx, "rules")
    acwi_sales = [r for r in rep["rows"] if r.get("symbol") == "ACWI" and r["type"] == "SELL"]
    deposits = [r for r in rep["rows"] if r["type"] == "DEPOSIT"]
    assert len(acwi_sales) == 1 and len(deposits) == 1                 # only the first buy needed new money
    assert simulate.check_rows(rep["rows"], market) == []


def test_broad_funds_get_no_rule_but_stocks_with_a_sector_do(market, monkeypatch):
    from radar import universe
    monkeypatch.setattr(universe, "sectors", lambda ts: pd.DataFrame(
        {"sector": ["" if t in ("ACWI", "CRASH") else "Technology" for t in ts], "industry": ""}, index=pd.Index(ts, name="ticker")))
    rep = exits.replay([buy("ACWI", 60, 10, 100 * 1.0004 ** 60)], context(market), "rules")
    assert rep["exits"] == [] and rep["no_rule"] == ["ACWI"]
    ctx = pit.Context.build(market, {"OLD", "ACWI"})          # a stock you sold long ago: no analyst row, a Yahoo sector
    assert "OLD" in ctx.eligible and "ACWI" not in ctx.eligible


def test_with_the_rule_off_the_overlay_returns_what_you_did(market):
    ctx = context(market, "CRASH", "S2")
    ctx.stops = ctx.stops | {"k_base": 1e6, "k_min": 1e6, "k_max": 1e6, "reward_risk": 1e6}
    main = userstore.save_portfolio({"name": "Real"})
    for r in [buy("CRASH", 190, 10), buy("S2", 150, 20, 100 * 1.001 ** 150), buy("S2", 260, 5, 100 * 1.001 ** 260),
              sell("CRASH", 260, 4, float(crash()[260]))]:          # a buy and a sale the same day net, as in the real book
        userstore.add_tx(r | {"portfolio_id": main})
    rep = exits.replay(userstore.transactions(portfolios=[main]), ctx, "overlay")
    assert rep["exits"] == []
    sid = simulate.new_sim_portfolio("Real · off", "exits-overlay")
    simulate.write_run(sid, "exits-overlay", {}, rep["start"], rep["end"], rep["rows"], market)
    real, sim = (performance.portfolio_performance(p, market)["series"]["index"] for p in (main, sid))
    assert sim == pytest.approx(real, rel=1e-9)


# ---------------- runs into simulated portfolios ----------------

def test_refresh_writes_both_variants_once_and_finds_them_again(market, tmp_data, monkeypatch):
    monkeypatch.setattr(mine, "level_universe", lambda etfs, ah=None: {"CRASH"})
    main = userstore.save_portfolio({"name": "Real", "kind": "frie_midler"})
    for r in [buy("CRASH", 190, 10), sell("CRASH", 260, 10, float(crash()[260]))]:
        userstore.add_tx(r | {"portfolio_id": main})
    first = exits.refresh([main], market)
    again = exits.refresh([main], market)
    ids = lambda rep: {v: x["portfolio_id"] for v, x in rep["portfolios"][0]["variants"].items()}   # noqa: E731
    assert ids(first) == ids(again) and set(ids(first)) == {"overlay", "rules"}
    for v, pid in ids(again).items():
        p = userstore.get_portfolio(pid)
        assert (p["mode"], p["origin"], p["parent_id"], p["kind"], p["tags"]) == ("virtual", "sim", main, "frie_midler",
                                                                                  [f"exits-{v}"])
        assert len(userstore.sim_runs(pid)) == 1
        assert pid not in userstore.portfolio_ids()                                  # never yours
    assert again["portfolios"][0]["variants"]["overlay"]["summary"]["stops"] == 1
    assert len(again["portfolios"][0]["compare"]["rows"]) == 3
    saved = json.loads((tmp_data / "reports" / "sim-exits.json").read_text(encoding="utf-8"))
    assert saved["portfolios"][0]["name"] == "Real"
    cmp = performance.compare(market, tags=["exits-overlay"])
    assert cmp["rows"][0]["members"] == [userstore.get_portfolio(ids(again)["overlay"])["name"]]


def test_simulations_accept_interest():
    assert "INTEREST" in simulate.SIM_TYPES
