"""A fresh download may only replace what is stored when it isn't less: the same keys (series, areas, tickers),
starting no later, ending no earlier, and not markedly fewer rows.

Free sources sometimes answer with a truncated file, a page cut short or a series missing, without an error.
Replacing the stored copy with that answer would silently lose history that may not come back (or only at the next
good answer, after the dashboard has shown the hole). `check` compares, per key, and either refuses (`Shrunk`, a
ValueError: the update step logs it as failed and keeps its cache) or, with `carry`, keeps the stored values of a
missing key and says so. Nothing is written before the check (`replace`).
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pandas as pd

from .config import write_parquet


class Shrunk(ValueError):
    """The fresh answer has less than what is stored: the stored copy is kept."""


def _spans(df: pd.DataFrame, key: str | None, date: str | None) -> dict:
    """{key: (rows, first, last)}; wide frames (key None, dates as index) per column."""
    if df is None or df.empty:
        return {}
    if key is None:
        out = {}
        for c in df.columns:
            s = df[c].dropna()
            if not s.empty:
                out[str(c)] = (len(s), pd.Timestamp(s.index.min()), pd.Timestamp(s.index.max()))
        return out
    d = pd.to_datetime(df[date]) if date else pd.Series(pd.NaT, index=df.index)
    g = pd.DataFrame({"k": df[key].astype(str), "d": d}).groupby("k")["d"]
    return {k: (int(n), lo, hi) for k, n, lo, hi in zip(g.size().index, g.size(), g.min(), g.max())}


def check(old: pd.DataFrame | None, new: pd.DataFrame, *, what: str, key: str | None = None,
          date: str | None = "date", min_rows: int = 1, row_tol: float = 0.0,
          start_tol: timedelta = timedelta(0), end_tol: timedelta = timedelta(0),
          expected_keys=None, carry: bool = False) -> tuple[pd.DataFrame, list[str]]:
    """(the frame to store, notes). Long frames: `key` names the column that tells series apart (None: one series)
    and `date` the date column. Wide frames (a date index, one column per series): pass `key=None, date=None`.

    Per stored key that is still expected (`expected_keys`, default: all): the fresh one must exist, start no later
    than `start_tol` after the stored start, end no earlier than `end_tol` before the stored end, and have at least
    (1 - row_tol) of the stored rows. A missing key raises, or with `carry` keeps its stored rows (noted)."""
    if new is None or len(new) < min_rows:
        raise Shrunk(f"{what}: {0 if new is None else len(new)} rows in the answer, need {min_rows}: kept the stored copy")
    wide = key is None and date is None
    long_single = key is None and date is not None
    if long_single:   # one series in long form: compare it as a whole
        old_s = {"*": (len(old), pd.to_datetime(old[date]).min(), pd.to_datetime(old[date]).max())} \
            if old is not None and not old.empty else {}
        new_s = {"*": (len(new), pd.to_datetime(new[date]).min(), pd.to_datetime(new[date]).max())}
    else:
        old_s, new_s = _spans(old, key, date), _spans(new, key, date)
    expected = None if expected_keys is None else {str(k) for k in expected_keys}
    problems, notes, carried = [], [], []
    for k, (n, first, last) in old_s.items():
        if expected is not None and k not in expected and k != "*":
            continue                      # no longer configured: may go
        if k not in new_s:
            if carry and not long_single:
                carried.append(k)
                notes.append(f"kept the stored {k} (to {last:%Y-%m-%d}): not in the answer")
                continue
            problems.append(f"{k} missing")
            continue
        n2, first2, last2 = new_s[k]
        if pd.notna(first) and pd.notna(first2) and first2 > first + start_tol:
            problems.append(f"{k} starts {first2:%Y-%m-%d}, stored from {first:%Y-%m-%d}")
        if pd.notna(last) and pd.notna(last2) and last2 < last - end_tol:
            problems.append(f"{k} ends {last2:%Y-%m-%d}, stored to {last:%Y-%m-%d}")
        if n2 < n * (1 - row_tol):
            problems.append(f"{k} has {n2} rows, stored {n}")
    if problems:
        raise Shrunk(f"{what}: the answer has less than what is stored ({'; '.join(problems[:5])}"
                     + (f" and {len(problems) - 5} more" if len(problems) > 5 else "") + "): kept the stored copy")
    if carried:
        if wide:
            new = new.join(old[carried], how="outer")
        else:
            new = pd.concat([new, old[old[key].astype(str).isin(carried)]], ignore_index=True)
    return new, notes


def replace(path: Path, old: pd.DataFrame | None, new: pd.DataFrame, **rules) -> list[str]:
    """`check`, then write (nothing is written when it raises). Returns the notes."""
    out, notes = check(old, new, **rules)
    wide = rules.get("key") is None and rules.get("date", "date") is None
    write_parquet(out, path, **({} if wide else {"index": False}))   # wide frames keep their date index
    return notes
