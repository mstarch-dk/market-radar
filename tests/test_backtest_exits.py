"""The stop-loss / take-profit rule replayed on your trades (backtest/), on the synthetic world: inputs as known on
each day (parity with the live functions, no look-ahead), the exits themselves, the overlay / rules-only
variants, funding, and the runs written into simulated portfolios."""
import json

import numpy as np
import pandas as pd
import pytest

import world
from radar import fees, performance, profile, simulate, userstore
from radar.backtest import exits, pit
from radar.model import inputs as minputs
from radar.model.score import score_vs
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
    return profile.Market.load()


def context(market, *held):
    ctx = pit.Context.build(market, set(held) | {"ACWI"})
    ctx.eligible |= {"CRASH"}                                    # a stock, as far as the rule is concerned
    ctx.stops = ctx.stops | {"mode": "atr", "take_profit": True}  # these tests pin the ATR stop and its take-profit
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
    assert ctx.score("S3", d) == score_vs(lead, row) is not None


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
    rep = exits.replay([buy("CRASH", 190, 10)], ctx, "rules", fee_bps=0)
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
    same = exits.replay([buy("CRASH", 190, 10)], ctx, "rules", fill="same", fee_bps=0)["exits"][0]
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
    monkeypatch.setattr(minputs, "level_universe", lambda etfs, ah=None: {"CRASH"})
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


# ---------------- costs and the ablation ----------------

def test_rule_and_parking_trades_pay_the_fee(market):
    ctx = context(market, "CRASH")
    free = exits.replay([buy("CRASH", 190, 10)], ctx, "rules", fee_bps=0)["exits"][0]
    paid = exits.replay([buy("CRASH", 190, 10)], ctx, "rules", fee_bps=25)
    [e] = paid["exits"]
    assert e["proceeds_dkk"] == pytest.approx(free["proceeds_dkk"] * (1 - 0.0025))
    assert e["park_units"] == pytest.approx(free["park_units"] * (1 - 0.0025) / (1 + 0.0025))
    rule_rows = [r for r in paid["rows"] if r["type"] in ("BUY", "SELL") and not r["note"].startswith("as your")]
    assert rule_rows and all(r["fee"] == pytest.approx(r["quantity"] * r["price"] * 0.0025) for r in rule_rows)
    assert simulate.check_rows(paid["rows"], market) == []



DANSKE = {"markets": [{"market": "US", "pct": 0.20, "min": 29, "currency": "DKK"}], "fx_pct": 0.30,
          "preset": "danske-online", "as_of": "2026-10-01"}


def test_an_accounts_replay_pays_its_broker_minimum_and_says_so(market, monkeypatch):
    monkeypatch.setattr(minputs, "level_universe", lambda etfs, ah=None: {"CRASH"})
    acct = userstore.save_portfolio({"name": "Danske", "kind": "frie_midler", "fee_schedule": DANSKE})
    plain = userstore.save_portfolio({"name": "Plain", "kind": "frie_midler"})
    for pid in (acct, plain):
        userstore.add_tx(buy("CRASH", 190, 10, fx=FX) | {"portfolio_id": pid})
    rep = exits.refresh([acct, plain], market, variants=("rules",), write=False)
    by = {e["name"]: e["variants"]["rules"]["portfolio_id"] for e in rep["portfolios"]}
    runs = {n: userstore.sim_runs(pid)[0]["params"] for n, pid in by.items()}
    assert runs["Danske"]["fee_model"] == {"kind": "schedule", "portfolio_id": acct, "portfolio": "Danske",
                                           "preset": "danske-online", "as_of": "2026-10-01", "fx_pct": 0.30,
                                           "schedule": DANSKE,
                                           "fallback_bps": 10.0, "fallbacks": {}}
    assert runs["Plain"]["fee_model"] == {"kind": "bps", "bps": 10.0}
    for name, pid in by.items():
        traded = [r for r in userstore.transactions(portfolios=[pid])
                  if r["type"] in ("BUY", "SELL") and not (r["note"] or "").startswith("as your")]
        assert len(traded) == 2                                               # the stop's sale and the parking buy
        for r in traded:
            value = r["quantity"] * r["price"]
            want = max(value * 0.002, 29 / FX) + value * 0.003 if name == "Danske" else value * 0.001
            assert r["fee"] == pytest.approx(want)
        if name == "Danske":            # ~11,000 DKK × 0.20% < 29 DKK: the minimum, plus 0.30% FX on a USD trade
            assert all(r["fee"] == pytest.approx(29 / FX + r["quantity"] * r["price"] * 0.003) for r in traded)


