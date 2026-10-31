"""/scout's forward record: each shortlisted hypothesis candidate frozen on the day it was shown, with the user's
decision (adopted, dismissed or watch), its narrative stage and a proxy basket, so the Evidence page can later say
whether the rumours paid off against ACWI and whether the user's adopt/dismiss calls added anything.

A record is a JSON file in exports/scout/ (home tier), dated today and never overwritten or back-dated; its tickers
are in the daily update (universe.all_price_tickers) so the follow-up has prices. The follow-up itself is
evidence.scout_review. The skill: .claude/skills/scout/SKILL.md; the guide: brugervejledning/scout.md."""
from __future__ import annotations

import json
import re
from datetime import date, datetime

from .config import write_text
from .errors import Invalid
from .jsonsafe import dumps
from .paths import HOME

RECORDS = HOME / "exports" / "scout"
STAGES = ("whisper", "confirming", "consensus")      # talk ahead of price / talk, price and revisions agree / priced
DECISIONS = ("adopted", "dismissed", "watch")
HORIZONS = ("3m", "6m", "12m", "3y")
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
TICKER = re.compile(r"[A-Z0-9][A-Z0-9.^=-]{0,19}")
MAX_TICKERS = 12


def _tickers(xs: list[str] | None, what: str) -> list[str]:
    out = list(dict.fromkeys(str(x).strip().upper() for x in xs or [] if str(x).strip()))
    bad = [t for t in out if not TICKER.fullmatch(t)]
    if bad:
        raise Invalid(f"Not a Yahoo symbol in {what}: {', '.join(bad)}.")
    if len(out) > MAX_TICKERS:
        raise Invalid(f"At most {MAX_TICKERS} {what}: a candidate's basket is a proxy, not a portfolio.")
    return out


def check(c: dict) -> dict:
    """A candidate as it is frozen: Invalid naming the first problem."""
    slug = str(c.get("slug") or "").strip()
    if not SLUG.fullmatch(slug):
        raise Invalid("slug is lower-case letters, digits and -, up to 40 characters (e.g. nuclear-smr).")
    statement = str(c.get("statement") or "").strip()
    if not statement:
        raise Invalid("A candidate needs its statement (the hypothesis in one sentence).")
    if c.get("stage") not in STAGES:
        raise Invalid(f"stage is one of {', '.join(STAGES)}.")
    if c.get("decision") not in DECISIONS:
        raise Invalid(f"decision is one of {', '.join(DECISIONS)}.")
    if c.get("horizon") not in HORIZONS:
        raise Invalid(f"horizon is one of {', '.join(HORIZONS)}.")
    proxies, stocks = _tickers(c.get("proxies"), "proxies"), _tickers(c.get("stocks"), "stocks")
    if not proxies and not stocks:
        raise Invalid("A candidate needs a proxy ETF or some stocks to follow.")
    view_id = c.get("view_id")
    if view_id is not None and (c["decision"] != "adopted" or not isinstance(view_id, int)):
        raise Invalid("view_id is the id add_view returned, and only for an adopted candidate.")
    return {"slug": slug, "statement": statement, "stage": c["stage"], "decision": c["decision"],
            "horizon": c["horizon"], "proxies": proxies, "stocks": stocks,
            "reason": (str(c.get("reason") or "").strip() or None), "view_id": view_id,
            "report": (str(c.get("report") or "").strip() or None)}


def freeze(candidate: dict, today: date | None = None) -> dict:
    """Write one candidate into exports/scout/ as `<today>_<slug>.json`, stamped now; a second freeze of the same
    slug on the same day gets -2, -3 … (never overwritten). Returns the record with its `id`."""
    rec = check(candidate)
    day = (today or date.today()).isoformat()
    rec = {"type": "scout-candidate", "date": day, "frozen_at": datetime.now().isoformat(timespec="seconds"), **rec}
    RECORDS.mkdir(parents=True, exist_ok=True)
    stem, k = f"{day}_{rec['slug']}", 1
    f = RECORDS / f"{stem}.json"
    while f.exists():
        k += 1
        f = RECORDS / f"{stem}-{k}.json"
    write_text(f, dumps(rec, indent=1, ensure_ascii=False))
    return {"id": f.stem, "file": str(f), **rec}


def records() -> list[dict]:
    """Every frozen candidate, oldest first, each with its `id`; a file that can't be read is listed with its
    `problem` rather than dropped."""
    if not RECORDS.is_dir():
        return []
    out = []
    for f in RECORDS.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            out.append({"id": f.stem, **check(d), "date": str(d["date"])[:10], "frozen_at": d.get("frozen_at"),
                        "_order": f.stat().st_mtime_ns})
        except (ValueError, KeyError, Invalid) as e:
            out.append({"id": f.stem, "problem": f"can't be read: {e}", "_order": f.stat().st_mtime_ns})
    out.sort(key=lambda r: (r.get("date") or "", r.get("frozen_at") or "", r.pop("_order")))   # -2 after its first
    return out


def symbols() -> set[str]:
    """Every ticker a frozen candidate follows (the daily update keeps their prices)."""
    return {t for r in records() if "problem" not in r for t in (*r["proxies"], *r["stocks"])}
