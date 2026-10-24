"""The forward A/B test: a kvalitet+værdi basket, a momentum basket and a 50/50 blend as three virtual portfolios
(tag `ab-qvm`), picked once a month and frozen when recorded (in the portfolio's params), run from today on against
ACWI and each other: the clean, out-of-sample counterpart to the backtests. The rules as the user sees them:
guide/brugervejledning/portefoljer-og-tags.md (*A/B-test*); side by side: guide/laerebog/diversifikation.md.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from . import money, performance, simulate, tracked, userstore
from .config import typed
from .config_schema import Abtest
from .model.select import capped

TAG = "ab-qvm"
KINDS = {   # strategy key -> portfolio name
    "ab-qv": "A/B · Kvalitet+værdi",
    "ab-momentum": "A/B · Momentum",
    "ab-blend": "A/B · 50/50",
}
LABELS = {"ab-qv": "Kvalitet + værdi", "ab-momentum": "Momentum", "ab-blend": "50/50"}


def _cfg() -> Abtest:
    return typed().abtest


def portfolios() -> dict[str, dict]:
    """{strategy key: portfolio} of the A/B test's portfolios that exist."""
    return {p["strategy"]: p for p in userstore.portfolios()
            if p["origin"] == "sim" and p.get("strategy") in KINDS and not p.get("archived")}


# ---------------- the day's rankings ----------------

def _sectors() -> dict[str, str]:
    from .paths import CACHE

    f = CACHE / "sectors.csv"
    return (pd.read_csv(f, keep_default_na=False).set_index("ticker")["sector"].to_dict() if f.exists() else {})


def rankings(market, value_score: str = "qv") -> dict[str, pd.DataFrame]:
    """Today's candidates per basket from the radar's stock lists: ticker, score, sector, group, sorted best first,
    only names with a price and a DKK rate. K+V (or the værdiscore, `abtest.value_score`) from fundamentals/context.py;
    momentum as the momentum score pooled over every stock group (one ranking, not one per region)."""
    from . import universe
    from .fundamentals import context as fcontext
    from .signals import momentum

    groups = {t: g for g, ts in tracked.stock_groups(offline=True).items() for t in ts}
    sectors = _sectors()
    names = [t for t in groups if t in market.closes.columns]
    ok = {t for t in names if (fx := performance.fx_series(market, t)) is not None and len(fx.dropna())}
    m = momentum.metrics(market.closes, market.volumes, names, typed().momentum.min_history_days)
    m = m.assign(score=momentum.score(m))                         # pooled: one ranking over every group
    fctx = fcontext.context(market.closes, market.raw_closes(), universe.tracked_stocks(), market.mtime)
    t = fctx.table()
    q = t[t["region"].notna()][["ticker", value_score]].rename(columns={value_score: "score"}) if not t.empty \
        else pd.DataFrame(columns=["ticker", "score"])

    def tidy(df: pd.DataFrame) -> pd.DataFrame:
        df = df[df["ticker"].isin(ok)].dropna(subset=["score"]).copy()
        df["sector"] = df["ticker"].map(sectors).fillna("")
        df["group"] = df["ticker"].map(groups)
        return df[["ticker", "score", "sector", "group"]].sort_values("score", ascending=False,
                                                                      kind="stable").reset_index(drop=True)
    return {"ab-qv": tidy(q), "ab-momentum": tidy(m[["ticker", "score"]])}


def picks(ranked: pd.DataFrame, n: int, max_per_sector: int | None) -> list[dict]:
    """The top `n` under the sector cap, equal weights."""
    chosen = capped(list(ranked.itertuples(index=False)), n, max_per_sector, None)
    return [{"ticker": r.ticker, "weight": 1 / len(chosen), "score": round(float(r.score), 1)} for r in chosen]


def blend(a: list[dict], b: list[dict]) -> list[dict]:
    """Both lists at half weight each; a name in both gets both halves."""
    w: dict[str, float] = {}
    for lst in (a, b):
        for p in lst:
            w[p["ticker"]] = w.get(p["ticker"], 0.0) + p["weight"] / 2
    return [{"ticker": t, "weight": x, "score": None} for t, x in w.items()]


# ---------------- creating and recording ----------------

