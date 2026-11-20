"""/sector-etfs' record: per sector of config/sector_etfs.yaml, the go-to UCITS ETF and its peers as the skill found
them (ISIN, Yahoo ticker, TER, size, distribution, domicile, tracking difference, each with its source and the day
it was read), and why the pick is the pick. The Sector ETFs page adds what changes every day (prices, the positive
list, the rotation) in sector_etf_view.py.

A record is a JSON file in exports/sector_etfs/ (home tier), one per run, dated today and never overwritten or
back-dated, so the history of the picks stays. A run may cover only some sectors: the others are carried over from
the latest record with their own `updated` date. The latest record's tickers are in the daily update
(universe.all_price_tickers). The skill: .claude/skills/sector-etfs/SKILL.md; plans/F13-sector-etfs.md."""
from __future__ import annotations

import json
import re
from datetime import date, datetime

from . import isin
from .config import sector_etf_taxonomy, write_text
from .errors import Invalid
from .jsonsafe import dumps
from .paths import HOME
from .values import num

RECORDS = HOME / "exports" / "sector_etfs"
SCOPES = ("world", "us", "europe", "other")
DISTRIBUTIONS = ("acc", "dist")
TICKER = re.compile(r"[A-Z0-9][A-Z0-9.^=-]{0,19}")
COUNTRY = re.compile(r"[A-Z]{2}")
CURRENCY = re.compile(r"[A-Z]{3}")
URL = re.compile(r"https?://\S+")
RUN = re.compile(r"(?:-(\d+))?")              # what follows the day in a record's id: nothing, -2, -3 …
MAX_ETFS = 8
MAX_TER = 0.03                 # a fraction: 0.0025 is 0.25 % a year
MAX_TRACKING = 0.2             # a tracking difference beyond ±20 % a year is a typo, not a fund


def _text(v, what: str, required: bool = False, limit: int = 200) -> str | None:
    s = str(v).strip() if v is not None else ""
    if required and not s:
        raise Invalid(f"{what} is required.")
    if len(s) > limit:
        raise Invalid(f"{what} is at most {limit} characters.")
    return s or None


def _day(v, what: str) -> str | None:
    if v is None or v == "":
        return None
    try:
        return date.fromisoformat(str(v)[:10]).isoformat()
    except ValueError:
        raise Invalid(f"{what} is a date (YYYY-MM-DD).") from None


def _fraction(v, what: str, lo: float, hi: float) -> float | None:
    """A number in [lo, hi], or None when it isn't known: missing stays missing, never 0."""
    if v is None or v == "":
        return None
    f = num(v)
    if f is None or not lo <= f <= hi:
        raise Invalid(f"{what} is a fraction between {lo:g} and {hi:g} (0.0025 is 0.25 %), or null when unknown.")
    return f


def _etf(e: dict, where: str) -> dict:
    code = str(e.get("isin") or "").strip().upper()
    if not isin.valid(code):
        raise Invalid(f"{where}: {code or 'the ISIN'} is not a valid ISIN (shape or check digit).")
    ticker = str(e.get("ticker") or "").strip().upper()
    if not TICKER.fullmatch(ticker):
        raise Invalid(f"{where} ({code}): {ticker or 'the ticker'} is not a Yahoo symbol.")
    if e.get("scope") not in SCOPES:
        raise Invalid(f"{where} ({code}): scope is one of {', '.join(SCOPES)}.")
    dist = e.get("distribution")
    if dist is not None and dist not in DISTRIBUTIONS:
        raise Invalid(f"{where} ({code}): distribution is acc or dist, or null when unknown.")
    domicile = _text(e.get("domicile"), "domicile")
    if domicile is not None and not COUNTRY.fullmatch(domicile.upper()):
        raise Invalid(f"{where} ({code}): domicile is a two-letter country code (IE, LU, DE).")
    currency = _text(e.get("currency"), "currency")
    if currency is not None and not CURRENCY.fullmatch(currency.upper()):
        raise Invalid(f"{where} ({code}): currency is a three-letter code (USD, EUR).")
    aum = e.get("aum_musd")
    aum = None if aum is None or aum == "" else num(aum)
    if e.get("aum_musd") not in (None, "") and (aum is None or aum < 0):
        raise Invalid(f"{where} ({code}): aum_musd is the fund's size in USD millions, or null when unknown.")
    sources = [str(s).strip() for s in e.get("sources") or [] if str(s).strip()]
    bad = [s for s in sources if not URL.fullmatch(s)]
    if bad:
        raise Invalid(f"{where} ({code}): a source is a web address: {', '.join(bad)}.")
    return {"isin": code, "ticker": ticker, "name": _text(e.get("name"), f"{where} ({code}): name", required=True),
            "issuer": _text(e.get("issuer"), "issuer"), "index": _text(e.get("index"), "index"),
            "scope": e["scope"], "ter": _fraction(e.get("ter"), f"{where} ({code}): ter", 0, MAX_TER),
            "distribution": dist, "domicile": domicile.upper() if domicile else None,
            "currency": currency.upper() if currency else None, "aum_musd": aum,
            "tracking_diff": _fraction(e.get("tracking_diff"), f"{where} ({code}): tracking_diff",
                                       -MAX_TRACKING, MAX_TRACKING),
            "sources": sources, "checked": _day(e.get("checked"), f"{where} ({code}): checked")}


