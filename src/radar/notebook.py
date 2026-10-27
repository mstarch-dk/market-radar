"""The notebook: what the Claude skills write as Markdown, shown read-only in the app (the Notebook page).

- `briefs/YYYY-MM-DD.md` (/market-brief and the monthly scheduled task)
- `research/<TICKER>.md` (/research) and `research/compare/YYYY-MM-DD_<tickers>.md` (/compare)
- `research/proposals/YYYY-MM-DD_<portfolio>.md` (/propose-portfolio) and `research/proposals/reviews/YYYY-MM.md`
- `journal/YYYY-MM-DD-<TICKER>-<action>.md` with YAML front matter (/journal) and `journal/reviews/YYYY-MM.md`

All of these folders are local and personal (gitignored, left out of the public export). A document is only ever
read by a name from the listing, so a crafted URL can't reach any other file. Writing stays with the skills.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import yaml

from . import guide
from .paths import HOME

# kind -> folder (each holds *.md directly; subfolders are their own kinds)
FOLDERS = {
    "briefs": HOME / "briefs",
    "research": HOME / "research",
    "compare": HOME / "research" / "compare",
    "proposals": HOME / "research" / "proposals",
    "proposal_reviews": HOME / "research" / "proposals" / "reviews",
    "journal": HOME / "journal",
    "reviews": HOME / "journal" / "reviews",
}
JOURNAL_FIELDS = ("ticker", "action", "account", "horizon", "style", "status", "review_by", "views")
DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}(?:-\d{2})?)")


class NotFound(KeyError):
    pass


def _iso(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()[:10]
    return v


def split_front_matter(text: str) -> tuple[dict | None, str, str | None]:
    """(front matter, body, problem). No front matter is (None, text, None); a broken one keeps the text and says
    what is wrong, so the entry is still listed."""
    if not text.startswith("---"):
        return None, text, None
    end = re.search(r"^---\s*$", text[3:], re.M)
    if not end:
        return None, text, "front matter is not closed with ---"
    raw, body = text[3:3 + end.start()], text[3 + end.end():].lstrip("\n")
    try:
        meta = yaml.safe_load(raw) or {}
    except yaml.YAMLError as e:
        return None, body, f"front matter can't be read ({type(e).__name__})"
    if not isinstance(meta, dict):
        return None, body, "front matter is not a set of fields"
    return {k: _iso(v) for k, v in meta.items()}, body, None


def _title(body: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+?)\s*$", body, re.M)
    return guide.plain(m.group(1)) if m else fallback


def _entry(kind: str, path: Path, today: date) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body, problem = split_front_matter(text)
    m = DATE_PREFIX.match(path.stem)
    when = (meta or {}).get("date") or (m.group(1) if m else datetime.fromtimestamp(path.stat().st_mtime).date().isoformat())
    out = {"kind": kind, "name": path.stem, "title": _title(body, path.stem), "date": str(when),
           "size": path.stat().st_size, "ticker": None, "problem": problem, "meta": None, "review_due": False}
    if kind == "research":
        out["ticker"] = path.stem.upper()
    if kind == "journal":
        fields = {k: (meta or {}).get(k) for k in JOURNAL_FIELDS}
        if fields["views"] is not None and not isinstance(fields["views"], list):
            fields["views"] = [fields["views"]]
        for k in ("ticker", "action", "account", "horizon", "style", "status", "review_by"):
            fields[k] = None if fields[k] is None else str(fields[k])
        out["meta"] = fields
        out["ticker"] = fields["ticker"]
        rb = fields["review_by"]
        try:
            out["review_due"] = fields["status"] == "open" and rb is not None and date.fromisoformat(rb[:10]) <= today
        except ValueError:
            out["problem"] = out["problem"] or f"review_by is not a date: {rb}"
        if meta is None and not problem:
            out["problem"] = "no front matter (status, account and review date unknown)"
    return out


def _files(kind: str) -> list[Path]:
    d = FOLDERS[kind]
    return sorted(p for p in d.glob("*.md") if p.is_file()) if d.is_dir() else []


def listing(today: date | None = None) -> dict:
    """Every document per kind, newest first."""
    today = today or date.today()
    out = {}
    for kind in FOLDERS:
        rows = [_entry(kind, p, today) for p in _files(kind)]
        out[kind] = sorted(rows, key=lambda r: (r["date"], r["name"]), reverse=True)
    return out


def document(kind: str, name: str, today: date | None = None) -> dict:
    """One document by its listed name: the Markdown without front matter, its headings and its listing fields."""
    if kind not in FOLDERS:
        raise NotFound(kind)
    match = next((p for p in _files(kind) if p.stem == name), None)
    if match is None:
        raise NotFound(f"{kind}/{name}")
    _, body, _ = split_front_matter(match.read_text(encoding="utf-8", errors="replace"))
    return _entry(kind, match, today or date.today()) | {"markdown": body, "headings": guide.headings(body)}