def create(market, capital: float | None = None, n: int | None = None, max_per_sector: int | None = None,
           value_score: str | None = None, today: date | None = None) -> dict:
    """Start the A/B test: the three portfolios and their first picks (refused when it exists, or when fewer than
    `n` stocks have a score yet)."""
    if portfolios():
        raise ValueError("the A/B test is already running (radar abtest status)")
    cfg = _cfg()
    params: dict[str, Any] = {"n": int(n or cfg.n), "max_per_sector": max_per_sector if max_per_sector is not None
              else cfg.max_per_sector, "capital": float(capital or cfg.capital),
              "value_score": value_score or cfg.value_score, "fee_bps": typed().backtest.fee_bps}
    if params["value_score"] not in ("qv", "value"):
        raise ValueError("value_score is qv (kvalitet + værdi) or value (værdiscore alone)")
    ranked = rankings(market, params["value_score"])
    short = {k: len(v) for k, v in ranked.items() if len(v) < params["n"]}
    if short:
        raise ValueError("too few stocks with a score to fill the baskets ("
                         + ", ".join(f"{LABELS[k]}: {v} of {params['n']}" for k, v in short.items())
                         + "); fetch statements first: radar fundamentals update --all")
    for name in KINDS.values():
        if userstore.portfolio_by_name(name):
            raise ValueError(f"there is already a portfolio called {name}")
    for key, name in KINDS.items():
        simulate.new_sim_portfolio(name, key, params | {"rebalances": []}, tags=[TAG, key])
    return refresh(market, today=today, ranked=ranked)


def _month(d: str) -> str:
    return str(d)[:7]


def record_due(market, today: date | None = None, ranked: dict | None = None) -> str | None:
    """This month's picks, when none are recorded yet for the month of the latest prices. Returns the date
    recorded, or None."""
    ps = portfolios()
    if not ps:
        return None
    asof = performance.benchmark_sessions(market)[-1].date().isoformat()
    params = next(iter(ps.values()))["params"]
    done = {_month(r["date"]) for p in ps.values() for r in p["params"].get("rebalances", [])}
    if _month(asof) in done:
        return None
    ranked = ranked or rankings(market, params["value_score"])
    n, cap = params["n"], params["max_per_sector"]
    lists = {"ab-qv": picks(ranked["ab-qv"], n, cap), "ab-momentum": picks(ranked["ab-momentum"], n, cap)}
    lists["ab-blend"] = blend(lists["ab-qv"], lists["ab-momentum"])
    for key, p in ps.items():
        if not lists.get(key):
            continue                                  # nothing scored this month: the basket keeps what it holds
        rec = {"date": asof, "recorded": (today or date.today()).isoformat(), "picks": lists[key],
               "candidates": len(ranked[key]) if key in ranked else None}
        userstore.save_portfolio({"params": p["params"] | {"rebalances": [*p["params"].get("rebalances", []), rec]}},
                                 p["id"])
    return asof


# ---------------- replaying the records ----------------

