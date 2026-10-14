"""Technical indicators for the ticker profile: pure functions on a price series (adjusted closes)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .risk import weekly

TRADING_DAYS = 252


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder's relative strength index (0-100), seeded with a simple average of the first n changes as on
    most charting sites. A series that only rises is 100, one that only falls is 0, a flat one 50."""
    c = close.dropna()
    d = c.diff().to_numpy()
    out = np.full(len(c), np.nan)
    if len(c) > n:
        up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
        ag, al = up[1:n + 1].mean(), dn[1:n + 1].mean()
        for i in range(n, len(c)):
            if i > n:
                ag, al = (ag * (n - 1) + up[i]) / n, (al * (n - 1) + dn[i]) / n
            out[i] = 50.0 if ag == al == 0 else 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return pd.Series(out, index=c.index).reindex(close.index)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD line (fast EMA - slow EMA), its signal EMA and the histogram, in price units."""
    line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    sig = line.ewm(span=signal, adjust=False).mean()
    out = pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})
    return out.where(close.notna().cumsum() >= slow)


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    """Bands at k standard deviations around the n-day mean; %B = 0 at the lower band, 1 at the upper."""
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std(ddof=0)
    upper, lower = mid + k * sd, mid - k * sd
    width = (upper - lower).replace(0, np.nan)
    return pd.DataFrame({"mid": mid, "upper": upper, "lower": lower, "pct_b": (close - lower) / width})


def realised_vol(close: pd.Series, n: int = 63) -> float:
    """Annualised standard deviation of daily log returns over the last n sessions."""
    r = np.log(close.dropna()).diff().dropna().iloc[-n:]
    return float(r.std(ddof=1) * np.sqrt(TRADING_DAYS)) if len(r) >= max(n // 2, 2) else float("nan")


def max_drawdown(close: pd.Series, n: int = TRADING_DAYS) -> float:
    """Largest peak-to-trough fall within the last n sessions (negative fraction)."""
    c = close.dropna().iloc[-n:]
    return float((c / c.cummax() - 1).min()) if len(c) > 1 else float("nan")


def beta_corr(close: pd.Series, bench: pd.Series, weeks: int = 52) -> tuple[float, float]:
    """Beta and correlation against the benchmark on weekly (Friday) returns over `weeks` (complete weeks only;
    see risk.weekly)."""
    w = pd.concat([weekly(close), weekly(bench)], axis=1, keys=["x", "b"], sort=True).dropna().iloc[-weeks:]
    if len(w) < 26 or w["b"].var() == 0:
        return float("nan"), float("nan")
    beta = w["x"].cov(w["b"]) / w["b"].var()
    return float(beta), float(w["x"].corr(w["b"]))
