"""A source that fails, answers with nothing or answers with less never shrinks what is stored.

One table: each source is updated once with a good answer (the stored copy), then again with a bad one, served in
the source's real format through `net.get` / yfinance stand-ins (tests/fakes.py). Whatever the second update
does (raise, log, carry on), every stored series, ticker or area must keep its rows, its first date and its last
date. Sources that append (CFTC, put/call, analyst) can't shrink this way; their partial-run losses are tested
with the sources themselves.

Entries marked `xfail(strict=True)` are known gaps: each fix turns its entry green and the strict mark then fails
until it is removed, so the table can't silently fall behind the code.
"""
from __future__ import annotations

import io
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from fakes import Resp, fake_yf, never_shrank, serve, stored
from radar import external, ingest, sentiment, valuation
from radar.discovery import scan

TODAY = date(2026, 10, 15)          # a Thursday
MODES = ("error", "empty", "short", "missing")


# ---------------- payloads in each source's real format ----------------

def _months(n: int, end: str = "2026-09") -> pd.DatetimeIndex:
    return pd.period_range(end=end, periods=n, freq="M").to_timestamp()


def fred_csv(sid: str, n: int, trim_end: int = 0) -> str:
    days = pd.bdate_range(end="2026-10-14", periods=n)[: n - trim_end]
    return "observation_date," + sid + "\n" + "".join(f"{d:%Y-%m-%d},{4 + i / 1000:.3f}\n" for i, d in enumerate(days))


def oecd_csv(areas: list[str], months: int = 60, trim_end: int = 0) -> str:
    rows = ["REF_AREA,TIME_PERIOD,OBS_VALUE"]
    for a in areas:
        for i, m in enumerate(_months(months)[: months - trim_end]):
            rows.append(f"{a},{m:%Y-%m},{100 + i / 100:.2f}")
    return "\n".join(rows) + "\n"


def ecb_csv(key: str, n: int = 300, trim_end: int = 0) -> str:
    days = pd.bdate_range(end="2026-10-14", periods=n)[: n - trim_end]
    return "KEY,FREQ,TIME_PERIOD,OBS_VALUE\n" + "".join(f"{key},B,{d:%Y-%m-%d},{3 + i / 1000:.4f}\n"
                                                        for i, d in enumerate(days))


def aaii_xls(weeks: int = 1100, trim_end: int = 0) -> bytes:
    dates = pd.date_range(end="2026-10-08", periods=weeks, freq="W-THU")[: weeks - trim_end]
    body = [["Date", "Bullish", "Neutral", "Bearish"]] + [[d, 0.4, 0.3, 0.3] for d in dates]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame([["AAII sentiment", "", "", ""]] + body).to_excel(w, sheet_name="SENTIMENT", header=False,
                                                                       index=False)
    return buf.getvalue()


def multpl_html(months: int = 1200, trim_end: int = 0) -> str:
    ms = _months(months, "2026-10")[: months - trim_end][::-1]          # newest first, as on the page
    return "<table>" + "".join(f"<tr><td>{m:%b} {m.day}, {m.year}</td><td>&#x2002;{20 + i / 100:.2f}</td></tr>"
                               for i, m in enumerate(ms)) + "</table>"


def damodaran_xlsx(months: int = 200, trim_end: int = 0) -> bytes:
    ms = _months(months, "2026-10")[: months - trim_end]
    df = pd.DataFrame({"Start of month": ms, "ERP (T12m)": 0.04, "T.Bond Rate": 0.042})
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="Historical ERP", index=False)
    return buf.getvalue()


# ---------------- the table ----------------

class Source:
    """How to update a source with a good answer, then a bad one; and how to measure what it stored."""

    file = None
    measure: dict = {}
    gaps: dict[str, str] = {}      # mode → why it fails today (xfail reason)
    modes = MODES

    def good(self, monkeypatch):
        raise NotImplementedError

    def bad(self, monkeypatch, mode):
        raise NotImplementedError


class Fred(Source):
    file = ingest.FRED_FILE
    measure = {"key": None, "date": None}
    gaps = {"short": "FRED replaces each series wholesale (plan 1.5)"}
    modes = ("error", "empty", "short")

    def good(self, mp):
        serve(mp, {"DGS10": Resp(text=fred_csv("DGS10", 400)), "T10Y2Y": Resp(text=fred_csv("T10Y2Y", 400))})
        ingest.update_fred(["DGS10", "T10Y2Y"])

    def bad(self, mp, mode):
        answer = {"error": Resp(500), "empty": Resp(text="observation_date,DGS10\n"),
                  "short": Resp(text=fred_csv("DGS10", 400, trim_end=30))}[mode]
        serve(mp, {"DGS10": answer, "T10Y2Y": Resp(text=fred_csv("T10Y2Y", 400))})
        ingest.update_fred(["DGS10", "T10Y2Y"])


