"""How well the momentum score ranked stocks on past days, judged on the returns that followed: the evidence for
(or against) the score, and a fair test of variants that might improve it. `radar study score` writes
reports/score-study.json.

- **Formation dates**: the last session of each completed month on the benchmark calendar. On each date D the
  score and every variant are computed from prices up to D only (momentum.metrics_panel, row D, as pit.py).
- **Forward return** over H ∈ {1, 3, 6, 12} months (21/63/126/252 sessions): adjusted close from the fill session
  (`backtest.fill`: the session after D, or D itself) to H sessions later, in the listing's currency. It is
  judged as **excess over the equal-weight universe** on the same date, so a market that rose or fell for every
  stock doesn't count for or against the score. A name without a forward return is left out and counted, never
  counted as 0. Top-N baskets are also given in DKK against ACWI in DKK.
- **Per date and horizon**: Spearman rank correlation (IC) between the variant and the forward return, the
  mean excess return per quintile, the top-quintile minus bottom-quintile spread, and the top N's excess return
  and hit rate (the share that beat the universe). A date needs `backtest.study_min_names` ranked names.
- **Across dates**: means with Newey-West t-statistics (lag H−1 months: monthly dates with longer horizons
  overlap, so neighbouring months are not independent), the share of dates with IC > 0, splits by year, by
  regime on D (pit.Context.regime), by stock group, and in-sample against the holdout
  (`backtest.study_holdout_from` on).
- **Variants**: the score's components alone and a few published alternatives (VARIANTS). The production score
  is the baseline. A variant counts as an improvement only when it beats the baseline in-sample **and** in the
  holdout, with a holdout IC t-statistic above 2; the report says how many were tried, since some will look
  better by chance.
- **The exit rule over many dates** (`exits=H`): each date's top-N basket (production score, equal weights,
  fees) held for H against the same buys with the stop/take-profit rule (both halves, stop only, take-profit
  only; backtest/exits.py, rule exits parked in ACWI), in DKK.
- **Redeploy instead of parking** (`radar study redeploy`, redeploy_study): the same baskets with the exit money
  buying the best-scoring name not held (Picker: trend filter, optional sector/group caps, a cool-down), with and
  without a month-end rotation out of names that fell outside a rank buffer, judged on return and risk-adjusted
  return (Sharpe and Sortino over the ECB deposit rate, Calmar, information ratio against ACWI).

What it can't fix: the universe is today's (S&P 500 constituents and curated lists), so names that left it are
missing; that flatters momentum, whose winners are the ones that get added. Sectors are today's (the
sector-neutral variant says so). Adjusted prices are rewritten after each dividend, which moves levels but
barely moves returns."""
from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .. import universe
from ..config import settings
from ..paths import REPORTS
from ..signals import momentum

HORIZONS = {1: 21, 3: 63, 6: 126, 12: 252}      # months -> sessions
QUANTILES = 5
GROUP_MIN = 10                                   # names a stock group needs on a date for its own IC
SECTOR_MIN = 5                                   # names a sector needs for the sector-neutral variant
REPORT_FILE = "score-study.json"
BASELINE = "score"
COMPONENTS = ("r12_1", "r6m", "r3m")


@dataclass
class Panels:
    closes: pd.DataFrame                         # adjusted closes of the stock universe (listing currency)
    dkk: pd.DataFrame                            # the same in DKK (a column is NaN without a known rate)
    m: dict[str, pd.DataFrame]                   # momentum.metrics_panel
    vol: pd.DataFrame                            # 63-session realised volatility, annualised
    group: pd.Series                             # ticker -> stock group
    sector: pd.Series                            # ticker -> today's Yahoo sector ("" unknown)
    sessions: pd.DatetimeIndex                   # benchmark calendar
    bench_dkk: pd.Series
    volumes: pd.DataFrame | None = None          # traded volume (gaps forward-filled, as ingest.wide)


def panels(market, tickers: list[str] | None = None) -> Panels:
    groups = universe.stock_groups(offline=True)
    group: dict[str, str] = {}
    for g, ts in groups.items():
        for t in ts:
            group.setdefault(t, g)
    stocks = sorted(t for t in (tickers or group) if t in market.closes.columns)
    c = market.closes[stocks]
    m = momentum.metrics_panel(market.closes, stocks, settings()["momentum"]["min_history_days"])
    vol = np.log(c).diff().rolling(63, min_periods=32).std() * math.sqrt(252)
    ccy = universe.currencies(stocks)
    fx_cache: dict = {}
    dkk = {}
    for t in stocks:
        k = ccy.get(t)
        if k not in fx_cache:
            fx_cache[k] = universe.fx_to_dkk(market.closes, k)
        fx = fx_cache[k]
        dkk[t] = c[t] * fx.reindex(c.index) if fx is not None else pd.Series(np.nan, index=c.index)
    from .. import performance

    sec = universe.sectors(stocks)["sector"].astype(str)
    return Panels(c, pd.DataFrame(dkk, index=c.index), m, vol, pd.Series(group).reindex(stocks), sec,
                  market.closes[universe.benchmark()].dropna().index, performance.bench_dkk(market),
                  market.volumes.reindex(columns=stocks) if getattr(market, "volumes", None) is not None else None)


# ---------------- the variants: higher = stronger, from data up to D ----------------

def pct(df: pd.DataFrame) -> pd.Series:
    """Mean percentile (0-100) of each column against the names given, as mine._pct_vs: the share of names
    strictly below; missing if any column is missing."""
    cols = [(df[c].rank(method="min") - 1) / df[c].notna().sum() for c in df.columns]
    return pd.concat(cols, axis=1).mean(axis=1, skipna=False) * 100


def _within(keys: pd.Series, df: pd.DataFrame, min_names: int = 2) -> pd.Series:
    out = pd.Series(np.nan, index=df.index)
    for _, idx in keys.reindex(df.index).groupby(keys.reindex(df.index)).groups.items():
        sub = df.loc[idx]
        if sub.dropna().shape[0] >= min_names:
            out.loc[idx] = pct(sub)
    return out


def _row(p: Panels, col: str, day) -> pd.Series:
    return p.m[col].loc[day]


def _comp(p: Panels, day) -> pd.DataFrame:
    return pd.DataFrame({c: _row(p, c, day) for c in COMPONENTS})


def _score(p, day):
    return pct(_comp(p, day))


def _score_trend(p, day):
    s, ok = _score(p, day), _row(p, "trend_ok", day)
    return s.where(ok.eq(True), s - 100).where(ok.notna())


def _score_vol(p, day):
    v = p.vol.loc[day].where(lambda x: x > 0)
    return pct(_comp(p, day).div(v, axis=0))


def _at(df: pd.DataFrame, day, back: int) -> pd.Series:
    """Row `back` sessions before D on the frame's own calendar (NaN when the history is shorter)."""
    i = int(df.index.searchsorted(day, side="right")) - 1
    return df.iloc[i - back] if i >= back else pd.Series(np.nan, index=df.columns)


def _score_skip(p, day):
    """The score with the latest month skipped in all three components: 12-1, 6-1 and 3-1 months."""
    c = p.closes
    m1 = _at(c, day, 21)
    return pct(pd.DataFrame({"r12_1": _row(p, "r12_1", day), "r6_1": m1 / _at(c, day, 126) - 1,
                             "r3_1": m1 / _at(c, day, 63) - 1}))


BETA_WEEKS, BETA_MIN_WEEKS = 104, 52


