"""Risk and return statistics from weekly returns: beta (with its standard error), alpha, idiosyncratic and
downside risk, Sharpe/Sortino, drawdowns, factor attribution and correlations.

Everything is computed on weekly (Friday) returns in DKK, the currency a Danish investor experiences, over the windows in
settings.yaml `risk:`. Each result reports how many weeks it used. With fewer than `min_weeks` there is no
result (None), never a guess. These are descriptive statistics of the past: a 52-week beta is noisy, so its
standard error and R² are part of the output.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..values import num

TRADING_DAYS = 252        # sessions a year: daily figures are annualised with these
WEEKS_PER_YEAR = 52
MONTHS_PER_YEAR = 12
FLAT = 1e-12  # variance below this is treated as no movement (floating-point noise, not a signal)


def weekly(prices: pd.Series) -> pd.Series:
    """Weekly simple returns from a price series (last close of each Friday-ending week). A week still in
    progress is left out: its return covers fewer days than the others and would distort the statistics."""
    p = prices.dropna()
    w = p.resample("W-FRI").last().pct_change().dropna()
    if not p.empty and not w.empty and p.index[-1] < w.index[-1]:   # the last bin ends after the data: partial week
        w = w.iloc[:-1]
    return w


def rf_weekly(rf_pct: pd.Series | None, index: pd.DatetimeIndex) -> pd.Series | None:
    """The 3-month T-bill yield (FRED DGS3MO, % a year) as a weekly return on `index`; None without data."""
    if rf_pct is None or rf_pct.dropna().empty:
        return None
    r = rf_pct.dropna().sort_index()
    r = r.reindex(r.index.union(index)).ffill().reindex(index)
    if r.isna().any():
        return None
    return (1 + r / 100) ** (1 / WEEKS_PER_YEAR) - 1


def ols(y: np.ndarray, X: np.ndarray) -> dict:
    """Least squares with an intercept: coefficients, standard errors, t-stats, R² and residuals."""
    A = np.column_stack([np.ones(len(y)), X])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ coef
    dof = len(y) - A.shape[1]
    s2 = resid @ resid / dof if dof > 0 else float("nan")
    cov = s2 * np.linalg.pinv(A.T @ A)
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    tss = ((y - y.mean()) ** 2).sum()
    return {"coef": coef, "se": se, "t": np.divide(coef, se, out=np.full_like(coef, np.nan), where=se > 0),
            "r2": 1 - (resid @ resid) / tss if tss > 0 else float("nan"), "resid": resid}


def underwater(level: pd.Series) -> pd.Series:
    """How far a value series is below its running peak, each day (0 at a new high, negative below it)."""
    return level / level.cummax() - 1


def deepest_drawdown(level: pd.Series) -> float:
    """The maximum drawdown of a value series: its deepest fall from a running peak (0 or negative; NaN when
    empty)."""
    return float(underwater(level).min())


def annualised_vol(returns: pd.Series, per_year: int = TRADING_DAYS) -> float:
    """The standard deviation of periodic returns, annualised (`per_year` periods a year)."""
    return float(returns.std() * math.sqrt(per_year))


def worst_window(level: pd.Series, n: int = 20) -> float | None:
    """The worst change of a value series over any `n` periods; None when it is shorter than that."""
    w = (level / level.shift(n) - 1).dropna()
    return float(w.min()) if len(w) else None


def drawdown(returns: pd.Series) -> tuple[float, int]:
    """Deepest fall from a peak of the cumulative return, and how many weeks the longest spell below a peak lasted."""
    wealth = (1 + returns).cumprod()
    under = underwater(wealth)
    longest = run = 0
    for v in under:
        run = run + 1 if v < 0 else 0
        longest = max(longest, run)
    return float(under.min()), int(longest)


def window_stats(asset: pd.Series, bench: pd.Series, rf: pd.Series | None, weeks: int, min_weeks: int) -> dict | None:
    """Statistics of weekly returns `asset` against `bench` over the last `weeks`. Sharpe and Sortino need the
    risk-free rate and stay None without it; alpha is then measured on raw returns (`alpha_basis`)."""
    df = pd.concat([asset, bench], axis=1, keys=["y", "b"], sort=True).dropna().iloc[-weeks:]
    if len(df) < min_weeks or not df["b"].var() > FLAT:       # a flat benchmark has no beta to measure
        return None
    r = rf_weekly(rf, df.index) if rf is not None else None
    y, b = (df["y"] - r, df["b"] - r) if r is not None else (df["y"], df["b"])
    fit = ols(y.to_numpy(), b.to_numpy()[:, None])
    down = df[df["b"] < 0]
    dfit = ols((down["y"] - (r.loc[down.index] if r is not None else 0)).to_numpy(),
               (down["b"] - (r.loc[down.index] if r is not None else 0)).to_numpy()[:, None]) if len(down) >= 10 else None
    vol = df["y"].std() * math.sqrt(WEEKS_PER_YEAR)
    excess = (df["y"] - r) if r is not None else None
    neg = excess[excess < 0] if excess is not None else pd.Series(dtype=float)
    dd, dd_weeks = drawdown(df["y"])
    total = (1 + df["y"]).prod() ** (WEEKS_PER_YEAR / len(df)) - 1
    return {
        "n_weeks": int(len(df)), "return_ann": num(total), "vol_ann": num(vol),
        "beta": num(fit["coef"][1]), "beta_se": num(fit["se"][1]), "r2": num(fit["r2"]), "corr": num(df["y"].corr(df["b"])),
        "alpha_ann": num(fit["coef"][0] * WEEKS_PER_YEAR), "alpha_t": num(fit["t"][0]),
        "alpha_basis": "excess over T-bills" if r is not None else "raw returns (no risk-free rate)",
        "idio_vol_ann": num(np.std(fit["resid"], ddof=2) * math.sqrt(WEEKS_PER_YEAR)),
        "downside_beta": num(dfit["coef"][1]) if dfit else None,
        "sharpe": num(excess.mean() / df["y"].std() * math.sqrt(WEEKS_PER_YEAR)) if excess is not None else None,
        "sortino": num(excess.mean() * WEEKS_PER_YEAR / (math.sqrt((neg ** 2).sum() / len(excess)) * math.sqrt(WEEKS_PER_YEAR)))
        if excess is not None and len(neg) > 0 else None,
        "max_dd": num(dd), "max_dd_weeks": dd_weeks,
    }


def factor_loadings(asset: pd.Series, market: pd.Series, tilts: dict[str, pd.Series], rf: pd.Series | None,
                    weeks: int, min_weeks: int) -> dict | None:
    """Regression of the asset's excess return on the market and on tilt spreads (each factor or sector ETF minus
    the market), so a loading reads as "extra exposure to X beyond the market". Descriptive only: factors are
    correlated and the sample is short; the t-stats say how much to trust each loading."""
    cols = {"market": market, **{k: v - market for k, v in tilts.items()}}
    df = pd.concat([asset, *cols.values()], axis=1, keys=["y", *cols], sort=True).dropna().iloc[-weeks:]
    cols = {k: v for k, v in cols.items() if df[k].var() > FLAT}   # a regressor that never moves can't be estimated
    if "market" not in cols:
        return None
    if len(df) < max(min_weeks, 4 * (len(cols) + 1)):
        return None
    r = rf_weekly(rf, df.index) if rf is not None else None
    y = (df["y"] - r) if r is not None else df["y"]
    X = df[list(cols)].copy()
    if r is not None:
        X["market"] = X["market"] - r
    fit = ols(y.to_numpy(), X.to_numpy())
    return {"n_weeks": int(len(df)), "r2": num(fit["r2"]),
            "alpha_ann": num(fit["coef"][0] * WEEKS_PER_YEAR), "alpha_t": num(fit["t"][0]),
            "loadings": [{"factor": k, "beta": num(fit["coef"][i + 1]), "t": num(fit["t"][i + 1])} for i, k in enumerate(cols)]}


def correlation(returns: dict[str, pd.Series], weeks: int, min_weeks: int) -> dict:
    """Pairwise correlation of weekly returns over the last `weeks` (pairwise complete; None below min_weeks)."""
    syms = list(returns)
    df = pd.concat(returns.values(), axis=1, keys=syms, sort=True).iloc[-weeks:]
    m: list[list[float | None]] = [[None] * len(syms) for _ in syms]
    for i, a in enumerate(syms):
        for j, c in enumerate(syms):
            pair = df[[a, c]].dropna()
            if len(pair) >= min_weeks:
                m[i][j] = 1.0 if i == j else num(pair[a].corr(pair[c]))
    return {"symbols": syms, "weeks": weeks, "matrix": m}


def risk_budget(stop_pct: float | None, risk: float = 0.01) -> float | None:
    """Position size (as a share of the portfolio) at which hitting the stop costs `risk` of the portfolio."""
    if stop_pct is None or not math.isfinite(stop_pct) or stop_pct >= 0:
        return None
    return risk / -stop_pct
