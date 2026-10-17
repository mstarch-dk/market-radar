"""The network layer: per-host pacing, the retry policy, cooldown after repeated 429s, redaction, and that every
request lands in the operations log with its source."""
import threading
from datetime import datetime, timedelta

import pytest
import requests

from radar import net, ops


class Resp:
    def __init__(self, status=200, headers=None, content=b"x"):
        self.status_code, self.headers, self.content = status, headers or {}, content


class FakeTime:
    """A clock that only moves when something sleeps."""

    def __init__(self):
        self.t, self.slept = 1000.0, []

    def clock(self):
        return self.t

    def sleep(self, s):
        self.slept.append(round(s, 3))
        self.t += s


@pytest.fixture
def fake_time(monkeypatch):
    ft = FakeTime()
    monkeypatch.setattr(net, "clock", ft.clock)
    monkeypatch.setattr(net, "sleep", ft.sleep)
    monkeypatch.setattr(net.random, "random", lambda: 0.0)   # no jitter
    return ft


def _replies(monkeypatch, *answers):
    """requests.get answers in turn (an exception instance is raised); returns the calls made."""
    calls, queue = [], list(answers)

    def get(url, **kw):
        calls.append((url, kw))
        a = queue.pop(0)
        if isinstance(a, Exception):
            raise a
        return a
    monkeypatch.setattr(net.requests, "get", get)
    return calls


def test_token_bucket_paces_after_the_burst(fake_time):
    b = net.Bucket(rate=2, burst=3)
    waits = [b.take() for _ in range(5)]
    assert waits[:3] == [0, 0, 0]                      # the burst goes at once
    assert waits[3:] == pytest.approx([0.5, 0.5])      # then 2 a second
    assert fake_time.t == pytest.approx(1001.0)


def test_hosts_matching_one_pattern_share_limits():
    yahoo = net.limits("query2.finance.yahoo.com")
    assert yahoo["pattern"] == "*.yahoo.com" and yahoo["budget"] == 20000
    assert net.limits("example.org")["pattern"] == "*" and net.limits("example.org")["rate"] > 0
    assert net.workers(8) == yahoo["concurrency"] and net.workers(2) == 2


def test_redaction_drops_the_query_and_masks_secrets():
    assert net.redact("https://api.stlouisfed.org/fred/series?series_id=X&api_key=SECRET") == \
        ("api.stlouisfed.org", "/fred/series")
    assert net.redact("https://x.org/v1;api_key=SECRET/data")[1] == "/v1;api_key=***/data"
    assert "SECRET" not in net.redact("https://x.org/a/token=SECRET")[1]


def test_get_records_each_request_with_its_source(fake_time, monkeypatch):
    _replies(monkeypatch, Resp(200, content=b"abcd"))
    with ops.context(source="fred"):
        r = net.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10")
    assert r.status_code == 200
    (row,) = ops.requests()
    assert row["source"] == "fred" and row["host"] == "fred.stlouisfed.org" and row["path"] == "/graph/fredgraph.csv"
    assert row["ok"] and row["status"] == 200 and row["bytes"] == 4 and row["attempt"] == 1


def test_retry_obeys_retry_after_and_backs_off(fake_time, monkeypatch):
    calls = _replies(monkeypatch, Resp(429, {"Retry-After": "7"}), Resp(503), Resp(200))
    r = net.get("https://example.org/data", source="t")
    assert r.status_code == 200 and len(calls) == 3
    assert 7 in fake_time.slept and 4.0 in fake_time.slept   # Retry-After, then backoff 2 * 2^(2-1)
    rows = ops.requests()
    assert [x["status"] for x in reversed(rows)] == [429, 503, 200] and [x["attempt"] for x in reversed(rows)] == [1, 2, 3]
    assert rows[-1]["throttled"] and not rows[-1]["ok"]


def test_no_retry_for_a_404_and_expected_statuses_are_not_errors(fake_time, monkeypatch):
    calls = _replies(monkeypatch, Resp(404), Resp(404))
    assert net.get("https://example.org/a").status_code == 404
    assert net.get("https://example.org/b", expected=(404,)).status_code == 404
    assert len(calls) == 2
    assert [r["ok"] for r in reversed(ops.requests())] == [False, True]


