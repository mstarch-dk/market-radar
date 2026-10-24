"""Rank snapshots, so the report can show what is new, rising or dropping out.

A snapshot is named by its data's date (`asof`: the benchmark's last session), not the day it was taken: a
Saturday run stores Friday's ranks under Friday, and a run on unchanged data (a failed update) adds nothing.
Older snapshots are named by the day they were taken; they are read as they are."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .config import write_parquet
from .paths import SNAPSHOTS


def path(kind: str, asof: date) -> Path:
    return (SNAPSHOTS / f"{asof.isoformat()}_{kind}.parquet").now()


def save(kind: str, df: pd.DataFrame, asof: date) -> bool:
    """Store the ranks of `asof`'s data (df needs columns: ticker, rank, score). A snapshot of that date is
    history and is kept: a second one is skipped. True when this one was written."""
    f = path(kind, asof)
    if f.exists():
        return False
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    write_parquet(df[["ticker", "rank", "score"]].assign(group=df.get("group", df.get("region"))), f, index=False)
    return True


def previous(kind: str, min_gap_days: int, asof: date) -> tuple[date | None, pd.DataFrame | None]:
    """The newest snapshot whose data is at least `min_gap_days` older than `asof`'s."""
    candidates = []
    for p in SNAPSHOTS.glob(f"*_{kind}.parquet"):
        d = date.fromisoformat(p.name[:10])
        if (asof - d).days >= min_gap_days:
            candidates.append((d, p))
    if not candidates:
        return None, None
    d, p = max(candidates)
    return d, pd.read_parquet(p)
