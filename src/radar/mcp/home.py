"""Tools that read the data folder and the reports: where things are, your notes and views, the summary in slices,
the studies and the notebook (briefs, research, proposals, journal)."""
from __future__ import annotations

import json
from datetime import date

from .. import errors, notebook, paths, propose
from .. import market_views as mv
from ..config import typed
from ..datahome import home as homes
from ..model import artifacts
from .common import freshness


def data_paths() -> dict:
    """Where your data folder, history, market-data cache and reports are, and whether the data folder is usable
    (`state`: ok, unset, missing, newer). Only needed to write a memo: every reading has its own tool."""
    st = homes.status()
    out = {k: st[k] for k in ("state", "source", "app_version", "home", "cache", "read_only", "warning")}
    if st["state"] != "unset":
        out["folders"] = {key: str(d) for key, _label, d, _tier in paths.folders()}
    return out


def investor_notes() -> dict:
    """The investor's own notes (notes/investor.md in the data folder): accounts, horizon, max position size,
    drawdown tolerance, what to avoid. Read before advising on placement or writing a journal entry."""
    f = paths.NOTES / "investor.md"
    if not f.is_file():
        raise errors.NotFound("No notes/investor.md in the data folder yet: copy investor.example.md from the "
                              "project into notes/investor.md and fill it in.")
    return {"path": str(f), "markdown": f.read_text(encoding="utf-8", errors="replace")}


def market_views(archived: bool = False) -> dict:
    """Your market views (subjective beliefs, not evidence), each with what the radar's data says about it: the
    exposures it helps or hurts and an evidence verdict. Personal. `archived`: the archived ones too."""
    return {"disclaimer": mv.DISCLAIMER, "views": mv.with_evidence(None if archived else "active")}


def summary(sections: list[str] | None = None) -> dict:
    """The digest of the last report (summary.json), in slices: without `sections`, the list of sections and how
    old the report is; with them, only those. Sections include regime, indicators, rotation, momentum_top10,
    momentum_new_entrants, me, portfolios, quality_top10, calendar, positioning_cot, leading_indicators,
    earnings_factset, valuation, revisions_regional, sentiment, coverage. `stale` is true once the report is older
    than the price limit in settings: say so, or run `uv run radar run`."""
    f = paths.REPORTS / "summary.json"
    if not f.is_file():
        raise errors.NotFound("No summary.json yet: run `uv run radar run` first.")
    s = json.loads(f.read_text(encoding="utf-8"))
    head = freshness(s["asof"])
    known = [k for k in s if k != "asof"]
    if not sections:
        return head | {"sections": known}
    unknown = [k for k in sections if k not in s]
    if unknown:
        raise errors.Invalid(f"No section {', '.join(unknown)} in summary.json (known: {', '.join(known)}).")
    return head | {k: s[k] for k in sections}


def discovery(top: int = 8, markets: list[str] | None = None) -> dict:
    """The last discovery scan (names outside the radar's own lists: Nordic, European, positive-list ETFs), cut to
    what a brief needs: per market, the off-radar rows that aren't thin, `check_data` or stale, as the `top` by
    score, the `top` biggest score rises (`d_score`) and those with a `new_high` or `trend_turn`, without the price
    sparklines. `stale` once the scan is older than its price limit in settings (run it weekly: the Discover page,
    or `uv run radar discover`). `markets`: only these keys."""
    from ..discovery import scan

    d = scan.load_report()
    if d is None:
        raise errors.NotFound("No discovery scan yet: start one on the Discover page or run `uv run radar discover`.")
    age = (date.today() - date.fromisoformat(d["asof"][:10])).days
    head = {"asof": d["asof"], "age_days": age, "stale": age > typed().coverage.max_age["discovery_prices"],
            "thresholds": d.get("thresholds")}
    known = [m["key"] for m in d["markets"]]
    unknown = [k for k in markets or [] if k not in known]
    if unknown:
        raise errors.Invalid(f"No market {', '.join(unknown)} in the scan (known: {', '.join(known)}).")
    out = []
    for m in d["markets"]:
        if markets and m["key"] not in markets:
            continue
        ok = [{k: v for k, v in r.items() if k != "spark"} for r in m["rows"]
              if r.get("off_radar") and not (r.get("thin") or r.get("check_data") or r.get("stale"))]
        by_score = sorted((r for r in ok if r.get("score") is not None), key=lambda r: -r["score"])
        risers = sorted((r for r in ok if r.get("d_score") is not None), key=lambda r: -r["d_score"])[:top]
        flagged = [r for r in by_score if r.get("new_high") or r.get("trend_turn")][:top]
        rows = {r["ticker"]: r for r in [*by_score[:top], *risers, *flagged]}
        out.append({"key": m["key"], "label": m["label"], "kind": m["kind"], "names": m["names"],
                    "scored": m["scored"], "off_radar_ok": len(ok), "top": [r["ticker"] for r in by_score[:top]],
                    "risers": [r["ticker"] for r in risers], "flagged": [r["ticker"] for r in flagged],
                    "rows": sorted(rows.values(), key=lambda r: -(r.get("score") or 0))})
    return head | {"markets": out}


