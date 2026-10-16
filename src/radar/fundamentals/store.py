"""The fact store: statement values from SEC EDGAR and Yahoo in one long format, and the period arithmetic on top.

One row per value as a source reported it:

    ticker, source (edgar | yahoo), item (items.py), start, end, value, currency, form, fp, filed, known,
    fetched, tag, accn, assumed

`start` is the first day of a flow's period (EDGAR only; Yahoo gives the period's end and its kind in `fp`: FY, Q
or TTM). `known` is the first day the radar could have known the value: for EDGAR the filing date plus a day; for
Yahoo the first day a fetch saw it. Values fetched from Yahoo the first time a ticker is fetched get an assumed
date (`assumed`), since Yahoo doesn't say when they were published; those never feed a test on past data.

A value that is restated is kept twice (two `filed` dates), so the arithmetic below can be done as it was known
on any day: every function takes `known_by` (None: everything known now). Live scores and the point-in-time study
call the same functions.

TTM (the last twelve months) of a flow, from the latest period end that has one:
- EDGAR: the fiscal year when it ends there; else the year to date plus the last fiscal year minus the same
  period a year earlier (10-Q cash flows are reported year to date, and there is no Q4 10-Q). A missing piece
  gives no TTM from that end (never a sum of mismatched periods).
- Yahoo: four consecutive quarters summed; else Yahoo's own trailing column (half-year reporters); else the year.
The basis is kept with the value. Missing is None, never 0.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from ..config import write_parquet
from ..paths import CACHE, HISTORY
from .items import BY_KEY

EDGAR_FILE = CACHE / "fundamentals" / "edgar.parquet"       # can be fetched again from SEC: cache
YAHOO_FILE = HISTORY / "fundamentals" / "yahoo.parquet"     # Yahoo keeps ~4 years: what scrolls out is history

COLS = ["ticker", "source", "item", "start", "end", "value", "currency", "form", "fp", "filed", "known", "fetched",
        "tag", "accn", "assumed"]
DATES = ("start", "end", "filed", "known", "fetched")

# length of a flow period in days -> its kind (52/53-week years and quarters fit inside the bands)
KINDS = (("Q", 70, 110), ("H", 160, 200), ("9M", 250, 290), ("FY", 340, 390))


def empty() -> pd.DataFrame:
    df = pd.DataFrame({c: pd.Series(dtype="object") for c in COLS})
    for c in DATES:
        df[c] = pd.Series(dtype="datetime64[ns]")
    df["value"] = pd.Series(dtype="float64")
    df["assumed"] = pd.Series(dtype="bool")
    return df


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """The columns in order with their types (missing columns added empty)."""
    out = df.reindex(columns=COLS).copy()
    for c in DATES:
        out[c] = pd.to_datetime(out[c])
    out["value"] = pd.to_numeric(out["value"], errors="coerce").astype("float64")
    out["assumed"] = out["assumed"].fillna(False).astype(bool)
    return out


def _read(path) -> pd.DataFrame:
    return normalize(pd.read_parquet(path)) if path.exists() else empty()


def load_edgar() -> pd.DataFrame:
    return _read(EDGAR_FILE)


def load_yahoo() -> pd.DataFrame:
    return _read(YAHOO_FILE)


def save(df: pd.DataFrame, path) -> None:
    out = normalize(df).sort_values(["ticker", "item", "end", "known"], kind="stable")
    write_parquet(out, path, index=False)


# ---------------- point in time ----------------

def as_known(df: pd.DataFrame, known_by: date | pd.Timestamp | None = None) -> pd.DataFrame:
    """The latest version of each value known by `known_by` (None: now): a restatement filed later doesn't count."""
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


def _rows(facts: pd.DataFrame, item: str, known_by) -> pd.DataFrame:
    d = facts[facts["item"] == item]
    return as_known(d, known_by)


def _val(r, basis: str, value: float | None = None) -> Value:
    return Value(float(r["value"] if value is None else value), pd.Timestamp(r["end"]), basis,
                 r.get("tag"), r.get("currency"), r.get("known"))


def _near(s: pd.Series, day, days: int) -> pd.Series:
    return (s - pd.Timestamp(day)).dt.days.abs() <= days


