"""The Danish books served in the app (the Guide page): a user guide (brugervejledning) and a textbook (lærebog).

`guide/guide.yaml` decides everything about order and titles: books → parts → chapters (`slug`, `title`), one
Markdown file per chapter at `guide/<book>/<slug>.md`. Files are only ever reached through the manifest, so a
crafted URL can't read anything else. Chapters may quote live settings with `{{settings:regime.vix_calm}}`
and the tax rules with `{{tax:2026.ask.rate}}` (`|pct` shows a fraction as a percentage, `|raw` keeps the decimal
point, for formulas), so the text never drifts from config/settings.yaml or config/tax_dk.yaml.
Heading ids (the `#anker` part of a link) are made here, once, and the page uses them.
"""
from __future__ import annotations

import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import yaml

from .config import ROOT, load_yaml, settings

GUIDE = ROOT / "guide"
MANIFEST = GUIDE / "guide.yaml"

PLACEHOLDER = re.compile(r"\{\{(settings|tax):([A-Za-z0-9_.]+)(?:\|(pct|raw))?\}\}")
FENCE = re.compile(r"^(```|~~~)")
HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")


class NotFound(KeyError):
    pass


# ---------------- manifest ----------------

@lru_cache(maxsize=4)
def _manifest(mtime: float) -> dict:
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    order = []                                     # (book, slug) in reading order, per book
    for book in data["books"]:
        for part in book["parts"]:
            for ch in part["chapters"]:
                order.append((book["id"], ch["slug"], ch["title"], part["title"]))
    data["_order"] = order
    return data


def manifest() -> dict:
    return _manifest(MANIFEST.stat().st_mtime)


def path(book: str, slug: str) -> Path:
    """The chapter's file, if the manifest lists it."""
    if not any(b == book and s == slug for b, s, _, _ in manifest()["_order"]):
        raise NotFound(f"{book}/{slug}")
    return GUIDE / book / f"{slug}.md"


def tree() -> dict:
    """Books, parts and chapter titles for the sidebar, plus the app's links into the books."""
    m = manifest()
    return {
        "books": [{"id": b["id"], "title": b["title"], "intro": b.get("intro", ""),
                   "parts": [{"title": p["title"], "chapters": [{"slug": c["slug"], "title": c["title"]}
                                                               for c in p["chapters"]]}
                             for p in b["parts"]]} for b in m["books"]],
        "page_links": m.get("page_links") or {},
        "glossary_links": m.get("glossary_links") or {},
        "settings": settings_text(),
    }


def settings_text() -> dict[str, str]:
    """Every setting that is a value (or a list of values) by its dotted key, as plain text: what the app's hover
    help quotes with `{{settings:…}}` (web/src/lib/glossary.ts), so it never states a stale threshold."""
    out: dict[str, str] = {}

    def walk(v, key: str) -> None:
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, f"{key}.{k}" if key else str(k))
        elif v is not None and not (isinstance(v, list) and any(isinstance(x, (dict, list)) for x in v)):
            out[key] = _fmt(v, "raw")
    walk(settings(), "")
    return out


# ---------------- text ----------------

def _setting(key: str, source: str = "settings"):
    v = settings() if source == "settings" else load_yaml("tax_dk.yaml")["years"]
    for part in key.split("."):
        part_ = int(part) if source == "tax" and part.isdigit() else part
        if not isinstance(v, dict) or part_ not in v:
            raise KeyError(f"{source} has no {key}")
        v = v[part_]
    return v


def _fmt(v, how: str | None) -> str:
    if how == "pct":
        return _fmt(round(v * 100, 4), None) + " %"
    if isinstance(v, bool):
        return "til" if v else "fra"
    if isinstance(v, float):
        s = f"{v:g}"
        return s if how == "raw" else s.replace(".", ",")
    if isinstance(v, (list, tuple)):
        return ", ".join(_fmt(x, how) for x in v)
    if isinstance(v, int) and abs(v) >= 10_000 and how != "raw":
        return f"{v:,}".replace(",", ".")              # Danish thousands: 10.000
    return str(v)


def fill(md: str) -> str:
    """Replace `{{settings:…}}` and `{{tax:…}}` with today's value from settings.yaml or tax_dk.yaml (Danish
    decimal comma unless `|raw`)."""
    return PLACEHOLDER.sub(lambda m: _fmt(_setting(m.group(2), m.group(1)), m.group(3)), md)