def test_a_trade_the_schedule_cannot_price_pays_fee_bps_and_is_counted(market):
    ctx = context(market, "CRASH")
    nordic = fees.SimFees(10, {"markets": [{"market": "NORDIC", "pct": 0.15, "min": 29, "currency": "DKK"}]})
    rep = exits.replay([buy("CRASH", 190, 10)], ctx, "rules", fees=nordic)
    rule_rows = [r for r in rep["rows"] if r["type"] in ("BUY", "SELL") and not r["note"].startswith("as your")]
    assert rule_rows and all(r["fee"] == pytest.approx(r["quantity"] * r["price"] * 0.001) for r in rule_rows)
    assert rep["fee_model"]["fallbacks"] == {"CRASH": {"trades": 1, "why": "no rule for US"},
                                             "ACWI": {"trades": 1, "why": "no rule for US"}}


def test_money_that_does_not_cover_the_minimum_stays_cash(market):
    ctx = context(market, "CRASH")
    steep = fees.SimFees(10, {"markets": [{"market": "US", "pct": 0.1, "min": 700, "currency": "DKK"}]})
    rep = exits.replay([buy("CRASH", 190, 1)], ctx, "rules", fees=steep)       # 1 share: ~1,150 DKK at the stop
    [e] = rep["exits"]
    assert e["proceeds_dkk"] == pytest.approx(e["quantity"] * e["fill_price"] * FX - 700)
    assert e["park_units"] == 0 and not [r for r in rep["rows"] if r.get("symbol") == "ACWI"]
    assert [ev["kind"] for ev in rep["events"] if ev["kind"] == "not parked"] == ["not parked"]
    assert simulate.check_rows(rep["rows"], market) == []


def test_terms_invert_the_fee_for_a_budget_and_a_net(market):
    for t in (fees.Terms(0.002, lo=29 / FX, hi=500 / FX), fees.Terms(0.002, lo=29 / FX, hi=500 / FX, fx=0.003),
              fees.Terms(0.001)):
        for budget in (1.0, 100.0, 5_000.0, 10_000.0, 1e6):
            v = t.value_for_budget(budget)
            assert v == 0 or v + t.fee(v) == pytest.approx(budget)
            assert t.value_for_net(budget) - t.fee(t.value_for_net(budget)) == pytest.approx(budget)

def test_the_ablation_keeps_only_one_half_of_the_rule(market):
    ctx = context(market, "CRASH")
    both = exits.replay([buy("CRASH", 190, 10)], ctx, "rules", fee_bps=0)
    stop = exits.replay([buy("CRASH", 190, 10)], ctx, "rules", rule="stop", fee_bps=0)
    tp = exits.replay([buy("CRASH", 190, 10)], ctx, "rules", rule="take_profit", fee_bps=0)
    assert [e["trigger"] for e in both["exits"]] == [e["trigger"] for e in stop["exits"]] == ["stop"]
    assert all(e["trigger"] == "take_profit" for e in tp["exits"]) and both["rule"] == "both"
    with pytest.raises(ValueError):
        exits.replay([buy("CRASH", 190, 10)], ctx, "rules", rule="trailing")


# ---------------- variants of the rule (RuleSpec) ----------------

def dip() -> np.ndarray:
    """Rises 0.3 % a bar for 200 bars, falls 1 % a bar for 10, then rises 0.5 % a bar: a shake-out."""
    up = 100 * 1.003 ** np.arange(200)
    down = up[-1] * 0.99 ** np.arange(1, 11)
    return np.r_[up, down, down[-1] * 1.005 ** np.arange(1, N - 210 + 1)]


