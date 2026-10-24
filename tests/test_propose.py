"""Proposals (propose.py) on a noisy version of the synthetic world: the ACWI weights file, the gates (each exclusion
listed, a missing K+V never scored as 0), the score, sizing within the ticket with every cost, the caps on the
portfolio after the addition, the ETF filler on an aktiesparekonto, the bootstrap and stress windows, the decision
rule, and the follow-up (freeze, shadow, review, check) that never touches a real portfolio."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import world
from conftest import with_settings
from radar import constituents, fees, profile, propose, universe, userstore
from radar.config import settings
from radar.config_schema import Propose
from radar.model import artifacts
from world import IDX, N


def _pc(**changes) -> Propose:
    """The propose settings in force (the test world's, once `market` set them) as the model, `changes` merged in
    section by section."""
    def merge(base, new):
        if isinstance(base, dict) and isinstance(new, dict):
            return {**base, **{k: merge(base.get(k), v) for k, v in new.items()}}
        return new
    return Propose.model_validate(merge(copy.deepcopy(settings()["propose"]), changes))

FIX = Path(__file__).parent / "fixtures"
SECTORS = {"S1": "Technology", "S2": "Technology", "S3": "Healthcare", "S4": "Energy", "S5": "Industrials",
           "S6": "Financial Services", "E1": "Healthcare", "E2": "Industrials", "E3": "Energy"}


def noisy_prices() -> pd.DataFrame:
    rng = np.random.default_rng(1)
    out = []
    common = rng.normal(0, 0.008, N)
    for t, v in world.closes().items():
        if t.endswith("=X") or t.startswith("^"):
            out.append(world.bars(t, v))
            continue
        own = rng.normal(0, 0.012, N)
        px = v * np.exp(np.cumsum(common + own))
        b = world.bars(t, px)
        b["volume"] = 1e5
        out.append(b)
    return pd.concat(out, ignore_index=True)


@pytest.fixture
def market(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    from radar import ingest
    from radar.fundamentals import context as fcontext

    monkeypatch.setattr(ingest, "load_prices", noisy_prices)
    fcontext.reset()
    monkeypatch.setattr(universe, "sectors", lambda ts: pd.DataFrame(
        {"sector": [SECTORS.get(t, "") for t in ts], "industry": "x"}, index=pd.Index(ts, name="ticker")))
    pd.DataFrame({"ticker": list(SECTORS), "sector": list(SECTORS.values()), "industry": "x"}).to_csv(
        tmp_data / "sectors.csv", index=False)
    c = with_settings(monkeypatch, propose={"gates": {"min_history_weeks": 40}, "bootstrap": {"draws": 400},
                                            "min_weeks": 20, "study_ns": [2, 3]},
                      backtest={"study_min_names": 4, "fill": "next", "fee_bps": 10})
    # ACWI's weights from the trimmed real file
    df = constituents.parse_acwi_holdings((FIX / "ishares_ssac_holdings.csv").read_text(encoding="utf-8"), min_rows=10)
    df.to_csv(tmp_data / "acwi_holdings.csv", index=False)
    m = profile.Market.load()
    m.cfg = c
    return m


@pytest.fixture
def ask(market):
    try:
        pid = userstore.save_portfolio({"name": "ASK", "mode": "real", "kind": "ask"})
    except ValueError:                                              # the new store seeds ASK itself
        pid = userstore.portfolio_by_name("ASK")["id"]
    px = float(market.closes["S1"].iloc[200])
    userstore.add_tx({"symbol": "S1", "date": IDX[200].date().isoformat(), "type": "BUY", "quantity": 100,
                      "price": px, "fee": 0, "portfolio_id": pid})
    return userstore.get_portfolio(pid)


# ---------------- ACWI's weights ----------------

def test_acwi_holdings_parse_to_weights_by_sector_region_and_currency():
    df = constituents.parse_acwi_holdings((FIX / "ishares_ssac_holdings.csv").read_text(encoding="utf-8"), min_rows=10)
    assert df["weight"].sum() == pytest.approx(1.0)
    assert not df["ticker"].isin(["USD", "MESZ6"]).any()               # cash and futures left out
    assert set(df["sector"]) <= {"Technology", "Communication Services", "Consumer Cyclical", "Financial Services",
                                 "Healthcare"}
    w = constituents.acwi_weights(df)
    assert w["region"]["us"] > 0.5 and w["region"]["nordic"] > 0 and w["region"]["other"] > 0    # Canada: other
    assert w["currency"]["USD"] > 0.5 and "DKK" in w["currency"]
    with pytest.raises(ValueError, match="only"):
        constituents.parse_acwi_holdings((FIX / "ishares_ssac_holdings.csv").read_text(encoding="utf-8"))


def test_acwi_holdings_missing_is_none_not_a_guess(tmp_data):
    assert constituents.acwi_holdings(offline=True) is None
    assert constituents.acwi_weights(offline=True) is None


@pytest.mark.parametrize("bad", ["error", "empty", "few"])
def test_a_bad_acwi_answer_keeps_the_cached_file(tmp_data, monkeypatch, bad):
    from fakes import Resp, serve

    good = (FIX / "ishares_ssac_holdings.csv").read_bytes()
    monkeypatch.setattr(constituents, "ACWI_MIN_HOLDINGS", 10)
    serve(monkeypatch, {"ishares-msci-acwi": Resp(content=good)})
    first = constituents.acwi_holdings(refresh=True)
    assert first is not None and len(first) >= 10 and constituents.ACWI_FILE.exists()
    lines = good.decode("utf-8").splitlines()
    few = "\n".join(lines[:6]).encode()                     # the header and three stocks: below the minimum
    answer = {"error": Resp(500), "empty": Resp(content=b""), "few": Resp(content=few)}[bad]
    serve(monkeypatch, {"ishares-msci-acwi": answer})
    again = constituents.acwi_holdings(refresh=True)
    pd.testing.assert_frame_equal(again, pd.read_csv(constituents.ACWI_FILE, keep_default_na=False))
    assert len(again) == len(first)


# ---------------- gates and score ----------------

def test_each_exclusion_is_listed_and_missing_qv_is_never_zero(market):
    pr = propose.Prices(market)
    df = propose.pool(market, pr)
    df.loc["E3", "qv"] = np.nan
    kept, out = propose.gates(df, "value", 10_000, _pc())
    assert "E3" in out["no K+V (kvalitet + værdi)"] and "E3" not in kept.index
    listed = {t for v in out.values() for t in v}
    assert listed | set(kept.index) == set(df.index) and not listed & set(kept.index)
    sc = propose.score(propose.annotate(kept, propose.info(list(kept.index), pr)), "value", _pc())
    assert sc["composite"].notna().all() and "E3" not in sc.index


def test_momentum_tilt_needs_an_uptrend_and_ranks_by_momentum(market):
    pr = propose.Prices(market)
    df = propose.pool(market, pr)
    df.loc["S2", "trend_ok"] = False
    c = _pc(penalties={"vol": 0, "stretch": 0, "corr": 0})
    kept, out = propose.gates(df, "momentum", 10_000, c)
    assert "S2" in out["not in an uptrend"]
    sc = propose.score(kept, "momentum", c)
    assert list(sc.index) == list(kept.sort_values("score", ascending=False).index)


def test_an_unknown_correlation_is_not_scored_as_unrelated(market):
    pr = propose.Prices(market)
    kept, _ = propose.gates(propose.pool(market, pr), "momentum", 10_000, _pc())
    c = _pc()
    corr = pd.Series(0.6, index=kept.index)
    unknown = kept.index[0]
    corr[unknown] = np.nan                                       # too few shared weeks with the portfolio
    sc = propose.score(kept, "momentum", c, corr)
    assert sc.loc[unknown, "pen_corr"] == pytest.approx(c.penalties.corr * 0.6)   # the pool's median
    assert np.isnan(sc.loc[unknown, "corr_book"])                # shown as unknown, not as 0
    none = propose.score(kept, "momentum", c, pd.Series(np.nan, index=kept.index))      # no book to compare with
    assert (none["pen_corr"] == 0).all()


def test_unknown_history_has_its_own_reason(market):
    pr = propose.Prices(market)
    df = propose.pool(market, pr)
    df.loc["S2", "history"] = np.nan
    _, out = propose.gates(df, "momentum", 10_000, _pc())
    assert "S2" in out["no price history"] and "S2" not in out.get("short history", [])


def test_share_price_above_the_ticket_is_gated(market):
    pr = propose.Prices(market)
    df = propose.pool(market, pr)
    cheap = df["price_dkk"].min()
    _, out = propose.gates(df, "momentum", cheap * 0.5, _pc())
    assert out.get("share price above the ticket")


# ---------------- sizing ----------------

def test_n_follows_the_amount_and_the_cap():
    c = _pc(min_ticket_dkk=10_000, max_names=8)
    assert propose.n_for(50_000, c) == 5 and propose.n_for(9_000, c) == 1 and propose.n_for(200_000, c) == 8
    assert propose.n_for(50_000, c, n=3) == 3 and propose.n_for(50_000, c, n=9) == 5


def test_inverse_vol_weights_respect_the_ticket_floor():
    b = propose.budgets(80_000, [0.1, 0.2, 0.8, 0.9, 1.0], "inverse-vol", 10_000)
    assert sum(b) == pytest.approx(80_000) and min(b) >= 10_000 - 1e-6 and b[0] > b[1] > b[-1]
    assert propose.budgets(50_000, [0.1, 0.2, 0.8, 0.9, 1.0], "inverse-vol", 10_000) == [10_000] * 5
    assert propose.budgets(30_000, [0.1, None, 0.3], "inverse-vol", 10_000) == [10_000] * 3


def test_size_stays_within_each_budget_with_fees_fx_and_spread(market, ask):
    sched = next(p["schedule"] for p in fees.presets() if p["id"] == "saxo-classic")
    userstore.save_portfolio({"fee_schedule": sched}, ask["id"])
    sf = fees.SimFees.for_portfolio(userstore.get_portfolio(ask["id"]), 10)
    pr = propose.Prices(market)
    df = propose.pool(market, pr)
    sz = propose.size(30_000, [{"ticker": "S2"}, {"ticker": "S3"}], df, pr, sf, "equal", _pc())
    for r in sz["rows"]:
        assert float(r["quantity"]).is_integer() and r["cash_dkk"] <= r["budget_dkk"] + 1e-6
        tm = propose.terms_for(pr, sf, r["ticker"])
        assert tm.fx > 0                                        # USD listing: the FX surcharge is charged
        assert r["roundtrip_dkk"] > r["fee_dkk"] + r["spread_dkk"]
    assert sz["leftover_dkk"] == pytest.approx(30_000 - sz["cash_dkk"])
    assert 0 < sz["roundtrip_pct"] < 0.02


# ---------------- selection ----------------

def _scored(market, tilt="momentum"):
    pr = propose.Prices(market)
    df = propose.pool(market, pr)
    kept, _ = propose.gates(df, tilt, 10_000, _pc())
    kept = propose.annotate(kept, propose.info(list(kept.index), pr))
    return propose.score(kept, tilt, _pc()), pr


def test_sector_count_and_correlation_caps(market):
    sc, pr = _scored(market)
    c = _pc(max_per_sector=1)
    R = pr.weekly(list(sc.index), 52)
    first = sc.index[0]
    R2 = R.assign(**{t: R[first] + 1e-6 for t in sc.index[1:2]})       # an exact twin of the best name
    base = propose.Base({}, pd.DataFrame(columns=list(propose.DIMS)), None, {}, R2)
    picked, passed = propose.select(sc, 4, 40_000, base, c)
    secs = [p["sector"] for p in picked]
    assert len(secs) == len(set(secs))
    assert "correlation" in passed.get(sc.index[1], "") or "already" in passed.get(sc.index[1], "")


def test_active_caps_count_what_is_already_held(market):
    sc, pr = _scored(market)
    top = sc.index[0]
    sec = sc.at[top, "sector"]
    acwi = {"sector": {sec: 0.05}, "region": {"us": 0.6, "europe": 0.4}, "currency": {"USD": 1.0}}
    meta = pd.DataFrame({"sector": [sec], "region": ["us"], "currency": ["USD"]}, index=["HELD"])
    base = propose.Base({"HELD": 100_000}, meta, acwi, {}, pd.DataFrame())
    c = _pc()
    picked, passed = propose.select(sc, 2, 20_000, base, c)
    assert top not in [p["ticker"] for p in picked] and "sector" in passed[top]
    empty = propose.Base({}, pd.DataFrame(columns=list(propose.DIMS)), acwi, {}, pd.DataFrame())
    picked, _ = propose.select(sc, 2, 20_000, empty, c)
    assert picked[0]["ticker"] == top                            # a bucket's first name is always allowed


def test_position_limit_is_against_the_whole_book(market):
    sc, pr = _scored(market)
    top = sc.index[0]
    base = propose.Base({}, pd.DataFrame(columns=list(propose.DIMS)), None, {top: 50_000, "X": 50_000}, pd.DataFrame())
    picked, passed = propose.select(sc, 2, 20_000, base, _pc(), max_position=0.2)
    assert top not in [p["ticker"] for p in picked] and "whole book" in passed[top]


def test_fill_gaps_prefers_an_underweight_sector(market):
    sc, pr = _scored(market, "value")
    low = sc[sc["sector"] != sc.iloc[0]["sector"]].iloc[-1]
    acwi = {"sector": {low["sector"]: 0.5}, "region": {}, "currency": {}}
    base = propose.Base({}, pd.DataFrame(columns=list(propose.DIMS)), acwi, {}, pd.DataFrame())
    caps = {"sector": 9, "region": 9, "currency": 9}
    conv, _ = propose.select(sc, 1, 10_000, base, _pc(caps=caps), "conviction")
    gaps, _ = propose.select(sc, 1, 10_000, base, _pc(caps=caps, fill_gaps_bonus=1000), "fill-gaps")
    assert conv[0]["sector"] != low["sector"]
    assert gaps[0]["sector"] == low["sector"]


# ---------------- the filler on an aktiesparekonto ----------------

def test_ask_filler_only_from_the_positive_list(market, monkeypatch):
    pr = propose.Prices(market)
    sf = fees.SimFees(10)
    monkeypatch.setattr(type(market), "positive_list", lambda self: {"XX0000000000"})
    no = propose.filler(5_000, "ask", pr, sf, True, _pc())
    assert no["positive_list"] == "no" and no["budget_dkk"] == 0 and "positive list" in no["note"]
    monkeypatch.setattr(type(market), "positive_list", lambda self: {_pc().etf_filler.isin})
    yes = propose.filler(5_000, "ask", pr, sf, True, _pc())
    assert yes["positive_list"] == "yes" and yes["value_dkk"] and yes["value_dkk"] < 5_000
    assert propose.filler(100, "ask", pr, sf, True, _pc()) is None
    assert propose.filler(5_000, "frie_midler", pr, sf, False, _pc()) is None


# ---------------- the model ----------------

def test_bootstrap_is_seeded_and_drawdowns_are_never_positive(market):
    pr = propose.Prices(market)
    R = pr.weekly(["S1", "S3", "ACWI"], 60)
    rp = propose.series({"S1": 1, "S3": 1}, R, "ACWI")
    c = _pc()
    a = propose.bootstrap(rp, R["ACWI"], 26, 0.02, c)
    b = propose.bootstrap(rp, R["ACWI"], 26, 0.02, c)
    assert a == b and a["max_dd"]["median"] <= 0 and a["max_dd"]["p10"] <= a["max_dd"]["median"]
    none = propose.bootstrap(rp, R["ACWI"], 26, None, c)
    assert none["drift_used"] is False
    assert a["excess"]["median"] > none["excess"]["median"]            # the drift moves the centre
    short = propose.bootstrap(rp.iloc[:5], R["ACWI"], 26, 0.0, c)
    assert "no bootstrap" in short["note"]


def test_stress_window_without_prices_is_marked(market):
    pr = propose.Prices(market)
    c = _pc(stress=[{"key": "old", "label": "Before the data", "start": "2001-01-02", "end": "2001-03-01"},
                   {"key": "in", "label": "In the data", "start": IDX[100].date(), "end": IDX[150].date()}])
    old, inside = propose.stress({"S1": 10_000, "S3": 10_000}, pr, "ACWI", c)
    assert old["ret"] is None and old["coverage"] == 0 and "not replayed" in old["note"]
    assert inside["coverage"] == 1 and inside["max_dd"] <= 0 and inside["acwi_ret"] is not None


def test_shrunk_covariance_is_positive_semidefinite(market):
    pr = propose.Prices(market)
    R = pr.weekly(["S1", "S2", "S3", "E1", "ACWI"], 60)
    cov = propose.shrunk_cov(R, 0.3, 20)
    assert np.linalg.eigvalsh(cov.to_numpy()).min() >= -1e-12
    r = propose.risk({"S1": 1, "S3": 1}, cov, "ACWI")
    assert r["vol_ann"] > 0 and r["coverage"] == 1 and sum(r["contributions"].values()) == pytest.approx(1)
    acwi = propose.risk({"ACWI": 1}, cov, "ACWI")
    assert acwi["te_ann"] == pytest.approx(0, abs=1e-9) and acwi["beta"] == pytest.approx(1)


def test_decision_rule(market):
    c = _pc()
    dd = {"bad_case": -0.2}
    hv = {"kept": {"holdout": {"gross_mean": 0.03}}}
    assert propose.decide({"drift_net": None}, hv, dd, None, c)["verdict"] == "A0"
    assert propose.decide({"drift_net": c.min_edge / 2}, hv, dd, None, c)["verdict"] == "A0"
    ok = propose.decide({"drift_net": 0.05}, hv, dd, 0.3, c)
    assert ok["verdict"] == "stocks" and ok["unchecked"] == []
    assert propose.decide({"drift_net": 0.05}, hv, dd, 0.1, c)["verdict"] == "A0"          # too deep a bad case
    assert propose.decide({"drift_net": 0.05}, {"kept": {"holdout": {"gross_mean": -0.01}}}, dd, None, c)["verdict"] == "A0"


def _study(results: dict, status: str = "ok") -> artifacts.Loaded:
    rep = artifacts.ProposeStudy.model_validate(
        {"schema_version": 1, "kind": "propose-study", "created": "2026-10-16T00:00:00", "data_asof": None,
         "rule_hash": "x", "results": results})
    return artifacts.Loaded("propose-study", status, rep)


def _longrun(gauge: float) -> artifacts.Loaded:
    rep = artifacts.LongrunStudy.model_validate(
        {"schema_version": 1, "kind": "longrun-study", "created": "2026-10-16T00:00:00", "data_asof": None,
         "survivorship": {"implied_haircut": gauge}})
    return artifacts.Loaded("longrun-study", "ok", rep)


def test_study_view_haircut_regime_and_staleness(market):
    c = _pc()
    kept = {"all": {"dates": 40, "gross_mean": 0.10}, "holdout": {"gross_mean": 0.02},
            "by_regime": {"Risk-on": {"dates": 30, "gross_mean": 0.20}, "Mixed": {"dates": 3, "gross_mean": -0.5}}}
    results = {"mix": {"3": {"6": {"kept": kept}}, "5": {"6": {"kept": kept}}}}
    v = propose.study_view(_study(results), "mix", 4, 6, "Risk-on", c)
    assert v["n_used"] == 3 and v["drift_gross"] == pytest.approx(0.20 * (1 - c.survivorship_haircut))
    assert v["kept"] == kept                                     # passed on as the study wrote it
    assert propose.study_view(_study(results), "mix", 5, 6, "Mixed", c)["drift_gross"] == pytest.approx(0.07)
    stale = propose.study_view(_study(results, "stale"), "mix", 5, 6, None, c)
    assert stale["drift_gross"] is None and stale["stale"] is True and stale["kept"] == kept
    assert propose.study_view(None, "mix", 5, 6, None, c)["drift_gross"] is None
    bad = artifacts.Loaded("propose-study", "invalid", reason="propose-study.json can't be read")
    v = propose.study_view(bad, "mix", 5, 6, None, c)
    assert v["drift_gross"] is None and v["note"] == "propose-study.json can't be read"     # said, never empty


def test_rule_hash_moves_with_the_rule_only(market):
    c = copy.deepcopy(market.cfg["propose"])                         # the raw section: the hash is of its values
    h = propose.rule_hash(c)
    assert propose.rule_hash(c | {"acwi_drift_annual": 0.5}) == h
    assert propose.rule_hash(c | {"max_corr": 0.5}) != h


# ---------------- end to end ----------------

def _draft(market, ask, **kw) -> dict:
    rep = propose.candidates(market, "ASK", 30_000, kw.pop("tilt", "momentum"), offline=True, **kw)
    assert rep["n"] == 3 and len(rep["shortlist"]) > 0
    return rep


def test_candidates_draft_and_evaluate(market, ask):
    rep = _draft(market, ask)
    assert rep["exposure_now"]["acwi_weights"] if "acwi_weights" in rep["exposure_now"] else True
    d = rep["draft_picks"]
    assert d["type"] == "propose-picks" and d["meta"]["rule_basket"] == [p["ticker"] for p in d["picks"]]
    assert all(p["exit"]["signal"]["metric"] == "score" for p in d["picks"])
    f = propose.save_picks(json.loads(json.dumps(d)))
    doc = json.loads(Path(f).read_text(encoding="utf-8"))
    assert doc["meta"]["frozen_at"]
    assert Path(propose.save_picks(json.loads(json.dumps(d)))).name != Path(f).name   # never overwritten
    ev = propose.evaluate(market, doc, offline=True)
    assert ev["decision"]["verdict"] == "A0" and "no evidence" in ev["decision"]["why"]   # no rule study yet
    assert ev["model"]["drift_net"] is None
    saved = propose.save_evaluation(Path(f).name, ev | {"unknown": float("nan")})   # NaN would be invalid JSON
    strict = json.loads(Path(saved).read_text(encoding="utf-8"), parse_constant=lambda c: pytest.fail(c))
    assert strict["unknown"] is None
    assert {"A0", "A1", "A2-value", "A2-mix", "A3", "A4", "A5", "A6"} <= set(ev["alternatives"])
    shared = {"risk", "bootstrap", "cost_pct", "drift_net", "realised_dd_1y"}
    assert all(shared <= set(ev["alternatives"][k]) for k in ("A0", "A1", "A4", "A5"))
    assert ev["alternatives"]["A0"]["risk"]["te_ann"] == pytest.approx(0, abs=1e-9)
    assert all(c["ok"] for c in ev["constraints"] if c["check"].startswith("swaps"))
    after = ev["exposure"]["after"]["weights"]["sector"]
    assert sum(after.values()) == pytest.approx(1)
    assert ev["exposure"]["before"]["weights"]["sector"] == {"Technology": pytest.approx(1)}   # S1 is held


def test_too_many_swaps_fail_the_constraint(market, ask, monkeypatch):
    d = _draft(market, ask)["draft_picks"]
    rule = set(d["meta"]["rule_basket"])
    others = [r for r in propose.candidates(market, "ASK", 30_000, "momentum", offline=True, top=20)["shortlist"]
              if r["ticker"] not in rule]
    with_settings(monkeypatch, base=market.cfg, propose={"max_swaps": 0})
    d["picks"][0]["ticker"] = others[0]["ticker"]
    ev = propose.evaluate(market, d, offline=True, light=True)
    assert not next(x for x in ev["constraints"] if x["check"].startswith("swaps"))["ok"]


def test_shadow_review_and_check_never_touch_a_real_portfolio(market, ask):
    d = _draft(market, ask)["draft_picks"]
    f = propose.save_picks(d)
    real_rows = len(userstore.transactions(portfolios=[ask["id"]]))
    res = propose.shadow(market, json.loads(Path(f).read_text(encoding="utf-8")), "Try")
    assert set(res["names"]) == {"proposal", "acwi", "rule"}
    for pid in res["ids"].values():
        p = userstore.get_portfolio(pid)
        assert p["mode"] == "virtual" and "proposal" in p["tags"] and p["params"]["proposal"]["arm"]
    assert len(userstore.transactions(portfolios=[ask["id"]])) == real_rows
    with pytest.raises(ValueError, match="already a portfolio"):
        propose.shadow(market, d, "Try")
    rev = propose.review(market)
    assert rev["proposals"][0]["note"] == "no prices since yet" and rev["enough"] is False
    chk = propose.check(market)
    names = chk["proposals"][0]["names"]
    assert {x["status"] for x in names} <= {"Intact", "Weakening", "Triggered"}
    assert all(x["held"] is False for x in names)                      # proposed, not bought


def test_check_flags_a_close_below_the_average_and_a_passed_time_stop(market, ask):
    d = _draft(market, ask)["draft_picks"]
    d["meta"]["date"] = IDX[150].date().isoformat()
    t = d["picks"][0]["ticker"]
    d["picks"][0]["exit"]["time_stop"] = IDX[200].date().isoformat()
    d["picks"][0]["exit"]["thesis"] = [{"text": "momentum stays above 99", "metric": "score", "op": "<", "value": 99},
                                       {"text": "management keeps guiding up"}]
    propose.save_picks(d)
    market.closes.loc[market.closes.index[-5:], t] *= 0.5                  # a crash below the 200-day average
    x = next(n for n in propose.check(market)["proposals"][0]["names"] if n["ticker"] == t)
    st = {i["criterion"]: i["status"] for i in x["items"]}
    assert x["status"] == "Triggered"
    assert st["close vs 200-day average"] == "triggered" and st[f"time stop {IDX[200].date()}"] == "triggered"
    assert st["momentum stays above 99"] == "triggered" and st["management keeps guiding up"] == "manual"
    assert propose.review(market)["proposals"][0]["ret"] is not None


def test_older_rule_is_flagged(market, ask):
    d = _draft(market, ask)["draft_picks"]
    d["meta"]["settings_hash"] = "000000000000"
    propose.save_picks(d)
    assert "changed since" in propose.check(market)["proposals"][0]["older_rule"][0]


def test_stops_frozen_today_are_not_a_change(market, ask):
    d = _draft(market, ask)["draft_picks"]
    same = Path(propose.save_picks(d)).name
    d["meta"]["stops"] = d["meta"]["stops"] | {"trend_sma": 100}
    moved = Path(propose.save_picks(d)).name
    older = {x["file"]: x["older_rule"] for x in propose.check(market)["proposals"]}
    assert older == {same: [], moved: ["settings.stops have changed since"]}


def test_parse_amount():
    from radar.money import parse_amount

    assert parse_amount("50000") == parse_amount("50.000") == parse_amount("50,000") == parse_amount("50k") == 50_000
    assert parse_amount("1.5m") == 1_500_000 and parse_amount("12,5k") == 12_500


def test_shrink_weights_by_precision():
    c = _pc(prior={"tau_annual": 0.0})
    prior = {"mean": 0.01, "se": 0.01}
    s = propose.shrink(0.05, 0.01, prior, 12, c)
    assert s["w_short"] == pytest.approx(0.5) and s["drift"] == pytest.approx(0.03)
    s = propose.shrink(0.05, 0.03, prior, 12, c)                   # a noisier study counts for less
    assert s["w_short"] == pytest.approx(0.1) and s["drift"] == pytest.approx(0.014)
    wide = propose.shrink(0.05, 0.01, prior, 12, _pc(prior={"tau_annual": 0.02}))   # tau widens the prior
    assert wide["w_short"] > 0.5
    assert propose.shrink(0.05, 0.01, None, 6, c)["drift"] == 0.05          # no prior: the study alone, said so
    assert propose.shrink(0.05, None, prior, 6, c)["drift"] == 0.01         # no standard error: the prior alone
    assert propose.shrink(None, 0.01, prior, 6, c)["drift"] is None
    vague = propose.shrink(0.05, 0.01, {"mean": 0.0, "se": None}, 6, c)   # a prior of unknown precision isn't exact
    assert vague["drift"] == 0.05 and vague["w_short"] == 1.0 and "standard error" in vague["note"]


def test_haircut_from_the_gauge_is_never_smaller():
    c = _pc(survivorship_haircut=0.3, haircut_from_gauge=True)
    assert propose.haircut(c, _longrun(0.55))["used"] == 0.55
    assert propose.haircut(c, _longrun(0.1))["used"] == 0.3
    assert propose.haircut(c, _longrun(1.4))["used"] == 0.3   # nonsense: ignored
    assert propose.haircut(c, None)["used"] == 0.3
    assert propose.haircut(_pc(survivorship_haircut=0.3, haircut_from_gauge=False), _longrun(0.55))["used"] == 0.3
    missing = propose.haircut(c, artifacts.Loaded("longrun-study", "missing", reason="no longrun-study yet"))
    assert missing["used"] == 0.3 and missing["gauge_note"] == "no longrun-study yet"     # configured, and why


def test_study_view_shrinks_toward_the_prior(market, monkeypatch):
    c = _pc(prior={"tau_annual": 0.0})
    kept = {"all": {"dates": 40, "gross_mean": 0.10, "mean": 0.09, "t": 3.0}}
    rep = _study({"momentum": {"5": {"6": {"kept": kept}}}})
    monkeypatch.setattr(propose.drift, "long_prior", lambda tilt, h, trend, c=None: {"mean": 0.01, "se": 0.03})
    v = propose.study_view(rep, "momentum", 5, 6, None, c, "up")
    short = 0.10 * (1 - c.survivorship_haircut)
    assert v["drift_short"] == pytest.approx(short) and v["se_short"] == pytest.approx(0.03)
    assert v["w_short"] == pytest.approx(0.5) and v["drift_gross"] == pytest.approx((short + 0.01) / 2)


def test_kv_picks_outside_the_us_are_flagged_untested(market, ask):
    d = _draft(market, ask)["draft_picks"]
    tickers = [p["ticker"] for p in d["picks"]]
    region = propose.info(tickers, propose.Prices(market))["region"]
    ev = propose.evaluate(market, d, offline=True, light=True)                     # momentum: K+V not used
    assert ev["untested_kv"] == []
    d["meta"]["tilt"] = "mix"
    ev = propose.evaluate(market, d, offline=True, light=True)
    assert ev["untested_kv"] == sorted(t for t in tickers if region[t] != "us")
    assert ev["untested_kv"] and any("never tested K+V" in n for n in ev["notes"])   # the fixture's pick is European


# ---------------- the frozen picks file's contract ----------------

def _picks(**meta) -> dict:
    return {"type": "propose-picks", "picks": [{"ticker": "S1", "exit": {"thesis": ["AI capex"]}, "note": "mine"}],
            "meta": {"portfolio": "ASK", "date": "2026-10-16", "amount": 30000, "settings_hash": "abc",
                     "stops": {"mode": "trend"}} | meta}


def test_the_picks_file_contract():
    from radar.propose import picks_file

    pf = picks_file.check(_picks())
    assert pf.picks[0].model_extra == {"note": "mine"}                       # the skill's own fields stay
    m = pf.meta                                                              # every field read has its default here
    assert (m.tilt, m.mode, m.weighting, m.horizon, m.max_position, m.etf) == ("mix", "conviction", "equal", 6, None, True)
    with pytest.raises(ValueError, match="isn't a picks file: meta.tilt"):
        picks_file.check(_picks(tilt="growth"))
    bad = _picks()
    del bad["meta"]["date"]
    with pytest.raises(ValueError, match="isn't a picks file: meta.date"):
        picks_file.check(bad)
    twice = _picks()
    twice["picks"].append({"ticker": "S1"})
    with pytest.raises(ValueError, match="S1 is picked twice"):
        picks_file.check(twice)
    with pytest.raises(ValueError, match="isn't a picks file: type"):
        picks_file.check(_picks() | {"type": "something-else"})


def test_a_frozen_file_that_doesnt_fit_is_named(tmp_data):
    from radar.propose import rules, store

    rules.PROPOSALS.mkdir(parents=True, exist_ok=True)
    doc = _picks(frozen_at="2026-10-16T12:00:00")
    del doc["meta"]["amount"]
    (rules.PROPOSALS / "2026-10-16_ask.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="2026-10-16_ask.json isn't a picks file: meta.amount"):
        store.proposals()
