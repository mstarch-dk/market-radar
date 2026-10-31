"""Tools on the engines: a basket proposal for one of your portfolios, from shortlist to frozen picks, evaluation,
shadow portfolios, review and exit check; the hindsight basket (`radar sim picks`); and /scout's frozen hypothesis
candidates and their follow-up. A proposal's picks go in as
structured input and are frozen before the model's numbers are seen; a frozen proposal is named by its id.

The sim tools run `radar sim …` as a child process: the server, like the app, never runs a study in its own process
(the layer contract in pyproject.toml)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .. import errors, evidence, profile, propose, scout, studyrun
from ..config import write_text
from ..jsonsafe import dumps
from .common import market

SIM_TIMEOUT = 1800       # seconds: a basket with its random draws and score check takes minutes, not half an hour


def _frozen(id: str) -> tuple[Path, dict]:
    """The frozen picks file `id` (as `propose_freeze` and `propose_review` name it) and its contents."""
    f = Path(propose.PROPOSALS) / f"{id}.json"
    if Path(id).name != id or id.endswith("-evaluation") or not f.is_file():
        known = [n for n, _ in propose.proposals()]
        raise errors.NotFound(f"No frozen proposal {id!r} (frozen: {', '.join(Path(n).stem for n in known) or 'none'}).")
    doc = json.loads(f.read_text(encoding="utf-8"))
    if not (doc.get("meta") or {}).get("frozen_at"):
        raise errors.Invalid(f"{id} isn't frozen: freeze the picks first with propose_freeze.")
    return f, doc


def propose_candidates(portfolio: str, amount: float, tilt: str = "mix", mode: str = "conviction",
                       n: int | None = None, weighting: str = "equal", max_position: float | None = None,
                       horizon: int = 6, etf: bool = True, top: int = 40) -> dict:
    """The gated, scored shortlist for adding `amount` DKK to `portfolio` (by name), the rule-only basket sized
    with the portfolio's fees, the rule study's view, and `draft_picks`: its `meta` and `picks` (with the standard
    exit criteria) are what `propose_freeze` takes after you choose. `tilt` momentum | value | mix, `mode`
    conviction | fill-gaps, `n` new names (default: amount ÷ the minimum ticket), `weighting` equal | inverse-vol,
    `max_position` the largest position as a share of your whole real book, `horizon` 3 or 6 months, `etf` false to
    leave leftover cash as cash. Analysis, not advice."""
    try:
        return propose.candidates(market(), portfolio, amount, tilt, mode, n, weighting, max_position, etf, horizon,
                                  top)
    except ValueError as e:
        raise errors.Invalid(f"No candidates: {e}") from None


def propose_freeze(meta: dict, picks: list[dict], filler: dict | None = None) -> dict:
    """Freeze a proposal's picks before its numbers are seen: `meta` as `propose_candidates` gave it in
    `draft_picks.meta`, `picks` the chosen names [{ticker, why, exit, swapped_from?, swap_reason?}] (start from
    `draft_picks.picks`), `filler` from `draft_picks.filler`. Stored in exports/proposals/, never overwritten.
    Returns the `id` that `propose_evaluate`, `propose_shadow` and `propose_check` take."""
    stamped: dict[str, Any] = {**meta, "frozen_at": None}         # save_picks stamps it now
    doc = {"type": "propose-picks", "meta": stamped, "picks": picks, "filler": filler}
    try:
        f = Path(propose.save_picks(doc))
    except ValueError as e:
        raise errors.Invalid(f"Not frozen: {e}") from None
    return {"id": f.stem, "file": str(f), "frozen_at": stamped["frozen_at"], "picks": [p["ticker"] for p in picks]}


def propose_evaluate(id: str, max_position: float | None = None, tolerance: float | None = None,
                     light: bool = False) -> dict:
    """Evaluate the frozen proposal `id`: sizing, constraints, exposures before and after vs ACWI, risk, the
    drawdown three ways, the modelled return from the rule study, the alternatives A0-A6 and the decision rule.
    `tolerance`: the largest drawdown you accept (0.25 = 25 %); `light` skips the alternatives. Saved beside the
    picks (review and check read it). Analysis, not advice."""
    f, doc = _frozen(id)
    try:
        rep = propose.evaluate(market(), doc, max_position, tolerance, light=light)
    except ValueError as e:
        raise errors.Invalid(f"Not evaluated: {e}") from None
    propose.keep_evaluation(str(f), rep)
    return rep


def propose_shadow(id: str, name: str) -> dict:
    """Virtual copies of the portfolio plus the amount for the frozen proposal `id`: the proposal (`name`), ACWI
    (`<name> · ACWI`) and the rule-only basket (`<name> · rule`), bought at the latest close and tagged proposal
    and proposal-<date>, so the Returns page follows them. Never touches a real portfolio."""
    _, doc = _frozen(id)
    try:
        return propose.shadow(market(), doc, name)
    except ValueError as e:
        raise errors.Invalid(f"No shadow: {e}") from None


def propose_picks(id: str, with_evaluation: bool = False) -> dict:
    """The frozen proposal `id` as stored: `meta` (portfolio, amount, tilt, date, frozen_at, …) and each pick with
    its `why` and its exit criteria (review level, signal exit, thesis checks, time stop), and whether it has been
    evaluated. `with_evaluation`: also the saved evaluation (as `propose_evaluate` returned it; null when there is
    none). `propose_review` lists the ids (`file` without .json)."""
    f, doc = _frozen(id)
    ev = propose.evaluation_file(f.name)
    out = {"id": id, "type": doc.get("type"), "meta": doc.get("meta"), "picks": doc.get("picks"),
           "filler": doc.get("filler"), "evaluated": ev.exists()}
    if with_evaluation:
        out["evaluation"] = json.loads(ev.read_text(encoding="utf-8")) if ev.exists() else None
    return out


def propose_review() -> dict:
    """Every frozen proposal since its day: return vs ACWI and vs its rule basket, its drawdown against the
    modelled band, and what the trend exit would have done."""
    return propose.review(market())


def propose_check(portfolio: str | None = None) -> dict:
    """Each open proposal's exit criteria today (review level, signal exit, thesis checks, time stop, basket
    drawdown): Intact, Weakening or Triggered, with the evidence. `portfolio`: only proposals for it."""
    return propose.check_exits(market(), portfolio)


def _sim(*args: str) -> Any:
    """`radar sim … --json` as a child process; its JSON, or a tool error with the command's own message."""
    cmd = [sys.executable, "-m", "radar", "sim", *args, "--json"]
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, env=studyrun.child_env(), text=True,
                           encoding="utf-8", errors="replace", timeout=SIM_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise errors.Conflict(f"radar sim {args[0]} took more than {SIM_TIMEOUT // 60} minutes and was stopped.") from None
    if r.returncode != 0:
        lines = [x for x in r.stderr.splitlines() if x.strip()]
        raise errors.Invalid(lines[-1] if lines else f"radar sim {args[0]} stopped (exit code {r.returncode}).")
    return json.loads(r.stdout)


