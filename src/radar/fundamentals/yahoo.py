"""Financial statements from Yahoo (yfinance): income statement and cash flow per year, per quarter and Yahoo's
trailing twelve months, and the balance sheet per year and quarter, for every tracked stock (Europe, the Nordics
and Asia have no EDGAR).

Yahoo shows about four years and five quarters, so what scrolls out of its window can't be fetched again: the
values are kept in the history tier, append-only. A value is stored once per change: a later fetch that sees the
same number adds nothing, a changed one (a restatement) is added with the day it was first seen. Values seen in a
ticker's first fetch get an assumed publication date (the period end plus `assumed_lag_days`) and are marked; they
feed the live scores, never a test on past data.

Yahoo gives the values in the company's reporting currency without naming it; the currency is taken from the
weekly valuation snapshot (`financial_currency`), and left empty when that doesn't know the name.
"""
from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd

from .. import locks, net, sourcelog
from ..config import settings
from ..paths import CACHE
from . import schedule, store
from .items import ITEMS

LOG_FILE = CACHE / "fundamentals" / "yahoo_log.csv"
SOURCE = "fundamentals_yahoo"

BLOCKS = {    # (statement, frequency) -> what it holds
    ("income", "yearly"): "FY", ("income", "quarterly"): "Q", ("income", "trailing"): "TTM",
    ("cash", "yearly"): "FY", ("cash", "quarterly"): "Q", ("cash", "trailing"): "TTM",
    ("balance", "yearly"): "FY", ("balance", "quarterly"): "Q",
}


def _cfg() -> dict:
    return settings()["fundamentals"]["yahoo"]


def fetch_statements(ticker: str) -> dict:
    """{"blocks": {(statement, freq): DataFrame}, "errors": {…}}: each block fails on its own."""
    yf = net.yf()
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    tk = yf.Ticker(ticker)
    calls = {"income": tk.get_income_stmt, "cash": tk.get_cash_flow, "balance": tk.get_balance_sheet}
    blocks, errors = {}, {}
    for (st, freq) in BLOCKS:
        try:
            df = calls[st](freq=freq)
            if isinstance(df, pd.DataFrame) and not df.empty:
                blocks[(st, freq)] = df
        except net.Throttled:
            raise
        except Exception as e:  # noqa: BLE001
            errors[f"{st} {freq}"] = f"{type(e).__name__}: {e}"[:200]
    return {"blocks": blocks, "errors": errors}


def parse_statements(blocks: dict, ticker: str, currency: str | None, fetched: date) -> pd.DataFrame:
    """Statement frames (rows = Yahoo's line names, columns = period ends) as fact-store rows without `known`. Per
    item and period the first of its Yahoo rows with a value is used."""
    out = []
    for (st, freq), df in blocks.items():
        fp = BLOCKS[(st, freq)]
        for item in ITEMS:
            if not item.yahoo or item.flow == (st == "balance"):
                continue
            names = [n for n in item.yahoo if n in df.index]
            if not names:
                continue
            for col in df.columns:
                end = pd.to_datetime(col, errors="coerce")
                if pd.isna(end):
                    continue
                for n in names:
                    v = pd.to_numeric(df.at[n, col], errors="coerce")
                    if pd.notna(v) and np.isfinite(v):
                        out.append({"ticker": ticker, "source": "yahoo", "item": item.key, "start": None, "end": end,
                                    "value": abs(float(v)) if item.outflow else float(v),
                                    "currency": None if item.unit == "shares" else currency, "form": freq, "fp": fp,
                                    "filed": None, "fetched": pd.Timestamp(fetched), "tag": n, "accn": None,
                                    "assumed": False})
                        break
    df = store.normalize(pd.DataFrame(out)) if out else store.empty()
    return df.drop_duplicates(["item", "fp", "end"], keep="first")     # an item in both income and cash flow