class ScoreRebalance:
    """A simulate.Strategy that replays a portfolio's recorded rebalances (params["rebalances"]): on the session
    after each record, sell what left the list, then trade every holding to its target weight at that day's traded
    closes and DKK rates, paying `backtest.fee_bps` on what is traded (no account, so no broker schedule). Buys never
    spend more cash than there is; a record whose next session isn't in the prices yet waits. A holding without a
    price that day stays as it is and counts at its last price in the value the targets are sized from."""
    key = "ab-rebalance"

    def __init__(self) -> None:
        self.notes: list[str] = []

    @staticmethod
    def _px(market, t: str, day: pd.Timestamp) -> tuple[float, float] | None:
        """(traded close, DKK rate) on `day` (or the last within 7 days before), else None."""
        b = market.bars(t) if t in market.closes.columns else pd.DataFrame()
        col = "raw_close" if "raw_close" in b else "close"
        s = b[col].dropna()[:day] if len(b) else pd.Series(dtype=float)
        fx = performance.fx_series(market, t)
        rate = money.rate_on(fx, day)
        if not len(s) or (day - s.index[-1]).days > 7 or rate is None:
            return None
        return float(s.iloc[-1]), rate

    def rows(self, market, start, end, capital_dkk: float, params: dict) -> list[dict]:
        cal = performance.benchmark_sessions(market)
        bps = money.bps(params.get("fee_bps", 0))
        held: dict[str, float] = {}
        last: dict[str, tuple[float, float]] = {}          # each name's last (traded close, DKK rate) seen
        cash = 0.0
        rows: list[dict] = []
        for rec in params.get("rebalances", []):
            after = cal[cal > pd.Timestamp(rec["date"])]
            if after.empty:
                self.notes.append(f"the picks of {rec['date']} are bought at the next session (not in the prices yet)")
                break
            day = after[0]
            ds = day.date().isoformat()
            if not rows:
                rows.append({"date": ds, "type": "DEPOSIT", "amount": float(capital_dkk), "currency": "DKK",
                             "note": "A/B test capital"})
                cash = float(capital_dkk)
            target = {p["ticker"]: p["weight"] for p in rec["picks"]}
            prices = {t: self._px(market, t, day) for t in set(held) | set(target)}
            unpriced = sorted(t for t, v in prices.items() if v is None)
            if unpriced:
                self.notes.append(f"{ds}: no price or DKK rate for {', '.join(unpriced)}: left as they were, "
                                  "a holding counted at its last price")
            last |= {t: p for t, p in prices.items() if p is not None}
            value = cash + sum(q * p[0] * p[1] for t, q in held.items() if (p := last.get(t)))
            trades = []
            for t in sorted(set(held) | set(target)):
                pr = prices.get(t)
                if pr is None:
                    continue
                px, rate = pr
                want = target.get(t, 0.0) * value / (px * rate)
                delta = want - held.get(t, 0.0)
                if abs(delta) * px * rate < 1.0:
                    continue
                trades.append((t, delta, px, rate))
            for t, delta, px, rate in [x for x in trades if x[1] < 0]:         # sells first, then buys
                q = min(-delta, held.get(t, 0.0))
                fee = q * px * bps
                rows.append({"symbol": t, "date": ds, "type": "SELL", "quantity": q, "price": px, "fee": fee,
                             "fx_rate": rate, "note": "A/B rebalance"})
                cash += (q * px - fee) * rate
                held[t] = held.get(t, 0.0) - q
                if held[t] <= 1e-9:
                    held.pop(t)
            buys = [x for x in trades if x[1] > 0]
            need = sum(d * px * rate * (1 + bps) for _, d, px, rate in buys)
            scale = min(1.0, cash / need) if need > 0 else 1.0                  # never more than the cash there is
            for t, delta, px, rate in buys:
                q = delta * scale * (1 - 1e-9)
                fee = q * px * bps
                rows.append({"symbol": t, "date": ds, "type": "BUY", "quantity": q, "price": px, "fee": fee,
                             "fx_rate": rate, "note": f"A/B rebalance: {target[t]:.1%}"})
                cash -= (q * px + fee) * rate
                held[t] = held.get(t, 0.0) + q
        return rows


def refresh(market, today: date | None = None, ranked: dict | None = None, log=None) -> dict:
    """Record this month's picks if due, then replay every A/B portfolio from its records. `simulate.write_run`
    stores each run, its params saying how fees were charged (`fee_model`), so a rerun gives the same rows."""
    ps = portfolios()
    if not ps:
        return {"recorded": None, "runs": {}, "notes": []}
    recorded = record_due(market, today, ranked)
    ps = portfolios()                                  # re-read: the params changed
    runs, notes = {}, []
    for key, p in ps.items():
        strat = ScoreRebalance()
        rows = strat.rows(market, None, None, p["params"]["capital"], p["params"])
        notes += [f"{LABELS[key]}: {n}" for n in strat.notes]
        if rows:
            recs = p["params"]["rebalances"]
            run_params = p["params"] | {"fee_model": {"kind": "bps", "bps": money.fee_bps(p["params"])}}
            runs[key] = simulate.write_run(p["id"], ScoreRebalance.key, run_params,
                                           recs[0]["date"], recs[-1]["date"], rows, market)
    if log:
        log(f"A/B test: {'picks recorded for ' + recorded if recorded else 'no new picks this month'}; "
            f"{len(runs)} portfolios replayed" + (f" ({'; '.join(notes)})" if notes else ""))
    return {"recorded": recorded, "runs": runs, "notes": notes}


