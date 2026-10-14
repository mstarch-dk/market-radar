"""The one network layer: every external request goes through here, so each one is rate-limited per host, recorded in
the operations log (ops.py) and, for plain HTTP, retried by one policy.

- **Per-host limits** (settings.yaml `network.hosts`, glob patterns, first match wins, else `network.default`): a token
  bucket (`rate` requests a second, `burst`) and a cap on parallel requests (`concurrency`). Hosts matching the same
  pattern share them (all of Yahoo's hosts are one budget).
- **Retry** (`get` only): 429, 5xx, timeouts and connection errors are retried with exponential backoff and jitter,
  obeying `Retry-After`; anything else (404, a parse error later) is not retried, it fails loudly.
- **Cooldown**: `trip` 429s from a host within `window_min` minutes pause it for `cooldown_min` minutes, doubling per
  repeat (`strikes`, reset after a quiet day) up to `max_cooldown_min`. While paused, requests fail at once with
  `Throttled`, so the step keeps its cached data. The pause is stored in ops.db, so the CLI and the server share it.
- **Budget**: a soft daily request count per pattern (`budget`); going over is a warning event, never a block.
- yfinance: `install_yfinance()` makes yfinance's one shared session (`YfData`) a recording, rate-limited session.
  yfinance does its own retries; we only see, pace and pause.

The User-Agent says what we are; we don't rotate identities or use proxies to get around limits.
"""
from __future__ import annotations

import contextvars
import fnmatch
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.parse import urlsplit

import requests

from . import ops
from .config import settings

UA = "Mozilla/5.0 (market-radar personal research script)"
HEADERS = {"User-Agent": UA}
YAHOO = "query1.finance.yahoo.com"   # a representative Yahoo host, for limits(); every *.yahoo.com host matches

DEFAULTS = {"rate": 4.0, "burst": 8, "concurrency": 4, "budget": None, "retries": 2, "backoff": 2.0,
            "max_wait": 120.0}
COOLDOWN = {"trip": 3, "window_min": 10, "cooldown_min": 15, "max_cooldown_min": 120}

# injectable for tests
clock = time.monotonic
sleep = time.sleep


class Throttled(RuntimeError):
    """A host is paused after repeated 429s; the request was not sent."""

    def __init__(self, host: str, until: str, reason: str | None):
        super().__init__(f"{host} is paused until {until[:16].replace('T', ' ')} ({reason or 'rate limited'})")
        self.host, self.until = host, until


# ---------------- config ----------------

def _net_cfg() -> dict:
    return settings().get("network") or {}


def _pattern(host: str) -> str:
    for pat in (_net_cfg().get("hosts") or {}):
        if fnmatch.fnmatch(host, pat):
            return pat
    return "*"


def limits(host: str) -> dict:
    """The limits that apply to `host` (defaults, then `network.default`, then its pattern)."""
    cfg = _net_cfg()
    pat = _pattern(host)
    return DEFAULTS | (cfg.get("default") or {}) | ((cfg.get("hosts") or {}).get(pat) or {}) | {"pattern": pat}


def _cooldown_cfg() -> dict:
    return COOLDOWN | (_net_cfg().get("cooldown") or {})


# ---------------- redaction ----------------

SECRET = re.compile(r"(api[_-]?key|apikey|token|key|secret|password|crumb)=[^/&;]*", re.I)


def redact(url: str) -> tuple[str, str]:
    """(host, path) to store: the query string and fragment are dropped, secrets in the path are masked."""
    parts = urlsplit(url)
    path = SECRET.sub(lambda m: f"{m.group(1)}=***", parts.path or "/")
    return (parts.hostname or "?").lower(), path[:300]


# ---------------- token bucket + concurrency per pattern ----------------

class Bucket:
    def __init__(self, rate: float, burst: float):
        self.rate, self.burst = float(rate), float(burst)
        self.tokens, self.last = float(burst), clock()
        self.lock = threading.Lock()

    def take(self) -> float:
        """Take one token, sleeping until one is free; returns the seconds waited."""
        waited = 0.0
        while True:
            with self.lock:
                t = clock()
                self.tokens = min(self.burst, self.tokens + (t - self.last) * self.rate)
                self.last = t
                if self.tokens >= 1:
                    self.tokens -= 1
                    return waited
                need = (1 - self.tokens) / self.rate
            sleep(need)
            waited += need


