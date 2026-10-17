"""The period arithmetic on one ticker's statement facts (fundamentals/store.py's long format), as known on a day.

Every function takes `known_by`, so the same arithmetic gives the live scores and the point-in-time study: TTM
(fiscal year, year to date plus the last year, four quarters), the latest balance, fiscal-year values. How the
scores use it (TTM, market value): guide/laerebog/kvalitetsscore.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

# length of a flow period in days -> its kind (52/53-week years and quarters fit inside the bands)
KINDS = (("Q", 70, 110), ("H", 160, 200), ("9M", 250, 290), ("FY", 340, 390))
# share counts (fundamentals/items.py, unit "shares"): a period's weighted average doesn't add up over quarters
SHARE_COUNTS = frozenset({"diluted_shares", "shares"})


# ---------------- point in time ----------------

def as_known(df: pd.DataFrame, known_by: date | pd.Timestamp | None = None) -> pd.DataFrame:
    """The latest version of each value known by `known_by` (None: now): a restatement filed later doesn't count.
    A restated value is kept twice in the store (two `filed` dates), so any day's view can be rebuilt."""
    if df.empty:
        return df
    if known_by is not None:
        df = df[df["known"] <= pd.Timestamp(known_by)]
    # a period is (start, end) in EDGAR, whatever filing reported it; Yahoo has no start, so its kind (FY, Q, TTM)
    # tells a year from a trailing twelve months ending the same day
    period = df["fp"].where(df["source"] == "yahoo", "")
    return (df.assign(_p=period).sort_values(["known", "filed"], kind="stable", na_position="first")
              .drop_duplicates(["ticker", "source", "item", "_p", "start", "end"], keep="last").drop(columns="_p"))


@dataclass(frozen=True)
class Value:
    value: float
    end: pd.Timestamp
    basis: str                 # fy | ytd | 4q | yahoo_ttm | instant | latest (a share count)
    tag: str | None = None
    currency: str | None = None
    known: pd.Timestamp | None = None


def kind(start, end) -> str | None:
    """Q, H, 9M or FY for a flow period's length; None when it fits none (a 2-month stub, a 15-month year)."""
    if pd.isna(start) or pd.isna(end):
        return None
    days = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
    return next((k for k, lo, hi in KINDS if lo <= days <= hi), None)


@dataclass(frozen=True)
class Row:
    start: pd.Timestamp | None
    end: pd.Timestamp
    value: float
    fp: str | None
    form: str | None
    tag: str | None
    currency: str | None
    known: pd.Timestamp | None
    kind: str | None              # Q, H, 9M, FY for an EDGAR flow; None otherwise


class View:
    """One ticker's facts as known on a day, resolved once and split by item (rows sorted by period end): the
    period arithmetic below runs on plain rows, so scoring hundreds of stocks stays quick."""

    def __init__(self, facts: pd.DataFrame, known_by=None, resolved: bool = False):
        d = facts if resolved else as_known(facts, known_by)     # resolved: as_known was already applied
        self.source = d["source"].iloc[0] if len(d) else None
        self.items: dict[str, list[Row]] = {}
        if d.empty:
            return
        d = d.sort_values(["end", "known"], kind="stable")
        # plain lists, read once: iterating the (Arrow-backed) frame row by row is what made a View slow
        cols = [d["item"].tolist(), pd.to_datetime(d["start"]).tolist(), pd.to_datetime(d["end"]).tolist(),
                d["value"].astype(float).tolist(), *(d[c].tolist() for c in ("fp", "form", "tag", "currency")),
                pd.to_datetime(d["known"]).tolist()]
        kinds: dict = {}
        txt = (lambda v: v if isinstance(v, str) else None)
        for item, start, end, value, fp, form, tag, cur, known in zip(*cols):
            start = None if start is pd.NaT else start
            if start is not None and (start, end) not in kinds:
                kinds[(start, end)] = kind(start, end)
            self.items.setdefault(item, []).append(
                Row(start, end, value, txt(fp), txt(form), txt(tag), txt(cur), None if known is pd.NaT else known,
                    kinds[(start, end)] if start is not None else None))

    def rows(self, item: str) -> list[Row]:
        return self.items.get(item, [])


def view(facts, known_by=None) -> View:
    """`facts` as a View (a View is passed through; `known_by` then must be what it was built with)."""
    return facts if isinstance(facts, View) else View(facts, known_by)


def _val(r: Row, basis: str, value: float | None = None) -> Value:
    return Value(r.value if value is None else float(value), r.end, basis, r.tag, r.currency, r.known)


def _near(a: pd.Timestamp, b: pd.Timestamp, days: int) -> bool:
    return abs((a - b).days) <= days