def _opt(flag: str, value) -> list[str]:
    if value is None or value is False:
        return []
    return [flag] if value is True else [flag, str(value)]


def sim_picks_candidates(asof: str, top: int | None = None, blind: bool = False, views: bool = False,
                         model_cutoff: str | None = None, fund: bool = False) -> dict:
    """The stock universe ranked by momentum score as the radar saw it on a past day (`asof`: 1M, 3M, 6M, 1Y back
    from the latest prices, today, or YYYY-MM-DD), from data up to that day only (sectors are today's). `top`: the
    best N; `blind` hides tickers and names (ids C001… by rank); `views` adds your market views created by then
    (personal); `model_cutoff` (YYYY-MM) flags days the picker may know the outcome of; `fund` adds K+V, kvalitet
    and værdi as known on the day (US stocks). For picking a hindsight basket with `sim_picks`."""
    out = _sim("picks-candidates", "--asof", asof, *_opt("--top", top), *_opt("--blind", blind),
               *_opt("--views", views), *_opt("--model-cutoff", model_cutoff), *_opt("--fund", fund))
    return out


def sim_picks(asof: str | None = None, name: str | None = None, picks: list[dict] | None = None,
              meta: dict | None = None, rule: str | None = None, n: int = 15, max_per_sector: int | None = None,
              max_per_group: int | None = None, trend: bool = False, weighting: str = "equal",
              capital: float = 100_000.0, end: str | None = None, model_cutoff: str | None = None,
              tags: list[str] | None = None, rerun: str | None = None) -> dict | list:
    """A basket picked on a past day (`asof`), simulated from there to `end` (default the latest prices): kept,
    with the stop/take-profit rule followed, and the score's own top N as a control, as virtual portfolios named
    after `name` (on the Returns page with ACWI). Give `picks` [{ticker or id, weight?, why?}] with optional `meta`
    (e.g. basis), or `rule` top-n with `n`, `max_per_sector`, `max_per_group`, `trend`, `weighting` equal | score.
    `rerun`: run stored baskets again on the latest prices (a basket's name, or tag:<tag>). Reports the
    equal-weight universe, the percentile among random baskets and that day's score check; writes
    reports/sim-picks/<name>.json. One basket over one period is an illustration, not evidence."""
    args = [*_opt("--asof", asof), *_opt("--name", name), *_opt("--rule", rule), "--n", str(n),
            *_opt("--max-per-sector", max_per_sector), *_opt("--max-per-group", max_per_group),
            *_opt("--trend", trend), "--weighting", weighting, "--capital", str(capital), *_opt("--end", end),
            *_opt("--model-cutoff", model_cutoff), *_opt("--rerun", rerun)]
    for t in tags or []:
        args += ["--tag", t]
    if picks is None:
        out = _sim("picks", *args)
    else:
        with tempfile.TemporaryDirectory() as tmp:       # the CLI takes the picks as a file; nobody writes it by hand
            f = Path(tmp) / "picks.json"
            write_text(f, dumps({"picks": picks, "meta": meta or {}}, ensure_ascii=False))
            out = _sim("picks", *args, "--picks", str(f))
    return out


