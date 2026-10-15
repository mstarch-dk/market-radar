import socket
import sys
from pathlib import Path

import pytest

from radar import coverage, net, paths, tickers, universe, valuation

pytest_plugins = ["pytester"]  # tests/test_offline.py runs a nested session

FIXTURES = Path(__file__).parent / "fixtures"
LOCAL = {"localhost", "127.0.0.1", "::1", "", None}


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