def check_sector(s: dict) -> dict:
    """One sector of a record as it is frozen: Invalid naming the first problem."""
    sectors = sector_etf_taxonomy().sectors
    key = str(s.get("key") or "").strip()
    if key not in sectors:
        raise Invalid(f"{key or 'The sector key'} is not a sector of config/sector_etfs.yaml "
                      f"({', '.join(sectors)}).")
    etfs = [_etf(e, key) for e in s.get("etfs") or []]
    if not etfs:
        raise Invalid(f"{key}: a sector needs at least its go-to ETF.")
    if len(etfs) > MAX_ETFS:
        raise Invalid(f"{key}: at most {MAX_ETFS} ETFs (the go-to and its closest peers).")
    codes = [e["isin"] for e in etfs]
    if len(codes) != len(set(codes)):
        raise Invalid(f"{key}: an ISIN is listed twice.")
    pick = str(s.get("pick") or "").strip().upper()
    if pick not in codes:
        raise Invalid(f"{key}: the pick is the ISIN of one of the sector's ETFs.")
    override = bool(s.get("rank_override"))
    reason = _text(s.get("reason"), f"{key}: reason", limit=1000)
    if override and not reason:
        raise Invalid(f"{key}: a pick that isn't the ranking's first needs its reason.")
    return {"key": key, "pick": pick, "reason": reason, "rank_override": override, "etfs": etfs,
            "updated": _day(s.get("updated"), f"{key}: updated")}


def check(record: dict) -> dict:
    """A run as it is frozen (the sectors it covers): Invalid naming the first problem."""
    sectors = [check_sector(s) for s in record.get("sectors") or []]
    if not sectors:
        raise Invalid("A record needs at least one sector.")
    keys = [s["key"] for s in sectors]
    if len(keys) != len(set(keys)):
        raise Invalid("A sector is listed twice.")
    return {"sectors": sectors, "note": _text(record.get("note"), "note", limit=2000),
            "report": _text(record.get("report"), "report")}


def merge(new: dict, base: dict | None, today: date | None = None) -> dict:
    """`new`'s sectors stamped today, and the sectors of `base` (the latest record) it doesn't cover, carried over
    with their own `updated` date; in the taxonomy's order."""
    day = (today or date.today()).isoformat()
    by_key = {s["key"]: {**s, "updated": day} for s in new["sectors"]}
    carried = [s["key"] for s in (base or {}).get("sectors", []) if s["key"] not in by_key]
    for s in (base or {}).get("sectors", []):
        by_key.setdefault(s["key"], s)
    order = list(sector_etf_taxonomy().sectors)
    sectors = sorted(by_key.values(), key=lambda s: order.index(s["key"]) if s["key"] in order else len(order))
    return {**new, "sectors": sectors, "carried": carried}


def freeze(record: dict, today: date | None = None) -> dict:
    """Write one run into exports/sector_etfs/ as `<today>.json`, stamped now, the latest record's other sectors
    carried over; a second run on the same day gets -2, -3 … (never overwritten). Returns the record with its `id`."""
    rec = merge(check(record), latest(), today)
    day = (today or date.today()).isoformat()
    rec = {"type": "sector-etfs", "date": day, "frozen_at": datetime.now().isoformat(timespec="seconds"), **rec}
    RECORDS.mkdir(parents=True, exist_ok=True)
    k, f = 1, RECORDS / f"{day}.json"
    while f.exists():
        k += 1
        f = RECORDS / f"{day}-{k}.json"
    write_text(f, dumps(rec, indent=1, ensure_ascii=False))
    return {"id": f.stem, "file": str(f), **rec}


def _read(f) -> dict:
    d = json.loads(f.read_text(encoding="utf-8"))
    rec = check(d)
    for s in rec["sectors"]:
        s["updated"] = s["updated"] or str(d["date"])[:10]
    return {"id": f.stem, **rec, "date": str(d["date"])[:10], "frozen_at": d.get("frozen_at"),
            "carried": [str(k) for k in d.get("carried") or []]}


def records() -> list[dict]:
    """Every record, oldest first, each with its `id`; a file that can't be read (or names a sector the taxonomy no
    longer has) is listed with its `problem` rather than dropped."""
    if not RECORDS.is_dir():
        return []
    out = []
    for f in RECORDS.glob("*.json"):
        try:
            out.append(_read(f))
        except (ValueError, KeyError, TypeError, Invalid) as e:
            out.append({"id": f.stem, "problem": f"can't be read: {e}"})
    out.sort(key=_order)
    return out


def _order(r: dict) -> tuple[str, int]:
    """By day, then by the run's number that day (freeze names them <day>, <day>-2, <day>-3 …). Not by the file's
    time: two runs in the same second can share it (Windows), and a copied folder gets new times."""
    run = RUN.fullmatch(r["id"][10:])
    return (r.get("date") or r["id"][:10], int(run.group(1)) if run and run.group(1) else 1)


def latest() -> dict | None:
    """The newest readable record; None before the first run."""
    good = [r for r in records() if "problem" not in r]
    return good[-1] if good else None


def symbols() -> set[str]:
    """Every ticker of the latest record (the daily update keeps their prices)."""
    rec = latest()
    return {e["ticker"] for s in rec["sectors"] for e in s["etfs"]} if rec else set()
