"""The proposal rule tested at every past month-end: the evidence behind `radar propose`'s modelled return and
drawdown (`radar study propose` → reports/propose-study.json).

On each formation date D (the last session of a completed month), for each tilt (momentum, value, mix) and each
basket size in `propose.study_ns`, the rule picks a basket exactly as a proposal's rule-only basket would, from
data up to D only: the gates, the proposal score with its penalties, and the caps against an empty portfolio
(today's ACWI weights for the active-weight caps, since no history of them is stored). Equal weights, bought at
the fill session (`backtest.fill`), each trade paying `propose.study_cost_bps`.

- **Kept**: held for 3 and 6 months, in DKK, against ACWI in DKK: the return gross and net of costs, the excess
  over ACWI, the path's max drawdown and worst 20 sessions.
- **With exits**: the same buys with the exits a proposal sets: a close below the `stops.trend_sma`-day average
  (sold at the next session's close) and the tilt's signal exit at each month-end (momentum score below
  `propose.exit.min_score`; K+V below `min_qv` for the value tilt), the money parked in ACWI.
- **Across dates**: means, medians, 10th/90th percentiles, Newey-West t (lag H−1 months: the windows overlap),
  hit rate, an effective N (dates ÷ horizon months: roughly the number of independent periods), splits in-sample
  vs holdout (`backtest.study_holdout_from`) and by the regime on D; the composite's IC with the next 6 months;
  the basket's monthly turnover.

The value and mix tilts need K+V as known on D, which only SEC EDGAR gives (filing dates), so they are tested on US
stocks only. Survivorship: the universe is today's, which flatters the past, most of all for momentum; the
proposal model cuts a positive excess by `propose.survivorship_haircut`. A change to the rule's settings (the
hash in the report) makes the report stale: the proposal then shows no drift until it is run again."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import propose, universe
from ..config import settings
from ..model import artifacts
from ..model import panels as mp
from ..model import paths as mpaths
from . import study

CAVEATS = [
    "Survivorship: today's universe (S&P 500 constituents and the curated lists), so names that left it are missing; "
    "it flatters momentum most. The proposal model cuts a positive excess by propose.survivorship_haircut.",
    "Value and mix tilts: US stocks only before today (SEC EDGAR is the one source with filing dates).",
    "The active-weight caps use today's ACWI weights (no history of them is stored); sectors are today's.",
    "Overlapping windows: monthly dates with 3- and 6-month horizons share most of their months, so the effective N "
    "(dates ÷ horizon) is what to read, and the Newey-West t corrects for the overlap.",
    "Costs: propose.study_cost_bps each way; before tax. The proposal's own costs replace them in `radar propose`.",
    "The tilt and basket size are chosen by you and by the cost frontier, never by which one did best here.",
]


def _q(v, p):
    v = [x for x in v if x is not None and np.isfinite(x)]
    return float(np.percentile(v, p)) if v else None


def _m(v):
    v = [x for x in v if x is not None and np.isfinite(x)]
    return float(np.mean(v)) if v else None


def summarize(recs: list[dict], h: int, prefix: str = "") -> dict | None:
    """Across dates for one arm (`prefix` '' kept, 'x_' with exits)."""
    recs = [r for r in recs if r.get(prefix + "excess") is not None]
    if not recs:
        return None
    ex = [r[prefix + "excess"] for r in recs]
    lag = max(h - 1, 0)
    out = {"dates": len(recs), "effective_n": round(len(recs) / h, 1),
           "mean": _m(ex), "gross_mean": _m([r[prefix + "excess_gross"] for r in recs]), "median": _q(ex, 50),
           "p10": _q(ex, 10), "p90": _q(ex, 90), "t": study.nw_t(ex, lag), "hit": _m([float(x > 0) for x in ex]),
           "ret_mean": _m([r[prefix + "net"] for r in recs]), "acwi_mean": _m([r["acwi"] for r in recs]),
           "dd_median": _q([r[prefix + "max_dd"] for r in recs], 50),
           "dd_p10": _q([r[prefix + "max_dd"] for r in recs], 10),
           "worst20_mean": _m([r[prefix + "worst20"] for r in recs])}
    if prefix:
        out["vs_kept_mean"] = _m([r["x_net"] - r["net"] for r in recs if r.get("net") is not None])
        out["exits_mean"] = _m([r["x_exits"] for r in recs])
    return out


def split(recs: list[dict], h: int, prefix: str, holdout) -> dict:
    return {"all": summarize(recs, h, prefix),
            "in_sample": summarize([r for r in recs if holdout is None or r["date"] < holdout], h, prefix),
            "holdout": summarize([r for r in recs if holdout is not None and r["date"] >= holdout], h, prefix),
            "by_regime": {str(g): summarize([r for r in recs if r["regime"] == g], h, prefix)
                          for g in sorted({r["regime"] for r in recs}, key=str)}}


class Paths:
    """Basket paths on the session calendar: kept and with the proposal's exits."""

    def __init__(self, p: mp.Panels, sma_n: int, c: dict):
        self.p = p
        self.dkk = p.dkk.reindex(p.sessions).ffill(limit=5)
        self.close = p.closes.reindex(p.sessions).ffill(limit=5)
        self.below = self.close < mpaths.trend_level(p.closes, sma_n).reindex(p.sessions)
        self.bench = p.bench_dkk.reindex(p.sessions).ffill()
        self.c = c
        self.month_ends = set(mp.formation_dates(p.sessions))
        self._sig: dict = {}

    def signal_below(self, day, tilt: str) -> pd.Series:
        """Names whose signal is below the exit level at month-end `day` (momentum score, or K+V for value)."""
        key = (day, tilt)
        if key not in self._sig:
            w = self.c["tilts"][tilt]
            if w.get("momentum", 0) >= w.get("qv", 0):
                s = mp.score_at(self.p, day)
                self._sig[key] = s < self.c["exit"]["min_score"]
            else:
                s = self.p.fund.col(day, "qv") if self.p.fund is not None else pd.Series(dtype=float)
                self._sig[key] = s < self.c["exit"]["min_qv"]
        return self._sig[key]

    def run(self, tickers: list[str], fi: int, H: int, tilt: str, cost: float) -> dict | None:
        idx = self.p.sessions[fi:fi + H + 1]
        sub = self.dkk.loc[idx, tickers]
        ok = sub.iloc[0].notna() & sub.iloc[-1].notna()
        tickers = [t for t in tickers if ok[t]]
        if not tickers:
            return None
        legs = sub[tickers] / sub[tickers].iloc[0]
        legs = legs.ffill()
        b = self.bench.loc[idx]
        v = legs.mean(axis=1)
        out = {"names": len(tickers), "acwi": float(b.iloc[-1] / b.iloc[0] - 1)}
        out |= self._stats(v, cost, "")
        xl, n_ex = [], 0
        for t in tickers:
            leg = legs[t]
            k = mpaths.exit_session(idx, self.below[t], lambda d, t=t: d in self.month_ends
                                    and bool(self.signal_below(d, tilt).get(t, False)))
            if k is not None:
                n_ex += 1
                leg = mpaths.park(leg, idx[k], b, cost)
            xl.append(leg)
        vx = pd.concat(xl, axis=1).mean(axis=1)
        out |= self._stats(vx, cost, "x_") | {"x_exits": n_ex}
        return out

    @staticmethod
    def _stats(v: pd.Series, cost: float, prefix: str) -> dict:
        w20 = (v / v.shift(20) - 1).dropna()
        gross = float(v.iloc[-1] - 1)
        return {prefix + "gross": gross, prefix + "net": float(v.iloc[-1] * (1 - cost) ** 2 - 1),
                prefix + "max_dd": float(min((v / v.cummax() - 1).min(), 0.0)),
                prefix + "worst20": float(w20.min()) if len(w20) else None}