def plain(text: str) -> str:
    """Heading or paragraph text without Markdown: links, emphasis, code and math markers."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[`*_]|\$+", "", text)
    return text.strip()


def slug(text: str) -> str:
    """The id of a heading: lower case, letters (æøå included) and digits, words joined by '-'."""
    s = plain(text).lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"[\s_]+", "-", s).strip("-")


def _lines(md: str):
    """(line, inside a code fence?) for each line."""
    fenced = False
    for line in md.splitlines():
        if FENCE.match(line.strip()):
            fenced = not fenced
            yield line, True
            continue
        yield line, fenced


def headings(md: str) -> list[dict]:
    """Every heading (h1–h4) outside code, in order, with a unique id."""
    out: list[dict] = []
    seen: dict[str, int] = {}
    for line, fenced in _lines(md):
        m = None if fenced else HEADING.match(line)
        if not m:
            continue
        text = plain(m.group(2))
        base = slug(m.group(2)) or "afsnit"
        n = seen.get(base, 0)
        seen[base] = n + 1
        out.append({"level": len(m.group(1)), "text": text, "id": base if n == 0 else f"{base}-{n}"})
    return out


# ---------------- chapters ----------------

def chapter(book: str, slug_: str) -> dict:
    p = path(book, slug_)
    md = fill(p.read_text(encoding="utf-8"))
    order = [o for o in manifest()["_order"] if o[0] == book]
    i = next(n for n, o in enumerate(order) if o[1] == slug_)
    _, _, title, part = order[i]
    book_title = next(b["title"] for b in manifest()["books"] if b["id"] == book)

    def ref(o):
        return {"book": o[0], "slug": o[1], "title": o[2]} if o else None
    return {"book": book, "book_title": book_title, "part": part, "slug": slug_, "title": title, "markdown": md,
            "headings": headings(md), "prev": ref(order[i - 1] if i > 0 else None),
            "next": ref(order[i + 1] if i + 1 < len(order) else None),
            "updated": datetime.fromtimestamp(p.stat().st_mtime).date().isoformat()}


def _sections(md: str) -> list[tuple[str | None, str]]:
    """(heading id, its text) blocks of a chapter, the text before the first h2 under None."""
    hs = iter(headings(md))
    out: list[tuple[str | None, str]] = []
    cur: str | None = None
    buf: list[str] = []
    for line, fenced in _lines(md):
        if not fenced and HEADING.match(line):
            h = next(hs)
            if h["level"] == 1:
                continue
            out.append((cur, "\n".join(buf)))
            cur, buf = h["id"], [h["text"]]
            continue
        buf.append(line)
    out.append((cur, "\n".join(buf)))
    return [(i, t) for i, t in out if t.strip()]


def _snippet(text: str, term: str, width: int = 90) -> str:
    flat = " ".join(plain(text).split())
    i = flat.lower().find(term)
    if i < 0:
        return flat[:2 * width] + ("…" if len(flat) > 2 * width else "")
    start, end = max(0, i - width), min(len(flat), i + len(term) + width)
    return ("…" if start else "") + flat[start:end] + ("…" if end < len(flat) else "")


def search(q: str, limit: int = 20) -> list[dict]:
    """Sections whose text holds every word of `q` (any case); title and heading hits first."""
    terms = [t for t in q.lower().split() if t]
    if not terms:
        return []
    hits = []
    for book, slug_, title, _ in manifest()["_order"]:
        md = fill(path(book, slug_).read_text(encoding="utf-8"))
        hs = {h["id"]: h["text"] for h in headings(md)}
        for sid, text in _sections(md):
            low = text.lower()
            if not all(t in low for t in terms):
                continue
            head = (hs.get(sid) or title).lower()
            score = 3 * all(t in title.lower() for t in terms) + 2 * all(t in head for t in terms) + 1
            hits.append({"book": book, "slug": slug_, "title": title, "section": hs.get(sid), "anchor": sid,
                         "snippet": _snippet(text, terms[0]), "score": score})
    hits.sort(key=lambda h: -h["score"])
    out: list[dict] = []
    per_chapter: dict[tuple[str, str], int] = {}
    for h in hits:                              # at most 3 sections per chapter, so other chapters show too
        n = per_chapter.get((h["book"], h["slug"]), 0)
        if n < 3:
            per_chapter[(h["book"], h["slug"])] = n + 1
            del h["score"]
            out.append(h)
    return out[:limit]
