"""Discovery signals over the wide universe: the momentum score (same formula as the Momentum page, ranked within
each market), its change over a month, size and liquidity, and flags for names that are starting to move.

Missing inputs give missing outputs (NaN / None), never 0 or False by default."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import momentum, rotation


def scores(closes: pd.DataFrame, volumes: pd.DataFrame, tickers: list[str], min_history: int,
           back: int = 0) -> pd.DataFrame:
    """Momentum metrics and score as they were `back` sessions ago (0 = now)."""
    c = closes.iloc[:len(closes) - back] if back else closes
    v = volumes.iloc[:len(volumes) - back] if back else volumes
    m = momentum.metrics(c, v, tickers, min_history)
    m["score"] = momentum.score(m)
    return m.set_index("ticker")


def traded_value_dkk(raw: pd.DataFrame, volumes: pd.DataFrame, currencies: dict[str, str | None],
                     fx: dict[str, float], days: int = 20) -> pd.Series:
    """Median daily traded value over `days` sessions in DKK (price x volume; GBp prices are pence)."""
    out = {}
    for t in raw.columns:
        ccy = currencies.get(t)
        rate = fx.get("GBP" if ccy == "GBp" else ccy) if ccy else None
        if rate is None or t not in volumes.columns:
            out[t] = np.nan
            continue
        tv = (raw[t] * volumes[t]).dropna().iloc[-days:]
        out[t] = float(tv.median()) * rate / (100 if ccy == "GBp" else 1) if len(tv) else np.nan
    return pd.Series(out, dtype=float)


def size_bucket(cap_dkk, large: float, mid: float) -> str | None:
    if cap_dkk is None or pd.isna(cap_dkk):
        return None
    return "large" if cap_dkk >= large else "mid" if cap_dkk >= mid else "small"


def trend_turn(closes: pd.Series, days: int) -> bool | None:
    """Crossed above its 200-day average within `days` sessions, with the 50-day average rising."""
    s = closes.dropna()
    if len(s) < 200 + days:
        return None
    sma200 = s.rolling(200).mean()
    above = (s > sma200).iloc[-days - 1:]
    sma50 = s.rolling(50).mean()
    return bool(above.iloc[-1] and not above.iloc[0] and sma50.iloc[-1] > sma50.iloc[-days])


def max_move(closes: pd.Series) -> float:
    r = closes.dropna().pct_change().abs()
    return float(r.max()) if len(r.dropna()) else np.nan


def compute(closes: pd.DataFrame, raw: pd.DataFrame, volumes: pd.DataFrame, meta: pd.DataFrame, bench: str,
            fx: dict[str, float], tracked: set[str], cfg: dict, min_history: int, asof: pd.Timestamp,
            rrg_window: int = 14) -> pd.DataFrame:
    """One row per name in `meta` (columns ticker, market, currency, market_cap_dkk, …) with its signals.

    Scores are percentiles within each market, so a Nordic small cap is ranked among Nordic names."""
    fl = cfg["flags"]
    frames = []
    for market, g in meta.groupby("market", sort=False):
        tickers = [t for t in g["ticker"] if t in closes.columns]
        if not tickers:
            continue
        now = scores(closes, volumes, tickers, min_history)
        before = scores(closes, volumes, tickers, min_history, back=fl["d_score_days"])
        now["score_prev"] = before["score"]
        now["d_score"] = now["score"] - now["score_prev"]
        now["market"] = market
        frames.append(now)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames)
    tickers = list(df.index)

    c = closes[tickers]
    df["r1w"] = c.iloc[-1] / c.iloc[-6] - 1 if len(c) > 5 else np.nan
    last_date = c.apply(lambda s: s.last_valid_index())
    df["last_date"] = last_date
    df["stale"] = (asof - pd.to_datetime(last_date)).dt.days > 7

    m = meta.set_index("ticker").reindex(tickers)
    df["liquidity_dkk"] = traded_value_dkk(raw.reindex(columns=tickers), volumes, m["currency"].to_dict(), fx)
    df["thin"] = (df["liquidity_dkk"] < cfg["liquidity_floor_dkk"]).where(df["liquidity_dkk"].notna())
    df["size"] = [size_bucket(v, cfg["size_dkk"]["large"], cfg["size_dkk"]["mid"]) for v in m["market_cap_dkk"]]
    df["new_high"] = ((df["from_high"] >= -1e-9) & (df["vol_surge"] >= fl["new_high_vol"])).where(
        df["from_high"].notna() & df["vol_surge"].notna())
    df["trend_turn"] = [trend_turn(c[t], fl["trend_turn_days"]) for t in tickers]
    moves = pd.Series({t: max_move(c[t].iloc[-260:]) for t in tickers})
    df["check_data"] = moves > cfg["check_data_move"]
    df["off_radar"] = [t not in tracked for t in tickers]

    # relative rotation vs the benchmark (weekly): which names are improving or leading against ACWI
    df["quadrant"] = None
    if bench in closes.columns:
        ok = [t for t in tickers if c[t].dropna().shape[0] >= 130]
        if ok:
            ratio, mom = rotation.rrg(closes[[*ok, bench]].dropna(how="all"), bench, ok, rrg_window, 1)
            df.loc[ok, "quadrant"] = [rotation.quadrant(ratio[t].iloc[-1], mom[t].iloc[-1]) for t in ok]
    df.index.name = "ticker"
    return df.reset_index()


def sparkline(closes: pd.Series, weeks: int = 26) -> list[float]:
    s = closes.dropna()
    if s.empty:
        return []
    w = s.resample("W-FRI").last().dropna().iloc[-weeks:]
    return [float(f"{v:.4g}") for v in w]
