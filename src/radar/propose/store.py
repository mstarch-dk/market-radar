"""Frozen proposals and their follow-up: saving picks and evaluations, the shadow portfolios, the review
and the exit-criteria check."""
from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from pydantic import ValidationError

from .. import fees, tracked, trades, userstore
from ..config import typed, write_text
from ..config_schema import Stops
from ..jsonsafe import clean as _clean
from ..jsonsafe import dumps
from ..model import artifacts
from ..model import paths as mpaths
from ..model.stats import mean as _mean
from ..signals.risk import deepest_drawdown
from ..values import num
from . import basket, draft, evaluation, picks_file, pricing, rules

if TYPE_CHECKING:
    from ..market import Market


def save_picks(doc: dict) -> str:
    """Write a picks file into exports/proposals/ (frozen: stamped once)."""
    picks_file.check(doc)
    m = doc["meta"]                                # the raw dict: what is written, stamped once
    if not m.get("frozen_at"):
        m["frozen_at"] = pd.Timestamp.now().isoformat(timespec="seconds")
    rules.PROPOSALS.mkdir(parents=True, exist_ok=True)
    stem = f"{m['date']}_{rules.slug(m['portfolio'])}"
    f, k = rules.PROPOSALS / f"{stem}.json", 1
    while f.exists():                              # a frozen proposal is never overwritten
        k += 1
        f = rules.PROPOSALS / f"{stem}-{k}.json"
    write_text(f, dumps(doc, indent=1, ensure_ascii=False))
    return str(f)


def evaluation_file(fname: str):
    return rules.PROPOSALS / fname.replace(".json", "-evaluation.json")


def keep_evaluation(picks_file: str, ev: dict) -> str | None:
    """Save the evaluation beside its picks when the picks file is a frozen one in exports/proposals/ (an
    evaluation of a copy elsewhere isn't kept); returns where it went."""
    from pathlib import Path

    if Path(picks_file).resolve().parent != Path(rules.PROPOSALS).resolve():
        return None
    return save_evaluation(Path(picks_file).name, ev)


def save_evaluation(fname: str, ev: dict) -> str:
    rules.PROPOSALS.mkdir(parents=True, exist_ok=True)
    f = evaluation_file(fname)
    write_text(f, dumps(ev, indent=1, ensure_ascii=False))
    return str(f)


def _band(fname: str) -> list[float] | None:
    """The modelled drawdown band [bad case, expected] from a proposal's saved evaluation."""
    f = evaluation_file(fname)
    try:
        dd = json.loads(f.read_text(encoding="utf-8")).get("drawdown") or {}
    except (FileNotFoundError, ValueError):
        return None
    return [dd["bad_case"], dd["expected"]] if dd.get("bad_case") is not None else None


