"""Incremental price download (yfinance) and macro series (FRED) into local parquet."""
from __future__ import annotations

import io
import json
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from . import net
from .config import settings, write_parquet
from .paths import CACHE, FRED_FILE, PRICES_FILE

# high/low/close are adjusted for dividends and splits; raw_close is the traded price (split-adjusted only)
COLUMNS = ["date", "ticker", "high", "low", "close", "raw_close", "volume"]
BATCH = 80
OVERLAP_DAYS = 7  # re-fetch a few days to pick up late corrections
RESCALE_TOL = 1e-5  # relative change in a stored adjusted close that means Yahoo re-based the history
FROM_FILE = "prices_from.json"  # ticker -> the start its stored history was last downloaded in full from


def load_prices() -> pd.DataFrame:
    if not PRICES_FILE.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_parquet(PRICES_FILE)


def _download(tickers: list[str], start: date, progress=None) -> pd.DataFrame:
    """Yahoo daily bars from `start`, in batches; `progress(done, total)` is called after each batch."""
    net.install_yfinance()
    frames = []
    for i in range(0, len(tickers), BATCH):
        batch = tickers[i:i + BATCH]
        if progress:
            progress(i, len(tickers))
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


def _load_from() -> dict[str, str]:
    f = CACHE / FROM_FILE
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except ValueError:
        return {}


def _save_from(d: dict[str, str]) -> None:
    f = CACHE / FROM_FILE
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, sort_keys=True), encoding="utf-8")
    tmp.replace(f)


