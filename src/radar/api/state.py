"""The server's state: the price store (loaded once, swapped in when a ticker's prices are downloaded) under one lock,
and the data home's gate."""
from __future__ import annotations

import threading

from .. import errors, ops, paths, profile
from ..datahome import home
from ..market import Market

gate: tuple[str, str | None] | None = None      # (state, why read-only), from home.gate() at start


# The price store and its lock: one download, reload or read of it at a time. Re-entrant, so a route that holds it
# can call market(), ensure() or has_prices() (they take it too) without deadlocking.
lock = threading.RLock()
_market: Market | None = None


def market() -> Market:
    """The price store, reloaded when `radar update` has written a new one (under the lock: one load at a time)."""
    global _market
    with lock:
        if _market is None or _market.stale():
            _market = Market.load()
        return _market


def ensure(symbol: str, missing: str = "404", refresh: bool = False) -> bool:
    """Prices for `symbol` in the store (an untracked one is downloaded and the store swapped in). Unknown to
    Yahoo: 404, or False with `missing="ignore"`."""
    global _market
    with lock:
        try:
            _market = profile.ensure_prices(symbol, market(), refresh=refresh)
            return True
        except profile.TickerNotFound as e:
            if missing == "ignore":
                return False
            raise errors.NotFound(str(e)) from e


def drop_prices() -> None:
    """Load the price store again on next use (a restore replaced the data under it)."""
    global _market
    with lock:
        _market = None



def has_prices(symbol: str) -> bool:
    """Make sure prices exist for `symbol` (downloads an untracked one); False if Yahoo has none."""
    return ensure(symbol, missing="ignore")



def open_home() -> tuple[str, str | None]:
    """Once a usable data home is known: tidy the operations log and record this version in the manifest.
    Returns the home's (state, why read-only)."""
    global gate
    gate = home.gate()
    if gate[0] != "ok":
        return gate
    from ..datahome import backup

    try:
        backup.before_upgrade()                  # a new version's first start: keep the data as it was
        home.upgrade(paths.locations().home)
        backup.daily()
    except Exception as e:                       # a full disk must not stop the app; the Data page shows the age
        ops.event("error", "job", f"backup: {type(e).__name__}: {e}", source="backup", exc=e)
    home.touch(paths.locations().home)
    ops.mark_interrupted()   # a job 'running' in the log from an earlier server can't still be running
    ops.prune()
    return gate



def reset() -> None:
    """Forget the loaded prices and the data home's state (tests; a new data home)."""
    global _market, gate
    _market, gate = None, None
