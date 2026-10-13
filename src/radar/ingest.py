"""Incremental price download (yfinance) and macro series (FRED) into local parquet."""
from __future__ import annotations

import io
from datetime import date, timedelta

import pandas as pd
import requests
import yfinance as yf

from .config import DATA, FRED_FILE, PRICES_FILE, settings

# high/low/close are adjusted for dividends and splits; raw_close is the traded price (split-adjusted only)
COLUMNS = ["date", "ticker", "high", "low", "close", "raw_close", "volume"]
BATCH = 80
OVERLAP_DAYS = 7  # re-fetch a few days to pick up late corrections
RESCALE_TOL = 1e-5  # relative change in a stored adjusted close that means Yahoo re-based the history


def load_prices() -> pd.DataFrame:
    if not PRICES_FILE.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_parquet(PRICES_FILE)


def _download(tickers: list[str], start: date) -> pd.DataFrame:
    frames = []
    for i in range(0, len(tickers), BATCH):
        batch = tickers[i:i + BATCH]
        raw = yf.download(batch, start=start.isoformat(), auto_adjust=False, group_by="ticker",
                          threads=True, progress=False)
        if raw is None or raw.empty:
            continue
        if not isinstance(raw.columns, pd.MultiIndex):
            raw.columns = pd.MultiIndex.from_product([batch, raw.columns])
        for t in batch:
            if t not in raw.columns.get_level_values(0):
                continue
            sub = raw[t].dropna(subset=["Close", "Adj Close"])
            if sub.empty:
                continue
            frames.append(_adjust(sub.reset_index(), t))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)


def _adjust(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Unadjusted yfinance bars → adjusted high/low/close plus the traded close (same as auto_adjust=True)."""
    factor = raw["Adj Close"] / raw["Close"]
    return pd.DataFrame({"date": raw["Date"], "ticker": ticker, "high": raw["High"] * factor,
                         "low": raw["Low"] * factor, "close": raw["Adj Close"], "raw_close": raw["Close"],
                         "volume": raw["Volume"]})


def rescaled(existing: pd.DataFrame, fresh: pd.DataFrame) -> list[str]:
    """Tickers whose stored adjusted closes no longer match a fresh download on the same dates.

    A new dividend or split makes Yahoo re-base every earlier adjusted price; an incremental fetch only sees
    the overlap window, so the stored history must be downloaded again. The earliest shared date is compared
    because late corrections land on the most recent bars.
    """
    if existing.empty or fresh.empty:
        return []
    both = existing[["ticker", "date", "close"]].merge(fresh[["ticker", "date", "close"]], on=["ticker", "date"],
                                                       suffixes=("_old", "_new"))
    first = both.sort_values("date").groupby("ticker").first()
    changed = (first["close_new"] / first["close_old"] - 1).abs() > RESCALE_TOL
    return sorted(first.index[changed])


def update_prices(tickers: list[str]) -> dict:
    existing = load_prices()
    if not existing.empty:
        existing["date"] = pd.to_datetime(existing["date"])
    if "raw_close" not in existing:  # stored before raw closes were kept: needs a full download
        existing = existing.iloc[0:0].reindex(columns=COLUMNS)
    last = existing.groupby("ticker")["date"].max() if not existing.empty else pd.Series(dtype="datetime64[ns]")
    new = [t for t in tickers if t not in last.index]
    known = [t for t in tickers if t in last.index]
    full_start = date.today() - timedelta(days=int(365.25 * settings()["history_years"]))

    full = _download(new, full_start) if new else pd.DataFrame(columns=COLUMNS)
    inc = pd.DataFrame(columns=COLUMNS)
    rebased: list[str] = []
    if known:
        start = pd.Timestamp(last[known].min()).date() - timedelta(days=OVERLAP_DAYS)
        inc = _norm_dates(_download(known, start))
        rebased = rescaled(existing, inc)
        if rebased:
            inc = inc[~inc["ticker"].isin(rebased)]
            full = pd.concat([full, _download(rebased, full_start)], ignore_index=True)

    full = _norm_dates(full)
    existing = existing[~existing["ticker"].isin(set(full["ticker"]))]  # replaced wholesale, not merged
    df = pd.concat([existing, inc, full], ignore_index=True)
    df = df.drop_duplicates(["ticker", "date"], keep="last").sort_values(["ticker", "date"])
    DATA.mkdir(exist_ok=True)
    df.to_parquet(PRICES_FILE, index=False)

    got = set(inc["ticker"]) | set(full["ticker"])
    return {"requested": len(tickers), "new": len(new), "rebased": rebased,
            "missing": sorted(set(tickers) - got - set(known)), "rows": len(df)}


def _norm_dates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    return df


def update_fred(series: list[str]) -> list[str]:
    """Download each FRED series in full; a series that fails keeps its cached values. Returns the failures."""
    cached = load_fred()
    cols, failed = {}, []
    for sid in series:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            csv = pd.read_csv(io.StringIO(resp.text))
            cols[sid] = pd.to_numeric(csv.set_index(pd.to_datetime(csv[csv.columns[0]]))[sid], errors="coerce")
        except Exception as e:
            failed.append(f"{sid} ({type(e).__name__})")
            if sid in cached:
                cols[sid] = cached[sid]
    if cols:
        DATA.mkdir(exist_ok=True)
        pd.DataFrame(cols).to_parquet(FRED_FILE)
    return failed


def load_fred() -> pd.DataFrame:
    return pd.read_parquet(FRED_FILE) if FRED_FILE.exists() else pd.DataFrame()


def wide(prices: pd.DataFrame, field: str = "close") -> pd.DataFrame:
    """Date x ticker matrix; short gaps (exchange holidays) are forward-filled."""
    return prices.pivot(index="date", columns="ticker", values=field).sort_index().ffill(limit=5)
