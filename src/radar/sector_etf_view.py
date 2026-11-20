"""The Sector ETFs page (plans/F13-sector-etfs.md): for each sector of config/sector_etfs.yaml, the go-to UCITS ETF
and its peers from /sector-etfs' latest record (sector_etfs.py), with what changes every day added here: returns
in DKK and against ACWI in DKK, a weekly sparkline, the cost Yahoo reports next to the recorded one, the Danish tax
status from SKAT's positive list, the sector's place in the rotation, and the ranking the pick is checked against.

The ranking is a rule, not a recommendation, applied in this order:
  1. tax: on the positive list for the year (aktiebaseret: share income, allowed on an aktiesparekonto) before
     unknown before off the list (capital income);
  2. size: a fund under settings `sector_etfs.min_aum_musd` ranks below every fund that isn't (unknown size counts
     as not under);
  3. TER, lowest first (unknown last);
  4. tracking difference, highest first (unknown last);
  5. accumulating before distributing (unknown last).
Ties keep the record's order. Missing data stays missing (None), never 0."""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from . import sector_etfs
from .config import sector_etf_taxonomy, settings, typed
from .market import Market
from .portfolios.performance import PERIODS, bench_dkk, period_return
from .portfolios.prices import Prices
from .reporting import dashboard
from .sources import external, positive_list
from .values import num

TER_TOLERANCE = 0.0005         # recorded vs Yahoo TER: a gap above 0.05 pp is flagged
SPARK_WEEKS = 52
MAX_POOL = 15                  # discovery-pool candidates per sector, for the skill
EXCLUDE = ("LEVERAGED", "SHORT", " 2X", " 3X", "DAILY", "INVERSE", "COVERED CALL", "BOND")
BLANK: dict[str, Any] = {"issuer": None, "index": None, "ter": None, "distribution": None, "domicile": None, "currency": None,
                         "aum_musd": None, "tracking_diff": None, "sources": [], "checked": None}   # the skill fills in


# ---------------- tax ----------------

def tax_status(code: str | None, years: dict[int, set[str]] | None, year: int) -> dict:
    """A fund's Danish tax status for an income year from SKAT's positive list: aktiebaseret (lager-taxed share
    income, allowed on an aktiesparekonto), kapitalindkomst (off the list: lager-taxed capital income, not on an
    aktiesparekonto) or ukendt (no sheet for the year, or no ISIN). `next_year`: the next year's status when SKAT
    has published that sheet (a fund leaving the list shows here first)."""
    st = positive_list.status(code, year, years)
    nxt = positive_list.status(code, year + 1, years) if years and year + 1 in years else None
    return {"status": st, "tax_class": {"yes": "aktiebaseret", "no": "kapitalindkomst"}.get(st, "ukendt"),
            "ask_ok": {"yes": True, "no": False}.get(st), "sheet_year": year if st in ("yes", "no") else None,
            "next_year": nxt}


def positive_list_years() -> dict[int, set[str]] | None:
    """Every sheet of SKAT's positive list by income year; None without the file or when it can't be read."""
    try:
        return positive_list.load_years()
    except (OSError, ValueError):
        return None


# ---------------- ranking ----------------

def _last(v, missing: float) -> float:
    return missing if v is None else v


def rank(etfs: list[dict], min_aum_musd: float | None = None) -> list[dict]:
    """The ETFs in the ranking's order (module docstring), each with `rank` (1 = first) and `reasons` (what
    placed it, in the ranking's order). Each ETF needs `tax` (tax_status) and the record's fields."""
    floor = typed().sector_etfs.min_aum_musd if min_aum_musd is None else min_aum_musd

    def key(ie: tuple[int, dict]):
        i, e = ie
        tax = {"yes": 0, "no": 2}.get(e["tax"]["status"], 1)
        small = 1 if e.get("aum_musd") is not None and e["aum_musd"] < floor else 0
        td = e.get("tracking_diff")
        dist = {"acc": 0, "dist": 1}.get(e.get("distribution") or "", 2)
        return (tax, small, _last(e.get("ter"), 1.0), -_last(td, -1.0), dist, i)

    out = []
    for n, (_, e) in enumerate(sorted(enumerate(etfs), key=key), start=1):
        reasons = [{"yes": "on the positive list: share income, allowed on an aktiesparekonto",
                    "no": "off the positive list: capital income, not allowed on an aktiesparekonto"}.get(
                        e["tax"]["status"], "tax status unknown (no ISIN or no sheet for the year)")]
        if e.get("aum_musd") is not None and e["aum_musd"] < floor:
            reasons.append(f"smaller than {floor:g}m USD")
        reasons.append("TER unknown" if e.get("ter") is None else f"TER {e['ter'] * 100:.2f} %")
        if e.get("tracking_diff") is not None:
            reasons.append(f"tracking difference {e['tracking_diff'] * 100:+.2f} % a year")
        if e.get("distribution"):
            reasons.append("accumulating" if e["distribution"] == "acc" else "distributing")
        out.append({**e, "rank": n, "reasons": reasons})
    return out


