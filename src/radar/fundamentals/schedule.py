"""Which tickers' statements to fetch on a run, and the per-ticker fetch log behind it.

Statements change once a quarter, so each ticker is fetched again when its last fetch is older than `refresh_days`,
when a new report should be out (an earnings date or a quarter after the last period end has passed since the last
fetch), or a day after a failed attempt. Never-fetched names come first, then the oldest; a run takes at most
`max_per_run`, so the first backfill is spread over a few daily updates.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ..config import write_csv

LOG_COLS = ["ticker", "fetched", "ok", "last_end", "n", "error"]


def load_log(path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=LOG_COLS)
    df = pd.read_csv(path, keep_default_na=False, na_values=[""])
    for c in ("fetched", "last_end"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df["ok"] = df["ok"].astype(str).str.lower().isin(["true", "1"])
    return df.reindex(columns=LOG_COLS)


def save_log(path, old: pd.DataFrame, rows: list[dict]) -> None:
    """Replace the attempted tickers' rows (one row per ticker: its last attempt; a failed attempt keeps the last
    good period end)."""
    if not rows:
        return
    new = pd.DataFrame(rows).reindex(columns=LOG_COLS)
    if not old.empty:
        prev = old.set_index("ticker")["last_end"]
        new["last_end"] = [le if pd.notna(le) else prev.get(t) for t, le in zip(new["ticker"], new["last_end"])]
    out = pd.concat([old[~old["ticker"].isin(set(new["ticker"]))], new], ignore_index=True).sort_values("ticker")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(out, path, index=False)


def next_report(last_end, after_days: int) -> pd.Timestamp | None:
    """When the report after the period ending `last_end` should be out: a quarter later plus `after_days`."""
    return None if last_end is None or pd.isna(last_end) else pd.Timestamp(last_end) + timedelta(days=91 + after_days)


def due(tickers: list[str], log: pd.DataFrame, today: date, refresh_days: int,
        expect: dict[str, pd.Timestamp | None] | None = None) -> list[str]:
    """The tickers to fetch, most needed first: never fetched, then (oldest fetch first) stale, failed or with a
    report expected since the last fetch."""
    today = pd.Timestamp(today)
    rows = log.drop_duplicates("ticker", keep="last").set_index("ticker") if not log.empty else pd.DataFrame()
    never, others = [], []
    for t in tickers:
        if t not in rows.index or pd.isna(rows.at[t, "fetched"]):
            never.append(t)
            continue
        fetched = rows.at[t, "fetched"]
        exp = (expect or {}).get(t)
        if ((today - fetched).days >= refresh_days
                or (not rows.at[t, "ok"] and (today - fetched).days >= 1)
                or (exp is not None and pd.notna(exp) and exp <= today and fetched < exp)):
            others.append((fetched, t))
    return never + [t for _, t in sorted(others)]
