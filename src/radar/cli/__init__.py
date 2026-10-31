"""The `radar` command line. Each command group is a module of this package; importing it registers its
commands on `app` (cli/root.py), the entry point in pyproject.toml (`radar = "radar.cli:app"`)."""
from . import (  # noqa: F401 (registers the commands)
    abtest,
    data,
    fundamentals,
    market,
    portfolios,
    propose,
    rules,
    scout,
    server,
    sim,
    study,
    tax,
)
from .root import app  # noqa: F401