def proposals() -> list[tuple[str, picks_file.PicksFile]]:
    """Every frozen picks file, oldest first, checked."""
    if not rules.PROPOSALS.exists():
        return []
    out = []
    for f in sorted(rules.PROPOSALS.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if d.get("type") == "propose-picks" and (d.get("meta") or {}).get("frozen_at"):
            out.append((f.name, picks_file.check(d, f.name)))   # a frozen file that doesn't fit says so, by name
    return out


def shadow(market: Market, doc: dict, name: str) -> dict:
    """Virtual copies of the portfolio at the latest close plus the amount: the proposal, ACWI (A0) and the rule
    basket (A1), tagged proposal and proposal-<date>. Never touches a real portfolio."""
    from .. import simulate

    pf = picks_file.check(doc)
    m = pf.meta
    src = userstore.portfolio_by_name(m.portfolio)
    if not src:
        raise ValueError(f"no portfolio called {m.portfolio}")
    names = {"proposal": name, "acwi": f"{name} · ACWI", "rule": f"{name} · rule"}
    for v in names.values():
        if userstore.portfolio_by_name(v):
            raise ValueError(f"there is already a portfolio called {v}: shadows are new, virtual portfolios")
    prices = pricing.Prices(market)
    sf = fees.SimFees.for_portfolio(src, typed().backtest.fee_bps)
    day = pd.Timestamp(market.closes.index[-1])
    when = m.date.isoformat()
    tags = ["proposal", f"proposal-{when}"]
    amount = m.amount
    rule = m.rule_basket
    arms = {"proposal": [x.ticker for x in pf.picks], "acwi": [tracked.benchmark()], "rule": rule}
    ids = {}
    for arm, ticks in arms.items():
        if not ticks:
            continue
        pid = simulate.fork(src["id"], names[arm], day, market, amount, tags)
        for t in ticks:
            px, rate = prices.last_px(t), prices.rate(t)
            if px is None or rate is None:
                continue
            tm = basket.terms_for(prices, sf, t)
            qty = tm.value_for_budget(amount / len(ticks) / rate) / px
            if arm != "acwi":
                qty = math.floor(qty)
            if qty <= 0:
                continue
            userstore.add_tx({"symbol": t, "date": day.date().isoformat(), "type": "BUY", "quantity": qty, "price": px,
                              "fee": tm.fee(qty * px), "fx_rate": rate, "portfolio_id": pid,
                              "note": f"proposal {when} ({arm})"}, source="fork")
        p = userstore.get_portfolio(pid) or {}
        userstore.save_portfolio({"params": (p.get("params") or {}) | {"proposal": {
            "date": when, "arm": arm, "tickers": ticks, "amount": amount, "picks_sha": evaluation.picks_sha(doc)}}}, pid)
        ids[arm] = pid
    return {"ids": ids, "names": {k: names[k] for k in ids}, "tags": tags,
            "returns_link": f"/returns?pf={','.join(str(v) for v in ids.values())}&from={day.date().isoformat()}"}


def _basket_path(prices: pricing.Prices, tickers: list[str], start: pd.Timestamp, sma: int | None = None) -> dict:
    """Equal DKK weights bought at the close of `start`: kept, and with the trend exit (model.paths: a close below
    the average after the buy day, sold at the next close, parked in ACWI)."""
    bench = tracked.benchmark()
    b = prices.dkk(bench)
    legs, legs_x, events = [], [], []
    for t in tickers:
        s = prices.dkk(t)
        if s is None or s.loc[start:].empty:
            continue
        w = s.loc[start:]
        leg = w / w.iloc[0]
        legs.append(leg)
        if sma and t in prices.market.closes:
            if b is None:
                raise ValueError(f"no {bench} prices in DKK to park the exits in")
            below = mpaths.below_trend(prices.market.closes[t], sma).reindex(w.index, fill_value=False)
            k = mpaths.exit_session(w.index, below)
            if k is not None:
                kd = w.index[k]
                legs_x.append(mpaths.park(leg, kd, b.reindex(w.index).ffill()))
                events.append({"ticker": t, "date": kd.date().isoformat()})
                continue
        legs_x.append(leg)
    if not legs:
        return {}
    v = pd.concat(legs, axis=1).ffill().mean(axis=1)
    vx = pd.concat(legs_x, axis=1).ffill().mean(axis=1)
    bi = b.loc[start:] / b.loc[start:].iloc[0] if b is not None else None
    return {"ret": float(v.iloc[-1] - 1), "max_dd": deepest_drawdown(v),
            "exits_ret": float(vx.iloc[-1] - 1), "exits": events,
            "acwi": float(bi.iloc[-1] - 1) if bi is not None and len(bi) else None, "days": int(len(v) - 1)}


def review(market: Market) -> dict:
    """How each frozen proposal did since its day, against ACWI, its rule basket and its own modelled range."""
    c = rules.cfg()
    prices = pricing.Prices(market)
    st = typed().stops
    rows: list[dict] = []
    for fname, d in proposals():
        m = d.meta
        when, start = m.date.isoformat(), pd.Timestamp(m.date)
        if start >= market.closes.index[-1]:
            rows.append({"file": fname, "date": when, "portfolio": m.portfolio, "note": "no prices since yet"})
            continue
        ticks = [x.ticker for x in d.picks]
        mine = _basket_path(prices, ticks, start, st.trend_sma)
        rule = _basket_path(prices, m.rule_basket, start) if m.rule_basket else {}
        band = _band(fname)
        rows.append({"file": fname, "date": when, "portfolio": m.portfolio, "tilt": m.tilt,
                     "tickers": ticks, "days": mine.get("days"), "ret": mine.get("ret"), "acwi": mine.get("acwi"),
                     "excess": None if mine.get("ret") is None or mine.get("acwi") is None else mine["ret"] - mine["acwi"],
                     "rule_ret": rule.get("ret"), "judgment_vs_rule": None if not rule or mine.get("ret") is None
                     else mine["ret"] - rule["ret"], "max_dd": mine.get("max_dd"), "modelled_dd": band,
                     "dd_inside_band": None if not band or mine.get("max_dd") is None else mine["max_dd"] >= band[0],
                     "exits_ret": mine.get("exits_ret"), "exits_vs_kept": None if mine.get("exits_ret") is None
                     else mine["exits_ret"] - mine["ret"], "exit_events": mine.get("exits")})
    judged = [r for r in rows if r.get("excess") is not None]
    return _clean({"proposals": rows, "count": len(judged), "enough": len(judged) >= c["review_min"],
                   "summary": {"mean_excess": float(np.mean([r["excess"] for r in judged])) if judged else None,
                               "beat_acwi": float(np.mean([r["excess"] > 0 for r in judged])) if judged else None,
                               "mean_judgment_vs_rule": _mean([r.get("judgment_vs_rule") for r in judged]),
                               "dd_inside_band": _mean([r.get("dd_inside_band") for r in judged]),
                               "mean_exits_vs_kept": _mean([r.get("exits_vs_kept") for r in judged])},
                   "note": None if len(judged) >= c["review_min"] else
                   f"{len(judged)} proposal(s) with a result: fewer than {c['review_min']} say nothing about the method yet"})


def _stops_changed(frozen: dict, now: Stops) -> bool:
    """The stops frozen with a proposal differ from today's (compared as the settings model, so 80 is 80.0 and a
    key added since with its default isn't a change; a frozen section that no longer fits the model is one)."""
    try:
        return Stops.model_validate(frozen) != now
    except ValidationError:
        return True


def check(market: Market, portfolio: str | None = None) -> dict:
    """Each open proposal's exit criteria today: Intact, Weakening or Triggered, with the evidence."""
    from ..model import panels as mp

    c = rules.cfg()
    prices = pricing.Prices(market)
    st = typed().stops
    p = mp.panels(market)
    pl = basket.pool(market, prices, p)
    exit_run = max((r.report.created for r in (artifacts.load("exit-study"), artifacts.load("redeploy-study"))
                    if r.report is not None), default=None)
    today = pd.Timestamp(market.closes.index[-1])
    out = []
    for fname, d in proposals():
        m = d.meta
        when = m.date.isoformat()
        if portfolio and m.portfolio != portfolio:
            continue
        held = None
        pf = userstore.portfolio_by_name(m.portfolio)
        if pf:
            pos, _ = trades.positions(trades.transactions([pf["id"]]))
            held = set(pos[pos["status"] == "holding"]["symbol"]) if not pos.empty else set()
        older = []
        if m.settings_hash and m.settings_hash != rules.rule_hash():
            older.append("the proposal rule's settings have changed since")
        if m.stops and _stops_changed(m.stops, st):
            older.append("settings.stops have changed since")
        if exit_run and pd.Timestamp(exit_run) > pd.Timestamp(m.frozen_at or m.date):
            older.append("the exit study was re-run since")
        names = []
        for x in d.picks:
            t = x.ticker
            ex = x.exit.model_dump() if x.exit else draft.default_exit(m.tilt, when, m.horizon)
            items = []
            cl = market.closes[t].dropna() if t in market.closes else pd.Series(dtype=float)
            sma = int((ex.get("review_level") or {}).get("sma") or st.trend_sma)
            if len(cl) >= sma:
                lvl = float(mpaths.trend_level(cl, sma).iloc[-1])
                gap = float(cl.iloc[-1] / lvl - 1)
                items.append({"criterion": f"close vs {sma}-day average", "value": gap,
                              "status": "triggered" if gap < 0 else "weakening" if gap < c["exit"]["weakening"] else "intact"})
            else:
                items.append({"criterion": f"close vs {sma}-day average", "value": None, "status": "unknown"})
            sig = ex.get("signal") or {}
            if sig.get("metric"):
                col = "score" if sig["metric"] == "score" else sig["metric"]
                v = num(pl.at[t, col]) if t in pl.index and col in pl else None
                lim = float(sig["below"])
                items.append({"criterion": f"{sig['metric']} below {lim:g}", "value": v,
                              "status": "unknown" if v is None else "triggered" if v < lim else
                              "weakening" if v < lim + 5 else "intact"})
            for th in ex.get("thesis") or []:
                if th.get("metric") and th.get("op") in ("<", ">") and th.get("value") is not None:
                    col = th["metric"]
                    v = num(pl.at[t, col]) if t in pl.index and col in pl else None
                    bad = None if v is None else (v < th["value"] if th["op"] == "<" else v > th["value"])
                    items.append({"criterion": th.get("text") or f"{col} {th['op']} {th['value']}", "value": v,
                                  "status": "unknown" if bad is None else "triggered" if bad else "intact"})
                else:
                    items.append({"criterion": th.get("text"), "value": None, "status": "manual"})
            ts = ex.get("time_stop")
            days = (pd.Timestamp(ts) - today).days if ts else None
            if ts:
                items.append({"criterion": f"time stop {ts}", "value": days,
                              "status": "triggered" if days is not None and days <= 0 else "intact"})
            stt = [i["status"] for i in items]
            status = "Triggered" if "triggered" in stt else "Weakening" if "weakening" in stt else "Intact"
            names.append({"ticker": t, "held": None if held is None else t in held, "status": status, "items": items,
                          "days_to_time_stop": days})
        start = pd.Timestamp(m.date)
        path = _basket_path(prices, [x.ticker for x in d.picks], start) if start < today else {}
        band = _band(fname)
        drawdown = {"max_dd": path.get("max_dd"), "bad_case": band[0] if band else None,
                    "status": None if not band or path.get("max_dd") is None else
                    "Triggered" if path["max_dd"] < band[0] else "Intact"}
        out.append({"file": fname, "date": when, "portfolio": m.portfolio, "older_rule": older,
                    "names": names, "basket": drawdown})
    return _clean({"asof": today.date().isoformat(), "proposals": out})