def _resid(p, day):
    """Residual momentum (after Blitz, Huij & Martens 2011), on one market factor: each stock's beta to ACWI from
    weekly DKK returns over up to two years to D; its eleven monthly returns of the 12-1 window less beta × ACWI's,
    summed and divided by their standard deviation. Beta-adjusted rather than alpha-removed: with only a year or
    two of history an intercept would absorb most of the window being measured."""
    c = p.dkk.loc[:day]
    b = p.bench_dkk.reindex(c.index).ffill()
    wc = c.resample("W-FRI").last().pct_change(fill_method=None).iloc[-BETA_WEEKS:]
    wb = b.resample("W-FRI").last().pct_change(fill_method=None).iloc[-BETA_WEEKS:]
    ok = wc.notna() & wb.notna().to_numpy()[:, None]
    n = ok.sum()
    B = pd.DataFrame(np.repeat(wb.to_numpy()[:, None], wc.shape[1], 1), index=wc.index, columns=wc.columns).where(ok)
    C = wc.where(ok)
    cov = ((B - B.mean()) * (C - C.mean())).sum() / (n - 1)
    beta = (cov / B.var()).where(n >= BETA_MIN_WEEKS)
    pts = [(_at(c, day, k), b.iloc[len(b) - 1 - k] if len(b) > k else np.nan) for k in range(252, 20, -21)]
    e = pd.DataFrame({i: (s1 / s0 - 1) - beta * (b1 / b0 - 1)
                      for i, ((s0, b0), (s1, b1)) in enumerate(zip(pts, pts[1:]))})
    sd = e.std(axis=1).where(lambda x: x > 0)
    return (e.sum(axis=1, skipna=False) / sd).where(_row(p, "r12_1", day).notna())


def _fip(p, day):
    """Frog in the pan (Da, Gurun & Warachka 2014): −sign(12-1 return) × (share of down days − share of up days)
    over the 12-1 window, so a return made of many small moves ranks above the same return made in a few jumps.
    Sessions without a move (holidays, forward-filled gaps) count as neither."""
    i = int(p.closes.index.searchsorted(day, side="right"))       # one past D
    if i < 253:
        return pd.Series(np.nan, index=p.closes.columns)
    d = p.closes.iloc[i - 253:i - 21].pct_change(fill_method=None).iloc[1:]     # closes D-252 .. D-21
    n = d.notna().sum().where(lambda x: x > 0)
    info = np.sign(_row(p, "r12_1", day)) * ((d < 0).sum() / n - (d > 0).sum() / n)
    return -info


def _score_fip(p, day):
    """Score blended 2:1 with frog in the pan (both as percentiles)."""
    return (2 * _score(p, day) + pct(_fip(p, day).to_frame("fip"))) / 3


def _vol_surge(p, day):
    """20-session mean volume over the 120-session mean (the Momentum page's column), as of D."""
    if p.volumes is None:
        return pd.Series(np.nan, index=p.closes.columns)
    v = p.volumes.reindex(columns=p.closes.columns).loc[:day]
    if len(v) < 120:
        return pd.Series(np.nan, index=p.closes.columns)
    return v.iloc[-20:].mean() / v.iloc[-120:].mean().where(lambda x: x > 0)


@dataclass(frozen=True)
class Variant:
    key: str
    label: str
    fn: Callable
    pit: bool = True
    note: str = ""


VARIANTS = [
    Variant("score", "Momentum score (pooled, as on My holdings)", _score,
            note="mean percentile of 12-1, 6- and 3-month returns against every stock"),
    Variant("score_region", "Score ranked within each region (as on the Momentum page)",
            lambda p, d: _within(p.group, _comp(p, d))),
    Variant("r12_1", "12-1-month return alone", lambda p, d: _row(p, "r12_1", d)),
    Variant("r6m", "6-month return alone", lambda p, d: _row(p, "r6m", d)),
    Variant("r3m", "3-month return alone", lambda p, d: _row(p, "r3m", d)),
    Variant("r1m", "1-month return alone", lambda p, d: _row(p, "r1m", d),
            note="short-term reversal check: a negative IC means last month's winners tend to give back"),
    Variant("score_trend", "Score, uptrend first", _score_trend,
            note="names above a rising 200-day average rank ahead of the rest, by score within each half"),
    Variant("score_vol", "Volatility-adjusted score", _score_vol,
            note="each return divided by its 63-session volatility before ranking"),
    Variant("from_high", "Nearness to the 52-week high", lambda p, d: _row(p, "from_high", d)),
    Variant("score_sector", "Score ranked within each sector", lambda p, d: _within(p.sector.replace("", np.nan), _comp(p, d), SECTOR_MIN),
            pit=False, note="uses today's sectors (not known as of D)"),
    Variant("score_skip", "Score with the latest month skipped in every component", _score_skip,
            note="12-1, 6-1 and 3-1 months: keeps last month's short-term reversal out of the 6- and 3-month parts"),
    Variant("resid", "Residual momentum (beta to ACWI removed)", _resid,
            note="12-1-month return less beta × ACWI's, month by month in DKK, divided by its own volatility"),
    Variant("fip", "Frog in the pan (smooth path)", _fip,
            note="the share of up days minus down days in the 12-1 window, signed by its return"),
    Variant("score_fip", "Score blended 2:1 with frog in the pan", _score_fip),
    Variant("vol_surge", "Volume surge (20 vs 120 sessions) alone", _vol_surge,
            note="the Momentum page's column; a negative IC means high recent volume precedes weaker returns"),
]
BY_KEY = {v.key: v for v in VARIANTS}


# ---------------- statistics ----------------

def nw_t(values, lag: int) -> float | None:
    """The mean's t-statistic with Newey-West (Bartlett) standard errors; None with fewer than 3 values."""
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)], dtype=float)
    n = len(v)
    if n < 3:
        return None
    e = v - v.mean()
    s = float(e @ e) / n
    for k in range(1, min(lag, n - 1) + 1):
        s += 2 * (1 - k / (lag + 1)) * float(e[k:] @ e[:-k]) / n
    if s <= 0:
        return None
    return float(v.mean() / math.sqrt(s / n))


def cross_section(x: pd.Series, y: pd.Series, n_top: int, min_names: int, y_dkk: pd.Series | None = None) -> dict | None:
    """One date: IC, quintile excess returns, spread and the top N, over the names with both a value and a
    forward return. None with fewer than `min_names`."""
    d = pd.concat({"x": x, "y": y}, axis=1).dropna()
    if len(d) < max(min_names, QUANTILES):
        return None
    ex = d["y"] - d["y"].mean()
    ic = d["x"].rank().corr(d["y"].rank())
    q = pd.qcut(d["x"].rank(method="first"), QUANTILES, labels=False)
    qm = ex.groupby(q).mean().reindex(range(QUANTILES))
    top = d["x"].sort_values(ascending=False, kind="stable").index[:n_top]
    out = {"n": int(len(d)), "ic": None if pd.isna(ic) else float(ic), "q": [float(v) for v in qm],
           "spread": float(qm.iloc[-1] - qm.iloc[0]), "top_excess": float(ex[top].mean()),
           "top_hit": float((ex[top] > 0).mean()), "ew": float(d["y"].mean()), "top": list(top)}
    if y_dkk is not None:
        t = y_dkk.reindex(top).dropna()
        out["top_dkk"] = float(t.mean()) if len(t) else None
    return out


def _mean(v):
    v = [x for x in v if x is not None and np.isfinite(x)]
    return float(np.mean(v)) if v else None


def summarize(rows: list[dict], lag: int) -> dict | None:
    """Across dates: means, Newey-West t-statistics and shares."""
    rows = [r for r in rows if r is not None]
    if not rows:
        return None
    ics = [r["ic"] for r in rows]
    q = [_mean([r["q"][i] for r in rows]) for i in range(QUANTILES)]
    top_dkk = [r.get("top_dkk") for r in rows]
    acwi = [r.get("acwi_dkk") for r in rows]
    beat = [a < b for a, b in zip(acwi, top_dkk) if a is not None and b is not None]
    return {
        "dates": len(rows), "n_mean": _mean([r["n"] for r in rows]),
        "ic_mean": _mean(ics), "ic_t": nw_t(ics, lag), "ic_pos": _mean([float(i > 0) for i in ics if i is not None]),
        "q": q, "spread": _mean([r["spread"] for r in rows]), "spread_t": nw_t([r["spread"] for r in rows], lag),
        "monotone": all(a is not None and b is not None and a < b for a, b in zip(q, q[1:])),
        "top_excess": _mean([r["top_excess"] for r in rows]), "top_excess_t": nw_t([r["top_excess"] for r in rows], lag),
        "top_hit": _mean([r["top_hit"] for r in rows]),
        "top_dkk": _mean(top_dkk), "acwi_dkk": _mean(acwi), "top_beats_acwi": _mean([float(b) for b in beat]),
    }


