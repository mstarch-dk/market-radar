"""The block bootstrap of a proposal's and ACWI's weekly returns: the spread of outcomes over the horizon."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..config_schema import Propose
from . import rules


def bootstrap(rp: pd.Series, rb: pd.Series, weeks: int, excess: float | None, c: Propose | None = None) -> dict:
    """Block bootstrap of the basket's and ACWI's weekly returns together: demeaned, scaled to today's (EWMA)
    volatility, re-centred on ACWI's assumed drift plus the modelled excess (none: on ACWI's drift alone)."""
    c = c or rules.cfg()
    bc = c.bootstrap
    d = pd.concat([rp, rb], axis=1, keys=["p", "b"]).dropna()
    if len(d) < c.min_weeks:
        return {"weeks_used": len(d), "note": f"fewer than {c.min_weeks} weeks of joint returns: no bootstrap"}
    lam = bc.ewma_lambda
    scale = {}
    for k in ("p", "b"):
        x = d[k] - d[k].mean()
        ew = float((x ** 2).ewm(alpha=1 - lam).mean().iloc[-1])
        full = float((x ** 2).mean())
        scale[k] = float(np.clip(math.sqrt(ew / full), 0.5, 2.0)) if full > 0 else 1.0
    mu_b = (1 + c.acwi_drift_annual) ** (1 / 52) - 1
    mu_p = mu_b + (excess / weeks if excess is not None else 0.0)
    X = np.column_stack([(d["p"] - d["p"].mean()) * scale["p"] + mu_p, (d["b"] - d["b"].mean()) * scale["b"] + mu_b])
    T, blk = len(X), max(1, bc.block_weeks)
    rng = np.random.default_rng(bc.seed)
    nb = math.ceil(weeks / blk)
    starts = rng.integers(0, T - blk + 1, size=(bc.draws, nb))
    idx = (starts[:, :, None] + np.arange(blk)).reshape(bc.draws, -1)[:, :weeks]
    paths = {}
    for j, k in enumerate(("p", "b")):
        cum = np.cumprod(1 + X[idx, j], axis=1)
        peak = np.maximum.accumulate(np.concatenate([np.ones((len(cum), 1)), cum], axis=1), axis=1)[:, 1:]
        paths[k] = {"ret": cum[:, -1] - 1, "dd": np.minimum((cum / peak - 1).min(axis=1), 0.0)}
    ex = paths["p"]["ret"] - paths["b"]["ret"]

    def q(a, p):
        return float(np.percentile(a, p))
    return {"draws": bc.draws, "weeks": weeks, "weeks_used": T, "block_weeks": blk, "vol_scale": scale,
            "drift_used": excess is not None, "acwi_drift_annual": c.acwi_drift_annual,
            "ret": {"median": q(paths["p"]["ret"], 50), "p10": q(paths["p"]["ret"], 10), "p90": q(paths["p"]["ret"], 90)},
            "acwi_ret": {"median": q(paths["b"]["ret"], 50), "p10": q(paths["b"]["ret"], 10), "p90": q(paths["b"]["ret"], 90)},
            "excess": {"median": q(ex, 50), "p10": q(ex, 10), "p90": q(ex, 90)},
            "p_beat": float((ex > 0).mean()),
            "max_dd": {"median": q(paths["p"]["dd"], 50), "p10": q(paths["p"]["dd"], 10)},
            "acwi_max_dd": {"median": q(paths["b"]["dd"], 50), "p10": q(paths["b"]["dd"], 10)},
            "note": "weekly steps: a fall inside a week isn't seen, so drawdowns read a little shallow"}
