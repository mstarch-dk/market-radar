"""Statistics the studies and the proposals share: means and Newey-West t, one date's cross-section of a score
and its summary across dates, verdicts on variants, a value path's return and risk."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..signals.risk import TRADING_DAYS, deepest_drawdown, worst_window

QUANTILES = 5


def mean(values) -> float | None:
    """The mean of the finite values; None when there are none (a NaN or inf is missing, not a number)."""
    v = [x for x in values if x is not None and np.isfinite(x)]
    return float(np.mean(v)) if v else None


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


def path_stats(level: pd.Series) -> dict:
    """A value path's return (from 1), maximum drawdown and worst 20-session change."""
    return {"ret": float(level.iloc[-1] - 1), "max_dd": deepest_drawdown(level), "worst20": worst_window(level, 20)}


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


def summarize(rows: list[dict], lag: int) -> dict | None:
    """Across dates: means, Newey-West t-statistics and shares."""
    rows = [r for r in rows if r is not None]
    if not rows:
        return None
    ics = [r["ic"] for r in rows]
    q = [mean([r["q"][i] for r in rows]) for i in range(QUANTILES)]
    top_dkk = [r.get("top_dkk") for r in rows]
    acwi = [r.get("acwi_dkk") for r in rows]
    beat = [a < b for a, b in zip(acwi, top_dkk) if a is not None and b is not None]
    return {
        "dates": len(rows), "n_mean": mean([r["n"] for r in rows]),
        "ic_mean": mean(ics), "ic_t": nw_t(ics, lag), "ic_pos": mean([float(i > 0) for i in ics if i is not None]),
        "q": q, "spread": mean([r["spread"] for r in rows]), "spread_t": nw_t([r["spread"] for r in rows], lag),
        "monotone": all(a is not None and b is not None and a < b for a, b in zip(q, q[1:])),
        "top_excess": mean([r["top_excess"] for r in rows]), "top_excess_t": nw_t([r["top_excess"] for r in rows], lag),
        "top_hit": mean([r["top_hit"] for r in rows]),
        "top_dkk": mean(top_dkk), "acwi_dkk": mean(acwi), "top_beats_acwi": mean([float(b) for b in beat]),
    }


def turnover(tops: list[set]) -> float | None:
    """Mean share of the top quintile replaced from one date to the next."""
    v = [1 - len(a & b) / len(b) for a, b in zip(tops, tops[1:]) if b]
    return mean(v)


def holdout_diff_t(rows: list[dict], base: list[dict], holdout, lag: int) -> float | None:
    """Newey-West t of the holdout's per-date IC difference (variant − baseline), on the dates both have."""
    b = {r["date"]: r["ic"] for r in base if holdout is not None and r["date"] >= holdout}
    d = [r["ic"] - b[r["date"]] for r in rows if r["date"] in b and r["ic"] is not None and b[r["date"]] is not None]
    return nw_t(d, lag)


def variant_verdict(res: dict, base: dict, diff_t: float | None = None) -> dict:
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


def risk_adjusted(idx: pd.Series, max_dd: float, bench: pd.Series | None, rf: pd.Series | None) -> dict:
    """Sharpe, Sortino (downside deviation of the excess returns), Calmar, information ratio and tracking error of
    a daily value index; a statistic whose input is missing (no `rf` / `bench`, too few days) is None."""
    r = idx.pct_change().dropna()
    out: dict[str, float | None] = {"ann_ret": None, "sharpe": None, "sortino": None, "calmar": None, "ir": None,
                                    "te": None}
    if len(r) < 20:
        return out
    ann = float(idx.iloc[-1] / idx.iloc[0]) ** (TRADING_DAYS / len(r)) - 1
    out["ann_ret"] = ann
    out["calmar"] = ann / -max_dd if max_dd < 0 else None
    sd = float(r.std())
    if rf is not None:
        f = rf.reindex(rf.index.union(r.index)).ffill().reindex(r.index)
        if not f.isna().any():
            ex = r - f
            down = math.sqrt(float((ex.clip(upper=0) ** 2).mean()))
            out["sharpe"] = float(ex.mean() / sd * math.sqrt(TRADING_DAYS)) if sd > 0 else None
            out["sortino"] = float(ex.mean() / down * math.sqrt(TRADING_DAYS)) if down > 0 else None
    if bench is not None:
        b = bench.reindex(bench.index.union(idx.index)).ffill().reindex(idx.index)
        if not b.isna().any():
            act = r - b.pct_change().dropna().reindex(r.index)
            te = float(act.std() * math.sqrt(TRADING_DAYS))
            out["te"] = te
            out["ir"] = float(act.mean() * TRADING_DAYS / te) if te > 0 else None
    return out


def daily_rf(market) -> pd.Series | None:
    """The ECB deposit rate (FRED ECBDFR, % a year) as a daily return: the krone follows the euro, so it is the
    nearest risk-free rate for DKK returns in the data. None without it (no FRED cache reads as an empty frame;
    a cache that can't be read is an error, not a missing rate)."""
    f = market.fred()
    if "ECBDFR" not in f or f["ECBDFR"].dropna().empty:
        return None
    return (1 + f["ECBDFR"].dropna().sort_index() / 100) ** (1 / TRADING_DAYS) - 1
