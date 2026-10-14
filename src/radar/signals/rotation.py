"""Relative strength vs the benchmark and a Relative Rotation Graph (RRG) approximation.

RS-Ratio: how strong the relative trend is: the (lightly smoothed) RS line as a ratio to its own moving average,
centred on 100. RS-Momentum: whether that relative trend is accelerating: RS-Ratio as a ratio to its own
exponential average, centred on 100. (The commercial JdK formula is unpublished; this is an approximation.)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

QUADRANTS = {  # (ratio > 100, momentum > 100) -> name
    (True, True): "Leading",
    (True, False): "Weakening",
    (False, False): "Lagging",
    (False, True): "Improving",
}


def rrg(closes: pd.DataFrame, bench: str, tickers: list[str], window: int, tail: int):
    weekly = closes[[*tickers, bench]].resample("W-FRI").last().dropna(subset=[bench])
    rs = weekly[tickers].div(weekly[bench], axis=0).ewm(span=3).mean()   # light smoothing of weekly noise
    ratio = 100 * rs / rs.rolling(window).mean()                          # >100: outperforming its recent norm
    mom = 100 * ratio / ratio.ewm(span=window // 2).mean()               # >100: relative trend accelerating
    return ratio.iloc[-tail:], mom.iloc[-tail:]


def quadrant(ratio: float, mom: float) -> str:
    if np.isnan(ratio) or np.isnan(mom):
        return "n/a"
    return QUADRANTS[(ratio > 100, mom > 100)]


def _ret(closes: pd.DataFrame, n: int) -> pd.Series:
    return closes.iloc[-1] / closes.iloc[-1 - n] - 1


def relative_table(closes: pd.DataFrame, bench: str, instruments, window: int, tail: int) -> pd.DataFrame:
    tickers = [i.ticker for i in instruments if i.ticker in closes.columns]
    ratio, mom = rrg(closes, bench, tickers, window, tail)
    b = closes[bench].dropna()
    rows = []
    for inst in instruments:
        t = inst.ticker
        if t not in tickers:
            continue
        s = closes[t].dropna()
        if len(s) < 130:
            continue
        bs = b[:s.index[-1]]  # same end date: a ticker that stopped updating isn't measured against newer bench gains
        rel = {f"rel_{col}": s.iloc[-1] / s.iloc[-1 - n] - bs.iloc[-1] / bs.iloc[-1 - n]
               for col, n in (("r1m", 21), ("r3m", 63), ("r6m", 126))}
        rows.append({
            "ticker": t, "name": inst.name, "group": inst.group, "ucits": inst.ucits, "isin": inst.isin, "ucits_name": inst.ucits_name,
            "r1m": s.iloc[-1] / s.iloc[-22] - 1,
            "r3m": s.iloc[-1] / s.iloc[-64] - 1,
            "r6m": s.iloc[-1] / s.iloc[-127] - 1,
            "above200": bool(s.iloc[-1] > s.iloc[-200:].mean()),
            "rs_ratio": ratio[t].iloc[-1], "rs_mom": mom[t].iloc[-1], **rel,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["quadrant"] = [quadrant(r, m) for r, m in zip(df["rs_ratio"], df["rs_mom"])]
    # composite relative-strength score used for ranking (weights favour 3-6 months)
    df["rs_score"] = 0.2 * df["rel_r1m"] + 0.4 * df["rel_r3m"] + 0.4 * df["rel_r6m"]
    df["rank"] = df.groupby("group")["rs_score"].rank(ascending=False).astype(int)
    return df.sort_values(["group", "rank"])
