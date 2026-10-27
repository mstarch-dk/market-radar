"""Trading rules: the store, validation and templates, every rule kind's reading (breaks, near, complies, the
boundary, each missing input as unknown, the comply hint), and checks on the synthetic world against the X-ray."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import world
from fakes import LOCAL
from radar import api, paths, rulecheck, userstore, xray
from radar import trading_rules as tr
from radar.errors import Invalid
from radar.signals import rules as sr
from radar.sources import ingest
from radar.userstore import rulestore
from test_propose import ask, market  # noqa: F401 - the shared fixtures
from world import IDX

CAP = {"statement": "No single stock above 10 %", "kind": "max_position_weight", "params": {"pct": 10},
       "severity": "hard", "rationale": "One bad name shouldn't sink me"}
BAND = 0.1


def ctx(**kw) -> dict:
    base = {"side": "buy", "symbol": "X", "date": "2026-10-27", "amount_dkk": 10_000.0,
            "values": {"A": 60_000.0, "B": 30_000.0}, "unvalued": [], "selection": "your real portfolios",
            "theme_corr": 0.5}
    return base | kw


# ---------------- store and validation ----------------

def test_rules_are_added_edited_deleted_restored_and_round_trip(tmp_data):
    assert rulestore.rules() == [] and not (tmp_data / "userdata" / userstore.DB_NAME).exists()  # reading creates nothing
    rid = rulestore.save_rule(tr.validate(CAP))
    r = rulestore.get_rule(rid)
    assert r["params"] == {"pct": 10.0} and r["scope"] == {"portfolios": "real"} and r["status"] == "active"
    rulestore.save_rule(tr.validate({**CAP, "params": {"pct": 12}, "status": "archived"}), rid)
    assert rulestore.rules("active") == [] and rulestore.get_rule(rid)["params"]["pct"] == 12
    gone = rulestore.delete_rule(rid)
    assert rulestore.rules() == []
    rulestore.restore_rule(gone)
    assert rulestore.get_rule(rid)["statement"] == CAP["statement"]

    pid = userstore.portfolio_by_name("frie midler")["id"]                         # the new store seeds it
    rulestore.save_rule(tr.validate({**CAP, "scope": {"portfolios": [pid]}}))
    text = rulestore.export_rules_json()
    assert {"portfolios": ["frie midler"]} in [r["scope"] for r in json.loads(text)]     # by name, not id
    assert rulestore.import_rules_json(text) == 2
    assert {"portfolios": [pid]} in [r["scope"] for r in rulestore.rules()]
    before = rulestore.export_rules_json()
    with pytest.raises(ValueError):
        rulestore.import_rules_json(json.dumps([{**CAP, "scope": {"portfolios": ["nowhere"]}}]))
    assert rulestore.export_rules_json() == before                                    # all or nothing


def test_checks_are_logged_with_the_decision(tmp_data):
    cid = rulestore.log_check({"side": "buy", "symbol": "X"}, [{"status": "breaks"}])
    assert rulestore.set_decision(cid, "went_ahead", "  my reason ")
    c = rulestore.checks()[0]
    assert c["decision"] == "went_ahead" and c["reason"] == "my reason" and c["verdicts"] == [{"status": "breaks"}]
    with pytest.raises(ValueError):
        rulestore.set_decision(cid, "maybe")
    assert not rulestore.set_decision(cid + 1, "dropped")


def test_validate_names_the_first_problem(tmp_data):
    for bad, words in ((dict(CAP, statement=" "), "statement"), (dict(CAP, kind="dsl"), "Unknown rule kind"),
                       (dict(CAP, params={"pct": 0}), "between"), (dict(CAP, params={"pct": "x"}), "number"),
                       (dict(CAP, params={"pct": 10, "x": 1}), "no parameter"),
                       (dict(CAP, severity="fatal"), "Severity"), (dict(CAP, scope={"portfolios": "mine"}), "scope"),
                       (dict(CAP, scope={"portfolios": [999]}), "No portfolio 999"),
                       (dict(CAP, scope={"style": "growth"}), "Style"),
                       ({"statement": "x", "kind": "max_exposure_weight", "params": {"pct": 20}}, "missing"),
                       ({"statement": "x", "kind": "max_exposure_weight", "params": {"pct": 20, "exposures": []}},
                        "at least one"),
                       ({"statement": "x", "kind": "max_exposure_weight",
                         "params": {"pct": 20, "exposures": [{"kind": "colour", "key": "red"}]}}, "kind")):
        with pytest.raises(Invalid, match=words):
            tr.validate(bad)
    v = tr.validate({"statement": " x ", "kind": "no_rebuy_within"})
    assert v["statement"] == "x" and v["params"] == {"days": 30} and v["severity"] == "soft"   # the default


def test_templates_are_valid_generic_and_cover_every_kind(tmp_data):
    seen = set()
    for t in tr.templates():
        tr.validate(t)
        seen.add(t["kind"])
        assert isinstance(t["scope"]["portfolios"], str)                     # never a personal portfolio id
    assert seen == set(tr.kinds())
    assert set(sr.ACTION) == set(tr.kinds())
    assert {k for k, v in tr.kinds().items() if v["when"] in ("state", "both")} == set(sr.STANDING)


# ---------------- the readings, kind by kind ----------------

def test_position_cap_breaks_near_complies_and_the_largest_amount_fits_exactly():
    p = {"pct": 10}
    v = sr.max_position_weight(p, ctx(amount_dkk=20_000.0), BAND)
    assert v["status"] == "breaks" and v["value"] == pytest.approx(20_000 / 110_000)
    assert "of your real portfolios (90.000 DKK invested, cash not counted)" in v["message"]
    fits = (0.1 * 90_000) / 0.9
    assert f"{fits:,.0f}".replace(",", ".") in v["comply"]
    at = sr.max_position_weight(p, ctx(amount_dkk=fits), BAND)
    assert at["status"] == "near" and at["value"] == pytest.approx(0.1)                  # the cap exactly: not a break
    assert sr.max_position_weight(p, ctx(amount_dkk=1_000.0), BAND)["status"] == "complies"
    over = sr.max_position_weight(p, ctx(symbol="A", amount_dkk=1.0), BAND)
    assert over["status"] == "breaks" and "already at" in over["comply"]
    assert sr.max_position_weight(p, ctx(amount_dkk=None), BAND)["status"] == "unknown"
    assert sr.max_position_weight(p, ctx(symbol="A", world={"A"}), BAND)["status"] == "not_applicable"
    assert [v["symbol"] for v in sr.standing_max_position_weight(p, ctx(side=None, world={"A"}), BAND)] == ["B"]
    assert sr.max_position_weight(p, ctx(symbol="Z", unvalued=["Z"]), BAND)["status"] == "unknown"


def test_theme_cap_uses_the_views_matcher_and_says_when_it_cannot_tell():
    p = {"pct": 25, "exposures": [{"kind": "industry", "key": "Semiconductors"}, {"kind": "etf", "key": "SMH"}]}
    meta = {"A": {"industry": "Semiconductors", "corr": {}}, "B": {"industry": "Banks", "corr": {}},
            "X": {"industry": "Semiconductors", "corr": {}}, "Y": {"industry": "Software", "corr": {"SMH": 0.7}},
            "Q": {"industry": None, "corr": {}}}
    v = sr.max_exposure_weight(p, ctx(meta=meta), BAND)                     # A (60k) + X: 70k / 100k
    assert v["status"] == "breaks" and v["value"] == pytest.approx(0.7)
    assert sr.max_exposure_weight(p, ctx(symbol="Y", meta=meta), BAND)["status"] == "breaks"    # moves with SMH
    assert sr.max_exposure_weight(p, ctx(symbol="B", meta=meta), BAND)["status"] == "not_applicable"
    assert sr.max_exposure_weight(p, ctx(symbol="Q", meta=meta), BAND)["status"] == "unknown"   # nothing to go by
    meta["B"] = {"industry": "Banks", "corr": {"SMH": float("nan")}}     # known industry, no correlation: not in it
    assert sr.max_exposure_weight(p, ctx(symbol="B", meta=meta), BAND)["status"] == "not_applicable"
    st = sr.standing_max_exposure_weight(p, ctx(side=None, meta=meta), BAND)
    assert st[0]["status"] == "breaks" and st[0]["symbols"] == ["A"] and st[0]["value"] == pytest.approx(60 / 90)


def test_core_floor_reads_the_direction_of_the_trade():
    p = {"pct": 50, "core": ["A"]}
    assert sr.min_core_weight(p, ctx(amount_dkk=40_000.0), BAND)["status"] == "breaks"   # 60/130 < 50 %
    fits = 60_000 / 0.5 - 90_000
    assert sr.min_core_weight(p, ctx(amount_dkk=fits), BAND)["status"] == "near"
    up = sr.min_core_weight(p, ctx(symbol="A", amount_dkk=5_000.0), BAND)
    assert up["status"] == "complies" and "moves it up" in up["message"]
    sell = sr.min_core_weight(p, ctx(side="sell", symbol="A", amount_dkk=40_000.0), BAND)
    assert sell["status"] == "breaks" and sell["value"] == pytest.approx(20 / 50)
    assert sr.standing_min_core_weight({"pct": 70, "core": ["A"]}, ctx(side=None), BAND)[0]["status"] == "breaks"


def test_ticket_positions_and_trade_count():
    assert sr.min_ticket({"dkk": 10_000}, ctx(amount_dkk=9_999.0), BAND)["status"] == "breaks"
    assert sr.min_ticket({"dkk": 10_000}, ctx(amount_dkk=10_000.0), BAND)["status"] == "complies"
    assert sr.max_positions({"n": 3}, ctx(), BAND)["status"] == "near"
    assert sr.max_positions({"n": 2}, ctx(), BAND)["status"] == "breaks"
    assert sr.max_positions({"n": 2}, ctx(symbol="A"), BAND)["status"] == "not_applicable"
    assert sr.standing_max_positions({"n": 1}, ctx(side=None), BAND)[0]["status"] == "breaks"
    tr_ = [{"symbol": "A", "date": "2026-10-02", "type": "BUY", "value_dkk": 1.0},
           {"symbol": "B", "date": "2026-09-30", "type": "SELL", "value_dkk": 1.0}]
    assert sr.max_trades_per_month({"n": 2}, ctx(trades=tr_), BAND)["status"] == "near"
    v = sr.max_trades_per_month({"n": 1}, ctx(trades=tr_), BAND)
    assert v["status"] == "breaks" and v["comply"] == "Wait until 2026-11-01"


def test_rebuy_pause_gives_the_first_allowed_day():
    sold = [{"symbol": "X", "date": "2026-10-10", "type": "SELL", "value_dkk": 5_000.0}]
    v = sr.no_rebuy_within({"days": 30}, ctx(trades=sold), BAND)
    assert v["status"] == "breaks" and v["comply"] == "Allowed from 2026-11-09"
    assert sr.no_rebuy_within({"days": 30}, ctx(trades=sold, date="2026-11-09"), BAND)["status"] == "complies"
    assert sr.no_rebuy_within({"days": 30}, ctx(trades=[]), BAND)["status"] == "complies"


def test_sell_cooling_counts_the_window_and_says_when_it_clears():
    day = date(2026, 10, 27)
    sold = [{"symbol": "B", "date": (day - timedelta(days=2)).isoformat(), "type": "SELL", "value_dkk": 10_000.0},
            {"symbol": "B", "date": (day - timedelta(days=9)).isoformat(), "type": "SELL", "value_dkk": 50_000.0}]
    p = {"pct": 15, "days": 7}
    v = sr.sell_cooling(p, ctx(side="sell", symbol="A", amount_dkk=10_000.0, trades=sold), BAND)
    assert v["value"] == pytest.approx(20_000 / 100_000) and v["status"] == "breaks"
    assert "at most 5.000 DKK now" in v["comply"] and "2026-11-01" in v["comply"]
    missing = [dict(sold[0], value_dkk=None)]
    assert sr.sell_cooling(p, ctx(side="sell", symbol="A", trades=missing), BAND)["status"] == "unknown"


def test_price_rules_and_their_missing_inputs():
    assert sr.no_average_down({"loss_pct": 10}, ctx(symbol="A", avg_cost=100.0, price=85.0), BAND)["status"] == "breaks"
    assert sr.no_average_down({"loss_pct": 10}, ctx(symbol="A", avg_cost=100.0, price=91.0), BAND)["status"] == "near"
    assert sr.no_average_down({"loss_pct": 10}, ctx(symbol="A", avg_cost=100.0, price=95.0), BAND)["status"] == "complies"
    assert sr.no_average_down({"loss_pct": 10}, ctx(avg_cost=None), BAND)["status"] == "not_applicable"
    assert sr.no_average_down({"loss_pct": 10}, ctx(symbol="A", avg_cost=100.0, price=None), BAND)["status"] == "unknown"
    t = sr.trend_filter({"ma": 200}, ctx(close=95.0, sma={50: 90.0, 200: 100.0}), 0.02)
    assert t["status"] == "breaks" and t["comply"] == "Wait for a close above 100.00"
    assert sr.trend_filter({"ma": 200}, ctx(close=101.0, sma={200: 100.0}), 0.02)["status"] == "near"
    assert sr.trend_filter({"ma": 50}, ctx(close=101.0, sma={50: None}), 0.02)["status"] == "unknown"
    assert sr.no_chase({"ret_3m_pct": 100}, ctx(ret_3m=1.2), BAND)["status"] == "breaks"
    assert sr.no_chase({"ret_3m_pct": 100}, ctx(ret_3m=None), BAND)["status"] == "unknown"
    assert sr.min_score_rank({"score": 70}, ctx(score=60.0), BAND)["status"] == "breaks"
    assert sr.min_score_rank({"score": 70}, ctx(score=75.0), BAND)["status"] == "near"
    assert sr.min_score_rank({"score": 70}, ctx(score=None), BAND)["status"] == "unknown"


def test_placement_exit_rule_and_judgment():
    p = {"horizon_max": 6, "account_kind": "ask"}
    assert sr.account_placement(p, ctx(horizon_months=3, account_kind="frie_midler"), BAND)["status"] == "breaks"
    assert sr.account_placement(p, ctx(horizon_months=3, account_kind="ask"), BAND)["status"] == "complies"
    assert sr.account_placement(p, ctx(horizon_months=12, account_kind="frie_midler"), BAND)["status"] == "not_applicable"
    assert sr.account_placement(p, ctx(horizon_months=None), BAND)["status"] == "unknown"
    assert sr.exit_rule_first({}, ctx(journal={"open": True, "exit_rules": True}), BAND)["status"] == "complies"
    assert sr.exit_rule_first({}, ctx(journal={"open": True, "exit_rules": False}), BAND)["status"] == "breaks"
    assert sr.exit_rule_first({}, ctx(journal=None), BAND)["status"] == "unknown"
    assert sr.judgment({}, ctx(), BAND)["status"] == "judgment"


def test_summary_counts_per_severity():
    s = sr.summary([{"status": "breaks", "severity": "hard"}, {"status": "breaks", "severity": "soft"},
                    {"status": "unknown", "severity": "hard"}])
    assert s["total"]["breaks"] == 2 and s["by_status"]["unknown"]["hard"] == 1 and s["total"]["complies"] == 0


# ---------------- checks on the synthetic world ----------------



def _rule(**kw) -> dict:
    return rulestore.get_rule(rulestore.save_rule(tr.validate(kw)))


@pytest.fixture
def book(market, ask):  # noqa: F811
    """The ASK portfolio in the store (the world's legacy CSVs removed): S1, and S3 bought at bar 150."""
    for f in (paths.TRANSACTIONS_FILE, paths.HOLDINGS_FILE):
        f.unlink(missing_ok=True)
    userstore.add_tx({"symbol": "S3", "date": IDX[150].date().isoformat(), "type": "BUY", "quantity": 40,
                      "price": float(market.closes["S3"].iloc[150]), "fee": 0, "portfolio_id": ask["id"]})
    return ask


def test_check_weights_agree_with_the_xray(market, book):  # noqa: F811
    cap = _rule(statement="cap", kind="max_position_weight", params={"pct": 100})
    xr = xray.build(market, userstore.portfolio_ids())
    data = rulecheck.Data(market, rulecheck.as_of(None))
    values, unvalued = data.book(rulecheck.selection(cap, data)[0])
    assert values == pytest.approx({c["symbol"]: c["value_dkk"] for c in xr["classes"]}) and unvalued == []
    s1 = values["S1"] / sum(values.values())
    st = rulecheck.standing(market, [_rule(statement="c", kind="max_position_weight", params={"pct": s1 * 100 - 1})])
    assert st["rows"][0]["symbol"] == "S1" and st["rows"][0]["value"] == pytest.approx(s1)
    assert st["flags"]["S1"][0]["status"] == "breaks"


def test_check_resolves_the_action_and_sells_all(market, book):  # noqa: F811
    _rule(statement="cap", kind="max_position_weight", params={"pct": 10})
    _rule(statement="core", kind="min_core_weight", params={"pct": 50, "core": ["S1"]})
    _rule(statement="ask only", kind="min_ticket", params={"dkk": 1}, scope={"portfolios": "real", "kind": "frie_midler"})
    out = rulecheck.check(market, {"side": "sell", "ticker": "S1", "portfolio": "ASK", "fraction": 1})
    act = out["action"]
    held = 100 * float(market.raw_closes()["S1"].dropna().iloc[-1]) * act["rate"]           # USD in the world
    assert act["quantity"] == pytest.approx(100) and act["amount_dkk"] == pytest.approx(held) and act["rate"] > 1
    by = {v["statement"]: v for v in out["verdicts"]}
    assert by["cap"]["status"] == "not_applicable"                          # a cap on buys
    assert by["core"]["status"] == "breaks" and by["core"]["value"] == 0     # only S3 is left
    assert by["ask only"]["status"] == "not_applicable" and "outside the rule's scope" in by["ask only"]["message"]
    assert out["verdicts"][0]["statement"] == "core" and out["check_id"] is None          # breaks first
    total = sum(rulecheck.Data(market, rulecheck.as_of(None)).book([book["id"]])[0].values())
    buy = rulecheck.check(market, {"side": "buy", "ticker": "S2", "portfolio": "ASK", "amount_dkk": total}, log=True)
    v = next(x for x in buy["verdicts"] if x["statement"] == "cap")
    assert v["status"] == "breaks" and v["value"] == pytest.approx(0.5)
    assert rulestore.checks()[0]["id"] == buy["check_id"]
    with pytest.raises(Invalid, match="isn't held"):
        rulecheck.check(market, {"side": "sell", "ticker": "S2", "portfolio": "ASK", "fraction": 0.5})
    with pytest.raises(Invalid, match="one of"):
        rulecheck.check(market, {"side": "buy", "ticker": "S2", "portfolio": "ASK"})


def test_style_scope_reads_the_action_then_the_journal(market, book):  # noqa: F811
    _rule(statement="trend", kind="trend_filter", params={"ma": 50}, scope={"portfolios": "real", "style": "momentum"})
    _rule(statement="exit", kind="exit_rule_first")
    act = {"side": "buy", "ticker": "S2", "portfolio": "ASK", "amount_dkk": 1000}
    by = {v["statement"]: v for v in rulecheck.check(market, act)["verdicts"]}
    assert by["trend"]["status"] == "unknown" and by["exit"]["status"] == "breaks"
    assert by["trend"]["severity"] == "soft"
    by = {v["statement"]: v for v in rulecheck.check(market, act | {"style": "value"})["verdicts"]}
    assert by["trend"]["status"] == "not_applicable"
    j = paths.HOME / "journal"
    j.now().mkdir(parents=True, exist_ok=True)
    (j.now() / f"{date.today()}-S2-buy.md").write_text(
        "---\nticker: S2\naction: buy\nstyle: momentum\nstatus: open\n---\n# S2\n\n## Exit rules\n- below the 200d\n",
        encoding="utf-8")
    out = rulecheck.check(market, act)
    by = {v["statement"]: v for v in out["verdicts"]}
    assert out["action"]["style"] == "momentum" and out["action"]["style_from"] == "journal"
    assert by["trend"]["status"] in ("complies", "near") and by["exit"]["status"] == "complies"   # S2 grows steadily


def test_a_past_day_never_sees_a_later_price(market, book):  # noqa: F811
    _rule(statement="chase", kind="no_chase", params={"ret_3m_pct": 1})
    day = IDX[150]
    out = rulecheck.check(market, {"side": "buy", "ticker": "S2", "portfolio": "ASK", "amount_dkk": 1000,
                                   "date": day.date().isoformat()})
    c = market.closes["S2"]
    expect = c.loc[:day].iloc[-1] / c.loc[:day].iloc[-1 - rulecheck.BARS_3M] - 1
    assert out["verdicts"][0]["value"] == pytest.approx(expect) and out["action"]["price"] == pytest.approx(
        market.raw_closes()["S2"].loc[:day].dropna().iloc[-1])
    assert out["action"]["date"] == day.date().isoformat()


# ---------------- the API ----------------

@pytest.fixture
def client(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers: {})
    api.reset()
    return TestClient(api.app, base_url=LOCAL)


def test_rules_api_round_trip_check_and_standing(client):
    from radar import api_models

    page = api_models.RulesPage.model_validate(client.get("/api/rules").json())
    assert page.rules == [] and page.standing is None and "never a gate" in page.disclaimer
    assert {k.key for k in page.catalogue.kinds} == set(tr.kinds()) and page.templates
    r = client.post("/api/rules", json={"statement": "x", "kind": "nope"})
    assert r.status_code == 422 and "Unknown rule kind" in r.json()["detail"]["message"]
    r = client.post("/api/rules", json={"statement": "Max 5 %", "kind": "max_position_weight", "params": {"pct": 5},
                                        "severity": "hard"})
    page = api_models.RulesPage.model_validate(r.json())
    assert page.standing is not None and page.standing.flags["S1"][0].status == "breaks"   # S1 is all of it
    rid = page.rules[0].id
    r = client.put(f"/api/rules/{rid}", json={"statement": "Max 100 %", "kind": "max_position_weight",
                                              "params": {"pct": 100}, "scope": {"portfolios": "all"}})
    assert r.json()["rules"][0]["scope"] == {"portfolios": "all", "kind": None, "tag": None, "style": None}
    assert client.put("/api/rules/999", json={"statement": "x", "kind": "judgment"}).status_code == 404

    chk = client.post("/api/rules/check", json={"side": "buy", "ticker": "S2", "amount_dkk": 5000, "log": True})
    res = api_models.CheckResult.model_validate(chk.json())
    assert res.verdicts[0].status in ("breaks", "near", "complies") and res.check_id is not None
    ok = client.post(f"/api/rules/checks/{res.check_id}/decision", json={"decision": "went_ahead", "reason": "why"})
    assert ok.json() == {"ok": True}
    assert client.post("/api/rules/checks/999/decision", json={"decision": "dropped"}).status_code == 404
    bad = client.post("/api/rules/check", json={"side": "buy", "ticker": "S2"})
    assert bad.status_code == 422

    api_models.StandingResult.model_validate(client.get("/api/rules/standing").json())
    rep = api_models.ReplayResult.model_validate(client.get("/api/rules/replay").json())
    assert rep.n_trades == 1 and rep.rules[0].n_flagged + rep.rules[0].n_passed + rep.rules[0].n_unknown == 1
    gone = client.delete(f"/api/rules/{rid}").json()
    assert client.post("/api/rules/restore", json=gone).status_code == 200
    assert client.post("/api/rules/restore", json=gone).status_code == 409


def test_holdings_carry_their_rule_flags(client):
    from radar import api_models
    from radar.reporting import report

    report.build()
    assert client.get("/api/me").json()["rule_flags"] == {}                 # no rules: no flags
    rulestore.save_rule(tr.validate({"statement": "Max 5 %", "kind": "max_position_weight", "params": {"pct": 5}}))
    me = api_models.MeView.model_validate(client.get("/api/me").json())
    assert [f.statement for f in me.rule_flags["S1"]] == ["Max 5 %"] and {r.symbol for r in me.rows} >= {"S1"}


def test_replay_is_point_in_time_and_counts_per_rule(market, book):  # noqa: F811
    """The replay checks each trade as of its own day: poisoning every price after the S3 buy changes what
    happened afterwards, never the verdicts."""
    _rule(statement="chase", kind="no_chase", params={"ret_3m_pct": 1})
    _rule(statement="trend", kind="trend_filter", params={"ma": 50})
    clean = rulecheck.replay(market)
    assert clean["n_trades"] == 2 and {x["side"] for x in clean["rules"]} == {"buy"}
    chase = next(x for x in clean["rules"] if x["statement"] == "chase")
    assert chase["n_flagged"] + chase["n_passed"] + chase["n_unknown"] == 2
    s3 = next(t for t in clean["trades"] if t["symbol"] == "S3")
    assert s3["after"]["days"] > 0 and s3["after"]["rel"] is not None

    day = IDX[150]
    poisoned = market.closes.copy()
    poisoned.loc[poisoned.index > day] *= 50
    raw = market.raw_closes().copy()
    raw.loc[raw.index > day] *= 50
    market.closes, market._raw = poisoned, raw
    dirty = rulecheck.replay(market, start=day.date().isoformat(), end=day.date().isoformat())
    d3 = next(t for t in dirty["trades"] if t["symbol"] == "S3")
    assert d3["verdicts"] == s3["verdicts"]
