import functools
import socket
import sys
import time
from pathlib import Path

import pytest
from hypothesis import settings

from radar import net, paths
from radar.reporting import coverage
from radar.sources import positive_list

pytest_plugins = ["pytester"]  # tests/test_offline.py runs a nested session

FIXTURES = Path(__file__).parent / "fixtures"
LOCAL = {"localhost", "127.0.0.1", "::1", "", None}

# Property tests (tests/test_properties.py): no per-example deadline (pandas' first call is slow, a CI runner slower)
settings.register_profile("radar", deadline=None)
settings.load_profile("radar")


CACHED = ("radar.api", "radar.reporting.dashboard", "radar.portfolios.performance", "radar.fundamentals.context",
          "radar.sources.valuation", "radar.reporting.tickers", "radar.market_views", "radar.attribution")


def reset_caches() -> None:
    """Every in-memory cache empty again (each module's reset()); a module not imported yet has none."""
    for name in CACHED:
        if name in sys.modules:
            sys.modules[name].reset()


def with_settings(monkeypatch, base: dict | None = None, **changes) -> dict:
    """settings.yaml (or `base`) with `changes` merged in, section by section (`backtest={"fee_bps": 0}`), for the
    rest of the test: settings() and typed() both read it, checked like the file. Returns the raw dict."""
    import copy

    from radar import config
    from radar.config_schema import check

    def merge(base, new):
        if isinstance(base, dict) and isinstance(new, dict):
            return {**base, **{k: merge(base.get(k), v) for k, v in new.items()}}
        return new

    raw = copy.deepcopy(config.load_yaml("settings.yaml") if base is None else base)
    for section, value in changes.items():
        raw[section] = merge(raw.get(section), value)
    loaded = (raw, check(raw))
    monkeypatch.setattr(config, "load_settings", functools.cache(lambda: loaded))
    return raw


class NetworkBlocked(RuntimeError):
    """A test tried to reach the internet. Stub the call (tests/fakes.py), or mark the test `network`."""


@pytest.fixture(autouse=True)
def _offline(request, monkeypatch):
    """Tests never reach the internet: sockets to anything but this machine, and yfinance's curl_cffi session
    (libcurl, so no Python socket), are refused. Production code often swallows errors (a failed name lookup
    becomes the ticker), so every attempt is also recorded and fails the test at teardown."""
    if request.node.get_closest_marker("network"):
        yield []
        return
    tried: list[str] = []

    def refuse(where: str):
        tried.append(where)
        raise NetworkBlocked(f"network access in a test: {where}")

    def host_of(address):
        return address[0] if isinstance(address, tuple) else None

    connect, connect_ex, getaddrinfo = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

    def guarded_connect(self, address):
        if self.family != getattr(socket, "AF_UNIX", object()) and host_of(address) not in LOCAL:
            refuse(f"connect {address!r}")
        return connect(self, address)

    def guarded_connect_ex(self, address):
        if self.family != getattr(socket, "AF_UNIX", object()) and host_of(address) not in LOCAL:
            refuse(f"connect {address!r}")
        return connect_ex(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if (host.decode() if isinstance(host, bytes) else host) not in LOCAL:
            refuse(f"resolve {host!r}")
        return getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    # pacing and retry backoff take no real time: net's clock jumps by what it would have slept
    slept = [0.0]
    monkeypatch.setattr(net, "clock", lambda: time.monotonic() + slept[0])
    monkeypatch.setattr(net, "sleep", lambda s: slept.__setitem__(0, slept[0] + s))
    try:
        from curl_cffi import requests as curl
        monkeypatch.setattr(curl.Session, "request", lambda self, method, url, *a, **kw: refuse(f"{method} {url}"))
    except ImportError:
        pass
    yield tried  # a test of the guard itself clears it
    if tried:
        pytest.fail("the test tried to reach the network (stub it, or mark it `network`): " + "; ".join(tried[:5]),
                    pytrace=False)


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
    reset_caches()
    net.reset()
    yield
    net.reset()
    reset_caches()
    paths.configure(None)


@pytest.fixture
def tmp_data(tmp_path, monkeypatch):
    """Every data folder in one temporary directory (tmp_path), with no positive list and no in-memory caches."""
    paths.configure(paths.Locations.flat(tmp_path))
    monkeypatch.setattr(coverage, "POSITIVE_LIST_FILE", tmp_path / "positivliste.xlsx")
    monkeypatch.setattr(positive_list, "POSITIVE_LIST_FILE", tmp_path / "positivliste.xlsx")
    reset_caches()
    return tmp_path