@pytest.fixture
def dip_market(tmp_data, monkeypatch):
    extra = world.install(tmp_data, monkeypatch)
    extra["CRASH"] = world.bars("CRASH", crash())
    extra["DIP"] = world.bars("DIP", dip())
    monkeypatch.setattr(performance, "_cache", {})
    return profile.Market.load()


def test_the_default_spec_is_the_rule_as_set(market):
    ctx = context(market, "CRASH", "S1")
    rows = [buy("CRASH", 190, 10), buy("S1", 50, 10, c1(50))]
    assert exits.replay(rows, ctx, "rules")["rows"] == exits.replay(rows, ctx, "rules", spec=exits.RuleSpec())["rows"]


def test_without_the_take_profit_nothing_sells_on_a_target(market):
    ctx = context(market, "S1")
    rep = exits.replay([buy("S1", 50, 10, c1(50))], ctx, "rules", spec=exits.RuleSpec("x", tp="off"))
    assert rep["exits"] == [] and rep["spec"] == "x"


def test_a_percent_trail_sells_that_far_below_the_high(market):
    ctx = context(market, "CRASH")
    rep = exits.replay([buy("CRASH", 190, 10)], ctx, "rules", fee_bps=0,
                       spec=exits.RuleSpec("t5", tp="off", stop="pct", pct=0.05))
    [e] = rep["exits"]
    peak = crash()[UP - 1]
    assert e["stop_kind"] == "pct-stop" and e["level"] == pytest.approx(peak * 0.95) and e["k"] is None
    assert IDX.get_loc(pd.Timestamp(e["trigger_date"])) == N - len(crash()) + UP - 1 + 6     # 0.99^6 < 0.95 < 0.99^5


def test_a_trend_exit_sells_on_the_close_below_the_average(market):
    ctx = context(market, "CRASH")
    rep = exits.replay([buy("CRASH", 190, 10)], ctx, "rules", fee_bps=0,
                       spec=exits.RuleSpec("s50", tp="off", stop="trend", sma=50))
    [e] = rep["exits"]
    s = pd.Series(crash(), index=IDX)
    below = s[s < s.rolling(50).mean()]
    assert e["trigger_date"] == below.loc[IDX[190]:].index[0].date().isoformat()
    assert e["level"] == pytest.approx(s.rolling(50).mean()[pd.Timestamp(e["trigger_date"])])


def test_reentry_buys_back_with_the_parked_money(dip_market):
    ctx = pit.Context.build(dip_market, {"DIP", "ACWI"})
    ctx.eligible |= {"DIP"}
    spec = exits.RuleSpec("re", tp="off", stop="pct", pct=0.05, reentry=True)
    rep = exits.replay([{"date": IDX[190].date().isoformat(), "type": "DEPOSIT", "amount": 10_000.0},
                        buy("DIP", 190, 10, float(dip()[190]), FX)], ctx, "rules", fee_bps=10, spec=spec)
    [e] = rep["exits"]
    [r] = rep["reentries"]
    assert r["fill_date"] > e["fill_date"] and r["symbol"] == "DIP"
    t = IDX.get_loc(pd.Timestamp(r["trigger_date"]))
    assert ctx.row("DIP", IDX[t])["trend_ok"] and ctx.score("DIP", IDX[t]) >= ctx.stops["strong_score"]
    assert t - IDX.get_loc(pd.Timestamp(e["fill_date"])) >= spec.reentry_wait
    parked = [x for x in rep["rows"] if x.get("symbol") == "ACWI"]
    assert sum(x["quantity"] for x in parked if x["type"] == "BUY") == pytest.approx(
        sum(x["quantity"] for x in parked if x["type"] == "SELL"))                      # all of it went back in
    assert simulate.check_rows(rep["rows"], dip_market) == []
    with pytest.raises(ValueError):
        exits.replay([buy("DIP", 190, 10, 100.0)], ctx, "overlay", spec=spec)


