"""Rank snapshots, so the report can show what is new, rising or dropping out."""
from __future__ import annotations

from datetime import date

import pandas as pd

from .config import write_parquet
from .paths import SNAPSHOTS


def save(kind: str, df: pd.DataFrame, today: date | None = None) -> None:
    """df needs columns: ticker, rank, score."""
    today = today or date.today()
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOTS / f"{today.isoformat()}_{kind}.parquet"
    write_parquet(df[["ticker", "rank", "score"]].assign(group=df.get("group", df.get("region"))), path, index=False)


def previous(kind: str, min_gap_days: int, today: date | None = None) -> tuple[date | None, pd.DataFrame | None]:
    today = today or date.today()
    candidates = []
    for p in SNAPSHOTS.glob(f"*_{kind}.parquet"):
        d = date.fromisoformat(p.name[:10])
        if (today - d).days >= min_gap_days:
            candidates.append((d, p))
    if not candidates:
        return None, None
    d, p = max(candidates)
    return d, pd.read_parquet(p)
