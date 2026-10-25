"""The risk model of a set of DKK holdings: shrunk covariance, volatility and tracking error, the weekly path,
stress windows, the realised drawdown and the factor tilts. Shared by proposals and the portfolio views."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from ..config import typed
from ..config_schema import Propose
from ..signals.risk import deepest_drawdown
from ..sources import tracked
from . import exposure
from .prices import Prices

if TYPE_CHECKING:
    from ..market import Market


def shrunk_cov(R: pd.DataFrame, shrink: float, min_weeks: int) -> pd.DataFrame:
    """Pairwise weekly covariance pulled `shrink` of the way to a constant-correlation matrix, made positive
    semi-definite; columns with fewer than `min_weeks` returns are dropped."""
    R = R.loc[:, R.notna().sum() >= min_weeks]
    if R.shape[1] == 0:
        return pd.DataFrame()
    S = R.cov(min_periods=min_weeks)
    sd = np.sqrt(np.diag(S.to_numpy()))
    C = R.corr(min_periods=min_weeks).to_numpy()
    off = C[~np.eye(len(C), dtype=bool)]
    rbar = float(np.nanmean(off)) if off.size and np.isfinite(off).any() else 0.0
    F = rbar * np.outer(sd, sd)
    np.fill_diagonal(F, sd ** 2)
    Sn = S.to_numpy()
    Sn = np.where(np.isnan(Sn), F, Sn)
    M = shrink * F + (1 - shrink) * Sn
    vals, vecs = np.linalg.eigh((M + M.T) / 2)
    M = vecs @ np.diag(np.clip(vals, 0, None)) @ vecs.T
    return pd.DataFrame(M, index=S.index, columns=S.columns)


def ex_ante_risk(values: dict[str, float], cov: pd.DataFrame, bench: str) -> dict:
    """Ex-ante risk of DKK `values` from a weekly covariance (that includes `bench`)."""
    lt = exposure.look_through()
    agg: dict[str, float] = {}
    for t, x in values.items():                    # a world fund without its own prices is modelled with ACWI
        if x:
            k = bench if t in lt and t not in cov.index else t
            agg[k] = agg.get(k, 0.0) + x
    total = sum(agg.values())
    out: dict[str, Any] = {"vol_ann": None, "beta": None, "te_ann": None, "div_ratio": None, "coverage": None,
           "missing": sorted(t for t in agg if t not in cov.index), "contributions": {}}
    covered = {t: x for t, x in agg.items() if t in cov.index}
    if total <= 0 or not covered or bench not in cov.index:
        return out
    out["coverage"] = sum(covered.values()) / total
    names = list(covered)
    w = np.array([covered[t] for t in names]) / sum(covered.values())
    S = cov.loc[names, names].to_numpy()
    sb = cov.loc[names, bench].to_numpy()
    vb = float(cov.at[bench, bench])
    var = float(w @ S @ w)
    if var <= 0:
        return out
    sd = np.sqrt(np.diag(S))
    out |= {"vol_ann": math.sqrt(var * 52), "beta": float(w @ sb) / vb if vb > 0 else None,
            "te_ann": math.sqrt(max(var - 2 * float(w @ sb) + vb, 0.0) * 52),
            "div_ratio": float(w @ sd) / math.sqrt(var),
            "contributions": {t: float(w[i] * (S @ w)[i] / var) for i, t in enumerate(names)}}
    return out


def weekly_returns(values: dict[str, float], R: pd.DataFrame, bench: str) -> pd.Series | None:
    """Weekly return of fixed DKK weights (rebalanced weekly; names without a return that week are left out and
    the rest re-weighted)."""
    lt = exposure.look_through()
    agg: dict[str, float] = {}
    for t, x in values.items():
        if x:
            k = bench if t in lt and t not in R.columns else t
            agg[k] = agg.get(k, 0.0) + x
    cols = [t for t in agg if t in R.columns]
    if not cols:
        return None
    w = pd.Series({t: agg[t] for t in cols})
    sub = R[cols]
    ok = sub.notna()
    ww = ok.mul(w, axis=1)
    # zero: left out of the sum, and the weights re-normalised over the names with a return (ww)
    out = (sub.fillna(0).mul(w, axis=1).sum(axis=1) / ww.sum(axis=1)).where(ww.sum(axis=1) > 0.5 * w.sum())
    return out.dropna()


def stress(values: dict[str, float], prices: Prices, bench: str, c: Propose | None = None) -> list[dict]:
    """Today's DKK weights through each stress window (daily DKK closes), where the price history covers it."""
    c = c or typed().propose
    lt = exposure.look_through()
    out = []
    for e in c.stress:
        s, t1 = pd.Timestamp(e.start), pd.Timestamp(e.end)
        rec = {"key": e.key, "label": e.label, "start": s.date().isoformat(), "end": t1.date().isoformat(),
               "coverage": None, "ret": None, "max_dd": None, "acwi_ret": None, "acwi_max_dd": None, "missing": []}
        total = sum(x for x in values.values() if x)
        legs, cov = [], 0.0
        for t, x in values.items():
            if not x:
                continue
            ser = prices.dkk(t)
            if ser is None and t in lt:
                ser = prices.dkk(bench)
            win = ser.loc[s:t1] if ser is not None else None
            if win is None or len(win) < 2 or (win.index[0] - s).days > 5 or (t1 - win.index[-1]).days > 5:
                rec["missing"].append(t)
                continue
            legs.append(win / win.iloc[0] * x)
            cov += x
        b = prices.dkk(bench)
        bw = b.loc[s:t1] if b is not None else None
        if bw is not None and len(bw) >= 2 and (bw.index[0] - s).days <= 5:
            bi = bw / bw.iloc[0]
            rec["acwi_ret"], rec["acwi_max_dd"] = float(bi.iloc[-1] - 1), deepest_drawdown(bi)
        rec["coverage"] = cov / total if total > 0 else None
        if legs and total > 0 and cov / total >= 0.5:
            v = pd.concat(legs, axis=1).ffill().sum(axis=1) / cov
            rec["ret"], rec["max_dd"] = float(v.iloc[-1] - 1), deepest_drawdown(v)
        elif legs or rec["missing"]:
            rec["note"] = "less than half of the value has prices in this window: not replayed"
        out.append(rec)
    return out


def realised_dd(rp: pd.Series | None, weeks: int) -> float | None:
    from ..signals import risk as rk

    if rp is None or len(rp.dropna()) < 10:
        return None
    return rk.drawdown(rp.dropna().iloc[-weeks:])[0]


def factor_tilts(values: dict[str, float], R: pd.DataFrame, market: Market) -> dict | None:
    """Loadings of the weekly return of fixed DKK `values` on ACWI and the factor ETFs' spreads over it
    (settings risk.factors), with t-stats; None without a return path or ACWI's returns."""
    from ..signals import risk as rk

    bench = tracked.benchmark()
    rp = weekly_returns(values, R, bench)
    if rp is None or bench not in R:
        return None
    tilts = {f: R[f] for f in typed().risk.factors if f in R}
    rf = market.fred().get("DGS3MO")   # None without the series: raw returns, said by alpha_basis
    c = typed().propose
    return rk.factor_loadings(rp, R[bench], tilts, rf, c.history_weeks, c.min_weeks)
