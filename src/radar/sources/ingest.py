"""Incremental price download (yfinance) and macro series (FRED) into local parquet."""
from __future__ import annotations

import io
import json
import re
from datetime import date, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

from .. import guard, locks, net
from ..config import typed, write_parquet, write_text
from ..jsonsafe import dumps
from ..paths import CACHE, FRED_FILE, FRED_ROLLING_FILE, PRICES_FILE

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


def download_bars(tickers: list[str], start: date, progress=None) -> pd.DataFrame:
    """Yahoo daily bars from `start`, in batches; `progress(done, total)` is called after each batch."""
    net.install_yfinance()
    frames, unusable = [], []
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
            if not {"Close", "Adj Close"} <= set(raw[t].columns):
                unusable.append(t)        # skipped (reported as missing); the others still arrive
                continue
            sub = raw[t].dropna(subset=["Close", "Adj Close"])
            if sub.empty:
                continue
            frames.append(adjust(sub.reset_index(), t))
    if unusable and not frames:   # no ticker came with both closes: Yahoo's or yfinance's format changed
        raise ValueError(f"no Close / Adj Close columns in Yahoo's answer ({', '.join(unusable[:5])}…): "
                         "has yfinance changed its download format?")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)


def adjust(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
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
    write_text(f, dumps(d, sort_keys=True))


def update_prices(tickers: list[str], progress=None, start: date | None = None, bench: str | None = None,
                  today: date | None = None) -> dict:
    """Incremental price update (full history for new tickers). `progress(done, total)` reports batches.

    The full history starts `history_years` back, or at `start` when that is earlier (universe.history_start:
    deep enough for your first trade). A stored history that starts later than that is downloaded again in full
    ("deepened"); prices_from.json remembers where each was fetched from, so a ticker listed later than the start
    isn't fetched again every time. A full download never shrinks what is stored (`stitch`): when Yahoo's answer
    starts later or ends earlier, the stored bars beyond it are kept, and a ticker whose answer started late is
    listed in `short` and asked again next time.

    With `bench`, tickers still without a bar on the benchmark's last session are fetched once more and the ones
    left over are returned as `behind` ({ticker: last bar}); `asof` is that session.

    The downloads run without a lock; the store is then re-read and written under `locks.file_lock`, so an update
    started elsewhere meanwhile (the app looking up a ticker, `radar update` in a terminal) isn't overwritten."""
    existing = _load_current()
    legacy = existing.attrs.get("legacy", False)
    last = existing.groupby("ticker")["date"].max() if not existing.empty else pd.Series(dtype="datetime64[ns]")
    new = [t for t in tickers if t not in last.index]
    known = [t for t in tickers if t in last.index]
    full_start = (today or date.today()) - timedelta(days=int(365.25 * typed().history_years))
    if start is not None and start < full_start:
        full_start = start
    fetched_from = _load_from()
    first = existing.groupby("ticker")["date"].min() if not existing.empty else pd.Series(dtype="datetime64[ns]")
    limit = pd.Timestamp(full_start + timedelta(days=OVERLAP_DAYS))
    deepen = known if legacy else [t for t in known if pd.Timestamp(fetched_from.get(t) or first[t]) > limit]
    known = [t for t in known if t not in deepen]

    full = download_bars(new + deepen, full_start, progress) if new or deepen else pd.DataFrame(columns=COLUMNS)
    inc = pd.DataFrame(columns=COLUMNS)
    rebased: list[str] = []
    if known:
        since = pd.Timestamp(last[known].min()).date() - timedelta(days=OVERLAP_DAYS)
        inc = norm_dates(download_bars(known, since, progress))
        rebased = rescaled(existing, inc)
        if rebased:
            inc = inc[~inc["ticker"].isin(rebased)]
            full = pd.concat([full, download_bars(rebased, full_start)], ignore_index=True)
    full = norm_dates(full)

    # Yahoo sometimes answers without the latest session for a whole exchange; ask once more for those
    more = pd.DataFrame(columns=COLUMNS)
    df, _, _ = _merge(existing, full, [inc], limit)
    late = behind(df, tickers, bench)
    if late:
        since = min(date.fromisoformat(d) for d in late.values()) - timedelta(days=OVERLAP_DAYS)
        more = norm_dates(download_bars(sorted(late), since))
        more = more[~more["ticker"].isin(rescaled(df, more))]   # another basis: the next run downloads it in full

    with locks.file_lock(PRICES_FILE, what="the price store is busy: another update is writing it"):
        current = _load_current()        # what is stored now, with anything written while we downloaded
        df, short, reached = _merge(current, full, [inc, more], limit)
        write_parquet(df, PRICES_FILE, index=False)
        _save_from(_load_from() | {t: full_start.isoformat() for t in reached})
    late = behind(df, tickers, bench)

    got = set(inc["ticker"]) | set(full["ticker"])
    return {"requested": len(tickers), "new": len(new), "rebased": rebased, "deepened": len(deepen),
            "missing": sorted(set(tickers) - got - set(known)), "rows": len(df), "behind": late,
            "short": short, "asof": _last(df, bench)}


def _load_current() -> pd.DataFrame:
    """The stored prices with parsed dates. A store from before raw closes were kept gets the column, empty
    (unknown, never 0), and `attrs["legacy"]`: every ticker in it is then downloaded again in full."""
    df = load_prices()
    legacy = not df.empty and "raw_close" not in df
    df = df.reindex(columns=COLUMNS)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    df.attrs["legacy"] = legacy
    return df


def _merge(current: pd.DataFrame, full: pd.DataFrame, upserts: list[pd.DataFrame], limit: pd.Timestamp):
    """(the store, short, reached): full histories stitched onto what is stored (`stitch`), then the incremental
    bars added (the last answer wins). `short`: {ticker: where Yahoo's history starts} when it didn't reach
    `limit` while more was stored, or couldn't be joined at all (the stored history is then kept as it is).
    `reached`: tickers whose stored history now goes as deep as asked (or as deep as the ticker goes)."""
    cur = {t: g for t, g in current.groupby("ticker", sort=False)} if not current.empty else {}
    stitched, short, reached, replaced = [], {}, set(), set()
    for t, g in full.groupby("ticker", sort=False):
        old = cur.get(t, current.iloc[0:0])
        fresh_first = g["date"].min()
        s = stitch(old, g)
        if s is None:
            short[t] = fresh_first.date().isoformat()
            continue
        stitched.append(s)
        replaced.add(t)
        if fresh_first <= limit or old.empty or old["date"].min() >= fresh_first:
            reached.add(t)
        else:
            short[t] = fresh_first.date().isoformat()
    parts = [current[~current["ticker"].isin(replaced)], *stitched, *upserts]
    parts = [x for x in parts if not x.empty]
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=COLUMNS)
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(["ticker", "date"], keep="last").sort_values(["ticker", "date"]).reset_index(drop=True)
    return df, short, reached


