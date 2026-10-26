"""What the tools share: the price store, choosing portfolios by name, how old a reading is, and the one way a tool
answers (JSON text without NaN) or fails (a message the client shows)."""
from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from datetime import date

from mcp.server.mcpserver.exceptions import ToolError

from .. import errors, notebook, profile, userstore
from ..config import typed
from ..jsonsafe import dumps
from ..market import Market
from ..portfolios import trades

UNITS = ("Returns and weights are fractions (0.12 = 12 %), money is DKK unless a field says otherwise, and null "
         "means not available: say n/a, never 0.")

_market: Market | None = None


def market() -> Market:
    """The price store, loaded once and again when `radar update` has written a new one."""
    global _market
    if _market is None or _market.stale():
        try:
            _market = Market.load()
        except SystemExit as e:                  # Market.load: no price data yet
            raise errors.NotFound(str(e)) from None
    return _market


def reset() -> None:
    """Forget the loaded prices (tests; a new data folder)."""
    global _market
    _market = None


def selection(portfolios: list[str] | None, tags: list[str] | None, scope: str | None) -> list[int] | None:
    """Which portfolios a tool is about: these names and/or tags, else a scope (real | virtual | all); None means
    the default, your real portfolios."""
    trades.ensure_migrated()
    if portfolios or tags:
        ids = []
        for name in portfolios or []:
            p = userstore.portfolio_by_name(name)
            if not p:
                known = ", ".join(r["name"] for r in userstore.portfolios())
                raise errors.NotFound(f"No portfolio called {name!r} (yours: {known or 'none'}).")
            ids.append(p["id"])
        return userstore.portfolio_ids(ids=ids, tags=tags)
    if scope:
        if scope not in userstore.SCOPES:
            raise errors.Invalid(f"scope must be one of {', '.join(userstore.SCOPES)}")
        return userstore.portfolio_ids(scope)
    return None


def freshness(asof: str, today: date | None = None) -> dict:
    """How old a reading is: stale once older than the price limit in settings (the API's rule, api/common.py)."""
    age = ((today or date.today()) - date.fromisoformat(asof[:10])).days
    return {"asof": asof, "age_days": age, "stale": age > typed().coverage.max_age["prices"]}


def iso_day(value: str | None, what: str) -> str | None:
    try:
        return date.fromisoformat(value).isoformat() if value else None
    except ValueError:
        raise errors.Invalid(f"{what} must be a date, YYYY-MM-DD") from None


FAILURES = (errors.RadarError, notebook.NotFound, profile.TickerNotFound, SystemExit)


def tool(fn: Callable[..., object]) -> Callable[..., str]:
    """A tool from a function that returns plain data: the client gets it as JSON text (NaN and inf as null, dates
    as YYYY-MM-DD), and what the domain refuses as a tool error with its message. The parameters and the
    docstring stay the tool's schema and description."""
    @functools.wraps(fn)
    def run(*args, **kwargs) -> str:
        try:
            return dumps(fn(*args, **kwargs), ensure_ascii=False)
        except FAILURES as e:
            raise ToolError(getattr(e, "message", None) or str(e).strip("'\"")) from None
    run.__signature__ = inspect.signature(fn).replace(return_annotation=str)  # type: ignore[attr-defined]
    return run