# ---------------- prices ----------------

def _returns(s: pd.Series | None, today: pd.Timestamp) -> dict[str, float | None]:
    """r1m, r3m, r6m, r1y over trading sessions, and YTD from the last close of last year; None without the
    history."""
    out: dict[str, float | None] = dict.fromkeys([*(f"r{k}" for k in PERIODS), "ytd"])
    if s is None or s.empty:
        return out
    for k, n in PERIODS.items():
        out[f"r{k}"] = period_return(s, n)
    start = pd.Timestamp(today.year, 1, 1)
    before = s[s.index < start]
    out["ytd"] = float(s.iloc[-1] / before.iloc[-1] - 1) if len(before) and before.iloc[-1] > 0 else None
    return out


def _spark(s: pd.Series | None) -> list[float]:
    if s is None or s.empty:
        return []
    w = s.resample("W-FRI").last().dropna().iloc[-SPARK_WEEKS:]
    return [round(float(v), 4) for v in w / w.iloc[0]] if len(w) > 1 else []


def _yahoo_ter(ticker: str) -> tuple[float | None, str | None]:
    raw, status, fetched = external.cached_detail(ticker)        # never fetches: the page is read live
    if status != "ok" or not raw:
        return None, None
    fund = external.parse_fund(raw.get("fund") or {}, raw.get("info") or {})
    return num(fund.get("expense_ratio")), fetched


# ---------------- the page ----------------

def _rotation(d: dict | None) -> dict[str, dict]:
    """Each rotation ticker's row of the last `radar run` (quadrant, rank, relative strength)."""
    out: dict[str, dict] = {}
    for g in ((d or {}).get("rotation") or {}).get("groups") or []:
        for r in g.get("rows") or []:
            out[r["ticker"]] = {"ticker": r["ticker"], "group": g["key"], "group_label": g.get("label"),
                                "name": r.get("name"), "quadrant": r.get("quadrant"), "rank": r.get("rank"),
                                "rs_score": num(r.get("rs_score")), "r3m": num(r.get("r3m")),
                                "rel_r3m": num(r.get("rel_r3m"))}
    return out


def _diff(a: float | None, b: float | None) -> float | None:
    return a - b if a is not None and b is not None else None


def enrich(e: dict, prices: Prices | None, bench: pd.Series, years, year: int, today: pd.Timestamp) -> dict:
    """One ETF of a record with its returns (DKK and vs ACWI in DKK), sparkline, Yahoo TER and tax status;
    without prices (`prices` None) the returns are None."""
    s = prices.dkk(e["ticker"]) if prices is not None else None
    r = _returns(s, today)
    b = _returns(bench, today)
    vs = {k: _diff(r[k], b[k]) for k in r}
    yter, yfetched = _yahoo_ter(e["ticker"])
    gap = abs(e["ter"] - yter) if e.get("ter") is not None and yter is not None else None
    return {**e, "returns_dkk": r, "vs_acwi": vs, "spark": _spark(s),
            "last_close": s.index[-1].date().isoformat() if s is not None and len(s) else None,
            "yahoo_ter": yter, "yahoo_fetched": yfetched,
            "ter_mismatch": gap is not None and gap > TER_TOLERANCE, "tax": tax_status(e["isin"], years, year)}