def turnover(tops: list[set]) -> float | None:
    """Mean share of the top quintile replaced from one date to the next."""
    v = [1 - len(a & b) / len(b) for a, b in zip(tops, tops[1:]) if b]
    return _mean(v)


# ---------------- the study ----------------

def formation_dates(sessions: pd.DatetimeIndex, since=None) -> list[pd.Timestamp]:
    s = sessions.to_series()
    me = s.groupby(sessions.to_period("M")).max()
    me = me[me.index < sessions[-1].to_period("M")]           # the current month isn't over
    out = [pd.Timestamp(d) for d in me]
    return [d for d in out if since is None or d >= pd.Timestamp(since)]


def fill_session(sessions: pd.DatetimeIndex, day: pd.Timestamp, fill: str) -> int | None:
    i = int(sessions.searchsorted(day))
    if i >= len(sessions) or sessions[i] != day:
        i -= 1
    i += 1 if fill == "next" else 0
    return i if 0 <= i < len(sessions) else None


def forward(p: Panels, fi: int, h: int, dkk: bool = False) -> pd.Series | None:
    """Forward returns from session `fi` over `h` sessions (None when that end is beyond the data)."""
    if fi + h >= len(p.sessions):
        return None
    f, e = p.sessions[fi], p.sessions[fi + h]
    c = p.dkk if dkk else p.closes
    return c.loc[e] / c.loc[f] - 1


