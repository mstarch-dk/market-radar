import sys
from pathlib import Path

import pytest

from radar import coverage, net, paths, tickers, universe, valuation

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _paths(tmp_path_factory, monkeypatch):
    """Every test gets its own empty data folders (operations log included), never the real ones, and never
    reads or writes this computer's remembered data folder."""
    monkeypatch.delenv(paths.ENV_HOME, raising=False)
    monkeypatch.delenv(paths.ENV_CACHE, raising=False)
    pointer = tmp_path_factory.mktemp("config") / "location.json"
    monkeypatch.setattr(paths, "pointer_file", lambda: pointer)
    defaults = tmp_path_factory.mktemp("defaults")
    monkeypatch.setattr(paths, "default_home", lambda: defaults / "Market Radar")
    monkeypatch.setattr(paths, "default_cache", lambda: defaults / "cache")
    paths.configure(paths.Locations.flat(tmp_path_factory.mktemp("radar")))
    if "radar.api" in sys.modules:
        monkeypatch.setattr(sys.modules["radar.api"], "_gate", None)
    net.reset()
    yield
    net.reset()
    paths.configure(None)


@pytest.fixture
def tmp_data(tmp_path, monkeypatch):
    """Every data folder in one temporary directory (tmp_path), with no positive list and no in-memory caches."""
    paths.configure(paths.Locations.flat(tmp_path))
    monkeypatch.setattr(coverage, "POSITIVE_LIST_FILE", tmp_path / "positivliste.xlsx")
    monkeypatch.setattr(universe, "POSITIVE_LIST_FILE", tmp_path / "positivliste.xlsx")
    monkeypatch.setattr(tickers, "_cache", None)
    monkeypatch.setattr(valuation, "_ctx", None)
    return tmp_path