def test_wider_k_moves_the_stop_down(market):
    ctx = context(market, "CRASH")
    d, a = IDX[N - len(crash()) + UP - 1], float(crash()[UP - 1])
    base = ctx.levels("CRASH", d, a)
    wide = ctx.levels("CRASH", d, a, {"k_base": 5.0, "k_min": 4.0, "k_max": 6.0})
    assert wide["k"] > base["k"] and wide["stop"] < base["stop"]
    slow = ctx.levels("CRASH", d, a, {"atr_days": 63})
    assert slow["atr"] != base["atr"]
    off = ctx.levels("CRASH", d, a, {"extended_vs_sma50": None})
    assert all(r["signal"] != "Extended" for r in off["reasons"])


# ---------------- risk on a path ----------------

def test_path_measures_return_and_drawdown(market):
    from radar.backtest import study

    i0 = N - len(crash())
    rows = [{"date": IDX[i0].date().isoformat(), "type": "DEPOSIT", "amount": 10 * float(crash()[0]) * FX},
            {**buy("CRASH", i0, 10, float(crash()[0]), FX)}]
    r = study.path(rows, market, IDX[i0], IDX[N - 1])
    assert r["ret"] == pytest.approx(crash()[-1] / crash()[0] - 1)
    assert r["max_dd"] == pytest.approx(crash()[UP + DOWN - 1] / crash()[UP - 1] - 1)
    assert r["worst20"] == pytest.approx(0.99 ** 20 - 1)
    assert study.path(rows, market, IDX[i0], IDX[N - 1] + pd.Timedelta(days=30)) is None


# ---------------- redeploy and rotation ----------------

class FakePicker:
    """Candidates in a fixed order; records what it was asked."""
    n = 5

    def __init__(self, order, ranks=None):
        self.order, self.ranks, self.calls = order, ranks or {}, []

    def pick(self, day, held, barred):
        self.calls.append((day, set(held), set(barred)))
        return next((t for t in self.order if t not in held and t not in barred), None)

    def rank(self, day, t):
        return self.ranks.get(t)


def funded(*buys):
    return [{"date": IDX[190].date().isoformat(), "type": "DEPOSIT", "amount": 20_000.0}, *buys]


def test_redeploy_buys_the_next_name_with_all_the_money(market):
    ctx = context(market, "CRASH", "S1", "S2")
    pk = FakePicker(["CRASH", "S1", "S2"])
    spec = exits.RuleSpec("r", tp="off", stop="pct", pct=0.05, redeploy="score")
    rep = exits.replay(funded(buy("CRASH", 190, 10, fx=FX)), ctx, "rules", fee_bps=10, spec=spec, picker=pk)
    [e] = rep["exits"]
    [r] = rep["redeploys"]
    assert r["symbol"] == "S1" and r["from"] == "CRASH" and r["fill_date"] == e["fill_date"] and e["park_units"] == 0
    assert r["amount_dkk"] == pytest.approx(e["proceeds_dkk"])
    [buy_s1] = [x for x in rep["rows"] if x.get("symbol") == "S1"]
    assert buy_s1["fee"] == pytest.approx(buy_s1["quantity"] * buy_s1["price"] * 10 / 1e4)
    assert buy_s1["quantity"] * buy_s1["price"] * buy_s1["fx_rate"] + buy_s1["fee"] * buy_s1["fx_rate"] == \
        pytest.approx(e["proceeds_dkk"])
    assert not [x for x in rep["rows"] if x.get("symbol") == "ACWI"]
    day, held, barred = pk.calls[0]
    assert day == pd.Timestamp(e["trigger_date"]) < pd.Timestamp(e["fill_date"])     # ranked on what was known
    assert "CRASH" in barred and "CRASH" not in held                                  # the cool-down
    assert simulate.check_rows(rep["rows"], market) == []


