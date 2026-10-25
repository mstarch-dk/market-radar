"""The forward A/B test on the synthetic world: starting it, the monthly picks (frozen once recorded), the replay
(fees, no negative cash, targets reached, the same rows twice) and the status view."""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import world
from fakes import LOCAL
from radar import abtest, api, userstore
from radar.market import Market
from radar.portfolios import simulate
from world import IDX


@pytest.fixture
def market(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    from radar.fundamentals import context as fcontext

    fcontext.reset()
    return Market.load()


def test_refused_with_too_few_scored_stocks(market):
    with pytest.raises(ValueError, match="too few stocks with a score"):
        abtest.create(market, n=15)
    assert abtest.portfolios() == {}


def test_start_records_this_months_picks(market):
    res = abtest.create(market, capital=30000, n=3, max_per_sector=3)
    ps = abtest.portfolios()
    assert set(ps) == set(abtest.KINDS)
    assert all(abtest.TAG in p["tags"] and p["mode"] == "virtual" and p["origin"] == "sim" for p in ps.values())
    assert res["recorded"] == IDX[-1].date().isoformat()
    mom = [x["ticker"] for x in ps["ab-momentum"]["params"]["rebalances"][0]["picks"]]
    assert mom == ["S1", "S2", "E1"]                                 # the fastest growers, pooled over regions
    qv = [x["ticker"] for x in ps["ab-qv"]["params"]["rebalances"][0]["picks"]]
    assert qv[0] == "S1" and len(qv) == 3 and "S6" not in qv         # the lone bank has no score
    blend = {x["ticker"]: x["weight"] for x in ps["ab-blend"]["params"]["rebalances"][0]["picks"]}
    assert sum(blend.values()) == pytest.approx(1.0)
    both = set(qv) & set(mom)
    assert all(blend[t] == pytest.approx(1 / 3) for t in both)
    assert all(blend[t] == pytest.approx(1 / 6) for t in set(blend) - both)
    # recorded on the last session: bought at the next one, which isn't in the prices yet
    assert res["runs"] == {} and any("next session" in n for n in res["notes"])
    with pytest.raises(ValueError, match="already running"):
        abtest.create(market, n=3)


def test_once_a_month_and_frozen(market):
    abtest.create(market, n=3)
    first = abtest.portfolios()["ab-qv"]["params"]["rebalances"]
    assert abtest.record_due(market) is None                         # same month: nothing new
    assert abtest.portfolios()["ab-qv"]["params"]["rebalances"] == first


def _params(dates: list[pd.Timestamp], targets: list[dict[str, float]], fee_bps: float = 10) -> dict:
    return {"fee_bps": fee_bps, "capital": 100000.0,
            "rebalances": [{"date": d.date().isoformat(), "picks": [{"ticker": t, "weight": w, "score": None}
                                                                     for t, w in tg.items()]}
                           for d, tg in zip(dates, targets)]}


def test_replay_reaches_targets_pays_fees_and_never_overdraws(market):
    dates = [IDX[-80], IDX[-40]]
    targets = [{"S1": 0.5, "S2": 0.5}, {"S2": 0.25, "S3": 0.75}]
    strat = abtest.ScoreRebalance()
    rows = strat.rows(market, None, None, 100000.0, _params(dates, targets))
    assert rows[0]["type"] == "DEPOSIT" and rows[0]["date"] == IDX[-79].date().isoformat()   # the next session
    assert simulate.check_rows(rows, market) == []                                           # no negative cash
    second = [r for r in rows if r["date"] == IDX[-39].date().isoformat()]
    assert [r["type"] for r in second][:2] == ["SELL", "SELL"]                               # sells first
    assert {r["symbol"] for r in second if r["type"] == "SELL"} == {"S1", "S2"}              # S1 out, S2 trimmed
    assert all(r["fee"] == pytest.approx(r["quantity"] * r["price"] * 0.001) for r in rows if r.get("symbol"))
    held: dict[str, float] = {}
    for r in rows:
        if r.get("symbol"):
            held[r["symbol"]] = held.get(r["symbol"], 0) + (r["quantity"] if r["type"] == "BUY" else -r["quantity"])
    day = IDX[-39]
    val = {t: q * market.bars(t)["raw_close"][:day].iloc[-1] for t, q in held.items() if q > 1e-9}
    tot = sum(val.values())
    assert val["S3"] / tot == pytest.approx(0.75, abs=0.01) and "S1" not in val
    assert strat.rows(market, None, None, 100000.0, _params(dates, targets)) == rows        # same rows again


def test_a_holding_without_a_price_still_counts_in_the_value_rebalanced(market, monkeypatch):
    bars = market.bars
    monkeypatch.setattr(market, "bars", lambda t: bars(t)[:IDX[-55]] if t == "S1" else bars(t))   # S1's prices stop
    dates = [IDX[-80], IDX[-40]]
    targets = [{"S1": 0.5, "S2": 0.5}, {"S1": 0.5, "S2": 0.25, "S3": 0.25}]
    strat = abtest.ScoreRebalance()
    rows = strat.rows(market, None, None, 100000.0, _params(dates, targets, fee_bps=0))
    day = IDX[-39]
    second = {r.get("symbol"): r for r in rows if r["date"] == day.date().isoformat()}
    assert "S1" not in second                                                                # left as it was
    px = {t: bars(t)["raw_close"][:day].iloc[-1] for t in ("S2", "S3")}
    s1 = next(r for r in rows if r.get("symbol") == "S1")
    s1_value = s1["quantity"] * bars("S1")["raw_close"][:IDX[-55]].iloc[-1] * s1["fx_rate"]
    s2_value = (next(r for r in rows if r.get("symbol") == "S2")["quantity"] - second["S2"]["quantity"]) \
        * px["S2"] * second["S2"]["fx_rate"]
    s3_value = second["S3"]["quantity"] * px["S3"] * second["S3"]["fx_rate"]
    total = s1_value + s2_value + s3_value                         # all invested: no cash left idle
    assert s3_value / total == pytest.approx(0.25, abs=0.01) and s2_value / total == pytest.approx(0.25, abs=0.01)
    assert any("S1" in n and "last price" in n for n in strat.notes)


def test_refresh_stores_runs_and_the_view(market):
    pid = simulate.new_sim_portfolio(abtest.KINDS["ab-qv"], "ab-qv", _params([IDX[-80]], [{"S1": 1.0}])
                                     | {"n": 1, "max_per_sector": 3, "value_score": "qv"}, tags=[abtest.TAG])
    res = abtest.refresh(market)
    assert "ab-qv" in res["runs"] and res["recorded"] == IDX[-1].date().isoformat()     # a new month's picks
    recs = userstore.get_portfolio(pid)["params"]["rebalances"]
    assert len(recs) == 2 and recs[0]["date"] == IDX[-80].date().isoformat()             # the first one is kept
    v = abtest.view(market)
    assert v["running"] and [p["kind"] for p in v["portfolios"]] == ["ab-qv"]
    assert v["comparison"]["rows"][0]["stats"] is not None
    assert v["next_due"] and any("week" in n for n in v["notes"])
    assert v["rebalances"][0]["turnover"] == pytest.approx(0.5)                          # 0 -> 100% S1: half


def test_summary_digest(market, tmp_data):
    import json

    from radar.paths import REPORTS
    from radar.reporting import report

    REPORTS.mkdir(parents=True, exist_ok=True)
    f = REPORTS / "summary.json"
    f.write_text(json.dumps({"asof": "x", "abtest": {"running": False}}), encoding="utf-8")
    report.add_abtest(market)
    assert json.loads(f.read_text(encoding="utf-8"))["abtest"] == {"running": False}    # no test: left as it was
    abtest.create(market, capital=30000, n=3)
    report.add_abtest(market)
    s = json.loads(f.read_text(encoding="utf-8"))
    a = s["abtest"]
    assert s["asof"] == "x" and a["running"] and [b["kind"] for b in a["baskets"]] == list(abtest.KINDS)
    mom = next(b for b in a["baskets"] if b["kind"] == "ab-momentum")
    assert mom["picks"] == ["S1", "S2", "E1"] and mom["twr"] is None    # bought at the next session: no return yet
    assert a["next_due"] and a["value_score"] == "qv"


def test_api(market, monkeypatch):
    api.reset()
    client = TestClient(api.app, base_url=LOCAL)
    assert client.get("/api/abtest").json()["running"] is False
    assert client.post("/api/abtest", json={"n": 15}).status_code == 422
    r = client.post("/api/abtest", json={"n": 3, "capital": 30000})
    assert r.status_code == 200 and r.json()["running"] and len(r.json()["portfolios"]) == 3
    assert client.post("/api/abtest", json={"n": 3}).status_code == 409