def _edgar_ttm(d: pd.DataFrame) -> Value | None:
    d = d.assign(kind=[kind(s, e) for s, e in zip(d["start"], d["end"])]).dropna(subset=["kind"])
    if d.empty:
        return None
    fy = d[d["kind"] == "FY"]
    year = timedelta(days=364)
    for end in sorted(d["end"].unique(), reverse=True):        # the latest end that gives a TTM
        at = d[d["end"] == end]
        hit = at[at["kind"] == "FY"]
        if not hit.empty:
            return _val(hit.iloc[-1], "fy")
        for _, ytd in at.sort_values("start").iterrows():          # earliest start = the longest year to date
            prev_fy = fy[_near(fy["end"], ytd["start"] - timedelta(days=1), 7)]
            if prev_fy.empty:
                continue                                           # not a year to date (a discrete quarter)
            prior = d[(d["kind"] == ytd["kind"]) & _near(d["end"], ytd["end"] - year, 20)
                      & _near(d["start"], ytd["start"] - year, 20)]
            if prior.empty:
                continue
            p, f = prior.iloc[-1], prev_fy.iloc[-1]
            return _val(ytd, "ytd", f["value"] + ytd["value"] - p["value"])
    return None


def _yahoo_ttm(d: pd.DataFrame) -> Value | None:
    cands: list[tuple[pd.Timestamp, int, Value]] = []
    q = d[d["fp"] == "Q"].sort_values("end").tail(4)
    if len(q) == 4:
        gaps = q["end"].diff().dt.days.dropna()
        if gaps.between(80, 100).all():
            cands.append((q["end"].iloc[-1], 0, _val(q.iloc[-1], "4q", q["value"].sum())))
    t = d[d["fp"] == "TTM"].sort_values("end")
    if not t.empty:
        cands.append((t["end"].iloc[-1], 1, _val(t.iloc[-1], "yahoo_ttm")))
    a = d[d["fp"] == "FY"].sort_values("end")
    if not a.empty:
        cands.append((a["end"].iloc[-1], 2, _val(a.iloc[-1], "fy")))
    if not cands:
        return None
    return min(cands, key=lambda c: (-c[0].value, c[1]))[2]     # the latest end; on a tie 4q, then Yahoo's, then FY


def ttm(facts: pd.DataFrame, item: str, known_by=None) -> Value | None:
    """The last twelve months of a flow item for one ticker's facts (one source), or None. A share count (the
    period's weighted average) doesn't add up over quarters: its latest period's value is used instead."""
    d = _rows(facts, item, known_by)
    if d.empty:
        return None
    if BY_KEY[item].unit == "shares":
        length = (d["end"] - d["start"]).dt.days.fillna(d["fp"].map({"Q": 91, "TTM": 365, "FY": 365}).fillna(400))
        r = d.assign(_len=length).sort_values(["end", "_len"], ascending=[False, True]).iloc[0]
        return _val(r, "latest")
    return _edgar_ttm(d) if d["source"].iloc[0] == "edgar" else _yahoo_ttm(d)


def instant(facts: pd.DataFrame, item: str, known_by=None, on=None) -> Value | None:
    """The latest balance of an item (on or before `on`, when given), or None."""
    d = _rows(facts, item, known_by)
    if d.empty:
        return None
    if d["source"].iloc[0] == "edgar":
        d = d[d["start"].isna()]
    if on is not None:
        d = d[d["end"] <= pd.Timestamp(on)]
    if d.empty:
        return None
    r = d.sort_values(["end", "known"]).iloc[-1]
    return _val(r, "instant")


def annual(facts: pd.DataFrame, item: str, known_by=None) -> pd.Series:
    """Fiscal-year values by year end (flows: the year's amount; balances: the year-end balance), oldest first."""
    d = _rows(facts, item, known_by)
    if d.empty:
        return pd.Series(dtype="float64")
    if d["source"].iloc[0] == "edgar":
        flows = d["start"].notna()
        is_year = pd.Series([kind(s, e) == "FY" for s, e in zip(d["start"], d["end"])], index=d.index)
        d = d[(flows & is_year)
              | (~flows & (d["fp"] == "FY") & d["form"].astype(str).str.startswith(("10-K", "20-F", "40-F")))]
    else:
        d = d[d["fp"] == "FY"]
    if d.empty:
        return pd.Series(dtype="float64")
    s = d.sort_values(["end", "known"]).drop_duplicates("end", keep="last").set_index("end")["value"]
    return s.astype("float64")


def latest_end(facts: pd.DataFrame, known_by=None) -> pd.Timestamp | None:
    """The latest period end a ticker's facts reach (revenue, else any item)."""
    d = as_known(facts, known_by)
    if d.empty:
        return None
    rev = d[d["item"] == "revenue"]
    return pd.Timestamp((rev if not rev.empty else d)["end"].max())