def test_without_a_candidate_the_money_is_parked_and_said(market):
    ctx = context(market, "CRASH")
    spec = exits.RuleSpec("r", tp="off", stop="pct", pct=0.05, redeploy="score")
    rep = exits.replay(funded(buy("CRASH", 190, 10, fx=FX)), ctx, "rules", fee_bps=10, spec=spec,
                       picker=FakePicker(["CRASH"]))
    [e] = rep["exits"]
    assert e["park_units"] > 0 and rep["redeploys"] == []
    assert [ev["kind"] for ev in rep["events"]] == ["redeploy skipped"]


def test_parking_is_unchanged_by_the_new_options(market):
    ctx = context(market, "CRASH")
    rows = funded(buy("CRASH", 190, 10, fx=FX))
    a = exits.replay(rows, ctx, "rules", fee_bps=10, spec=exits.RuleSpec("p", tp="off", stop="pct", pct=0.05))
    b = exits.replay(rows, ctx, "rules", fee_bps=10, spec=exits.RuleSpec("p", tp="off", stop="pct", pct=0.05),
                     picker=FakePicker(["S1"]))
    assert a["rows"] == b["rows"] and b["redeploys"] == []


def test_rotation_sells_names_outside_the_buffer_at_month_end(market):
    ctx = context(market, "S1", "S2", "S3")
    pk = FakePicker(["S1", "S2", "S3"], ranks={"S1": 2, "S2": 40})            # keep = 3 x 5 = 15; S2 is out
    spec = exits.RuleSpec("rot", tp="off", stop="none", redeploy="score", rotate=3)
    rep = exits.replay(funded(buy("S1", 190, 10, fx=FX), buy("S2", 190, 10, fx=FX)), ctx, "rules", fee_bps=10,
                       spec=spec, picker=pk)
    sold = {e["symbol"] for e in rep["exits"]}
    assert sold == {"S2", "S3"}                     # S3 came in for S2 and, unranked, went out at the next month-end
    first = min(rep["exits"], key=lambda e: e["trigger_date"])
    t = pd.Timestamp(first["trigger_date"])
    assert first["symbol"] == "S2" and first["trigger"] == "rotation" and first["rank"] == 40
    assert IDX[IDX.get_loc(t) + 1].month != t.month                              # on the last session of a month
    assert rep["redeploys"][0]["symbol"] == "S3"


def test_redeploy_and_rotation_are_checked():
    with pytest.raises(ValueError):
        exits.RuleSpec("x", rotate=3)                        # rotation without redeploy
    with pytest.raises(ValueError):
        exits.RuleSpec("x", redeploy="cash")


def test_redeploy_needs_a_picker_and_the_rules_variant(market):
    ctx = context(market, "CRASH")
    spec = exits.RuleSpec("r", tp="off", stop="pct", pct=0.05, redeploy="score")
    with pytest.raises(ValueError):
        exits.replay([buy("CRASH", 190, 10)], ctx, "rules", spec=spec)
    with pytest.raises(ValueError):
        exits.replay([buy("CRASH", 190, 10)], ctx, "overlay", spec=spec, picker=FakePicker([]))


def test_the_redeploy_study_runs_end_to_end(market, monkeypatch):
    from radar.backtest import study

    rep = study.redeploy_study(market, n_top=3, horizons=(1,), keys=["sma200-redeploy", "rotate-tp-only"])
    assert [a["key"] for a in rep["arms"]][:3] == ["sma200-park", "sma200-redeploy", "rotate"]
    res = rep["results"]["1"]
    assert set(res) == {"sma200-park", "sma200-redeploy", "rotate", "rotate-tp-only", "mix50", "acwi"}
    a = res["sma200-park"]["all"]
    assert a["dates"] >= 1 and a["hold"]["ret_mean"] is not None
    assert res["sma200-redeploy"]["twin"] == "sma200-park" and res["rotate-tp-only"]["twin"] == "rotate"
    for d in rep["dates"]:
        for k, run in d["runs"].items():
            assert run["trades"] >= 3 and run["fees_pct"] > 0
    study.write_redeploy(rep)
    assert (exits.REPORTS / study.REDEPLOY_REPORT_FILE).exists()