def stitch(old: pd.DataFrame, fresh: pd.DataFrame) -> pd.DataFrame | None:
    """One ticker's fresh full history, extended with the stored bars before its first and after its last bar.

    Yahoo's long history can start later or end a session earlier than what an earlier fetch stored; replacing it
    wholesale would lose those bars. They are kept, rescaled to the fresh adjustment basis at the nearest bar both
    have (a dividend or split re-bases every earlier bar by one factor, so the factor at that bar holds for the
    kept ones): adjusted prices by the ratio of adjusted closes, the traded close by the ratio of traded closes,
    volume by its inverse. None: nothing in common while the stored history reaches further (keep it)."""
    if old.empty:
        return fresh
    lo, hi = fresh["date"].min(), fresh["date"].max()
    before, after = old[old["date"] < lo], old[old["date"] > hi]
    if before.empty and after.empty:
        return fresh
    o, f = old.set_index("date"), fresh.set_index("date")
    common = o.index.intersection(f.index)
    if common.empty:
        return None
    parts = [fresh]
    for side, at in ((before, common.min()), (after, common.max())):
        if side.empty:
            continue
        r = _rescale(side, o.loc[at], f.loc[at])
        if r is None:
            return None
        parts.append(r)
    return pd.concat(parts, ignore_index=True).sort_values("date")


def _rescale(rows: pd.DataFrame, old_bar: pd.Series, new_bar: pd.Series) -> pd.DataFrame | None:
    """Stored bars moved to a fresh adjustment basis by the factors at one bar both have; None when the factor
    can't be known (a missing or zero close)."""
    adj = new_bar["close"] / old_bar["close"]
    if not np.isfinite(adj) or adj <= 0:
        return None
    raw = new_bar["raw_close"] / old_bar["raw_close"]
    out = rows.copy()
    for c in ("high", "low", "close"):
        out[c] = out[c] * adj
    if np.isfinite(raw) and raw > 0:
        out["raw_close"] = out["raw_close"] * raw
        out["volume"] = out["volume"] / raw
    return out


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


