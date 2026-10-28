"""What the command groups share: running a command as a recorded job, number formats, JSON out, choosing portfolios."""
from contextlib import contextmanager

import typer

PHASE_EVERY = 5.0   # seconds between a phase's progress lines in the terminal


@contextmanager
def tracked_job(kind: str):
    """Record a CLI run in the operations log (ops.db in the cache) like the app's jobs; yields its log function
    and a progress tracker. The log, each step ("[4/20] Prices"), a phase's progress every few seconds and each
    issue go to stderr, so a command's --json output on stdout stays valid JSON; the app and the MCP server follow
    the same run from the operations log while it runs. An update or scan that is already running elsewhere ends
    the command with its message and exit code 1."""
    import time
    from datetime import datetime

    from .. import locks, ops
    from ..progress import Progress

    lines: list[str] = []
    live: list[ops.Live] = []
    seen: dict = {"step": None, "issues": 0, "phase_at": 0.0}

    def log(line: str) -> None:
        typer.echo(line, err=True)
        lines.append(f"{datetime.now():%H:%M:%S} {line}")
        if live:
            live[0].update(lines=lines[-200:])

    def changed(snap: dict, urgent: bool) -> None:
        step, phase = snap["step"], snap["phase"]
        if step and step["key"] != seen["step"]:
            typer.echo(f"[{step['i']}/{step['n']}] {step['label']}…", err=True)
        seen["step"] = step["key"] if step else None
        new = snap["issues_total"] - seen["issues"]
        for i in snap["issues"][-new:] if new > 0 else []:
            typer.echo(f"  ! {i['message']}", err=True)
        seen["issues"] = snap["issues_total"]
        if phase and phase["total"] and (time.monotonic() - seen["phase_at"] >= PHASE_EVERY
                                         or phase["done"] == phase["total"]):
            typer.echo(f"  … {phase['label']}: {phase['done']} of {phase['total']}", err=True)
            seen["phase_at"] = time.monotonic()
        if live:
            live[0].update(progress=snap, urgent=urgent)

    progress = Progress("Working", changed)
    try:
        with ops.job(kind, lines) as jid:
            live.append(ops.Live(jid))
            try:
                yield log, progress
            finally:
                live[0].close(progress.snapshot() | {"phase": None, "step": None}, lines[-200:])
    except locks.Busy as e:
        typer.echo(f"Not started: {e}.", err=True)
        raise typer.Exit(1) from None


@contextmanager
def job(kind: str):
    """`tracked_job` for a command that only logs: yields its log function."""
    with tracked_job(kind) as (log, _):
        yield log


@contextmanager
def study_job():
    """`job("study")` holding the study lock: one study at a time, from a terminal or the app (studyrun.py)."""
    from .. import locks, studyrun

    with job(studyrun.KIND) as log, locks.file_lock(studyrun.LOCK, timeout=0, what=studyrun.BUSY):
        yield log


def portfolio_ids(names: list[str] | None, tags: list[str] | None) -> list[int]:
    """Portfolio names (and tags) as ids; an unknown name stops the command."""
    from .. import userstore

    ids = []
    for n in names or []:
        p = userstore.portfolio_by_name(n)
        if not p:
            raise SystemExit(f"No portfolio called {n!r}: see `radar portfolios list`.")
        ids.append(p["id"])
    return userstore.portfolio_ids(ids=ids, tags=tags) if (ids or tags) else []


def one_portfolio(name: str) -> dict:
    from .. import userstore

    p = userstore.portfolio_by_name(name)
    if not p:
        raise SystemExit(f"No portfolio called {name!r}: see `radar portfolios list`.")
    return p


def fmt_pct(v, signed: bool = True) -> str:
    return "–" if v is None else (f"{v:+.1%}" if signed else f"{v:.0%}")


def fmt_num(v, fmt: str = "+.2f") -> str:
    return "–" if v is None else format(v, fmt)


def to_json(obj, **kw) -> str:
    from ..jsonsafe import dumps

    return dumps(obj, **kw)
