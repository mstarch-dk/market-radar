"""Stock momentum metrics and a composite score (percentile rank within each region)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def metrics(closes: pd.DataFrame, volumes: pd.DataFrame, tickers: list[str], min_history: int) -> pd.DataFrame:
    tickers = [t for t in tickers if t in closes.columns]
    c = closes[tickers].iloc[-260:]
    v = volumes.reindex(columns=tickers).iloc[-120:]
    last = c.iloc[-1]

    def back(n: int) -> pd.Series:
        return c.iloc[-1 - n] if len(c) > n else pd.Series(np.nan, index=tickers)

    df = pd.DataFrame({
        "last": last,
        "r1m": last / back(21) - 1,
        "r3m": last / back(63) - 1,
        "r6m": last / back(126) - 1,
        "r12_1": back(21) / back(252) - 1,          # classic 12-month momentum, skipping the last month
        "from_high": last / c.iloc[-252:].max() - 1,
        "sma50": c.iloc[-50:].mean(),
        "sma200": c.iloc[-200:].mean(),
        "vol_surge": v.iloc[-20:].mean() / v.mean(),
        "history": c.notna().sum(),
    })
    df.loc[df["history"] < min_history, ["r12_1", "sma200"]] = np.nan
    df["above50"] = df["last"] > df["sma50"]
    df["above200"] = (df["last"] > df["sma200"]).where(df["sma200"].notna())
    df["trend_ok"] = (df["above200"].eq(True) & (df["sma50"] > df["sma200"])).where(df["sma200"].notna())
    df.index.name = "ticker"
    return df.reset_index()


def score(df: pd.DataFrame) -> pd.Series:
    """0-100: mean percentile of 12-1, 6m and 3m returns (higher = stronger momentum)."""
    ranks = df[["r12_1", "r6m", "r3m"]].rank(pct=True)
    return (ranks.mean(axis=1, skipna=False) * 100).round(1)


def leaders(closes, volumes, groups: dict[str, list[str]], min_history: int) -> pd.DataFrame:
    frames = []
    for region, tickers in groups.items():
        m = metrics(closes, volumes, tickers, min_history)
        m["region"] = region
        m["score"] = score(m)
        m["rank"] = m["score"].rank(ascending=False, method="first")
        frames.append(m)
    return pd.concat(frames, ignore_index=True).sort_values(["region", "rank"])


def metrics_panel(closes: pd.DataFrame, tickers: list[str], min_history: int) -> dict[str, pd.DataFrame]:
    """`metrics` for every day at once: date x ticker frames whose row D equals `metrics(closes.loc[:D])` (for
    the columns that don't need volumes). For point-in-time backtests (backtest/pit.py)."""
    c = closes[[t for t in tickers if t in closes.columns]]

    def back(n: int) -> pd.DataFrame:
        return c.shift(n)

    history = c.notna().astype(float).rolling(260, min_periods=1).sum()
    short = history < min_history
    p = {"last": c, "r1m": c / back(21) - 1, "r3m": c / back(63) - 1, "r6m": c / back(126) - 1,
         "r12_1": (back(21) / back(252) - 1).mask(short), "from_high": c / c.rolling(252, min_periods=1).max() - 1,
         "sma50": c.rolling(50, min_periods=1).mean(), "sma200": c.rolling(200, min_periods=1).mean().mask(short),
         "history": history}
    p["above50"] = c > p["sma50"]
    p["above200"] = (c > p["sma200"]).where(p["sma200"].notna())
    p["trend_ok"] = ((c > p["sma200"]) & (p["sma50"] > p["sma200"])).where(p["sma200"].notna())
    return p
