"""The guide (guide.py): Danish user guide and textbook; and the notebook (notebook.py): briefs, research
memos and the decision journal."""
from __future__ import annotations

from typing import Any, Literal

from .common import Strict


class GuideChapterRef(Strict):
    slug: str
    title: str


class GuidePart(Strict):
    title: str
    chapters: list[GuideChapterRef]


class GuideBook(Strict):
    id: str
    title: str
    intro: str
    parts: list[GuidePart]


class GuideTree(Strict):
    books: list[GuideBook]
    page_links: dict[str, str]
    glossary_links: dict[str, str]
    settings: dict[str, str]          # settings.yaml's values by dotted key, for the glossary's {{settings:…}}


class GuideHeading(Strict):
    level: int
    text: str
    id: str


class GuideLink(Strict):
    book: str
    slug: str
    title: str


class GuideChapter(Strict):
    book: str
    book_title: str
    part: str
    slug: str
    title: str
    markdown: str
    headings: list[GuideHeading]
    prev: GuideLink | None = None
    next: GuideLink | None = None
    updated: str


class GuideHit(Strict):
    book: str
    slug: str
    title: str
    section: str | None = None
    anchor: str | None = None
    snippet: str


NotebookKind = Literal["briefs", "research", "compare", "proposals", "proposal_reviews", "scout", "journal", "reviews"]


class JournalMeta(Strict):
    """A journal entry's front matter (missing fields are None, never guessed)."""
    type: str | None = None                 # hypothesis: a /scout run's decisions (no ticker); else a trade decision
    ticker: str | None = None
    action: str | None = None
    account: str | None = None
    horizon: str | None = None
    style: str | None = None                # momentum, value, core or tactical: what a style-scoped trading rule reads
    status: str | None = None
    review_by: str | None = None
    views: list[Any] | None = None


class NotebookEntry(Strict):
    kind: NotebookKind
    name: str
    title: str
    date: str
    size: int
    ticker: str | None = None
    problem: str | None = None
    meta: JournalMeta | None = None
    review_due: bool


class NotebookListing(Strict):
    briefs: list[NotebookEntry]
    research: list[NotebookEntry]
    compare: list[NotebookEntry]
    proposals: list[NotebookEntry]
    proposal_reviews: list[NotebookEntry]
    scout: list[NotebookEntry]
    journal: list[NotebookEntry]
    reviews: list[NotebookEntry]


class NotebookDocument(NotebookEntry):
    markdown: str
    headings: list[GuideHeading]