def test_connection_errors_are_retried_then_raised(fake_time, monkeypatch):
    err = requests.ConnectionError("refused")
    calls = _replies(monkeypatch, err, err, err)
    with pytest.raises(requests.ConnectionError):
        net.get("https://example.org/x")
    assert len(calls) == 3 and all(not r["ok"] and "ConnectionError" in r["error"] for r in ops.requests())


def test_a_long_retry_after_gives_up_instead_of_blocking(fake_time, monkeypatch):
    _replies(monkeypatch, Resp(429, {"Retry-After": "3600"}))
    assert net.get("https://example.org/x").status_code == 429 and fake_time.slept == []


def test_repeated_429s_pause_the_host_across_processes(fake_time, monkeypatch):
    _replies(monkeypatch, *[Resp(429) for _ in range(3)])
    net.get("https://slow.example.org/x", retries=2)       # 3 × 429 = the trip count
    st = ops.host_state("slow.example.org")
    assert st["cooldown_until"] > ops._ts() and st["strikes"] == 1 and "429" in st["reason"]
    assert any(e["kind"] == "throttle" for e in ops.events())
    net.reset()                                             # a new process: only ops.db remembers
    calls = _replies(monkeypatch, Resp(200))
    with pytest.raises(net.Throttled):
        net.get("https://slow.example.org/y")
    assert calls == []                                      # nothing was sent
    assert ops.clear_cooldown("slow.example.org") and not ops.clear_cooldown("slow.example.org")
    net.reset()
    assert net.get("https://slow.example.org/y").status_code == 200


def test_a_repeat_pause_within_a_day_lasts_longer(fake_time, monkeypatch):
    t0 = datetime(2026, 10, 14, 12, 0)
    monkeypatch.setattr(ops, "now", lambda: t0)
    ops.set_cooldown("h.example.org", t0 - timedelta(minutes=1), "earlier", strikes=1)   # expired, 1 strike
    for _ in range(3):
        ops.record_request("h.example.org", "/", "GET", 429, False, 1.0)
    net._note_429("h.example.org")
    st = ops.host_state("h.example.org")
    assert st["strikes"] == 2 and st["cooldown_until"] == ops._ts(t0 + timedelta(minutes=30))


def test_over_budget_is_a_warning_not_a_block(fake_time, monkeypatch):
    monkeypatch.setattr(net, "limits", lambda host: net.DEFAULTS | {"pattern": "*", "budget": 2})
    _replies(monkeypatch, *[Resp(200) for _ in range(4)])
    for i in range(4):
        assert net.get(f"https://example.org/{i}").status_code == 200
    warns = [e for e in ops.events() if e["kind"] == "throttle"]
    assert len(warns) == 1 and "budget" in warns[0]["message"]


def test_pool_threads_keep_the_callers_source(monkeypatch):
    seen = []
    with ops.context(source="analyst"), net.pool(8) as ex:
        list(ex.map(lambda _: seen.append((ops.current_source(), threading.current_thread().name)), range(6)))
    assert {s for s, _ in seen} == {"analyst"}
    assert len({t for _, t in seen}) <= net.workers(8)


def test_yfinance_keeps_the_tracked_session():
    from yfinance._http import new_session
    from yfinance.data import YfData

    net.install_yfinance()
    YfData(session=new_session())     # what yf.download / Ticker / Search do when no session is passed
    assert type(YfData()._session).__name__ == "TrackedSession"


def test_library_threads_fall_back_to_the_one_active_source(monkeypatch):
    """yf.download starts its own threads, which don't inherit context variables."""
    seen = []
    with ops.context(source="prices", job=7):
        t = threading.Thread(target=lambda: seen.append((ops.current_source(), ops.current_job())))
        t.start()
        t.join()
        with ops.context(source="fred"):            # two active: ambiguous, so no attribution
            t = threading.Thread(target=lambda: seen.append(ops.current_source()))
            t.start()
            t.join()
    assert seen == [("prices", 7), None] and ops.current_source() is None