def merge(old: pd.DataFrame, new: pd.DataFrame, fetched: date, assumed_lag: dict[str, int]) -> pd.DataFrame:
    """The values in `new` that the store doesn't have yet (new periods, changed numbers), dated: `known` is the
    fetch day, or for a ticker's first fetch the period end plus the assumed lag (marked `assumed`). Never drops."""
    if new.empty:
        return new
    fetched = pd.Timestamp(fetched)
    first = set(new["ticker"]) - set(old["ticker"])
    latest = store.as_known(old) if not old.empty else old
    key = ["ticker", "item", "fp", "end"]
    if not latest.empty:
        m = new.merge(latest[key + ["value"]], on=key, how="left", suffixes=("", "_old"))
        same = np.isclose(m["value"], m["value_old"], rtol=1e-9, atol=1e-9) & m["value_old"].notna()
        new = new[~same.to_numpy()]
    lag = new["fp"].map({"FY": assumed_lag["annual"], "Q": assumed_lag["quarterly"],
                         "TTM": assumed_lag["quarterly"]}).fillna(assumed_lag["quarterly"])
    assumed = new["ticker"].isin(first)
    guess = (new["end"] + pd.to_timedelta(lag, unit="D")).where(lambda s: s < fetched, fetched)
    return new.assign(known=guess.where(assumed, fetched), assumed=assumed)


def _currencies() -> dict[str, str]:
    from .. import valuation

    now = valuation.latest(valuation.load_stocks())
    if now.empty or "financial_currency" not in now:
        return {}
    return {t: c for t, c in now["financial_currency"].dropna().items()}


def _earnings_dates() -> dict[str, pd.Timestamp]:
    from .. import valuation

    now = valuation.latest(valuation.load_stocks())
    if now.empty or "earnings_date" not in now:
        return {}
    return {t: pd.Timestamp(d) for t, d in now["earnings_date"].dropna().items()}


def update_yahoo(today: date | None = None, force: bool = False, tickers: list[str] | None = None) -> str:
    """Fetch statements for the tracked stocks that are due (or `tickers`, or all with `force`); add what is new."""
    from .. import valuation

    cfg = _cfg()
    today = today or date.today()
    names = tickers or valuation.tracked_stocks()
    log = schedule.load_log(LOG_FILE)
    if tickers or force:
        batch = list(names)
    else:
        after = pd.Timedelta(days=cfg["after_earnings_days"])
        expect = {t: schedule.next_report(le, 45) for t, le in zip(log["ticker"], log["last_end"])}
        for t, d in _earnings_dates().items():
            expect[t] = d + after
        batch = schedule.due(list(names), log, today, cfg["refresh_days"], expect)[: cfg["max_per_run"]]
    if not batch:
        return f"up to date ({len(names)} stocks)"
    ccy = _currencies()

    frames, errors, throttled = {}, {}, None
    for t in batch:
        try:
            raw = fetch_statements(t)
        except net.Throttled as e:
            throttled = str(e)
            break
        except Exception as e:  # noqa: BLE001
            errors[t] = f"{type(e).__name__}: {e}"[:200]
            continue
        df = parse_statements(raw["blocks"], t, ccy.get(t), today)
        if df.empty:
            errors[t] = "no statement values" + (f" ({'; '.join(list(raw['errors'].values())[:2])})"
                                                 if raw["errors"] else "")
        else:
            frames[t] = df

    added = 0
    rows = []
    if frames:
        with locks.file_lock(store.YAHOO_FILE, what="the Yahoo statement store"):
            old = store.load_yahoo()
            fresh = merge(old, pd.concat(frames.values(), ignore_index=True), today, cfg["assumed_lag_days"])
            if not fresh.empty:
                store.save(pd.concat([old, fresh], ignore_index=True), store.YAHOO_FILE)
            added = len(fresh)
    rows += [{"ticker": t, "fetched": today, "ok": True, "last_end": store.latest_end(df), "n": len(df), "error": None}
             for t, df in frames.items()]
    rows += [{"ticker": t, "fetched": today, "ok": False, "last_end": None, "n": 0, "error": e} for t, e in errors.items()]
    schedule.save_log(LOG_FILE, log, rows)

    tried = len(frames) + len(errors)
    msg = f"{len(frames)} of {tried} due stocks answered, {added:,} new values; {len(names)} stocks in all"
    if tried and not frames:
        raise ValueError(f"no statements from Yahoo for any of {tried} stocks (has Yahoo changed?): "
                         + "; ".join(f"{t}: {e}" for t, e in list(errors.items())[:3]))
    if throttled or (tried and len(frames) < cfg["min_ok_share"] * tried):
        raise sourcelog.PartialFailure(f"{msg}; {len(errors)} failed" + (f"; stopped: {throttled}" if throttled else ""))
    return msg + (f"; {len(errors)} without statements" if errors else "")
