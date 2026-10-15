"""The test suite never reaches the internet (conftest._offline): a stray call fails the test even when the code
under test swallows the error."""
import socket

import pytest
import requests

from conftest import NetworkBlocked


def test_requests_and_raw_sockets_are_refused(_offline):
    with pytest.raises(NetworkBlocked):
        requests.get("https://example.com", timeout=1)
    with pytest.raises(NetworkBlocked):
        socket.create_connection(("example.com", 80), timeout=1)
    assert len(_offline) == 2
    _offline.clear()   # recorded on purpose here; the teardown check is tested below


def test_yfinance_session_is_refused(_offline):
    from curl_cffi import requests as curl
    with pytest.raises(NetworkBlocked):
        curl.Session().get("https://query2.finance.yahoo.com/v8/finance/chart/SPY")
    assert _offline == ["GET https://query2.finance.yahoo.com/v8/finance/chart/SPY"]
    _offline.clear()


def test_localhost_still_works():
    a, b = socket.socketpair()
    a.sendall(b"ok")
    assert b.recv(2) == b"ok"
    srv = socket.create_server(("127.0.0.1", 0))
    c = socket.create_connection(srv.getsockname(), timeout=1)
    c.close(), srv.close(), a.close(), b.close()


def test_a_swallowed_attempt_still_fails_the_test(pytester):
    pytester.makeconftest((__import__("pathlib").Path(__file__).parent / "conftest.py").read_text(encoding="utf-8"))
    pytester.makepyfile("""
        import requests
        def test_swallows():
            try:
                requests.get("https://example.com", timeout=1)
            except Exception:
                pass
    """)
    res = pytester.runpytest("-p", "no:cacheprovider")
    res.assert_outcomes(passed=1, errors=1)   # the body passes; the teardown check fails it
    res.stdout.fnmatch_lines(["*tried to reach the network*"])