_state_lock = threading.Lock()
_buckets: dict[str, Bucket] = {}
_slots: dict[str, threading.BoundedSemaphore] = {}
_paused: dict[str, tuple[float, dict | None]] = {}   # host -> (checked at, host_state row): a short read cache
_budget_warned: dict[str, str] = {}                 # pattern -> date warned


def reset() -> None:
    """Forget the in-memory limiter state (tests; settings changed)."""
    with _state_lock:
        _buckets.clear()
        _slots.clear()
        _paused.clear()
        _budget_warned.clear()


def _limiter(host: str) -> tuple[dict, Bucket, threading.BoundedSemaphore]:
    lim = limits(host)
    with _state_lock:
        key = lim["pattern"]
        if key not in _buckets:
            _buckets[key] = Bucket(lim["rate"], lim["burst"])
            _slots[key] = threading.BoundedSemaphore(max(1, int(lim["concurrency"])))
        return lim, _buckets[key], _slots[key]


def workers(n: int, host: str = YAHOO) -> int:
    """Thread count for a pool that calls `host`: at most its `concurrency`."""
    return max(1, min(n, int(limits(host)["concurrency"])))


def pool(n: int, host: str = YAHOO) -> ThreadPoolExecutor:
    """A thread pool sized for `host` whose tasks keep the caller's ops context (source, job)."""
    return _ContextPool(workers(n, host))


class _ContextPool(ThreadPoolExecutor):
    def submit(self, fn, /, *args, **kwargs):
        ctx = contextvars.copy_context()
        return super().submit(ctx.run, fn, *args, **kwargs)


# ---------------- cooldown ----------------

def _check_paused(host: str) -> None:
    t = clock()
    hit = _paused.get(host)
    if hit is None or t - hit[0] > 5:      # read ops.db at most every 5 s per host
        hit = (t, ops.host_state(host))
        _paused[host] = hit
    st = hit[1]
    if st and st["cooldown_until"] and st["cooldown_until"] > ops._ts():
        raise Throttled(host, st["cooldown_until"], st["reason"])


def _note_429(host: str) -> None:
    """Count recent 429s; trip the host's cooldown when there are too many."""
    cfg = _cooldown_cfg()
    t = ops.now()
    try:
        n = ops.count_requests(host, t - timedelta(minutes=cfg["window_min"]), status=429)
    except Exception:
        return
    if n < cfg["trip"]:
        return
    st = ops.host_state(host) or {}
    if st.get("cooldown_until") and st["cooldown_until"] > ops._ts(t):
        return                               # already paused (another thread tripped it)
    recent = st.get("updated") and st["updated"] > ops._ts(t - timedelta(days=1))
    strikes = (st.get("strikes", 0) if recent else 0) + 1
    minutes = min(cfg["cooldown_min"] * 2 ** (strikes - 1), cfg["max_cooldown_min"])
    until = t + timedelta(minutes=minutes)
    reason = f"{n} × HTTP 429 in {cfg['window_min']} min"
    ops.set_cooldown(host, until, reason, strikes)
    _paused.pop(host, None)
    ops.event("warn", "throttle", f"{host} paused for {minutes} min: {reason}")


def _note_budget(host: str, lim: dict) -> None:
    budget = lim.get("budget")
    if not budget:
        return
    today = ops.now().date().isoformat()
    if _budget_warned.get(lim["pattern"]) == today:
        return
    start = ops.now().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        n = ops.count_requests(host, start)
    except Exception:
        return
    if n > budget:
        _budget_warned[lim["pattern"]] = today
        ops.event("warn", "throttle", f"{host}: {n:,} requests today, over the soft budget of {budget:,}")


# ---------------- the request wrapper ----------------

def _gate(host: str) -> tuple[dict, threading.BoundedSemaphore]:
    _check_paused(host)
    lim, bucket, slot = _limiter(host)
    bucket.take()
    return lim, slot