def run(market, tilts=propose.TILTS, ns=None, horizons=None, since=None, with_regime: bool = True,
        log=lambda *_: None, p: mp.Panels | None = None) -> dict:
    c = propose.cfg()
    bt = settings().get("backtest") or {}
    ns = list(ns or c["study_ns"])
    horizons = list(horizons or c["horizons"])
    for h in horizons:
        if h not in study.HORIZONS:
            raise ValueError(f"horizons are months among {', '.join(map(str, study.HORIZONS))}")
    unknown = [t for t in tilts if t not in propose.TILTS]
    if unknown:
        raise ValueError(f"unknown tilt(s): {', '.join(unknown)}")
    fill = bt.get("fill", "next")
    holdout = pd.Timestamp(bt["study_holdout_from"]) if bt.get("study_holdout_from") else None
    min_names = int(bt.get("study_min_names", 30))
    p = p or mp.panels(market)
    needs_fund = any(c["tilts"][t].get("qv", 0) > 0 for t in tilts)
    if needs_fund and p.fund is None:
        from .fund import FundPIT

        p.fund = FundPIT(market)
        if not p.fund.names:
            log("no SEC EDGAR statements stored: the value and mix tilts are skipped")
            tilts = [t for t in tilts if c["tilts"][t].get("qv", 0) == 0]
    acwi = universe.acwi_weights(offline=True)
    ccy = universe.currencies(list(p.closes.columns))
    meta = pd.DataFrame({"sector": p.sector.replace("", "?").fillna("?"), "region": p.group.fillna("?"),
                         "currency": pd.Series({t: ("GBP" if ccy.get(t) == "GBp" else ccy.get(t) or "?")
                                                for t in p.closes.columns})}).reindex(p.closes.columns)
    W = p.dkk.resample("W-FRI").last().pct_change(fill_method=None)
    paths = Paths(p, settings()["stops"]["trend_sma"], c)
    cost = c["study_cost_bps"] / 1e4
    ctx = None
    if with_regime:
        from .pit import Context

        ctx = Context.build(market, set())
    vols = p.volumes.reindex(columns=p.dkk.columns) if p.volumes is not None else None
    recs = {t: {n: {h: [] for h in horizons} for n in ns} for t in tilts}
    tops = {t: {n: [] for n in ns} for t in tilts}
    short = {t: {n: 0 for n in ns} for t in tilts}
    ics = {t: [] for t in tilts}
    dates_out = []
    for day in mp.formation_dates(p.sessions, since):
        fi = mp.fill_session(p.sessions, day, fill)
        if fi is None:
            continue
        df0 = mp.ranked(p, day).set_index("ticker")
        if df0["score"].notna().sum() < min_names:
            continue
        tick = list(df0.index)
        df0["history"] = p.m["history"].loc[day].reindex(tick)
        dk = p.dkk.loc[:day].iloc[-20:]
        df0["adv_dkk"] = (vols.loc[:day].iloc[-20:] * dk).mean().reindex(tick) if vols is not None else np.nan
        df0["last_bar"] = day
        df0["price_dkk"] = p.dkk.loc[day].reindex(tick)
        tbl = p.fund.table(day) if needs_fund and p.fund is not None else pd.DataFrame()
        for k in ("qv", "quality", "value"):
            df0[k] = tbl[k].reindex(tick).astype(float) if k in tbl else np.nan
        rg = ctx.regime(day)["label"] if ctx is not None else None
        Wd = W.loc[:day].iloc[-52:]
        rec = {"date": day.date().isoformat(), "fill": p.sessions[fi].date().isoformat(), "regime": rg, "picks": {}}
        y6 = study.forward(p, fi, study.HORIZONS[6])
        for tilt in tilts:
            needs_qv = c["tilts"][tilt].get("qv", 0) > 0
            if needs_qv and not df0["qv"].notna().any():
                continue
            kept, _ = propose.gates(df0, tilt, c["min_ticket_dkk"], c, day)
            kept = propose.annotate(kept, meta)
            sc = propose.score(kept, tilt, c, None)
            if len(sc) < max(ns) * 2:
                continue
            if y6 is not None:
                cs = study.cross_section(sc["composite"], y6, 15, min(min_names, len(sc)))
                if cs and cs.get("ic") is not None:
                    ics[tilt].append({"date": day, "ic": cs["ic"]})
            base = propose.Base({}, pd.DataFrame(columns=list(propose.DIMS)), acwi, {},
                                Wd.reindex(columns=list(sc.index[:80])))
            rec["picks"][tilt] = {}
            for n in ns:
                chosen, _ = propose.select(sc, n, n * c["min_ticket_dkk"], base, c)
                if len(chosen) < n:
                    short[tilt][n] += 1
                    continue
                names = [x["ticker"] for x in chosen]
                tops[tilt][n].append(set(names))
                rec["picks"][tilt][str(n)] = names
                for h in horizons:
                    H = study.HORIZONS[h]
                    if fi + H >= len(p.sessions):
                        continue
                    r = paths.run(names, fi, H, tilt, cost)
                    if r is None:
                        continue
                    r |= {"date": day, "regime": rg, "excess": r["net"] - r["acwi"],
                          "excess_gross": r["gross"] - r["acwi"], "x_excess": r["x_net"] - r["acwi"],
                          "x_excess_gross": r["x_gross"] - r["acwi"]}
                    recs[tilt][n][h].append(r)
        dates_out.append(rec)
        if len(dates_out) % 12 == 0:
            log(f"{len(dates_out)} formation dates, at {rec['date']}")
    if not dates_out:
        raise ValueError(f"no formation date with {min_names} ranked names: not enough price history yet")
    log(f"{len(dates_out)} formation dates, {dates_out[0]['date']} to {dates_out[-1]['date']}")
    results = {t: {str(n): {str(h): {"kept": split(recs[t][n][h], h, "", holdout),
                                     "exits": split(recs[t][n][h], h, "x_", holdout)}
                            for h in horizons} for n in ns} for t in tilts}
    turnover = {t: {str(n): study.turnover(tops[t][n]) for n in ns} for t in tilts}
    return {
        "generated": pd.Timestamp.now().isoformat(timespec="seconds"), "asof": p.sessions[-1].date().isoformat(),
        "settings_hash": propose.rule_hash(c), "settings": {k: c.get(k) for k in propose.RULE_KEYS},
        "fill": fill, "holdout_from": holdout.date().isoformat() if holdout is not None else None,
        "cost_bps": c["study_cost_bps"],
        "universe": {"tickers": int(len(p.closes.columns)), "first": dates_out[0]["date"],
                     "last": dates_out[-1]["date"], "dates": len(dates_out),
                     "fund_names": len(p.fund.names) if p.fund is not None else None},
        "us_only": {t: c["tilts"][t].get("qv", 0) > 0 for t in tilts},
        "acwi_weights": "today's" if acwi else None,
        "results": results,
        "ic": {t: {"dates": len(v), "mean": _m([x["ic"] for x in v]), "t": study.nw_t([x["ic"] for x in v], 5)}
               for t, v in ics.items()},
        "turnover": turnover,
        "annual_cost_if_repicked_monthly": {t: {n: (v * 12 * 2 * cost if v is not None else None) for n, v in d.items()}
                                            for t, d in turnover.items()},
        "shortfall": {t: {str(n): v for n, v in d.items()} for t, d in short.items()},
        "dates": dates_out,
        "caveats": CAVEATS,
    }


def write(rep: dict) -> str:
    return str(artifacts.write("propose-study", rep, data_asof=rep["asof"], rule_hash=rep["settings_hash"],
                               default=study._json))