def update_prices(tickers: list[str], progress=None, start: date | None = None, bench: str | None = None) -> dict:
    """Incremental price update (full history for new tickers). `progress(done, total)` reports batches.

    The full history starts `history_years` back, or at `start` when that is earlier (universe.history_start:
    deep enough for your first trade). A stored history that starts later than that is downloaded again in full
    ("deepened"); prices_from.json remembers where each was fetched from, so a ticker listed later than the start
    isn't fetched again every time.

    With `bench`, tickers still without a bar on the benchmark's last session are fetched once more and the ones
    left over are returned as `behind` ({ticker: last bar}); `asof` is that session."""
    existing = load_prices()
    if not existing.empty:
        existing["date"] = pd.to_datetime(existing["date"])
    if "raw_close" not in existing:  # stored before raw closes were kept: needs a full download
        existing = existing.iloc[0:0].reindex(columns=COLUMNS)
    last = existing.groupby("ticker")["date"].max() if not existing.empty else pd.Series(dtype="datetime64[ns]")
    new = [t for t in tickers if t not in last.index]
    known = [t for t in tickers if t in last.index]
    full_start = date.today() - timedelta(days=int(365.25 * settings()["history_years"]))
    if start is not None and start < full_start:
        full_start = start
    fetched_from = _load_from()
    first = existing.groupby("ticker")["date"].min() if not existing.empty else pd.Series(dtype="datetime64[ns]")
    limit = pd.Timestamp(full_start + timedelta(days=OVERLAP_DAYS))
    deepen = [t for t in known if pd.Timestamp(fetched_from.get(t) or first[t]) > limit]
    known = [t for t in known if t not in deepen]

    full = _download(new + deepen, full_start, progress) if new or deepen else pd.DataFrame(columns=COLUMNS)
    inc = pd.DataFrame(columns=COLUMNS)
    rebased: list[str] = []
    if known:
        since = pd.Timestamp(last[known].min()).date() - timedelta(days=OVERLAP_DAYS)
        inc = _norm_dates(_download(known, since, progress))
        rebased = rescaled(existing, inc)
        if rebased:
            inc = inc[~inc["ticker"].isin(rebased)]
            full = pd.concat([full, _download(rebased, full_start)], ignore_index=True)

    full = _norm_dates(full)
    full = pd.concat([full, kept_after(existing, full)], ignore_index=True)
    existing = existing[~existing["ticker"].isin(set(full["ticker"]))]  # replaced wholesale, not merged
    df = pd.concat([existing, inc, full], ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(["ticker", "date"], keep="last").sort_values(["ticker", "date"])

    # Yahoo sometimes answers without the latest session for a whole exchange; ask once more for those
    late = behind(df, tickers, bench)
    if late:
        since = min(date.fromisoformat(d) for d in late.values()) - timedelta(days=OVERLAP_DAYS)
        more = _norm_dates(_download(sorted(late), since))
        more = more[~more["ticker"].isin(rescaled(df, more))]   # another basis: the next run downloads it in full
        df = pd.concat([df, more], ignore_index=True)
        df = df.drop_duplicates(["ticker", "date"], keep="last").sort_values(["ticker", "date"])
        late = behind(df, tickers, bench)
    write_parquet(df, PRICES_FILE, index=False)

    got = set(inc["ticker"]) | set(full["ticker"])
    _save_from(fetched_from | {t: full_start.isoformat() for t in set(full["ticker"])})
    return {"requested": len(tickers), "new": len(new), "rebased": rebased, "deepened": len(deepen),
            "missing": sorted(set(tickers) - got - set(known)), "rows": len(df), "behind": late,
            "asof": _last(df, bench)}


def kept_after(existing: pd.DataFrame, fresh: pd.DataFrame) -> pd.DataFrame:
    """Stored bars newer than a full download's last bar, where both agree on that bar's adjusted close.

    Yahoo's long history can end a session earlier than what an earlier fetch already stored; replacing the
    history wholesale would lose those bars. On another adjustment basis they're dropped (the catch-up fetch
    then gets them on the new one)."""
    if existing.empty or fresh.empty:
        return existing.iloc[0:0]
    end = fresh.groupby("ticker")["date"].max()
    old = existing[existing["ticker"].isin(end.index)]
    newer = old[old["date"] > old["ticker"].map(end)]
    if newer.empty:
        return newer
    at_end = old.merge(fresh[["ticker", "date", "close"]], on=["ticker", "date"], suffixes=("_old", "_new"))
    at_end = at_end[at_end["date"] == at_end["ticker"].map(end)]
    same = at_end.loc[(at_end["close_new"] / at_end["close_old"] - 1).abs() <= RESCALE_TOL, "ticker"]
    return newer[newer["ticker"].isin(set(same))]


def _last(df: pd.DataFrame, ticker: str | None) -> str | None:
    d = df.loc[df["ticker"] == ticker, "date"] if ticker else df.iloc[0:0]["date"]
    return pd.Timestamp(d.max()).date().isoformat() if not d.empty else None


def behind(df: pd.DataFrame, tickers: list[str], bench: str | None) -> dict[str, str]:
    """{ticker: its last bar} for tickers without a bar on the benchmark's last session (an exchange holiday,
    or Yahoo doesn't have it yet). Tickers with no prices at all are `missing`, not behind."""
    ref = _last(df, bench)
    if ref is None:
        return {}
    last = df[df["ticker"].isin(set(tickers))].groupby("ticker")["date"].max()
    return {t: pd.Timestamp(d).date().isoformat() for t, d in last.items() if d < pd.Timestamp(ref)}


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
            resp = net.get(url, timeout=30)
            resp.raise_for_status()
            cols[sid] = parse_fred_csv(resp.text, sid)
        except Exception as e:
            failed.append(f"{sid} ({type(e).__name__})")
            if sid in cached:
                cols[sid] = cached[sid]
    if cols:
        write_parquet(pd.DataFrame(cols), FRED_FILE)
    return failed


def parse_fred_csv(text: str, sid: str) -> pd.Series:
    """One series from FRED's graph CSV (date column first, named DATE or observation_date; gaps blank or ".")."""
    csv = pd.read_csv(io.StringIO(text))
    if sid not in csv.columns:
        raise ValueError(f"no {sid} column in FRED's CSV (columns: {', '.join(csv.columns)})")
    s = pd.to_numeric(csv[sid], errors="coerce")
    s.index = pd.to_datetime(csv[csv.columns[0]])
    if s.dropna().empty:
        raise ValueError(f"FRED returned no values for {sid}")
    return s


def load_fred() -> pd.DataFrame:
    return pd.read_parquet(FRED_FILE) if FRED_FILE.exists() else pd.DataFrame()


def wide(prices: pd.DataFrame, field: str = "close") -> pd.DataFrame:
    """Date x ticker matrix; short gaps (exchange holidays) are forward-filled."""
    return prices.pivot(index="date", columns="ticker", values=field).sort_index().ffill(limit=5)
