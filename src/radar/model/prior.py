"""The long-run prior for a proposal tilt: what decades of survivorship-free portfolios say about the tilt's edge.
propose.py shrinks the rule study's mean toward it; `radar study longrun` reports it for every tilt.

JKP's tercile portfolios per characteristic (factors.py) give the long-only edge of a characteristic: the top
tercile less the mean of the three. A tilt's weights on the momentum score and K+V are spread over those
characteristics (`prior_weights`) and the weighted edge over H months is one number with a Newey-West standard
error (`tilt_prior`), also split by the region's trend when the window began."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..sources import factors
from .stats import nw_t


def window(r: pd.DataFrame, months: int, skip: int = 0) -> pd.DataFrame:
    """Compounded return over `months` months ending `skip` months before each date; missing when any month in the
    window is missing."""
    lg = np.log1p(r)
    return np.expm1(lg.rolling(months, min_periods=months).sum().shift(skip))


def tercile_excess(p: pd.DataFrame, months: int) -> pd.Series:
    """Compounded return of the top tercile ("3") over `months` months ending at each date, less that of the mean
    of the three terciles (the region's stocks with the same weighting): the long-only edge of the characteristic."""
    if p.empty or not {"1", "2", "3"} <= set(p.columns):
        return pd.Series(dtype=float)
    p = p[["1", "2", "3"]]
    top = window(p[["3"]], months)["3"]
    avg = window(p.mean(axis=1, skipna=False).to_frame("a"), months)["a"]
    return top - avg


def _stats(s: pd.Series, months: int) -> dict | None:
    s = s.dropna()
    if len(s) < max(24, 2 * months):
        return None
    t = nw_t(s.tolist(), max(months - 1, 0))
    mean = float(s.mean())
    return {"mean": mean, "t": t, "se": abs(mean / t) if t else None, "months": int(len(s)),
            "eff_n": round(len(s) / months, 1), "first": s.index[0], "last": s.index[-1]}


def tilt_prior(weights: dict[str, float], months: int, region: str, data: pd.DataFrame | None = None,
               since=None, trend_months: int = 10) -> dict | None:
    """The long-run evidence for a tilt as one number: the weighted mean of the characteristics' top-tercile
    excess (`tercile_excess`) over `months` months in JKP's `region`, from `since` on, with its Newey-West standard
    error, and the same split by the region's trend at the start of each window (the terciles' mean above or below
    its `trend_months`-month average). None when a characteristic is missing."""
    data = factors.load() if data is None else data
    parts, comps = [], {}
    for ch, w in weights.items():
        if not w:
            continue
        x = tercile_excess(factors.panel(f"jkp_pf:{region}:{ch}", data), months)
        if x.empty:
            return None
        if since is not None:
            x = x[x.index >= pd.Timestamp(since)]
        comps[ch] = float(x.mean()) if x.notna().any() else None
        parts.append(x * w)
    if not parts:
        return None
    total_w = sum(w for w in weights.values() if w)
    s = pd.concat(parts, axis=1).sum(axis=1, min_count=len(parts)) / total_w
    out = _stats(s, months)
    if out is None:
        return None
    first = next(ch for ch, w in weights.items() if w)
    mkt = factors.panel(f"jkp_pf:{region}:{first}", data)[["1", "2", "3"]].mean(axis=1, skipna=False)
    level = (1 + mkt).cumprod()
    up = (level >= level.rolling(trend_months, min_periods=trend_months).mean()).where(
        level.rolling(trend_months).count() >= trend_months)
    start = up.shift(months).reindex(s.index)        # the trend when the window began
    out["by_trend"] = {lbl: _stats(s[start == v], months) for lbl, v in (("up", True), ("down", False))}
    out |= {"region": region, "horizon": months, "since": since, "weights": weights, "components": comps}
    return out


def prior_weights(tilt_weights: dict[str, float], components: dict[str, list[str]], qv: dict[str, float]) -> dict:
    """The tilt's weights on the momentum score and K+V spread over JKP characteristics: momentum's over
    `components["momentum"]`, K+V's over value and quality (`qv`) and then their characteristics, equally."""
    out: dict[str, float] = {}

    def spread(chars, w):
        for ch in chars or []:
            out[ch] = out.get(ch, 0) + w / len(chars)
    spread(components.get("momentum"), float(tilt_weights.get("momentum", 0)))
    for part, share in (qv or {}).items():
        spread(components.get(part), float(tilt_weights.get("qv", 0)) * float(share))
    return {k: v for k, v in out.items() if v}
