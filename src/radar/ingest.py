"""Incremental price download (yfinance) and macro series (FRED) into local parquet."""
from __future__ import annotations

import io
from datetime import date, timedelta

import pandas as pd
import requests
import yfinance as yf

from .config import DATA, FRED_FILE, PRICES_FILE, settings

COLUMNS = ["date", "ticker", "high", "low", "close", "volume"]
BATCH = 80
OVERLAP_DAYS = 7  # re-fetch a few days to pick up late corrections


def load_prices() -> pd.DataFrame:
    if not PRICES_FILE.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_parquet(PRICES_FILE)


def _download(tickers: list[str], start: date) -> pd.DataFrame:
    frames = []
    for i in range(0, len(tickers), BATCH):
        batch = tickers[i:i + BATCH]
        raw = yf.download(batch, start=start.isoformat(), auto_adjust=True, group_by="ticker",
                          threads=True, progress=False)
        if raw is None or raw.empty:
            continue
        if not isinstance(raw.columns, pd.MultiIndex):
            raw.columns = pd.MultiIndex.from_product([batch, raw.columns])
        for t in batch:
            if t not in raw.columns.get_level_values(0):
                continue
            sub = raw[t].dropna(subset=["Close"])
            if sub.empty:
                continue
            sub = sub.reset_index().rename(columns=str.lower)
            sub["ticker"] = t
            frames.append(sub[COLUMNS])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)


def update_prices(tickers: list[str]) -> dict:
    existing = load_prices()
    last = existing.groupby("ticker")["date"].max() if not existing.empty else pd.Series(dtype="datetime64[ns]")
    new = [t for t in tickers if t not in last.index]
    known = [t for t in tickers if t in last.index]

    fetched = []
    if new:
        start = date.today() - timedelta(days=int(365.25 * settings()["history_years"]))
        fetched.append(_download(new, start))
    if known:
        start = pd.Timestamp(last[known].min()).date() - timedelta(days=OVERLAP_DAYS)
        fetched.append(_download(known, start))

    df = pd.concat([existing, *fetched], ignore_index=True)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    df = df.drop_duplicates(["ticker", "date"], keep="last").sort_values(["ticker", "date"])
    DATA.mkdir(exist_ok=True)
    df.to_parquet(PRICES_FILE, index=False)

    got = set(pd.concat(fetched)["ticker"]) if fetched else set()
    return {"requested": len(tickers), "new": len(new), "missing": sorted(set(tickers) - got - set(known)),
            "rows": len(df)}


def update_fred(series: list[str]) -> None:
    cols = {}
    for sid in series:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
        csv = pd.read_csv(io.StringIO(requests.get(url, timeout=30).text))
        date_col = csv.columns[0]
        cols[sid] = pd.to_numeric(csv.set_index(pd.to_datetime(csv[date_col]))[sid], errors="coerce")
    DATA.mkdir(exist_ok=True)
    pd.DataFrame(cols).to_parquet(FRED_FILE)


def load_fred() -> pd.DataFrame:
    return pd.read_parquet(FRED_FILE) if FRED_FILE.exists() else pd.DataFrame()


def wide(prices: pd.DataFrame, field: str = "close") -> pd.DataFrame:
    """Date x ticker matrix; short gaps (exchange holidays) are forward-filled."""
    return prices.pivot(index="date", columns="ticker", values=field).sort_index().ffill(limit=5)
