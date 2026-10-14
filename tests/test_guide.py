"""The Danish books in guide/: the manifest and the files agree, every placeholder and link resolves, and the API
serves chapters, search and the app's links into them."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import api, guide

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.S)
MATH = re.compile(r"\$\$.*?\$\$|\$[^$\n]+\$", re.S)


def _chapters():
    return [(b, s) for b, s, _, _ in guide.manifest()["_order"]]


def _app_routes() -> set[str]:
    main = (ROOT / "web" / "src" / "main.tsx").read_text(encoding="utf-8")
    return set(re.findall(r'\["(/[a-z]+)",', main)) | {"/", "/guide"}


def test_every_listed_chapter_exists_and_every_file_is_listed():
    listed = {guide.GUIDE / b / f"{s}.md" for b, s in _chapters()}
    assert len(listed) == len(_chapters()), "a slug is listed twice"
    for p in listed:
        assert p.exists(), f"missing {p.relative_to(ROOT)}"
    for book in {b for b, _ in _chapters()}:
        orphans = set((guide.GUIDE / book).glob("*.md")) - listed
        assert not orphans, f"not in guide.yaml: {sorted(o.name for o in orphans)}"


@pytest.mark.parametrize("book,slug", _chapters())
def test_chapter_title_placeholders_and_links(book, slug):
    ch = guide.chapter(book, slug)              # fails on an unknown {{settings:…}}
    md = ch["markdown"]
    assert md.splitlines()[0] == f"# {ch['title']}", "first line must be '# <title from guide.yaml>'"
    assert "{{" not in CODE.sub("", md), "an unresolved placeholder"
    assert sum(h["level"] == 1 for h in ch["headings"]) == 1, "one H1 per chapter"
    routes = _app_routes()
    for href in LINK.findall(MATH.sub("", CODE.sub("", md))):
        if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I):
            continue                            # external
        target, _, anchor = href.partition("#")
        if not target:
            ids = {h["id"] for h in ch["headings"]}
        elif target.startswith("/"):
            path = target.split("?")[0]
            assert path in routes or path.startswith(("/ticker/", "/guide/")), f"{href}: no such app page"
            continue
        else:
            b, _, s = target.partition("/")
            assert (b, s) in _chapters(), f"{href}: no such chapter"
            ids = {h["id"] for h in guide.chapter(b, s)["headings"]}
        if anchor:
            assert anchor in ids, f"{href}: no heading with that id"


def test_app_links_into_the_books_resolve():
    tree = guide.tree()
    glossary = (ROOT / "web" / "src" / "lib" / "glossary.ts").read_text(encoding="utf-8")
    keys = set(re.findall(r"^  (\w+):", glossary, re.M))
    for route, target in tree["page_links"].items():
        assert route in _app_routes() or route == "/ticker", f"page_links: no page {route}"
        assert tuple(target.split("/")) in _chapters(), f"page_links {route}: no chapter {target}"
    for key, target in tree["glossary_links"].items():
        assert key in keys, f"glossary_links: {key} is not in glossary.ts"
        where, _, anchor = target.partition("#")
        assert tuple(where.split("/")) in _chapters(), f"glossary_links {key}: no chapter {where}"
        assert not anchor or anchor in {h["id"] for h in guide.chapter(*where.split("/"))["headings"]}, \
            f"glossary_links {key}: no heading #{anchor}"


def test_slugs_and_headings():
    assert guide.slug("Sådan gør radaren") == "sådan-gør-radaren"
    assert guide.slug("RS-Ratio og `RS-Momentum`") == "rs-ratio-og-rs-momentum"
    assert guide.slug("Beta, alfa & R²") == "beta-alfa-r²"
    md = "# T\n\n## A\n\n```\n## not a heading\n```\n\n## A\n### [B](x)\n"
    assert [(h["level"], h["id"]) for h in guide.headings(md)] == [(1, "t"), (2, "a"), (2, "a-1"), (3, "b")]


def test_placeholders_format_danish():
    assert guide.fill("{{settings:regime.vix_calm}}") == "18"
    assert guide.fill("{{settings:regime.rates_shock}}") == "0,5"
    assert guide.fill("{{settings:regime.rates_shock|raw}}") == "0.5"
    assert guide.fill("{{settings:regime.oil_shock|pct}}") == "30 %"
    with pytest.raises(KeyError):
        guide.fill("{{settings:regime.nope}}")


# ---------------- API ----------------

@pytest.fixture
def client():
    return TestClient(api.app)


def test_guide_endpoints(client):
    tree = client.get("/api/guide").json()
    assert [b["id"] for b in tree["books"]] == ["brugervejledning", "laerebog"]
    first = tree["books"][0]["parts"][0]["chapters"]
    ch = client.get(f"/api/guide/brugervejledning/{first[0]['slug']}").json()
    assert ch["prev"] is None and ch["next"]["slug"] == first[1]["slug"] and ch["headings"][0]["level"] == 1
    assert client.get("/api/guide/laerebog/nope").status_code == 404
    assert client.get("/api/guide/laerebog/..%2F..%2FREADME").status_code == 404
    assert client.get("/api/guide/guide.yaml/x").status_code == 404


def test_guide_search(client):
    hits = client.get("/api/guide/search?q=momentum").json()
    assert hits and all({"book", "slug", "title", "snippet"} <= set(h) for h in hits)
    assert client.get("/api/guide/search?q=zzqqxxnotaword").json() == []
    assert client.get("/api/guide/search?q=a").status_code == 422
