"""The update log of every data source (sources.json in the cache): each step records its attempt here, a failure
keeping the last success, and each attempt is also an event in the operations log. Low level on purpose: the
data sources write it, reporting/coverage.py reads it for the Data & coverage page."""
from __future__ import annotations

import json
import threading
from datetime import datetime

from . import locks, ops
from .config import write_text
from .jsonsafe import dumps
from .paths import CACHE

LOG_FILE = CACHE / "sources.json"
_log_lock = threading.Lock()  # the update and the discovery scan can record at the same time


def load_log() -> dict:
    try:
        return json.loads(LOG_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


class PartialFailure(RuntimeError):
    """The step stored part of what it fetched, then failed: the message says what was kept and what failed."""


def record(source: str, ok: bool, detail: str | None = None, error: str | None = None,
           exc: BaseException | None = None) -> None:
    """Log one update attempt. A failure keeps the last success, so the page can say how old the data is. Each
    attempt is also an event in the operations log (a failure with its traceback when `exc` is given; a
    ValueError is a parse failure: the source answered, but not in the shape we expect)."""
    f = LOG_FILE.now()
    with _log_lock, locks.file_lock(f, timeout=30):          # the app and a terminal update both write it
        log = load_log()
        now = datetime.now().isoformat(timespec="seconds")
        entry = log.get(source, {}) | {"last_attempt": now, "detail": detail, "error": None if ok else error}
        if ok:
            entry["last_success"] = now
        log[source] = entry
        CACHE.mkdir(parents=True, exist_ok=True)
        write_text(f, dumps(log, indent=1))
    if ok:
        ops.event("info", "source", detail or "updated", source=source)
    else:
        ops.event("error", "parse" if isinstance(exc, ValueError) else "source", error or "failed", source=source,
                  exc=exc)