def view(market: Market | None, today: date | None = None) -> dict:
    """The whole page: every sector of the taxonomy (in its order), with the latest record's ETFs ranked and
    enriched; a sector the record doesn't cover has no ETFs. `as_of` None before the first /sector-etfs run;
    without prices (`market` None) the returns are None."""
    today = today or date.today()
    ts = pd.Timestamp(today)
    tax = sector_etf_taxonomy()
    cfg = typed().sector_etfs
    recs = sector_etfs.records()
    good = [r for r in recs if "problem" not in r]
    rec = good[-1] if good else None
    years, year = positive_list_years(), today.year
    rot = _rotation(dashboard.load())
    prices = Prices(market) if market is not None else None
    bench = bench_dkk(market) if market is not None else pd.Series(dtype=float)
    by_key = {s["key"]: s for s in (rec or {}).get("sectors", [])}
    sectors = []
    for key, d in tax.sectors.items():
        row: dict[str, Any] = {"key": key, "label": d.label, "parent": d.parent,
               "rotation": [rot[t] for t in d.rotation if t in rot], "pick": None, "reason": None,
               "rank_override": False, "recheck": False, "updated": None, "age_days": None, "etfs": []}
        s = by_key.get(key)
        if s is not None:
            etfs = rank([enrich(e, prices, bench, years, year, ts) for e in s["etfs"]], cfg.min_aum_musd)
            for e in etfs:
                e["pick"] = e["isin"] == s["pick"]
            pick = next(e for e in etfs if e["pick"])
            row.update(pick=s["pick"], reason=s.get("reason"), rank_override=bool(s.get("rank_override")),
                       recheck=pick["rank"] != 1 and not s.get("rank_override"), updated=s["updated"],
                       age_days=(today - date.fromisoformat(s["updated"])).days, etfs=etfs)
        sectors.append(row)
    age = (today - date.fromisoformat(rec["date"])).days if rec else None
    return {"as_of": rec["date"] if rec else None, "record_id": rec["id"] if rec else None, "age_days": age,
            "stale": age is not None and age > cfg.stale_days, "stale_days": cfg.stale_days,
            "min_aum_musd": cfg.min_aum_musd, "tax_year": year, "prices": market is not None,
            "tax_sheet": year in years if years else False, "note": rec.get("note") if rec else None,
            "problems": [{"id": r["id"], "problem": r["problem"]} for r in recs if "problem" in r],
            "sectors": sectors}


_cache: dict = {}


def _stamp(f) -> tuple:
    st = f.stat()
    return (str(f), st.st_mtime_ns, st.st_size)


def cached(market: Market | None, today: date | None = None) -> dict:
    """`view`, kept until a record, the prices, the last `radar run`, the settings or the day change."""
    today = today or date.today()
    recs = tuple(sorted(_stamp(f) for f in sector_etfs.RECORDS.glob("*.json"))) if sector_etfs.RECORDS.is_dir() else ()
    dash = dashboard.path()
    key = (recs, market.mtime if market is not None else None, _stamp(dash) if dash.exists() else None,
           id(settings()), today)
    if key not in _cache:
        _cache.clear()
        _cache[key] = view(market, today)
    return _cache[key]


def reset() -> None:
    _cache.clear()


def history() -> list[dict]:
    """What each readable record picked, oldest first: per record its date and sector → pick (ISIN, ticker)."""
    out = []
    for r in sector_etfs.records():
        if "problem" in r:
            out.append({"id": r["id"], "problem": r["problem"]})
            continue
        picks = {}
        for s in r["sectors"]:
            e = next(e for e in s["etfs"] if e["isin"] == s["pick"])
            picks[s["key"]] = {"isin": e["isin"], "ticker": e["ticker"], "name": e["name"], "updated": s["updated"],
                               "carried": s["key"] in r["carried"]}
        out.append({"id": r["id"], "date": r["date"], "picks": picks})
    return out


# ---------------- what a new run changes ----------------

def changes(new: list[dict], base: dict | None) -> list[dict]:
    """Per sector of a new run (checked sectors), what differs from the latest record: the pick, ETFs added or
    dropped, a TER that moved. A sector the record didn't have is `new`."""
    old = {s["key"]: s for s in (base or {}).get("sectors", [])}
    out = []
    for s in new:
        o = old.get(s["key"])
        if o is None:
            out.append({"key": s["key"], "new": True, "pick": {"from": None, "to": s["pick"]}})
            continue
        before = {e["isin"]: e for e in o["etfs"]}
        after = {e["isin"]: e for e in s["etfs"]}
        ter = [{"isin": i, "from": before[i]["ter"], "to": after[i]["ter"]} for i in after
               if i in before and before[i]["ter"] != after[i]["ter"]]
        out.append({"key": s["key"], "new": False,
                    "pick": {"from": o["pick"], "to": s["pick"]} if o["pick"] != s["pick"] else None,
                    "added": [i for i in after if i not in before], "dropped": [i for i in before if i not in after],
                    "ter": ter})
    return out


