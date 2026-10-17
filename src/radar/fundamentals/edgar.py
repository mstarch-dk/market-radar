"""US financial statements from SEC EDGAR (the XBRL "company facts" API): every value a company filed in its 10-K
and 10-Q reports, with the date it was filed, so a past day can be scored on what was public then.

SEC asks automated clients to say who they are: the User-Agent carries a contact e-mail address, which the user
enters (`radar fundamentals contact EMAIL`, or the Data page), stored in their own database and passed in. Without
one the step fails and says so; Yahoo's statements still cover US names. SEC's fair-access limit is 10 requests a
second; settings.yaml `network.hosts` keeps us well under it.

Only the us-gaap and dei taxonomies are read. Companies filing under IFRS (most foreign issuers, on 20-F) have no
us-gaap facts and are left to Yahoo. Dimensional facts (a value per share class or segment) aren't in company
facts, so a company with several share classes may report only one class's share count: the scores check the
count against diluted shares and Yahoo's market value.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

import pandas as pd

from .. import guard, locks, net, sourcelog
from ..config import settings, write_csv
from ..paths import CACHE
from . import schedule, store
from .items import ITEMS

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
HOST = "data.sec.gov"
CIK_FILE = CACHE / "fundamentals" / "cik.csv"
LOG_FILE = CACHE / "fundamentals" / "edgar_log.csv"
SOURCE = "fundamentals_edgar"
FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A", "10-KT", "10-QT"}


def _cfg() -> dict:
    return settings()["fundamentals"]["edgar"]


class NoContact(RuntimeError):
    """No contact e-mail for SEC's User-Agent rule: nothing was sent."""


class NotGaap(ValueError):
    """The company files under IFRS (no us-gaap facts)."""


# ---------------- the contact address ----------------

def headers(contact: str | None) -> dict:
    if not contact:
        raise NoContact("SEC asks for a contact e-mail address in each request: set one on the Data page or with "
                        "`radar fundamentals contact EMAIL` (Yahoo's statements cover US names meanwhile)")
    return {"User-Agent": f"Market Radar personal research {contact}", "Accept-Encoding": "gzip, deflate"}


# ---------------- ticker -> CIK ----------------

def parse_tickers(js) -> pd.DataFrame:
    """SEC's company_tickers.json ({"0": {"cik_str", "ticker", "title"}, …}) as ticker, cik, title."""
    rows = list(js.values()) if isinstance(js, dict) else list(js or [])
    df = pd.DataFrame(rows).rename(columns={"cik_str": "cik"})
    if df.empty or not {"cik", "ticker"} <= set(df.columns):
        raise ValueError("SEC's ticker list parsed to nothing: has its format changed?")
    df["ticker"] = df["ticker"].astype(str).str.upper().str.replace(".", "-", regex=False)
    df["cik"] = pd.to_numeric(df["cik"], errors="coerce")
    return df.dropna(subset=["cik"]).astype({"cik": int}).drop_duplicates("ticker")[["ticker", "cik", "title"]]


def cik_map(hdr: dict, today: date | None = None, refresh: bool = False) -> dict[str, int]:
    """{ticker: CIK}, from the cached list; fetched again when older than `tickers_max_age_days`."""
    today = today or date.today()
    if CIK_FILE.exists() and not refresh:
        df = pd.read_csv(CIK_FILE)
        age = (pd.Timestamp(today) - pd.Timestamp(CIK_FILE.stat().st_mtime, unit="s").normalize()).days
        if age < _cfg()["tickers_max_age_days"] and not df.empty:
            return dict(zip(df["ticker"], df["cik"].astype(int)))
    r = net.get(TICKERS_URL, source=SOURCE, headers=hdr, timeout=60)
    r.raise_for_status()
    df = parse_tickers(r.json())
    write_csv(df, CIK_FILE, index=False)
    return dict(zip(df["ticker"], df["cik"]))


def sec_symbol(ticker: str) -> str:
    return ticker.upper().replace(".", "-")


# ---------------- company facts ----------------

def _unit(units: dict, kind: str) -> str | None:
    """The unit to read for an item: money in the company's reporting currency (the one with the most values),
    shares, or money per share."""
    if kind == "shares":
        names = [u for u in units if u == "shares"]
    elif kind == "per_share":
        names = [u for u in units if u.endswith("/shares")]
    else:
        names = [u for u in units if "/" not in u and u not in ("shares", "pure")]
    return max(names, key=lambda u: len(units[u])) if names else None


