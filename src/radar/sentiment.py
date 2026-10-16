"""Sentiment: CBOE's daily put/call ratios and the AAII weekly investor survey. Both are free and keyless;
neither feeds the regime vote (they are contrarian readings shown on Positioning & cycle).
"""
from __future__ import annotations

import io
import time
from datetime import date, timedelta

import pandas as pd

from . import guard, net
from .config import settings, write_parquet
from .paths import CACHE, HISTORY

PUTCALL_FILE = HISTORY / "putcall.parquet"   # the backfill only reaches a year back
AAII_FILE = CACHE / "aaii.parquet"

CBOE_URL = "https://cdn.cboe.com/data/us/options/market_statistics/daily/{d:%Y-%m-%d}_daily_options"
CBOE_RATIOS = {"TOTAL PUT/CALL RATIO": "total", "EQUITY PUT/CALL RATIO": "equity", "INDEX PUT/CALL RATIO": "index"}
AAII_URL = "https://www.aaii.com/files/surveys/sentiment.xls"


# ---------------- CBOE put/call ----------------

def parse_cboe(data: dict) -> dict:
    """One day's market statistics → {total, equity, index}. The total ratio must be there."""
    ratios = {CBOE_RATIOS[r["name"]]: float(r["value"]) for r in data.get("ratios", []) if r.get("name") in CBOE_RATIOS
              and r.get("value") not in (None, "")}
    if "total" not in ratios:
        raise ValueError("no TOTAL PUT/CALL RATIO in CBOE's daily statistics: has the format changed?")
    if not all(0.05 < v < 10 for v in ratios.values()):
        raise ValueError(f"put/call ratios out of range: {ratios}")
    return ratios


def load_putcall() -> pd.DataFrame:
    return pd.read_parquet(PUTCALL_FILE) if PUTCALL_FILE.exists() else pd.DataFrame(columns=["date", "total", "equity", "index"])


def update_putcall(today: date | None = None, get=None, sleep=time.sleep) -> str:
    """Fetch every weekday since the last stored one (a year back on the first run), and any weekday in the last
    `sentiment.putcall_retry_days` that isn't stored (a day CBOE hadn't published yet, or refused, is asked again
    instead of staying a hole). A missing day (holiday, not yet published) is skipped; nothing new for a week of
    weekdays means the source has moved: raise. A failure part-way stores the days already fetched, then raises
    `PartialFailure`."""
    from .coverage import PartialFailure

    today = today or date.today()
    get = get or (lambda url: net.get(url, timeout=30, expected=(403, 404)))
    cfg = settings()["sentiment"]
    old = load_putcall()
    have = set(pd.to_datetime(old["date"]).dt.date) if not old.empty else set()
    last = max(have) if have else None
    start = (min(last + timedelta(days=1), today - timedelta(days=cfg.get("putcall_retry_days", 10))) if last
             else today - timedelta(days=cfg["putcall_backfill_days"]))
    days = [d.date() for d in pd.bdate_range(start, today) if d.date() not in have]
    rows, failed = [], None
    for d in days:
        try:
            r = get(CBOE_URL.format(d=d))
            if r.status_code in (403, 404):
                continue
            r.raise_for_status()
            rows.append({"date": pd.Timestamp(d)} | parse_cboe(r.json()))
        except Exception as e:  # keep what came before it; say what failed
            failed = (d, e)
            break
        sleep(0.15)
    new_days = [d for d in days if last is None or d > last]
    if not rows and failed is None and len(new_days) >= 5:
        raise ValueError(f"no CBOE statistics for any of the last {len(new_days)} weekdays: has the address changed?")
    if rows:
        df = pd.concat([old, pd.DataFrame(rows)], ignore_index=True) if not old.empty else pd.DataFrame(rows)
        df = df.drop_duplicates("date", keep="last").sort_values("date")
        write_parquet(df, PUTCALL_FILE, index=False)
    newest = max([r["date"] for r in rows] + ([pd.Timestamp(last)] if last else []), default=None)
    msg = f"{len(rows)} new days" + (f", latest {newest:%d %b}" if newest is not None else "")
    if failed:
        d, e = failed
        raise PartialFailure(f"{msg}; stopped at {d}: {type(e).__name__}: {e}") from e
    return msg


# ---------------- AAII sentiment survey ----------------

def parse_aaii(content: bytes, min_rows: int = 1000) -> pd.DataFrame:
    """AAII's sentiment.xls: weekly bullish / neutral / bearish shares (fractions) since 1987."""
    if content.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
        raise ValueError("AAII answered with a web page, not the spreadsheet (a bot check after many requests?): "
                         "try again later")
    raw = pd.read_excel(io.BytesIO(content), sheet_name="SENTIMENT", header=None)
    head = None
    for i in range(min(10, len(raw))):
        cells = [str(v).strip() for v in raw.iloc[i, :4]]
        if cells[1:4] == ["Bullish", "Neutral", "Bearish"]:
            head = i
            break
    if head is None:
        raise ValueError("no Bullish / Neutral / Bearish header in AAII's sheet: has the file changed?")
    body = raw.iloc[head + 1:, :4]
    df = pd.DataFrame({"date": pd.to_datetime(body[0], errors="coerce", format="mixed"),
                       "bullish": pd.to_numeric(body[1], errors="coerce"),
                       "neutral": pd.to_numeric(body[2], errors="coerce"),
                       "bearish": pd.to_numeric(body[3], errors="coerce")}).dropna()
    if len(df) < min_rows:
        raise ValueError(f"only {len(df)} weekly AAII rows: has the file changed?")
    total = df[["bullish", "neutral", "bearish"]].sum(axis=1)
    if not total.between(0.97, 1.03).all():
        raise ValueError("AAII shares don't add up to 100%: a unit change in the file?")
    return df.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def load_aaii() -> pd.DataFrame:
    return pd.read_parquet(AAII_FILE) if AAII_FILE.exists() else pd.DataFrame(columns=["date", "bullish", "neutral", "bearish"])


def update_aaii() -> str:
    resp = net.get(AAII_URL, timeout=60)
    resp.raise_for_status()
    df = parse_aaii(resp.content)
    guard.replace(AAII_FILE, load_aaii(), df, what="AAII", key=None, date="date", row_tol=0.01)
    last = df.iloc[-1]
    return f"{len(df):,} weeks; {last['date']:%d %b}: bull {last['bullish']:.0%}, bear {last['bearish']:.0%}"
