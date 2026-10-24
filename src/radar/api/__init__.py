"""Local web API for the radar (`radar serve`), served from 127.0.0.1 only, without authentication. `app.py` builds the
app (lifespan, error handlers, middlewares, the web app) from one router per page area; `state.py` holds the price
store and its lock; `common.py` what the routers share."""
from . import common, state
from .app import WEB_DIST, app, rebuild_if_older
from .state import has_prices, market, reset

__all__ = ["WEB_DIST", "app", "common", "has_prices", "market", "rebuild_if_older", "reset", "state"]