class Oecd(Source):
    file = external.CLI_FILE
    measure = {"key": None, "date": None}

    def areas(self):
        return list(external._cfg().get("oecd_cli", {}))

    def good(self, mp):
        serve(mp, {"oecd": Resp(text=oecd_csv(self.areas()))})
        external.update_oecd_cli(today=TODAY)

    def bad(self, mp, mode):
        areas = self.areas()
        answer = {"error": Resp(500), "empty": Resp(text="REF_AREA,TIME_PERIOD,OBS_VALUE\n"),
                  "short": Resp(text=oecd_csv(areas, trim_end=3)),
                  "missing": Resp(text=oecd_csv(areas[1:]))}[mode]
        serve(mp, {"oecd": answer})
        external.update_oecd_cli(today=TODAY)


class Ecb(Source):
    file = external.ECB_FILE
    measure = {"key": None, "date": None}
    gaps = {"short": "ECB replaces wholesale (plan 1.5)"}
    modes = ("error", "empty", "short")

    def series(self):
        return external._cfg().get("ecb", {})

    def answers(self, first):
        return {sid: (first if i == 0 else Resp(text=ecb_csv(sid)))
                for i, (sid, _l) in enumerate(self.series().values())}

    def good(self, mp):
        serve(mp, {sid: Resp(text=ecb_csv(sid)) for sid, _l in self.series().values()})
        external.update_ecb(today=TODAY)

    def bad(self, mp, mode):
        sid = next(iter(self.series().values()))[0]
        answer = {"error": Resp(500), "empty": Resp(text="KEY,FREQ,TIME_PERIOD,OBS_VALUE\n"),
                  "short": Resp(text=ecb_csv(sid, trim_end=20))}[mode]
        serve(mp, self.answers(answer))
        external.update_ecb(today=TODAY)


class Aaii(Source):
    file = sentiment.AAII_FILE
    measure = {"key": None, "date": "date"}
    gaps = {"short": "AAII replaces wholesale (plan 1.5)"}
    modes = ("error", "empty", "short")

    def good(self, mp):
        serve(mp, {"aaii": Resp(content=aaii_xls())})
        sentiment.update_aaii()

    def bad(self, mp, mode):
        answer = {"error": Resp(500), "empty": Resp(content=b""), "short": Resp(content=aaii_xls(trim_end=4))}[mode]
        serve(mp, {"aaii": answer})
        sentiment.update_aaii()


class Cape(Source):
    file = valuation.MARKET_FILE
    measure = {"key": "series", "date": "date"}
    gaps = {"short": "CAPE replaces its series wholesale (plan 1.5)"}
    modes = ("error", "empty", "short")

    def good(self, mp):
        serve(mp, {"multpl": Resp(text=multpl_html()), "damodaran|adamodar": Resp(content=damodaran_xlsx())})
        valuation.update_cape()
        valuation.update_erp()

    def bad(self, mp, mode):
        answer = {"error": Resp(500), "empty": Resp(text="<html></html>"),
                  "short": Resp(text=multpl_html(trim_end=6))}[mode]
        serve(mp, {"multpl": answer})
        valuation.update_cape()


class Erp(Cape):
    gaps = {"short": "ERP replaces its series wholesale (plan 1.5)"}

    def bad(self, mp, mode):
        answer = {"error": Resp(500), "empty": Resp(content=b""), "short": Resp(content=damodaran_xlsx(trim_end=6))}[mode]
        serve(mp, {"adamodar": answer})
        valuation.update_erp()


class Etfs(Source):
    file = valuation.ETFS_FILE
    measure = {"key": "ticker", "date": None}   # weekly snapshots: a same-week rerun re-dates a row by design
    modes = ("error", "empty", "short", "missing")
    TICKERS = [f"ETF{i}" for i in range(10)]

    def _install(self, mp, funds):
        mp.setattr(valuation, "etf_tickers", lambda: list(self.TICKERS))
        fake_yf(mp, funds=funds)

    def good(self, mp):
        eh = pd.DataFrame({"fund": {"Price/Earnings": 0.05, "Price/Book": 0.4}})
        self._install(mp, {t: eh for t in self.TICKERS})
        valuation.update_etfs(today=TODAY - timedelta(days=3))       # Monday of the same ISO week

    def bad(self, mp, mode):
        eh = pd.DataFrame({"fund": {"Price/Earnings": 0.05, "Price/Book": 0.4}})
        funds = {"error": {t: RuntimeError("Yahoo") for t in self.TICKERS},
                 "empty": {t: pd.DataFrame() for t in self.TICKERS},
                 "short": {t: (eh if t == "ETF0" else RuntimeError("429")) for t in self.TICKERS},
                 "missing": {t: (eh if t != "ETF9" else None) for t in self.TICKERS}}[mode]
        self._install(mp, funds)
        valuation.update_etfs(force=True, today=TODAY)