def _study(key: str, got: artifacts.Loaded, command: str, today: date) -> dict:
    rep = got.report
    created = rep.created.date() if rep is not None and rep.created else None
    return {"key": key, "status": got.status, "reason": got.reason, "command": f"uv run {command}",
            "created": created, "data_asof": rep.data_asof if rep is not None else None,
            "age_days": (today - created).days if created else None}


def study_reports() -> dict:
    """Every study report (score studies per signal, long-run, proposal, exit and redeploy studies): `status` ok,
    stale (tested another rule than today's settings: its numbers are shown, never acted on), missing or invalid,
    with why, when it was made (`created`, `age_days`), its last day of data and the command that writes it."""
    today = date.today()
    out = [_study(artifacts.run_key("score-study", sig), artifacts.score(
        sig, rule_hash=artifacts.study_rule_hash("score-study", sig)), s.command, today)
           for sig, s in artifacts.SCORE_SIGNALS.items()]
    hashes = {"longrun-study": artifacts.study_rule_hash("longrun-study"), "propose-study": propose.rule_hash()}
    out += [_study(name, artifacts.load(name, rule_hash=hashes.get(name)), spec.command, today)
            for name, spec in artifacts.ARTIFACTS.items() if name != "score-study"]
    return {"studies": out}


def documents(kind: str | None = None, ticker: str | None = None) -> dict:
    """The notebook: what the skills wrote, newest first, per kind (briefs, research, compare, proposals,
    proposal_reviews, journal, reviews), with title, date and for journal entries their front matter (ticker,
    action, account, horizon, status, review_by, views) and `review_due`. Filter by `kind` and/or `ticker`."""
    listing = notebook.listing()
    if kind and kind not in listing:
        raise errors.Invalid(f"kind must be one of {', '.join(listing)}")
    t = ticker.strip().upper() if ticker else None
    return {k: [r for r in rows if t is None or (r["ticker"] or "").upper() == t]
            for k, rows in listing.items() if kind is None or k == kind}


def journal_entries(status: str | None = None, ticker: str | None = None) -> dict:
    """Decision journal entries (front matter and title, newest first), filtered by `status` (open, closed, …)
    and/or `ticker`. `review_due`: an open entry whose review date has come."""
    rows = documents("journal", ticker)["journal"]
    return {"entries": [r for r in rows if status is None or (r["meta"] or {}).get("status") == status]}


def read_document(kind: str, name: str) -> dict:
    """One notebook document by `kind` and `name` as `documents` lists them (e.g. research / NVDA, briefs /
    2026-10-01): its Markdown without front matter, its headings and its listing fields."""
    try:
        return notebook.document(kind, name)
    except notebook.NotFound:
        raise errors.NotFound(f"No {kind} document called {name!r}: see the documents tool "
                              f"(kinds: {', '.join(notebook.FOLDERS)}).") from None


TOOLS = (data_paths, investor_notes, market_views, summary, discovery, study_reports, documents, journal_entries,
         read_document)