# ---------------- the view ----------------

def _weekly(b) -> pd.Series:
    idx = performance.twr(b.value, b.inflow, b.outflow).dropna()
    return idx.resample("W-FRI").last().pct_change().dropna() if len(idx) else pd.Series(dtype=float)


def view(market) -> dict:
    """The test's state: the three lines and ACWI from the first purchase, the correlation of their weekly
    returns, every recorded rebalance with its turnover, and when the next picks are due."""
    from .signals import risk

    ps = portfolios()
    if not ps:
        return {"running": False, "portfolios": [], "comparison": None, "correlation": None, "rebalances": [],
                "next_due": None, "notes": []}
    order = [k for k in KINDS if k in ps]
    ids = [ps[k]["id"] for k in order]
    cmp = performance.compare(market, ids=ids)
    weekly = {}
    for k in order:
        b = performance.portfolio_book(ps[k], market)
        if b is not None:
            weekly[LABELS[k]] = _weekly(b)
    bench = performance.bench_dkk(market)
    if weekly and any(len(w) for w in weekly.values()):
        first = min(w.index[0] for w in weekly.values() if len(w))
        weekly["ACWI"] = bench.loc[first:].resample("W-FRI").last().pct_change().dropna()
    rc = typed().risk
    corr = risk.correlation(weekly, rc.windows["3y"], rc.min_weeks) if weekly else None
    rebal = []
    for k in order:
        prev: dict[str, float] = {}
        for r in ps[k]["params"].get("rebalances", []):
            now = {p["ticker"]: p["weight"] for p in r["picks"]}
            turnover = sum(abs(now.get(t, 0) - prev.get(t, 0)) for t in set(now) | set(prev)) / 2
            rebal.append({"kind": k, "label": LABELS[k], "date": r["date"], "picks": r["picks"],
                          "turnover": round(turnover, 4)})
            prev = now
    last = max((r["date"] for r in rebal), default=None)
    next_due = (pd.Timestamp(last) + pd.offsets.MonthBegin(1)).date().isoformat() if last else None
    notes = []
    weeks = max((len(w) for w in weekly.values()), default=0)
    if weeks < rc.min_weeks:
        notes.append(f"{weeks} week(s) of returns so far: correlations need {rc.min_weeks}, and a fair comparison "
                     "needs a year or more")
    return {"running": True,
            "portfolios": [{"kind": k, "label": LABELS[k], "id": ps[k]["id"], "name": ps[k]["name"]} for k in order],
            "params": {k: v for k, v in ps[order[0]]["params"].items() if k != "rebalances"},
            "comparison": cmp, "correlation": corr, "rebalances": rebal, "next_due": next_due, "notes": notes}


def summary(market) -> dict:
    """The compact digest for summary.json (the skills read it): per basket its return, ACWI's and the difference
    since the first purchase, and its latest picks; the correlation of the weekly returns; when the next picks are
    due. {"running": False} when no test runs."""
    v = view(market)
    if not v["running"]:
        return {"running": False}
    rows = {r["portfolio"]["id"]: r for r in (v["comparison"] or {}).get("rows", []) if r.get("portfolio")}
    latest = {}
    for r in v["rebalances"]:                                  # in date order: the last one per basket wins
        latest[r["kind"]] = r
    baskets = []
    for p in v["portfolios"]:
        s = (rows.get(p["id"]) or {}).get("stats") or {}
        r = latest.get(p["kind"]) or {}
        baskets.append({"kind": p["kind"], "label": p["label"], "name": p["name"], "start": s.get("start"),
                        "twr": s.get("twr_total"), "acwi": s.get("acwi_twr_total"), "excess": s.get("excess_twr"),
                        "max_drawdown": s.get("max_drawdown"), "picked": r.get("date"), "turnover": r.get("turnover"),
                        "picks": [x["ticker"] for x in sorted(r.get("picks", []), key=lambda x: -x["weight"])]})
    c = v["correlation"]
    return {"running": True, "value_score": (v["params"] or {}).get("value_score"), "baskets": baskets,
            "correlation": {"weeks": c["weeks"], "symbols": c["symbols"], "matrix": c["matrix"]} if c else None,
            "next_due": v["next_due"], "notes": v["notes"]}