def _record(host: str, path: str, method: str, resp, t0: float, attempt: int, error: str | None = None,
            expected: tuple[int, ...] = ()) -> None:
    status = getattr(resp, "status_code", None) if resp is not None else None
    ok = error is None and (status < 400 or status in expected if isinstance(status, int)
                            else bool(getattr(resp, "ok", True)))
    size = None
    if resp is not None:
        content = getattr(resp, "content", None)
        size = len(content) if isinstance(content, (bytes, bytearray)) else None
    ops.record_request(host, path, method, status if isinstance(status, int) else None, ok,
                       round((clock() - t0) * 1000, 1), size, attempt, status == 429, error)


def _retry_after(resp) -> float | None:
    try:
        v = resp.headers.get("Retry-After")
        return float(v) if v is not None else None
    except (AttributeError, TypeError, ValueError):
        return None


def _backoff(lim: dict, attempt: int) -> float:
    return lim["backoff"] * 2 ** (attempt - 1) * (1 + random.random() * 0.25)


def get(url: str, *, source: str | None = None, timeout: float = 60, headers: dict | None = None,
        expected: tuple[int, ...] = (), retries: int | None = None, **kw):
    """requests.get through the limiter, recorded, with the retry policy. Returns the last response (the caller
    decides what a 404 means; statuses in `expected`, such as a probe's 404, aren't counted as errors); raises
    `Throttled` while the host is paused, or the last connection error. `retries` overrides the host's."""
    host, path = redact(url)
    with ops.context(source=source):
        attempt = 0
        while True:
            attempt += 1
            lim, slot = _gate(host)
            if retries is not None:
                lim = lim | {"retries": retries}
            t0 = clock()
            try:
                with slot:
                    resp = requests.get(url, headers=HEADERS | (headers or {}), timeout=timeout, **kw)
            except (requests.ConnectionError, requests.Timeout) as e:
                _record(host, path, "GET", None, t0, attempt, f"{type(e).__name__}: {e}"[:300])
                if attempt > lim["retries"]:
                    raise
                sleep(_backoff(lim, attempt))
                continue
            _record(host, path, "GET", resp, t0, attempt, expected=expected)
            status = getattr(resp, "status_code", None)
            _note_budget(host, lim)
            if status == 429:
                _note_429(host)
            if isinstance(status, int) and (status == 429 or status >= 500) and attempt <= lim["retries"]:
                wait = _retry_after(resp)
                wait = _backoff(lim, attempt) if wait is None else wait
                if wait > lim["max_wait"]:
                    return resp              # the host asks for longer than we'll block a step: give up now
                sleep(wait)
                continue
            return resp


# ---------------- yfinance ----------------

_yf_installed = False


def _tracked_session_class():
    from curl_cffi.requests import Session

    class TrackedSession(Session):
        """yfinance's HTTP session: rate-limited per host, every request recorded, 429s counted."""

        def request(self, method, url, *args, **kwargs):
            host, path = redact(str(url))
            lim, slot = _gate(host)
            t0 = clock()
            try:
                with slot:
                    resp = super().request(method, url, *args, **kwargs)
            except Exception as e:
                _record(host, path, str(method), None, t0, 1, f"{type(e).__name__}: {e}"[:300])
                raise
            _record(host, path, str(method), resp, t0, 1)
            _note_budget(host, lim)
            if resp.status_code == 429:
                _note_429(host)
            return resp

    return TrackedSession


def install_yfinance() -> None:
    """Route all of yfinance through one tracked session. yfinance keeps a single session in its `YfData`
    singleton, but `yf.download`, `Ticker`, `Search` and `screen` replace it with a fresh one when none is
    passed; we keep ours by refusing any session that isn't one. Idempotent."""
    global _yf_installed
    if _yf_installed:
        return
    from yfinance.data import YfData

    cls = _tracked_session_class()
    original = YfData._set_session

    def _set_session(self, session):
        if session is not None and not isinstance(session, cls):
            session = getattr(self, "_session", None) if isinstance(getattr(self, "_session", None), cls) \
                else cls(impersonate="chrome")
        original(self, session)

    YfData._set_session = _set_session
    YfData(session=cls(impersonate="chrome"))
    _yf_installed = True


def yf():
    """The yfinance module, with its session routed through here."""
    install_yfinance()
    import yfinance

    return yfinance