def _entries(facts: dict, tag: str, flow: bool, kind: str) -> tuple[str | None, list[dict]]:
    tax, name = ("dei", tag[4:]) if tag.startswith("dei:") else ("us-gaap", tag)
    node = (facts.get(tax) or {}).get(name)
    if not node:
        return None, []
    units = node.get("units") or {}
    u = _unit(units, kind)
    if u is None:
        return None, []
    rows = [r for r in units[u] if r.get("form") in FORMS and r.get("end") and r.get("filed")
            and r.get("val") is not None and (bool(r.get("start")) == flow)]
    return u, rows


def parse_companyfacts(js: dict, ticker: str, today: date | None = None, lag_days: int = 1,
                       years: int = 12) -> pd.DataFrame:
    """One company's facts as fact-store rows (store.COLS). Per item and period the recipe in items.py that finds
    the most of its tags is used (on a tie the earlier one); a value filed again unchanged (a later report's
    comparative) keeps its first filing date, a changed one (a restatement) is kept as a second version. Raises
    NotGaap for an IFRS filer and ValueError when nothing usable is in the answer."""
    facts = (js or {}).get("facts") or {}
    if not facts.get("us-gaap"):
        raise NotGaap("no us-gaap facts" + (" (files under IFRS)" if facts.get("ifrs-full") else ""))
    today = pd.Timestamp(today or date.today())
    cutoff = today - pd.DateOffset(years=years)
    out = []
    for item in ITEMS:
        best: dict[tuple, tuple[tuple[int, int], list[dict]]] = {}     # period -> ((tags found, -recipe), rows)
        for ri, recipe in enumerate(item.edgar):
            unit, base = _entries(facts, recipe[0], item.flow, item.unit)
            if not base:
                continue
            extra = []
            for tag in recipe[1:]:
                u2, rows = _entries(facts, tag, item.flow, item.unit)
                if u2 == unit:
                    extra.append({(r.get("start"), r["end"], r["accn"]): r["val"] for r in rows})
            by_period: dict[tuple, list[dict]] = {}
            for r in base:
                parts = [m.get((r.get("start"), r["end"], r["accn"])) for m in extra]
                used = [recipe[0]] + [t for t, p in zip(recipe[1:], parts) if p is not None]
                by_period.setdefault((r.get("start"), r["end"]), []).append(
                    {"ticker": ticker, "source": "edgar", "item": item.key, "start": r.get("start"), "end": r["end"],
                     "value": float(r["val"]) + sum(p for p in parts if p is not None), "currency": unit,
                     "form": r["form"], "fp": r.get("fp"), "filed": r["filed"], "fetched": today,
                     "tag": "+".join(used), "accn": r["accn"], "assumed": False})
            for period, rows in by_period.items():
                score = (max(len(x["tag"].split("+")) for x in rows), -ri)
                if period not in best or score > best[period][0]:
                    best[period] = (score, rows)
        for _, rows in best.values():
            out += rows
    if not out:
        raise ValueError("company facts parsed to nothing usable")
    df = store.normalize(pd.DataFrame(out))
    df = df[df["end"] >= cutoff]
    df = (df.sort_values("filed", kind="stable")
            .drop_duplicates(["item", "start", "end", "value"], keep="first"))   # first filing of each value
    df["known"] = df["filed"] + pd.Timedelta(days=lag_days)
    if df.empty:
        raise ValueError(f"no values from the last {years} years")
    return store.normalize(df)


def fetch_companyfacts(cik: int, hdr: dict) -> dict | None:
    """The JSON, or None when SEC has no facts for the CIK (404)."""
    r = net.get(FACTS_URL.format(cik=cik), source=SOURCE, headers=hdr, timeout=90)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


# ---------------- the update step ----------------

def _keep_or_replace(old: pd.DataFrame, new: pd.DataFrame, ticker: str) -> str | None:
    """Why a fresh parse may not replace the stored one (None: it may): per item it must reach the stored latest
    period and hold at least 90% of the stored values (the oldest years may drop off as `years` moves on)."""
    if old.empty:
        return None
    try:
        guard.check(old, new, what=ticker, key="item", date="end", row_tol=0.1, start_tol=timedelta(days=400))
    except guard.Shrunk as e:
        return str(e).split("(", 1)[-1].rsplit(")", 1)[0]
    return None


