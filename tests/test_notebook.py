"""The notebook: briefs, research memos, comparisons and the decision journal, listed and read without leaving
their folders."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from radar import api, notebook
from radar.api_models import NotebookDocument, NotebookListing

ENTRY = """---
date: 2026-09-01
ticker: RHM.DE
action: buy
account: ASK
horizon: 3 months
status: open
views: [4]
review_by: 2026-10-01
---
# Buy Rheinmetall (RHM.DE)

## Why (thesis, in the user's words)
Defence budgets.
"""


@pytest.fixture
def folders(tmp_path, monkeypatch):
    dirs = {k: tmp_path / rel for k, rel in
            {"briefs": "briefs", "research": "research", "compare": "research/compare", "journal": "journal",
             "reviews": "journal/reviews"}.items()}
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(notebook, "FOLDERS", dirs)
    (dirs["briefs"] / "2026-09-01.md").write_text("# Market brief – 2026-09-01\n\n## TL;DR\n- a\n", encoding="utf-8")
    (dirs["briefs"] / "2026-10-01.md").write_text("# Markedsbrief – 2026-10-01\n", encoding="utf-8")
    (dirs["briefs"] / "lyt").mkdir()                                # the NotebookLM listening version
    (dirs["briefs"] / "lyt" / "2026-10-01.md").write_text("# Markedsbrief til lytning\n", encoding="utf-8")
    (dirs["research"] / "NOVO-B.CO.md").write_text("# Novo Nordisk\n", encoding="utf-8")
    (dirs["compare"] / "2026-10-14_NVDA-AMD.md").write_text("# NVDA vs AMD\n", encoding="utf-8")
    (dirs["journal"] / "2026-09-01-RHM.DE-buy.md").write_text(ENTRY, encoding="utf-8")
    (dirs["journal"] / "2026-09-02-X-pass.md").write_text("---\nstatus: [open\n---\n# Pass X\n", encoding="utf-8")
    (dirs["reviews"] / "2026-09.md").write_text("# Journal review – September\n", encoding="utf-8")
    (tmp_path / "secret.md").write_text("# not in the notebook\n", encoding="utf-8")
    return dirs


def test_listing_newest_first_with_journal_fields(folders):
    nb = NotebookListing.model_validate(notebook.listing(date(2026, 10, 14))).model_dump()
    assert [b["name"] for b in nb["briefs"]] == ["2026-10-01", "2026-09-01"]   # briefs/lyt/ is not a second brief
    assert nb["briefs"][0]["title"] == "Markedsbrief – 2026-10-01"
    assert nb["research"][0]["ticker"] == "NOVO-B.CO" and nb["compare"][0]["title"] == "NVDA vs AMD"
    entry = next(e for e in nb["journal"] if e["name"] == "2026-09-01-RHM.DE-buy")
    assert entry["meta"] == {"ticker": "RHM.DE", "action": "buy", "account": "ASK", "horizon": "3 months",
                             "status": "open", "review_by": "2026-10-01", "views": [4]}
    assert entry["review_due"] and entry["date"] == "2026-09-01" and entry["title"] == "Buy Rheinmetall (RHM.DE)"
    broken = next(e for e in nb["journal"] if e["name"] == "2026-09-02-X-pass")
    assert broken["problem"] and not broken["review_due"]          # still listed, with what is wrong
    assert nb["reviews"][0]["date"] == "2026-09"


def test_a_closed_or_future_review_is_not_due(folders):
    (folders["journal"] / "2026-09-01-RHM.DE-buy.md").write_text(ENTRY.replace("status: open", "status: closed"),
                                                                 encoding="utf-8")
    assert not notebook.listing(date(2026, 10, 14))["journal"][1]["review_due"]
    assert not notebook.listing(date(2026, 9, 15))["journal"][1]["review_due"]


def test_document_strips_front_matter_and_reads_only_listed_files(folders):
    d = NotebookDocument.model_validate(notebook.document("journal", "2026-09-01-RHM.DE-buy")).model_dump()
    assert d["markdown"].startswith("# Buy Rheinmetall") and [h["id"] for h in d["headings"]][1] == \
        "why-thesis-in-the-users-words"
    for kind, name in (("journal", "../secret"), ("briefs", "nope"), ("etc", "x"), ("research", "compare")):
        with pytest.raises(notebook.NotFound):
            notebook.document(kind, name)


def test_missing_folders_are_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(notebook, "FOLDERS", {k: tmp_path / k for k in notebook.FOLDERS})
    assert all(v == [] for v in notebook.listing().values())


def test_notebook_endpoints(folders):
    c = TestClient(api.app)
    assert c.get("/api/notebook").json()["briefs"][0]["name"] == "2026-10-01"
    assert c.get("/api/notebook/research/NOVO-B.CO").json()["markdown"] == "# Novo Nordisk\n"
    assert c.get("/api/notebook/journal/..%2Fsecret").status_code == 404
    assert c.get("/api/notebook/other/x").status_code == 404
