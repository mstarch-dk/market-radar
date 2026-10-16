"""The momentum score's percentile rule, once for every caller.

A name's percentile on a column is the share of names with a value that are strictly below it (ties share the
lower value), so the weakest name gets 0 and the strongest 100 x (N-1)/N. The score is the mean of the
percentiles of `COMPONENTS`, missing if any of them is missing. My holdings, ticker profiles, the Momentum and
Discover pages, the regime's momentum payoff, the A/B test, the studies and the proposals all use it."""
from __future__ import annotations

import pandas as pd

COMPONENTS = ("r12_1", "r6m", "r3m")


def pct_below(s: pd.Series) -> pd.Series:
    """0-1: the share of the series' values strictly below each value (missing stays missing)."""
    return (s.rank(method="min") - 1) / s.notna().sum()


def mean_pct(df: pd.DataFrame) -> pd.Series:
    """Mean percentile (0-100) of every column against the names given; missing if any column is missing."""
    return pd.concat([pct_below(df[c]) for c in df.columns], axis=1).mean(axis=1, skipna=False) * 100


def weighted_pct(df: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Weighted mean percentile (0-100) of the columns in `weights`; missing if any of them is missing."""
    tot = sum(weights.values())
    return sum(pct_below(df[c]) * w for c, w in weights.items()) / tot * 100


def score(df: pd.DataFrame) -> pd.Series:
    """0-100, one decimal: the momentum score of every row against the rows given."""
    return mean_pct(df[list(COMPONENTS)]).round(1)


def score_vs(dist: pd.DataFrame, row) -> float | None:
    """One name's momentum score against a distribution it may or may not belong to (`row` maps the components to
    values); None if a component is missing for the name or the distribution has no values for it."""
    vals = []
    for col in COMPONENTS:
        d = dist[col].dropna()
        if pd.isna(row[col]) or d.empty:
            return None
        vals.append((d < row[col]).mean())
    return round(100 * sum(vals) / len(vals), 1)