def us_tickers(stocks: list[str]) -> list[str]:
    """The US listings among the tracked `stocks`, plus the US stock group."""
    from .. import tracked

    us = set(tracked.stock_groups(offline=True).get("us", []))
    return sorted(us | {t for t in stocks if "." not in t and not t.startswith("^")})


def update_edgar(stocks: list[str], contact: str | None, today: date | None = None, force: bool = False,
                 tickers: list[str] | None = None) -> str:
    """Fetch company facts for the US tickers among the tracked `stocks` that are due (or `tickers`, or all with `force`); store per ticker.
    A ticker whose fresh answer has less than what is stored keeps its stored values (and counts as failed)."""
    from .. import tracked

    cfg = _cfg()
    today = today or date.today()
    hdr = headers(contact)
    cmap = cik_map(hdr, today)
    us = tracked.stock_groups(offline=True).get("us", [])
    if us:
        mapped = sum(sec_symbol(t) in cmap for t in us)
        if mapped < 0.95 * len(us):
            raise ValueError(f"SEC's ticker list maps only {mapped} of {len(us)} US stocks: has its format changed?")
    names = [t for t in (tickers or us_tickers(stocks)) if sec_symbol(t) in cmap]
    log = schedule.load_log(LOG_FILE)
    if tickers or force:
        batch = names
    else:
        expect = {t: schedule.next_report(le, cfg["after_period_days"])
                  for t, le in zip(log["ticker"], log["last_end"])}
        batch = schedule.due(names, log, today, cfg["refresh_days"], expect)[: cfg["max_per_run"]]
    if not batch:
        return f"up to date ({len(names)} US stocks)"

    results: dict[str, pd.DataFrame] = {}
    skipped: dict[str, str] = {}
    errors: dict[str, str] = {}
    throttled = None

    def one(t: str):
        js = fetch_companyfacts(cmap[sec_symbol(t)], hdr)
        if js is None:
            raise NotGaap("SEC has no company facts")
        return parse_companyfacts(js, t, today, settings()["backtest"]["fundamentals_lag_days"], cfg["years"])

    with net.pool(len(batch), HOST) as ex:
        futures = {t: ex.submit(one, t) for t in batch}
        for t, f in futures.items():
            try:
                results[t] = f.result()
            except NotGaap as e:
                skipped[t] = str(e)
            except net.Throttled as e:
                throttled = str(e)
                errors[t] = str(e)
            except Exception as e:  # noqa: BLE001 (one company's answer never stops the rest)
                errors[t] = f"{type(e).__name__}: {e}"[:200]

    rows = []
    with locks.file_lock(store.EDGAR_FILE, what="the EDGAR fact store"):
        old = store.load_edgar()
        keep = old
        for t, df in results.items():
            mine = old[old["ticker"] == t]
            why = _keep_or_replace(mine, df, t)
            if why:
                errors[t] = f"the answer has less than what is stored ({why}): kept the stored values"
                continue
            keep = pd.concat([keep[keep["ticker"] != t], df], ignore_index=True)
            rows.append({"ticker": t, "fetched": today, "ok": True, "last_end": store.latest_end(df), "n": len(df),
                         "error": None})
        if len(keep) != len(old) or results:
            store.save(keep, store.EDGAR_FILE)
    rows += [{"ticker": t, "fetched": today, "ok": True, "last_end": None, "n": 0, "error": e} for t, e in skipped.items()]
    rows += [{"ticker": t, "fetched": today, "ok": False, "last_end": None, "n": 0, "error": e} for t, e in errors.items()]
    schedule.save_log(LOG_FILE, log, rows)

    stored = len(results) - sum(t in errors for t in results)
    msg = (f"{stored} of {len(batch)} due companies stored" + (f", {len(skipped)} without us-gaap facts (Yahoo covers "
           f"them)" if skipped else "") + f"; {len(names)} US stocks in all")
    attempted = len(batch) - len(skipped)
    if throttled or (attempted and len(errors) > cfg["max_fail_share"] * attempted):
        kinds = Counter(e.split(":")[0] for e in errors.values()).most_common(3)
        raise sourcelog.PartialFailure(f"{msg}; {len(errors)} failed ("
                                      + ", ".join(f"{k} × {n}" for k, n in kinds) + ")"
                                      + (f"; {throttled}" if throttled else ""))
    return msg + (f"; {len(errors)} failed and kept their stored values" if errors else "")