def scout_freeze(slug: str, statement: str, stage: str, decision: str, horizon: str, proxies: list[str] | None = None,
                 stocks: list[str] | None = None, reason: str | None = None, view_id: int | None = None,
                 report: str | None = None) -> dict:
    """Freeze one /scout candidate as shown today, whatever the user decided, so its follow-up can later say whether
    the rumour paid off and whether the decision added anything: `slug` (e.g. nuclear-smr), `statement` (the
    hypothesis), `stage` whisper | confirming | consensus, `decision` adopted | dismissed | watch, `horizon` 3m | 6m
    | 12m | 3y, `proxies` the proxy ETFs and `stocks` the representative stocks (Yahoo symbols, at most 12 each;
    the proxies are the basket that is scored, the stocks when there is none), `reason` the user's own words,
    `view_id` the view add_view saved (adopted only), `report` the scout report's name. Each ticker's prices are
    downloaded now if the radar doesn't have them, and the daily update keeps them from then on. Stored in
    exports/scout/, dated today, never overwritten. Freeze every shortlisted candidate: the dismissed are the
    control group."""
    c = scout.check({"slug": slug, "statement": statement, "stage": stage, "decision": decision, "horizon": horizon,
                     "proxies": proxies, "stocks": stocks, "reason": reason, "view_id": view_id, "report": report})
    m, unknown = market(), []
    for t in (*c["proxies"], *c["stocks"]):
        try:
            m = profile.ensure_prices(t, m)
        except profile.TickerNotFound:
            unknown.append(t)
    if unknown:
        raise errors.Invalid(f"Not frozen: no Yahoo prices for {', '.join(unknown)} (check the symbols, e.g. with "
                             f"ticker_profile, or leave them out).")
    return scout.freeze(c)


def scout_review() -> dict:
    """Every frozen /scout candidate since its day: its basket (`basket`: the proxy ETFs, or the stocks without one)
    against ACWI over the same days (`ret`, `acwi`, `excess`, `max_dd`), its stocks' `stocks_excess`, tickers with
    no prices (`missing`), and the means per decision (`by_decision`: did the adopted beat the dismissed?) and per
    stage (`by_stage`: did whispers beat consensus?), shown once `need` candidates are `min_months` old. Few
    candidates say nothing yet: say so."""
    return evidence.scout_review(market())


TOOLS = (propose_candidates, propose_freeze, propose_evaluate, propose_shadow, propose_picks, propose_review,
         propose_check, sim_picks_candidates, sim_picks, scout_freeze, scout_review)
