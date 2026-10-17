"""What the command groups share: running a command as a recorded job, number formats, JSON out, choosing portfolios."""
from contextlib import contextmanager

import typer


@contextmanager
def job(kind: str):
    """Record a CLI run in the operations log (ops.db in the cache) like the app's jobs; yields its log function.
    Progress goes to stderr, so a command's --json output on stdout stays valid JSON. An update or scan that is
    already running elsewhere ends the command with its message and exit code 1."""
    from datetime import datetime

    from .. import locks, ops

    lines: list[str] = []

    def log(line: str) -> None:
        typer.echo(line, err=True)
        lines.append(f"{datetime.now():%H:%M:%S} {line}")
    try:
        with ops.job(kind, lines):
            yield log
    except locks.Busy as e:
        typer.echo(f"Not started: {e}.", err=True)
        raise typer.Exit(1) from None


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