def norm_dates(df: pd.DataFrame) -> pd.DataFrame:
    """A copy with `date` as naive midnight timestamps (no time zone, no time of day)."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    return df


class Unavailable(RuntimeError):
    """FRED answered with a web page (its maintenance page, say) instead of CSV: the site, not the series, is down."""


def update_fred(series: list[str]) -> list[str]:
    """Download each FRED series in full; a series that fails, or answers with less than is cached (ending
    earlier, fewer values: guard.check), keeps its cached values. Returns the failures.

    A series whose answer starts later than the cache (FRED serves ICE BofA's spreads for ~3 years only, a window
    that rolls forward) is merged into it: fresh values win, the older ones FRED no longer serves are kept, and the
    merged series also goes to FRED_ROLLING_FILE (history: it can't be downloaded again). An HTML answer stops the
    loop: every series left keeps its cached values."""
    cached = load_fred()
    cols, failed, rolling = {}, [], {}
    down: Unavailable | None = None
    for sid in series:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
        try:
            if down:
                raise down
            resp = net.get(url, timeout=30)
            resp.raise_for_status()
            if "html" in resp.headers.get("Content-Type", "").lower():
                raise Unavailable(_html_reason(resp.text))
            s = parse_fred_csv(resp.text, sid)
            if sid in cached:
                old = cached[sid].dropna()
                if not old.empty and s.dropna().index.min() > old.index.min():
                    s = s.combine_first(old)
                    rolling[sid] = s
                guard.check(cached[[sid]], s.to_frame(sid), what=f"FRED {sid}", key=None, date=None, row_tol=0.01)
            cols[sid] = s
            continue
        except Unavailable as e:
            failed.append(f"{sid} (Unavailable)" if down else f"{sid} (Unavailable: {e})")
            down = e
        except Exception as e:
            failed.append(f"{sid} ({type(e).__name__})")
        rolling.pop(sid, None)
        if sid in cached:
            cols[sid] = cached[sid]
    if cols:
        write_parquet(pd.DataFrame(cols), FRED_FILE)
    if rolling:
        kept = pd.read_parquet(FRED_ROLLING_FILE) if FRED_ROLLING_FILE.exists() else pd.DataFrame()
        write_parquet(pd.concat([kept.drop(columns=list(rolling), errors="ignore"), pd.DataFrame(rolling)], axis=1),
                      FRED_ROLLING_FILE)
    return failed


def _html_reason(text: str) -> str:
    title = re.search(r"<title>(.*?)</title>", text, re.I | re.S)
    name = re.sub(r"\s+", " ", title.group(1)).strip(" <") if title else ""
    return f"FRED answered with a web page{f' ({name})' if name else ''}, not CSV"


def parse_fred_csv(text: str, sid: str) -> pd.Series:
    """One series from FRED's graph CSV (date column first, named DATE or observation_date; gaps blank or ".")."""
    if text.lstrip().startswith("<"):
        raise Unavailable(_html_reason(text))
    csv = pd.read_csv(io.StringIO(text))
    if sid not in csv.columns:
        raise ValueError(f"no {sid} column in FRED's CSV (columns: {', '.join(csv.columns)})")
    s = pd.to_numeric(csv[sid], errors="coerce")
    s.index = pd.to_datetime(csv[csv.columns[0]])
    if s.dropna().empty:
        raise ValueError(f"FRED returned no values for {sid}")
    return s


def load_fred() -> pd.DataFrame:
    """The cached series, with the history FRED no longer serves (FRED_ROLLING_FILE) filled in behind them."""
    df = pd.read_parquet(FRED_FILE) if FRED_FILE.exists() else pd.DataFrame()
    if not FRED_ROLLING_FILE.exists():
        return df
    kept = pd.read_parquet(FRED_ROLLING_FILE)
    return df.combine_first(kept)[list(df.columns) + [c for c in kept.columns if c not in df.columns]]


def wide(prices: pd.DataFrame, field: str = "close") -> pd.DataFrame:
    """Date x ticker matrix; short gaps (exchange holidays) are forward-filled."""
    return prices.pivot(index="date", columns="ticker", values=field).sort_index().ffill(limit=5)