def preview(record: dict, market: Market | None, today: date | None = None) -> dict:
    """A run before it is saved: the checked sectors, each ranked with today's data (so the pick can be held against
    the rule), and the changes against the latest record. Invalid when the run doesn't pass sector_etfs.check."""
    today = today or date.today()
    rec = sector_etfs.check(record)
    prices = Prices(market) if market is not None else None
    bench = bench_dkk(market) if market is not None else pd.Series(dtype=float)
    years, ts = positive_list_years(), pd.Timestamp(today)
    sectors = []
    for s in rec["sectors"]:
        ranked = rank([enrich(e, prices, bench, years, today.year, ts) for e in s["etfs"]])
        first = ranked[0]["isin"]
        warn = []
        if first != s["pick"] and not s["rank_override"]:
            warn.append(f"the pick isn't the ranking's first ({first}): set rank_override with a reason, or pick it")
        pick = next(e for e in ranked if e["isin"] == s["pick"])
        if pick["tax"]["status"] != "yes":
            warn.append(f"the pick is {pick['tax']['tax_class']} for {today.year}: not allowed on an aktiesparekonto")
        sectors.append({"key": s["key"], "pick": s["pick"], "rank_override": s["rank_override"],
                        "reason": s["reason"], "warnings": warn,
                        "ranking": [{k: e[k] for k in ("rank", "isin", "ticker", "name", "ter", "aum_musd",
                                                       "returns_dkk", "tax", "reasons")} for e in ranked]})
    base = sector_etfs.latest()
    covered = {x["key"] for x in rec["sectors"]}
    carried = [s["key"] for s in (base or {}).get("sectors", []) if s["key"] not in covered]
    return {"sectors": sectors, "changes": changes(rec["sectors"], base), "carried_over": carried,
            "latest": base["id"] if base else None}


# ---------------- candidates for the skill ----------------

def _pool(key: str, words: list[str], known: set[str]) -> list[dict]:
    """ETFs of the discovery scan (positive-list funds mapped to Yahoo) whose name says ETF and matches the
    sector's words (active funds, leveraged, short and bond funds left out)."""
    from .discovery import scan

    df = scan.load_universe()
    if df is None or df.empty or not words:
        return []
    df = df[df["kind"] == "etf"]
    up = df["name"].astype(str).str.upper()
    hit = up.apply(lambda n: "ETF" in n and any(w in n for w in words) and not any(x in n for x in EXCLUDE))
    out = []
    for _, r in df[hit].iterrows():
        code = str(r.get("isin") or "").strip().upper()
        if not code or code in known:
            continue
        out.append({**BLANK, "isin": code, "ticker": r["ticker"], "name": r["name"], "scope": None,
                    "source": "discovery",
                    "category": r.get("category") or None, "exchange": r.get("exchange") or None})
        known.add(code)
        if len(out) >= MAX_POOL:
            break
    return out


def candidates(key: str, market: Market, today: date | None = None) -> dict:
    """Where /sector-etfs starts for one sector: the latest record's ETFs, the taxonomy's seeds and matching funds
    of the discovery pool, each with its returns, Yahoo TER and tax status, ranked by the rule with what is known
    so far (the skill fills in TER, size and tracking from the issuers, then the ranking is run again on save)."""
    tax = sector_etf_taxonomy()
    if key not in tax.sectors:
        from .errors import NotFound

        raise NotFound(f"{key} is not a sector of config/sector_etfs.yaml ({', '.join(tax.sectors)}).")
    d = tax.sectors[key]
    today = today or date.today()
    rec = sector_etfs.latest()
    current = next((s for s in (rec or {}).get("sectors", []) if s["key"] == key), None)
    rows = [{**e, "source": "record"} for e in (current or {}).get("etfs", [])]
    known = {e["isin"] for e in rows}
    for s in d.seeds:
        if s.isin not in known:
            rows.append({**BLANK, "isin": s.isin, "ticker": s.ticker, "name": s.name, "scope": s.scope,
                         "source": "seed"})
            known.add(s.isin)
    pool = _pool(key, d.match, known)
    prices, bench, years = Prices(market), bench_dkk(market), positive_list_years()
    ts = pd.Timestamp(today)
    known_rows = rank([enrich(e, prices, bench, years, today.year, ts) for e in rows])
    return {"key": key, "label": d.label, "parent": d.parent, "rotation": d.rotation,
            "current_pick": current["pick"] if current else None,
            "current_updated": current["updated"] if current else None,
            "candidates": known_rows,
            "pool": [{**e, "tax": tax_status(e["isin"], years, today.year)} for e in pool],
            "fields": "per ETF: isin, ticker, name, scope (world|us|europe|other), issuer, index, ter (fraction), "
                      "distribution (acc|dist), domicile, currency, aum_musd, tracking_diff (fraction a year), "
                      "sources (URLs), checked (date); unknown is null"}