def _edgar_ttm(rows: list[Row]) -> Value | None:
    """From the latest period end that gives one: the fiscal year when it ends there; else the year to date plus the
    last fiscal year minus the same period a year earlier (10-Q cash flows are reported year to date, and there is
    no Q4 10-Q). A missing piece gives no TTM from that end, never a sum of mismatched periods."""
    rows = [r for r in rows if r.kind]
    if not rows:
        return None
    fy = [r for r in rows if r.kind == "FY"]
    year, day = timedelta(days=364), timedelta(days=1)
    for end in sorted({r.end for r in rows}, reverse=True):        # the latest end that gives a TTM
        at = [r for r in rows if r.end == end]
        hit = [r for r in at if r.kind == "FY"]
        if hit:
            return _val(hit[-1], "fy")
        for ytd in sorted(at, key=lambda r: r.start or pd.Timestamp.min):   # earliest start = the longest year to date
            if ytd.start is None:                                  # never: a row has a kind only with a start
                continue
            start = ytd.start
            prev_fy = [r for r in fy if _near(r.end, start - day, 7)]
            if not prev_fy:
                continue                                           # not a year to date (a discrete quarter)
            prior = [r for r in rows if r.kind == ytd.kind and _near(r.end, ytd.end - year, 20)
                     and r.start is not None and _near(r.start, start - year, 20)]
            if not prior:
                continue
            return _val(ytd, "ytd", prev_fy[-1].value + ytd.value - prior[-1].value)
    return None


def _yahoo_ttm(rows: list[Row]) -> Value | None:
    """Four consecutive quarters summed; else Yahoo's own trailing column (half-year reporters); else the year.
    The latest period end wins."""
    cands: list[tuple[pd.Timestamp, int, Value]] = []
    q = [r for r in rows if r.fp == "Q"][-4:]
    if len(q) == 4 and all(80 <= (b.end - a.end).days <= 100 for a, b in zip(q, q[1:])):
        cands.append((q[-1].end, 0, _val(q[-1], "4q", sum(r.value for r in q))))
    t = [r for r in rows if r.fp == "TTM"]
    if t:
        cands.append((t[-1].end, 1, _val(t[-1], "yahoo_ttm")))
    a = [r for r in rows if r.fp == "FY"]
    if a:
        cands.append((a[-1].end, 2, _val(a[-1], "fy")))
    if not cands:
        return None
    return min(cands, key=lambda c: (-c[0].value, c[1]))[2]     # the latest end; on a tie 4q, then Yahoo's, then FY


def ttm(facts, item: str, known_by=None) -> Value | None:
    """The last twelve months of a flow item for one ticker's facts (one source; a frame or a View), or None. A
    share count (the period's weighted average) doesn't add up over quarters: its latest period's value is used.
    The basis (`Value.basis`) is kept with the value; missing is None, never 0."""
    v = view(facts, known_by)
    rows = v.rows(item)
    if not rows:
        return None
    if item in SHARE_COUNTS:
        length = {"Q": 91, "TTM": 365, "FY": 365}

        def days(r: Row) -> int:
            return (r.end - r.start).days if r.start is not None else length.get(r.fp or "", 400)
        return _val(min(rows, key=lambda r: (-r.end.value, days(r))), "latest")
    return _edgar_ttm(rows) if v.source == "edgar" else _yahoo_ttm(rows)


def instant(facts, item: str, known_by=None, on=None) -> Value | None:
    """The latest balance of an item (on or before `on`, when given), or None."""
    v = view(facts, known_by)
    rows = v.rows(item)
    if v.source == "edgar":
        rows = [r for r in rows if r.start is None]
    if on is not None:
        on = pd.Timestamp(on)
        rows = [r for r in rows if r.end <= on]
    return _val(rows[-1], "instant") if rows else None       # rows are sorted by end, then known


def annual(facts, item: str, known_by=None) -> pd.Series:
    """Fiscal-year values by year end (flows: the year's amount; balances: the year-end balance), oldest first."""
    v = view(facts, known_by)
    if v.source == "edgar":
        rows = [r for r in v.rows(item) if r.kind == "FY" or (r.start is None and r.fp == "FY" and r.form
                                                              and r.form.startswith(("10-K", "20-F", "40-F")))]
    else:
        rows = [r for r in v.rows(item) if r.fp == "FY"]
    if not rows:
        return pd.Series(dtype="float64")
    last = {r.end: r.value for r in rows}                       # sorted by end, then known: the latest version wins
    return pd.Series(last, dtype="float64").sort_index()


def latest_end(facts, known_by=None) -> pd.Timestamp | None:
    """The latest period end a ticker's facts reach (revenue, else any item)."""
    v = view(facts, known_by)
    rows = v.rows("revenue") or [r for rs in v.items.values() for r in rs]
    return max(r.end for r in rows) if rows else None