def run(market, horizons=(1, 3, 6, 12), variants: list[str] | None = None, n_top: int = 15, exits: int | None = None,
        seasoned: bool = False, since=None, with_regime: bool = True, log=lambda *_: None, p: Panels | None = None) -> dict:
    cfg = settings()
    bt = cfg.get("backtest") or {}
    min_names = int(bt.get("study_min_names", 30))
    fill = bt.get("fill", "next")
    holdout = pd.Timestamp(bt.get("study_holdout_from")) if bt.get("study_holdout_from") else None
    keys = variants or [v.key for v in VARIANTS]
    unknown = [k for k in keys if k not in BY_KEY]
    if unknown:
        raise ValueError(f"unknown variant(s): {', '.join(unknown)} (known: {', '.join(BY_KEY)})")
    if BASELINE not in keys:
        keys = [BASELINE, *keys]
    for h in horizons:
        if h not in HORIZONS:
            raise ValueError(f"horizons are months among {', '.join(map(str, HORIZONS))}")
    p = p or panels(market)
    log(f"{len(p.closes.columns)} stocks, {len(keys)} variants")
    ctx = None
    if with_regime or exits:
        from .pit import Context

        ctx = Context.build(market, set())
    per = {h: {k: [] for k in keys} for h in horizons}
    groups_res = {h: {k: {} for k in keys} for h in horizons}
    tops = {k: [] for k in keys}
    dates_out = []
    for day in formation_dates(p.sessions, since):
        fi = fill_session(p.sessions, day, fill)
        if fi is None:
            continue
        last = p.m["last"].loc[day]
        listed = last.notna()
        if seasoned:
            listed &= p.m["history"].loc[day] >= 252
        xs = {k: BY_KEY[k].fn(p, day).where(listed) for k in keys}
        base = xs[BASELINE]
        if base.notna().sum() < min_names:
            continue
        rg = ctx.regime(day)["label"] if ctx is not None and with_regime else None
        rec = {"date": day.date().isoformat(), "fill": p.sessions[fi].date().isoformat(), "regime": rg,
               "ranked": int(base.notna().sum()), "no_price": int((~last.notna()).sum()),
               "no_score": int((last.notna() & base.isna()).sum()), "horizons": {}}
        for k in keys:
            x = xs[k].dropna()
            tops[k].append(set(x.sort_values(ascending=False).index[: max(len(x) // QUANTILES, 1)]))
        for h in horizons:
            y = forward(p, fi, HORIZONS[h])
            if y is None:
                continue
            yd = forward(p, fi, HORIZONS[h], dkk=True)
            f, e = p.sessions[fi], p.sessions[fi + HORIZONS[h]]
            b = p.bench_dkk
            acwi = float(b.asof(e) / b.asof(f) - 1) if len(b) else None
            hrec = {"fwd_missing": int((base.notna() & y.isna()).sum()), "acwi_dkk": acwi, "ic": {}}
            for k in keys:
                cs = cross_section(xs[k], y, n_top, min_names, yd)
                if cs is None:
                    continue
                cs |= {"date": day, "regime": rg, "acwi_dkk": acwi}
                if k == BASELINE:
                    hrec["top"] = cs["top"]
                    hrec["top_dkk"] = cs.get("top_dkk")
                per[h][k].append(cs)
                hrec["ic"][k] = cs["ic"]
                for g in p.group.dropna().unique():
                    members = p.group.index[p.group == g]
                    gc = cross_section(xs[k].reindex(members), y.reindex(members), min(n_top, 5), GROUP_MIN)
                    if gc is not None:
                        groups_res[h][k].setdefault(g, []).append(gc)
            rec["horizons"][str(h)] = hrec
        dates_out.append(rec)
    if not dates_out:
        raise ValueError(f"no formation date with {min_names} ranked names: not enough price history yet")
    log(f"{len(dates_out)} formation dates, {dates_out[0]['date']} to {dates_out[-1]['date']}")

    results, verdicts, decay = {}, {}, {k: {} for k in keys}
    for h in horizons:
        lag = max(h - 1, 0)
        results[str(h)] = {}
        for k in keys:
            rows = per[h][k]
            res = {"all": summarize(rows, lag),
                   "in_sample": summarize([r for r in rows if holdout is None or r["date"] < holdout], lag),
                   "holdout": summarize([r for r in rows if holdout is not None and r["date"] >= holdout], lag),
                   "by_year": {str(y): summarize([r for r in rows if r["date"].year == y], lag)
                               for y in sorted({r["date"].year for r in rows})},
                   "by_regime": {str(g): summarize([r for r in rows if r["regime"] == g], lag)
                                 for g in sorted({r["regime"] for r in rows}, key=str)},
                   "by_group": {g: summarize(v, lag) for g, v in groups_res[h][k].items()}}
            results[str(h)][k] = res
            decay[k][str(h)] = (res["all"] or {}).get("ic_mean")
        base = results[str(h)][BASELINE]
        verdicts[str(h)] = {k: _verdict(results[str(h)][k], base, _diff_t(per[h][k], per[h][BASELINE], holdout, lag))
                            for k in keys if k != BASELINE}

    out = {
        "generated": pd.Timestamp.now().isoformat(timespec="seconds"), "asof": p.sessions[-1].date().isoformat(),
        "settings": {"n_top": n_top, "min_names": min_names, "fill": fill, "seasoned": seasoned,
                     "holdout_from": holdout.date().isoformat() if holdout is not None else None,
                     "horizons": {str(h): HORIZONS[h] for h in horizons}, "fee_bps": float(bt.get("fee_bps", 0))},
        "universe": {"tickers": int(len(p.closes.columns)),
                     "groups": {g: int((p.group == g).sum()) for g in p.group.dropna().unique()},
                     "first": dates_out[0]["date"], "last": dates_out[-1]["date"]},
        "variants": [{"key": k, "label": BY_KEY[k].label, "pit": BY_KEY[k].pit, "note": BY_KEY[k].note,
                      "baseline": k == BASELINE} for k in keys],
        "variants_tried": len(keys) - 1,
        "results": results, "verdicts": verdicts, "decay": decay,
        "turnover": {k: turnover(tops[k]) for k in keys},
        "dates": dates_out,
        "exits": exit_study(market, p, ctx, dates_out, exits, n_top, log) if exits else None,
        "caveats": CAVEATS,
    }
    return out


CAVEATS = [
    "Survivorship: the universe is today's (S&P 500 constituents from SPY and the curated lists). Names that left "
    "it are missing, and stocks that joined after strong runs are in it, which flatters momentum most.",
    "Sectors are today's, so the sector-neutral variant isn't strictly as of D.",
    "Adjusted prices are rewritten after each dividend or split; that moves price levels, barely returns.",
    "Monthly dates with horizons longer than a month overlap: the t-statistics use Newey-West errors for that, "
    "but the number of independent periods is still small (about one per horizon).",
    "Several variants are tried: a few will look better by chance. Only an improvement that holds in the holdout "
    "too counts, and even then it is a candidate for a decision, not a change.",
    "Costs and taxes: the basket returns are before tax; the exit-rule comparison charges backtest.fee_bps per "
    "trade, and realised gains would be taxed differently in frie midler and an aktiesparekonto.",
]


def _diff_t(rows: list[dict], base: list[dict], holdout, lag: int) -> float | None:
    """Newey-West t of the holdout's per-date IC difference (variant − baseline), on the dates both have."""
    b = {r["date"]: r["ic"] for r in base if holdout is not None and r["date"] >= holdout}
    d = [r["ic"] - b[r["date"]] for r in rows if r["date"] in b and r["ic"] is not None and b[r["date"]] is not None]
    return nw_t(d, lag)


def _verdict(res: dict, base: dict, diff_t: float | None = None) -> dict:
    """Better than the baseline only when it is so in-sample and in the holdout, with a holdout IC t above 2; a
    holdout difference whose own t is below 2 is called small (it may still be chance)."""
    def ic(r, part):
        return ((r or {}).get(part) or {}).get("ic_mean")
    i, o, bi, bo = ic(res, "in_sample"), ic(res, "holdout"), ic(base, "in_sample"), ic(base, "holdout")
    t = ((res or {}).get("holdout") or {}).get("ic_t")
    if None in (i, o, bi, bo):
        label = "not enough data"
    elif i > bi and o > bo and t is not None and t > 2:
        label = "candidate improvement" if diff_t is not None and diff_t > 2 else "candidate, but the difference is small"
    elif i > bi and o <= bo:
        label = "better in-sample only (likely chance)"
    elif o > bo:
        label = "better in the holdout only"
    else:
        label = "not better"
    return {"label": label, "in_sample_ic": i, "holdout_ic": o, "baseline_in_sample_ic": bi,
            "baseline_holdout_ic": bo, "holdout_ic_t": t, "holdout_diff_t": diff_t}


# ---------------- the exit rule across dates ----------------

def exit_study(market, p: Panels, ctx, dates: list[dict], months: int, n_top: int, log) -> dict:
    """Each date's top-N basket (production score, equal weights) held for `months` against the same buys with the
    rule (both halves, stop only, take-profit only), in DKK, fees included."""
    from .. import performance
    from . import exits as ex
    from . import picks

    if months not in HORIZONS:
        raise ValueError(f"the exit study horizon must be one of {', '.join(map(str, HORIZONS))} months")
    h = HORIZONS[months]
    bt = settings().get("backtest") or {}
    fee = float(bt.get("fee_bps", 0))
    park = bt.get("park") or universe.benchmark()
    capital = 100_000.0
    baskets = []
    for d in dates:
        day = pd.Timestamp(d["date"])
        fi = int(p.sessions.searchsorted(pd.Timestamp(d["fill"])))
        if fi + h >= len(p.sessions):
            continue
        baskets.append((d["date"], fi, top_names(p, day, n_top)))
    if not baskets:
        return {"months": months, "dates": [], "summary": None, "note": "no date with a complete horizon"}
    held = {t for _, _, b in baskets for t in b} | {park}
    from .pit import Context

    ctx = fast(Context.build(market, held), p)
    rows_out = []
    missing: dict[str, int] = {}
    rule_days = 0
    for i, (ds, fi, tickers) in enumerate(baskets):
        f, e = p.sessions[fi], p.sessions[fi + h]
        rows, problems = picks.basket_rows(market, {t: 1 / len(tickers) for t in tickers}, f, capital, fee)
        if not rows:
            continue
        rec = {"date": ds, "fill": f.date().isoformat(), "end": e.date().isoformat(), "skipped": problems}
        rec["hold"] = _value_return(rows, market, e, capital)
        for rule in ex.RULES:
            rep = ex.replay(rows, ctx, "rules", end=e, rule=rule, fee_bps=fee)
            rec[rule] = _value_return(rep["rows"], market, e, capital)
            rec[f"{rule}_exits"] = len(rep["exits"])
            if rule == "both":
                c = rep["counts"]
                rule_days += c["rule_days"]
                for k, n in c["missing"].items():
                    missing[k] = missing.get(k, 0) + n
        b = performance.bench_dkk(market)
        rec["acwi"] = float(b.asof(e) / b.asof(f) - 1)
        rows_out.append(rec)
        if (i + 1) % 12 == 0:
            log(f"exit rule: {i + 1} of {len(baskets)} dates")
    lag = max(months - 1, 0)
    summ = {}
    for rule in ex.RULES:
        diff = [r[rule] - r["hold"] for r in rows_out if r.get(rule) is not None and r.get("hold") is not None]
        summ[rule] = {"dates": len(diff), "mean_diff": _mean(diff), "t": nw_t(diff, lag),
                      "helped": _mean([float(x > 0) for x in diff]), "worst": min(diff) if diff else None,
                      "best": max(diff) if diff else None,
                      "exits_mean": _mean([r[f"{rule}_exits"] for r in rows_out])}
    summ["hold"] = {"mean": _mean([r["hold"] for r in rows_out]),
                    "beats_acwi": _mean([float(r["hold"] > r["acwi"]) for r in rows_out if r.get("hold") is not None]),
                    "acwi_mean": _mean([r["acwi"] for r in rows_out])}
    return {"months": months, "n_top": n_top, "fee_bps": fee, "park": park, "dates": rows_out, "summary": summ,
            "inputs_missing": {k: n / rule_days for k, n in missing.items()} if rule_days else {},
            "note": "the rule as it would have been set then: inputs that didn't exist yet (analyst data before "
                    "fetching began) move nothing, so for early dates it isn't quite today's rule"}


def top_names(p: Panels, day: pd.Timestamp, n: int) -> list[str]:
    """The `n` best by score on `day` among names with a price and a DKK rate (so they can be bought)."""
    ok = p.m["last"].loc[day].notna() & p.dkk.loc[day].notna()
    x = _score(p, day).where(ok).dropna()
    return list(x.sort_values(ascending=False, kind="stable").index[:n])


def fast(ctx, p: Panels):
    """The same answers, faster: the score for every stock at once per day (as Context.score, one name at a time),
    and each (stops variant, name, day, anchor)'s levels computed once, however many replays ask."""
    day_scores: dict = {}

    def score(t, d):
        if d not in day_scores:
            day_scores[d] = _score(p, d).round(1)
        v = day_scores[d].get(t)
        return None if v is None or pd.isna(v) else float(v)
    levels_at, cached = ctx.levels, {}

    def levels(t, d, anchor, stops=None):
        k = (tuple(sorted(stops.items())) if stops else (), t, d, anchor)
        if k not in cached:
            cached[k] = levels_at(t, d, anchor, stops)
        return cached[k]
    ctx.score, ctx.levels = score, levels
    return ctx


def _value_return(rows: list[dict], market, end: pd.Timestamp, capital: float) -> float | None:
    from .. import performance

    rows = [dict(r, fee=r.get("fee") or 0.0, currency="DKK" if r["type"] not in ("BUY", "SELL") else None) for r in rows]
    b = performance.book(rows, market)
    if b is None:
        return None
    v = b.value.loc[:end].dropna()
    if not len(v) or v.index[-1] != end:
        return None
    ext = float((b.inflow - b.outflow).loc[:end].sum())
    return float(v.iloc[-1] / ext - 1) if ext > 0 else None


def write(rep: dict) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    f = REPORTS / REPORT_FILE
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(rep, indent=1, default=_json), encoding="utf-8")
    tmp.replace(f)


def _json(v):
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat()
    if isinstance(v, set):
        return sorted(v)
    if hasattr(v, "item"):
        return v.item()
    return str(v)


# ---------------- variants of the exit rule: return and risk ----------------

def _exit_variants():
    from .exits import RuleSpec as R

    wide4 = (("k_base", 4.0), ("k_min", 3.0), ("k_max", 5.0))
    return [
        R(),
        R("atr-tp", "ATR stop with take-profit (the rule until 2026-10)"),
        R("tp-off", "ATR stop, take-profit off", tp="off"),
        R("tp-off-noext", "TP off, no tightening when extended", (("extended_vs_sma50", None),), tp="off"),
        R("k4", "TP off, k 4 (3-5)", wide4, tp="off"),
        R("k5", "TP off, k 5 (4-6)", (("k_base", 5.0), ("k_min", 4.0), ("k_max", 6.0)), tp="off"),
        R("atr63-k4", "TP off, ATR over 63 days, k 4 (3-5)", (("atr_days", 63),) + wide4, tp="off"),
        R("trail20", "20 % trail from the high", tp="off", stop="pct", pct=0.20),
        R("trail30", "30 % trail from the high", tp="off", stop="pct", pct=0.30),
        R("sma200", "Close below the 200-day average", tp="off", stop="trend", sma=200),
        R("sma100", "Close below the 100-day average", tp="off", stop="trend", sma=100),
    ]


EXIT_HORIZONS = (3, 6)
COST_PER_6M = 0.02            # a variant may cost at most this much return per 6 months against holding
DD_CUT = 0.25                 # ... and must cut the mean max drawdown by at least this share
FIRST_CANDIDATE = 4           # variants from this index on are candidates for the re-entry run
MIXES = (0.75, 0.5)           # no exit rule: the basket at this weight, the rest in ACWI from the start (sizing)


def path(rows: list[dict], market, start: pd.Timestamp, end: pd.Timestamp, bench: pd.Series | None = None,
         rf: pd.Series | None = None) -> dict | None:
    """Return, max drawdown, volatility and worst 20-session return of a run's value from `start` to `end`, per DKK
    put in (the first day's buying fees included). None when the value at the end is unknown. With `rf` (a daily
    return series): Sharpe and Sortino of the daily returns over it, annualised; with `bench` (ACWI in DKK): the
    information ratio and tracking error against it. Calmar is the annualised return over the max drawdown."""
    from .. import performance

    rows = [dict(r, fee=r.get("fee") or 0.0, currency="DKK" if r["type"] not in ("BUY", "SELL") else None) for r in rows]
    b = performance.book(rows, market)
    if b is None:
        return None
    v = b.value.loc[start:end].dropna()
    if not len(v) or v.index[-1] != end:
        return None
    ext = float((b.inflow - b.outflow).loc[:end].sum())
    if ext <= 0:
        return None
    idx = v / ext
    r = idx.pct_change().dropna()
    w20 = (idx / idx.shift(20) - 1).dropna()
    out = {"ret": float(idx.iloc[-1] - 1), "max_dd": float(min((idx / idx.cummax() - 1).min(), 0.0)),
           "vol": float(r.std() * math.sqrt(252)) if len(r) > 2 else None,
           "worst20": float(w20.min()) if len(w20) else None}
    out |= risk_adjusted(idx, out["max_dd"], bench, rf)
    return out


def risk_adjusted(idx: pd.Series, max_dd: float, bench: pd.Series | None, rf: pd.Series | None) -> dict:
    """Sharpe, Sortino (downside deviation of the excess returns), Calmar, information ratio and tracking error of
    a daily value index; a statistic whose input is missing (no `rf` / `bench`, too few days) is None."""
    r = idx.pct_change().dropna()
    out = {"ann_ret": None, "sharpe": None, "sortino": None, "calmar": None, "ir": None, "te": None}
    if len(r) < 20:
        return out
    ann = float(idx.iloc[-1] / idx.iloc[0]) ** (252 / len(r)) - 1
    out["ann_ret"] = ann
    out["calmar"] = ann / -max_dd if max_dd < 0 else None
    sd = float(r.std())
    if rf is not None:
        f = rf.reindex(rf.index.union(r.index)).ffill().reindex(r.index)
        if not f.isna().any():
            ex = r - f
            down = math.sqrt(float((ex.clip(upper=0) ** 2).mean()))
            out["sharpe"] = float(ex.mean() / sd * math.sqrt(252)) if sd > 0 else None
            out["sortino"] = float(ex.mean() / down * math.sqrt(252)) if down > 0 else None
    if bench is not None:
        b = bench.reindex(bench.index.union(idx.index)).ffill().reindex(idx.index)
        if not b.isna().any():
            act = r - b.pct_change().dropna().reindex(r.index)
            te = float(act.std() * math.sqrt(252))
            out["te"] = te
            out["ir"] = float(act.mean() * 252 / te) if te > 0 else None
    return out


def daily_rf(market) -> pd.Series | None:
    """The ECB deposit rate (FRED ECBDFR, % a year) as a daily return: the krone follows the euro, so it is the
    nearest risk-free rate for DKK returns in the data. None without it."""
    try:
        f = market.fred()
    except Exception:  # noqa: BLE001 - no FRED cache: the statistics that need it stay None
        return None
    if "ECBDFR" not in f or f["ECBDFR"].dropna().empty:
        return None
    return (1 + f["ECBDFR"].dropna().sort_index() / 100) ** (1 / 252) - 1


def _pct(v, q):
    v = [x for x in v if x is not None]
    return float(np.percentile(v, q)) if v else None


def summarize_exits(recs: list[dict], key: str, lag: int) -> dict | None:
    """Across dates, one variant (`key`) against holding on the same dates."""
    pairs = [(r["hold"], r[key]) for r in recs if r.get("hold") and r.get(key)]
    if not pairs:
        return None
    hold, var = [h for h, _ in pairs], [v for _, v in pairs]
    diff = [v["ret"] - h["ret"] for h, v in pairs]
    out = {"dates": len(pairs), "ret_mean": _mean([v["ret"] for v in var]), "ret_median": _pct([v["ret"] for v in var], 50),
           "ret_p10": _pct([v["ret"] for v in var], 10), "diff_mean": _mean(diff), "diff_median": _pct(diff, 50),
           "diff_t": nw_t(diff, lag), "helped": _mean([float(x > 0) for x in diff]),
           "dd_mean": _mean([v["max_dd"] for v in var]), "dd_worst": min(v["max_dd"] for v in var),
           "vol_mean": _mean([v["vol"] for v in var]), "worst20_mean": _mean([v["worst20"] for v in var]),
           "hold": {"ret_mean": _mean([h["ret"] for h in hold]), "ret_p10": _pct([h["ret"] for h in hold], 10),
                    "dd_mean": _mean([h["max_dd"] for h in hold]), "dd_worst": min(h["max_dd"] for h in hold),
                    "vol_mean": _mean([h["vol"] for h in hold]), "worst20_mean": _mean([h["worst20"] for h in hold])},
           "exits_mean": _mean([r.get(f"{key}_exits") for r in recs if r.get(key)]),
           "reentries_mean": _mean([r.get(f"{key}_reentries") for r in recs if r.get(key)])}
    for m in RISK_KEYS:
        out[f"{m}_mean"] = _mean([v.get(m) for v in var])
        out["hold"][f"{m}_mean"] = _mean([h.get(m) for h in hold])
    sd = [v["sharpe"] - h["sharpe"] for h, v in pairs if v.get("sharpe") is not None and h.get("sharpe") is not None]
    out["sharpe_diff_mean"], out["sharpe_diff_t"] = _mean(sd), nw_t(sd, lag) if sd else None
    rd = out["ret_mean"] / abs(out["dd_mean"]) if out["dd_mean"] else None
    hd = out["hold"]["ret_mean"] / abs(out["hold"]["dd_mean"]) if out["hold"]["dd_mean"] else None
    out["ret_per_dd"], out["hold"]["ret_per_dd"] = rd, hd
    return out


RISK_KEYS = ("ann_ret", "sharpe", "sortino", "calmar", "ir", "te")


def exit_verdict(parts: dict, months: int) -> dict:
    """Passes when, in-sample and in the holdout, it costs at most COST_PER_6M (pro rata) of mean return against
    holding, cuts the mean max drawdown by DD_CUT and lifts the 10 % worst outcome."""
    limit = COST_PER_6M * months / 6
    why = []
    for part in ("in_sample", "holdout"):
        s = parts.get(part)
        if not s or s["dates"] < 3:
            return {"label": "not enough data", "why": [f"too few {part.replace('_', '-')} dates"]}
        if s["diff_mean"] < -limit:
            why.append(f"{part.replace('_', '-')}: costs {-s['diff_mean']:.1%} (limit {limit:.0%})")
        if not s["dd_mean"] >= (1 - DD_CUT) * s["hold"]["dd_mean"]:
            why.append(f"{part.replace('_', '-')}: drawdown {s['dd_mean']:.1%} vs held {s['hold']['dd_mean']:.1%} "
                       f"(needs a {DD_CUT:.0%} cut)")
        if not s["ret_p10"] > s["hold"]["ret_p10"]:
            why.append(f"{part.replace('_', '-')}: worst 10 % {s['ret_p10']:.1%} vs held {s['hold']['ret_p10']:.1%}")
    return {"label": "passes" if not why else "fails", "why": why, "cost_limit": limit}


def exit_variants(market, n_top: int = 15, horizons=EXIT_HORIZONS, keys: list[str] | None = None, since=None,
                  reentry: bool = True, log=lambda *_: None, p: Panels | None = None) -> dict:
    """Each month-end's top-N basket (equal weights, fees) held against every variant of the exit rule over each
    horizon: return and risk (max drawdown, volatility, worst 20 sessions, the 10 % worst outcome), split in-sample
    and holdout, with a verdict per variant (exit_verdict). With `reentry`, the variant that did best in-sample
    on the longest horizon is also run with re-entry."""
    from dataclasses import replace

    from . import exits as ex
    from . import picks
    from .pit import Context

    bt = settings().get("backtest") or {}
    fee = float(bt.get("fee_bps", 0))
    park = bt.get("park") or universe.benchmark()
    holdout = pd.Timestamp(bt.get("study_holdout_from")) if bt.get("study_holdout_from") else None
    specs = _exit_variants()
    if keys:
        unknown = set(keys) - {s.key for s in specs}
        if unknown:
            raise ValueError(f"unknown exit variant(s): {', '.join(sorted(unknown))} (known: {', '.join(s.key for s in specs)})")
        specs = [s for s in specs if s.key in keys or s.key == "rule"]
    for h in horizons:
        if h not in HORIZONS:
            raise ValueError(f"horizons are months among {', '.join(map(str, HORIZONS))}")
    p = p or panels(market)
    longest = max(horizons)
    baskets = []
    for day in formation_dates(p.sessions, since):
        fi = fill_session(p.sessions, day, bt.get("fill", "next"))
        if fi is None or fi + HORIZONS[min(horizons)] >= len(p.sessions):
            continue
        names = top_names(p, day, n_top)
        if len(names) >= n_top:
            baskets.append((day, fi, names))
    if not baskets:
        raise ValueError("no formation date with a complete horizon: not enough price history yet")
    ctx = fast(Context.build(market, {t for _, _, b in baskets for t in b} | {park}), p)
    log(f"{len(baskets)} formation dates, {len(specs)} variants{' + re-entry' if reentry else ''}")

    def run_spec(spec, recs):
        for i, (day, fi, names) in enumerate(baskets):
            rec = recs[i]
            if rec is None:
                continue
            rep = ex.replay(rec["_rows"], ctx, "rules", end=rec["_end"], fee_bps=fee, spec=spec)
            res = {}
            for h in horizons:
                if fi + HORIZONS[h] < len(p.sessions):
                    res[h] = path(rep["rows"], market, p.sessions[fi], p.sessions[fi + HORIZONS[h]])
            rec["_by"][spec.key] = res
            rec[f"{spec.key}_exits"] = len(rep["exits"])
            rec[f"{spec.key}_reentries"] = len(rep.get("reentries") or [])
        log(f"  {spec.key}: done")

    recs = []
    for day, fi, names in baskets:
        f = p.sessions[fi]
        rows, problems = picks.basket_rows(market, {t: 1 / len(names) for t in names}, f, 100_000.0, fee)
        if not rows:
            recs.append(None)
            continue
        end = p.sessions[min(fi + HORIZONS[longest], len(p.sessions) - 1)]
        ends = {h: p.sessions[fi + HORIZONS[h]] for h in horizons if fi + HORIZONS[h] < len(p.sessions)}
        by = {"hold": {h: path(rows, market, f, e) for h, e in ends.items()}}
        for w in MIXES:
            mix, _ = picks.basket_rows(market, {**{t: w / len(names) for t in names}, park: 1 - w}, f, 100_000.0, fee)
            by[_mix_key(w)] = {h: path(mix, market, f, e) for h, e in ends.items()} if mix else {}
        recs.append({"date": day, "fill": f, "_rows": rows, "_end": end, "_by": by, "skipped": problems,
                     **{f"{_mix_key(w)}_exits": 0 for w in MIXES}})
    for spec in specs:
        run_spec(spec, recs)

    def table(spec_keys):
        out = {}
        for h in horizons:
            lag = max(h - 1, 0)
            flat = []
            for r in recs:
                if r is None or h not in r["_by"]["hold"] or not r["_by"]["hold"][h]:
                    continue
                flat.append({"date": r["date"], "hold": r["_by"]["hold"][h],
                             **{k: r["_by"].get(k, {}).get(h) for k in spec_keys},
                             **{f"{k}_exits": r.get(f"{k}_exits") for k in spec_keys},
                             **{f"{k}_reentries": r.get(f"{k}_reentries") for k in spec_keys}})
            out[str(h)] = {}
            for k in spec_keys:
                parts = {"all": summarize_exits(flat, k, lag),
                         "in_sample": summarize_exits([x for x in flat if holdout is None or x["date"] < holdout], k, lag),
                         "holdout": summarize_exits([x for x in flat if holdout is not None and x["date"] >= holdout], k, lag)}
                out[str(h)][k] = parts | {"verdict": exit_verdict(parts, h)}
        return out

    mixes = [_mix_key(w) for w in MIXES]
    results = table([s.key for s in specs] + mixes)
    chosen = None
    if reentry:
        cands = [(s, results[str(longest)][s.key]["in_sample"]) for s in specs[FIRST_CANDIDATE:]]
        cands = [(s, x) for s, x in cands if x]
        cut = [(s, x) for s, x in cands if x["dd_mean"] >= (1 - DD_CUT) * x["hold"]["dd_mean"]]
        pick = max(cut, key=lambda c: c[1]["diff_mean"]) if cut else \
            max(cands, key=lambda c: c[1]["ret_per_dd"] or -1e9) if cands else None
        if pick:
            chosen = replace(pick[0], key=f"{pick[0].key}-re", label=f"{pick[0].label}, with re-entry", reentry=True)
            specs.append(chosen)
            run_spec(chosen, recs)
            results = table([s.key for s in specs] + mixes)
    per_date = []
    for r in recs:
        if r is None:
            continue
        per_date.append({"date": r["date"].date().isoformat(), "fill": r["fill"].date().isoformat(), "skipped": r["skipped"],
                         **{k: {str(h): v for h, v in by.items()} for k, by in r["_by"].items()}})
    return {
        "generated": pd.Timestamp.now().isoformat(timespec="seconds"), "asof": p.sessions[-1].date().isoformat(),
        "settings": {"n_top": n_top, "fee_bps": fee, "park": park, "horizons": list(horizons),
                     "holdout_from": holdout.date().isoformat() if holdout is not None else None,
                     "cost_per_6m": COST_PER_6M, "dd_cut": DD_CUT},
        "variants": [{"key": s.key, "label": s.label, "stops": dict(s.stops), "tp": s.tp, "stop": s.stop,
                      "pct": s.pct if s.stop == "pct" else None, "sma": s.sma if s.stop == "trend" else None,
                      "reentry": s.reentry} for s in specs]
                    + [{"key": _mix_key(w), "label": f"No exits: {w:.0%} in the basket, {1 - w:.0%} in {park} (sizing)",
                        "stops": {}, "tp": "off", "stop": "none", "pct": None, "sma": None, "reentry": False, "mix": w}
                       for w in MIXES],
        "variants_tried": len(specs), "reentry_on": chosen.key if chosen else None,
        "results": results, "dates": per_date,
        "caveats": [CAVEATS[0], "The rule as it would have been set then: analyst data didn't exist for most of the "
                    "period, so it moves nothing there. The baskets are the score's top N, held without rebalancing; "
                    "exits are parked in ACWI.", CAVEATS[4], CAVEATS[5]],
    }


def _mix_key(w: float) -> str:
    return f"mix{round(w * 100)}"


EXIT_REPORT_FILE = "exit-study.json"


def write_exits(rep: dict) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    f = REPORTS / EXIT_REPORT_FILE
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(rep, indent=1, default=_json), encoding="utf-8")
    tmp.replace(f)


# ---------------- redeploy: the exit money into the next momentum name ----------------

class Picker:
    """The candidates for a redeploy, from data up to the day asked: the names with a price, a DKK rate and a
    score, best first. `pick` gives the best one not held and not barred that is in an uptrend (`trend`) and fits
    the caps given what is held; `rank` is a name's place among all of them (1 = best, None = unranked)."""

    def __init__(self, p: Panels, n: int, max_per_sector: int | None = None, max_per_group: int | None = None,
                 trend: bool = True):
        self.p, self.n, self.max_sector, self.max_group, self.trend = p, n, max_per_sector, max_per_group, trend
        self._ranked: dict = {}

    def ranked(self, day: pd.Timestamp) -> pd.Series:
        if day not in self._ranked:
            p = self.p
            if day not in p.m["last"].index:
                self._ranked[day] = pd.Series(dtype=float)
            else:
                ok = p.m["last"].loc[day].notna() & p.dkk.loc[day].notna()
                self._ranked[day] = _score(p, day).where(ok).dropna().sort_values(ascending=False, kind="stable")
        return self._ranked[day]

    def rank(self, day: pd.Timestamp, t: str) -> int | None:
        r = self.ranked(day)
        return int(r.index.get_loc(t)) + 1 if t in r.index else None

    def _key(self, t: str) -> tuple[str, str]:
        sec = self.p.sector.get(t, "") if t in self.p.sector.index else ""
        sec = sec if isinstance(sec, str) and sec.strip() else f"?{t}"
        grp = self.p.group.get(t) if t in self.p.group.index else None
        return sec, grp if isinstance(grp, str) else f"?{t}"

    def capped(self, day: pd.Timestamp, n: int, held: set[str] = frozenset(), barred: set[str] = frozenset(),
               trend: bool | None = None) -> list[str]:
        """Up to `n` names, best first, that can be added to `held` under the caps."""
        trend = self.trend if trend is None else trend
        tr = self.p.m["trend_ok"]
        up = set(tr.columns[tr.loc[day].eq(True)]) if trend and day in tr.index else None
        sec, grp = {}, {}
        for t in held:
            a, b = self._key(t)
            sec[a], grp[b] = sec.get(a, 0) + 1, grp.get(b, 0) + 1
        out = []
        for t in self.ranked(day).index:
            if t in held or t in barred or (up is not None and t not in up):
                continue
            a, b = self._key(t)
            if (self.max_sector and sec.get(a, 0) >= self.max_sector) or (self.max_group and grp.get(b, 0) >= self.max_group):
                continue
            out.append(t)
            sec[a], grp[b] = sec.get(a, 0) + 1, grp.get(b, 0) + 1
            if len(out) >= n:
                break
        return out

    def pick(self, day: pd.Timestamp, held: set[str], barred: set[str]) -> str | None:
        c = self.capped(day, 1, held, barred)
        return c[0] if c else None


REDEPLOY_HORIZONS = (6, 12)
BUFFER = 3                    # rotation: sell at month-end a holding ranked outside BUFFER x N
COOLDOWN = 21                 # sessions before a sold name can be bought again by redeploy


def _redeploy_arms(buffer: int = BUFFER, cooldown: int = COOLDOWN):
    """(spec, twin): each arm with the arm it is judged against besides holding (redeploy against parking the
    same exits; a rotation with an exit rule against the rotation alone)."""
    from .exits import RuleSpec as R

    atr = (("mode", "atr"),)
    sc = {"redeploy": "score", "cooldown": cooldown}
    rot = sc | {"rotate": buffer}
    arms = [
        (R("sma200-park", "Close below the 200-day average, parked in ACWI", tp="off", stop="trend", sma=200), None),
        (R("sma200-redeploy", "Close below the 200-day average, redeployed", tp="off", stop="trend", sma=200, **sc),
         "sma200-park"),
        (R("atr-tp-park", "ATR stop and take-profit, parked in ACWI", atr), None),
        (R("atr-tp-redeploy", "ATR stop and take-profit, redeployed", atr, **sc), "atr-tp-park"),
        (R("tp-only-park", "Take-profit only, parked in ACWI", atr, stop="none"), None),
        (R("tp-only-redeploy", "Take-profit only, redeployed", atr, stop="none", **sc), "tp-only-park"),
        (R("rotate", f"No exit rule; month-end rotation out of names outside the top {buffer}xN", tp="off",
           stop="none", **rot), None),
        (R("rotate-sma200", "Rotation and the 200-day stop, redeployed", tp="off", stop="trend", sma=200, **rot),
         "rotate"),
        (R("rotate-atr-tp", "Rotation and the ATR stop with take-profit, redeployed", atr, **rot), "rotate"),
        (R("rotate-tp-only", "Rotation and the take-profit only, redeployed", atr, stop="none", **rot), "rotate"),
    ]
    return arms


def _paired(flat: list[dict], a: str, b: str, metric: str, lag: int) -> dict | None:
    d = [x[a][metric] - x[b][metric] for x in flat
         if x.get(a) and x.get(b) and x[a].get(metric) is not None and x[b].get(metric) is not None]
    return {"mean": _mean(d), "t": nw_t(d, lag), "share": _mean([float(v > 0) for v in d]), "dates": len(d)} if d else None


def redeploy_verdict(parts: dict, months: int) -> dict:
    """Better risk-adjusted only when, in-sample and in the holdout, its mean Sharpe beats holding and its twin's
    (parking the same exits, or the rotation alone) and its mean return costs at most COST_PER_6M (pro rata)
    against holding."""
    limit = COST_PER_6M * months / 6
    why = []
    for part in ("in_sample", "holdout"):
        s = parts.get(part)
        name = part.replace("_", "-")
        if not s or s["dates"] < 3 or s.get("sharpe_mean") is None:
            return {"label": "not enough data", "why": [f"too few {name} dates (or no risk-free rate)"]}
        if not s["sharpe_mean"] > s["hold"]["sharpe_mean"]:
            why.append(f"{name}: Sharpe {s['sharpe_mean']:.2f} vs held {s['hold']['sharpe_mean']:.2f}")
        tw = (parts.get("vs_twin") or {}).get(part)
        if tw is not None and not tw["sharpe"]["mean"] > 0:
            why.append(f"{name}: Sharpe {tw['sharpe']['mean']:+.2f} vs {parts['twin']}")
        if s["diff_mean"] < -limit:
            why.append(f"{name}: costs {-s['diff_mean']:.1%} (limit {limit:.0%})")
    return {"label": "better" if not why else "not better", "why": why, "cost_limit": limit}


def redeploy_study(market, n_top: int = 15, horizons=REDEPLOY_HORIZONS, buffer: int = BUFFER, cooldown: int = COOLDOWN,
                   max_per_sector: int | None = None, max_per_group: int | None = None, trend: bool = True, since=None,
                   keys: list[str] | None = None, log=lambda *_: None, p: Panels | None = None) -> dict:
    """Each month-end's top N (under the caps, equal weights, fees) held against the exit rules with the money
    parked in ACWI and redeployed into the next momentum name, and against a month-end rotation with and without
    the rules: return, risk and risk-adjusted return per horizon, in-sample and holdout, with a verdict per arm."""
    from . import exits as ex
    from . import picks
    from .pit import Context

    bt = settings().get("backtest") or {}
    fee = float(bt.get("fee_bps", 0))
    park = bt.get("park") or universe.benchmark()
    holdout = pd.Timestamp(bt.get("study_holdout_from")) if bt.get("study_holdout_from") else None
    arms = _redeploy_arms(buffer, cooldown)
    if keys:
        unknown = set(keys) - {s.key for s, _ in arms}
        if unknown:
            raise ValueError(f"unknown arm(s): {', '.join(sorted(unknown))} (known: {', '.join(s.key for s, _ in arms)})")
        want = set(keys) | {t for s, t in arms if s.key in keys and t}
        arms = [(s, t) for s, t in arms if s.key in want]
    for h in horizons:
        if h not in HORIZONS:
            raise ValueError(f"horizons are months among {', '.join(map(str, HORIZONS))}")
    p = p or panels(market)
    picker = Picker(p, n_top, max_per_sector, max_per_group, trend)
    rf = daily_rf(market)
    bench = p.bench_dkk
    longest = max(horizons)
    baskets = []
    for day in formation_dates(p.sessions, since):
        fi = fill_session(p.sessions, day, bt.get("fill", "next"))
        if fi is None or fi + HORIZONS[min(horizons)] >= len(p.sessions):
            continue
        names = picker.capped(day, n_top, trend=False)
        if len(names) >= n_top:
            baskets.append((day, fi, names))
    if not baskets:
        raise ValueError("no formation date with a complete horizon: not enough price history yet")
    ctx = fast(Context.build(market, set(p.closes.columns) | {park}), p)
    log(f"{len(baskets)} formation dates, {len(arms)} arms, {len(p.closes.columns)} names to redeploy into")

    recs = []
    for day, fi, names in baskets:
        f = p.sessions[fi]
        rows, problems = picks.basket_rows(market, {t: 1 / len(names) for t in names}, f, 100_000.0, fee)
        if not rows:
            recs.append(None)
            continue
        ends = {h: p.sessions[fi + HORIZONS[h]] for h in horizons if fi + HORIZONS[h] < len(p.sessions)}
        end = p.sessions[min(fi + HORIZONS[longest], len(p.sessions) - 1)]
        by = {"hold": {h: path(rows, market, f, e, bench, rf) for h, e in ends.items()}}
        for key, w in (("mix50", 0.5), ("acwi", 0.0)):
            mix, _ = picks.basket_rows(market, {**({t: w / len(names) for t in names} if w else {}), park: 1 - w},
                                       f, 100_000.0, fee)
            by[key] = {h: path(mix, market, f, e, bench, rf) for h, e in ends.items()} if mix else {}
        recs.append({"date": day, "fill": f, "_rows": rows, "_end": end, "_ends": ends, "_by": by, "skipped": problems,
                     "names": names, "runs": {}})
    for spec, _ in arms:
        for rec in recs:
            if rec is None:
                continue
            rep = ex.replay(rec["_rows"], ctx, "rules", end=rec["_end"], fee_bps=fee, spec=spec,
                            picker=picker if spec.redeploy == "score" else None)
            rec["_by"][spec.key] = {h: path(rep["rows"], market, rec["fill"], e, bench, rf) for h, e in rec["_ends"].items()}
            trades = [r for r in rep["rows"] if r["type"] in ("BUY", "SELL") and r["symbol"] != park]
            kinds: dict = {}
            for e in rep["exits"]:
                kinds[e["trigger"]] = kinds.get(e["trigger"], 0) + 1
            rec["runs"][spec.key] = {"exits": len(rep["exits"]), "by_trigger": kinds, "redeploys": len(rep["redeploys"]),
                                     "skipped": sum(ev["kind"] == "redeploy skipped" for ev in rep["events"]),
                                     "trades": len(trades), "fees_pct": sum(r["fee"] * r["fx_rate"] for r in rep["rows"]
                                                                            if r["type"] in ("BUY", "SELL")) / 100_000.0,
                                     "new_names": sorted({r["symbol"] for r in rep["redeploys"]})}
            rec[f"{spec.key}_exits"] = len(rep["exits"])
        log(f"  {spec.key}: done")

    arm_keys = [s.key for s, _ in arms] + ["mix50", "acwi"]
    twins = {s.key: t for s, t in arms}
    results = {}
    for h in horizons:
        lag = max(h - 1, 0)
        flat = []
        for r in recs:
            if r is None or not r["_by"]["hold"].get(h):
                continue
            flat.append({"date": r["date"], "hold": r["_by"]["hold"][h], **{k: r["_by"].get(k, {}).get(h) for k in arm_keys},
                         **{f"{k}_exits": r.get(f"{k}_exits", 0) for k in arm_keys}})
        split = {"all": flat, "in_sample": [x for x in flat if holdout is None or x["date"] < holdout],
                 "holdout": [x for x in flat if holdout is not None and x["date"] >= holdout]}
        results[str(h)] = {}
        for k in arm_keys:
            parts = {part: summarize_exits(xs, k, lag) for part, xs in split.items()}
            tw = twins.get(k)
            if tw:
                parts["twin"] = tw
                parts["vs_twin"] = {part: {"sharpe": _paired(xs, k, tw, "sharpe", lag), "ret": _paired(xs, k, tw, "ret", lag),
                                           "max_dd": _paired(xs, k, tw, "max_dd", lag)} for part, xs in split.items()}
            if k not in ("mix50", "acwi"):
                runs = [r["runs"][k] for r in recs if r is not None and k in r["runs"]]
                parts["activity"] = {"exits": _mean([x["exits"] for x in runs]), "redeploys": _mean([x["redeploys"] for x in runs]),
                                     "skipped": _mean([x["skipped"] for x in runs]), "trades": _mean([x["trades"] for x in runs]),
                                     "fees_pct": _mean([x["fees_pct"] for x in runs]),
                                     "by_trigger": {t: _mean([x["by_trigger"].get(t, 0) for x in runs])
                                                    for t in sorted({t for x in runs for t in x["by_trigger"]})},
                                     "over": f"{longest} months"}
            parts["verdict"] = redeploy_verdict(parts, h) if k not in ("mix50", "acwi") else None
            results[str(h)][k] = parts
    per_date = []
    for r in recs:
        if r is None:
            continue
        per_date.append({"date": r["date"].date().isoformat(), "fill": r["fill"].date().isoformat(), "names": r["names"],
                         "skipped": r["skipped"], "runs": r["runs"],
                         **{k: {str(h): v for h, v in by.items()} for k, by in r["_by"].items()}})
    return {
        "generated": pd.Timestamp.now().isoformat(timespec="seconds"), "asof": p.sessions[-1].date().isoformat(),
        "settings": {"n_top": n_top, "fee_bps": fee, "park": park, "horizons": list(horizons), "buffer": buffer,
                     "cooldown": cooldown, "max_per_sector": max_per_sector, "max_per_group": max_per_group,
                     "trend": trend, "holdout_from": holdout.date().isoformat() if holdout is not None else None,
                     "cost_per_6m": COST_PER_6M, "rf": "ECB deposit rate (FRED ECBDFR)" if rf is not None else None},
        "arms": [{"key": s.key, "label": s.label, "twin": t, "stop": s.stop, "tp": s.tp, "redeploy": s.redeploy,
                  "rotate": s.rotate, "cooldown": s.cooldown} for s, t in arms]
                + [{"key": "mix50", "label": f"No exits: 50% in the basket, 50% in {park} (sizing)", "twin": None},
                   {"key": "acwi", "label": f"All in {park}", "twin": None}],
        "results": results, "dates": per_date,
        "caveats": [
            "Survivorship: the universe is today's list, so every name redeployed into is one that survived to be on "
            "it. That flatters redeploying and rotating more than holding, which only ever owns the first basket.",
            "Sectors and stock groups (the caps) are today's.",
            "No tax: on frie midler every exit and rotation realises a gain or loss (realisationsbeskatning); on the "
            "aktiesparekonto (lagerbeskattet) turnover costs no extra tax. Trades and fees are given per arm so this "
            "can be judged.",
            "Sharpe and Sortino are over the ECB deposit rate (the krone follows the euro); annualised from 6- or "
            "12-month windows they are noisy, so compare them across arms, not with long-run figures.",
            "The rule as it would have been set then: analyst data didn't exist for most of the period, so it moves "
            "nothing there.",
        ] + ([] if rf is not None else ["No ECB deposit rate in the data: Sharpe and Sortino are missing."]),
    }


REDEPLOY_REPORT_FILE = "redeploy-study.json"


def write_redeploy(rep: dict) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    f = REPORTS / REDEPLOY_REPORT_FILE
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(rep, indent=1, default=_json), encoding="utf-8")
    tmp.replace(f)