def _bars(t: str, start: str, end: str, close: float = 100.0, factor: float = 1.0) -> pd.DataFrame:
    d = pd.bdate_range(start, end)
    c = close + np.arange(len(d)) * 0.1
    return pd.DataFrame({"date": d, "ticker": t, "high": c * factor, "low": c * factor, "close": c * factor,
                         "raw_close": c, "volume": 1.0})


class Prices(Source):
    file = ingest.PRICES_FILE
    measure = {"key": "ticker", "date": "date"}

    def _serve(self, mp, world):
        def download(tickers, start, progress=None):
            frames = [w[w["date"] >= pd.Timestamp(start)] for t, w in world.items() if t in tickers]
            return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=ingest.COLUMNS)
        mp.setattr(ingest, "_download", download)
        mp.setattr(ingest, "settings", lambda: {"history_years": 1})

    def good(self, mp):
        self._serve(mp, {"A": _bars("A", "2025-10-16", "2026-10-14"), "B": _bars("B", "2025-10-16", "2026-10-14")})
        ingest.update_prices(["A", "B"], today=TODAY)

    def bad(self, mp, mode):
        full = {"A": _bars("A", "2024-10-16", "2026-10-14"), "B": _bars("B", "2024-10-16", "2026-10-14")}
        if mode == "error":
            world = {}
        elif mode == "empty":
            world = {"A": full["A"].iloc[0:0], "B": full["B"].iloc[0:0]}
        elif mode == "short":     # asked to go deeper; Yahoo's answer starts later than what is stored
            world = {"A": _bars("A", "2026-06-01", "2026-10-14"), "B": full["B"]}
        else:                     # A was re-based and the full answer ends two sessions early
            world = {"A": _bars("A", "2025-10-16", "2026-10-12", factor=0.98), "B": full["B"]}
        self._serve(mp, world)
        ingest.update_prices(["A", "B"], start=date(2024, 10, 16), today=TODAY)


class DiscoveryPrices(Source):
    file = scan.PRICES_FILE
    measure = {"key": "ticker", "date": "date"}
    gaps = {"short": "discovery prices are replaced when half the names answer (plan 1.6)",
            "missing": "discovery prices are replaced when half the names answer (plan 1.6)"}
    NAMES = [f"N{i}" for i in range(10)]

    def _serve(self, mp, names):
        def download(tickers, start, progress=None):
            frames = [_bars(t, str(start), "2026-10-14") for t in tickers if t in names]
            return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=ingest.COLUMNS)
        mp.setattr(ingest, "_download", download)

    def good(self, mp):
        self._serve(mp, self.NAMES)
        scan.update_prices(self.NAMES, log=lambda m: None, sleep=lambda s: None, today=TODAY)

    def bad(self, mp, mode):
        names = {"error": [], "empty": [], "short": self.NAMES[:6], "missing": self.NAMES[:-1]}[mode]
        self._serve(mp, names)
        scan.update_prices(self.NAMES, log=lambda m: None, sleep=lambda s: None, today=TODAY)


SOURCES = [Fred(), Oecd(), Ecb(), Aaii(), Cape(), Erp(), Etfs(), Prices(), DiscoveryPrices()]
CASES = [pytest.param(s, m, id=f"{type(s).__name__}-{m}",
                      marks=[pytest.mark.xfail(strict=True, reason=s.gaps[m])] if m in s.gaps else [])
         for s in SOURCES for m in s.modes]


@pytest.mark.parametrize("source, mode", CASES)
def test_a_bad_answer_never_shrinks_what_is_stored(source, mode, monkeypatch):
    source.good(monkeypatch)
    before = stored(source.file, **source.measure)
    assert before, "the good answer stored nothing: the table entry is broken"
    try:
        source.bad(monkeypatch, mode)
    except Exception:  # noqa: BLE001 (refusing is fine; shrinking isn't)
        pass
    assert never_shrank(before, stored(source.file, **source.measure)) == []
