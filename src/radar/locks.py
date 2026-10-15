"""One writer at a time for a file, across threads and processes (the app's update job, `radar update` in a
terminal, a ticker lookup in the app).

`file_lock(path)` holds an OS lock on `<path>.lock` (msvcrt on Windows, flock elsewhere): the OS releases it when
the holder exits or crashes, so a stale lock file never blocks anyone. Hold it around read-modify-write of the
file, not around a download: other writers wait at most `timeout` seconds.
"""
from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

if os.name == "nt":
    import msvcrt

    def _try(fd: int) -> bool:
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def _release(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _try(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _release(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)

_held = threading.local()   # paths this thread holds: taking one again is a no-op (no self-deadlock)


class Busy(TimeoutError):
    """Someone else holds the lock."""


def lock_path(path: Path) -> Path:
    path = Path(path)
    return path.with_name(path.name + ".lock")


@contextmanager
def file_lock(path: Path, timeout: float = 120, poll: float = 0.1, what: str | None = None):
    """Hold the lock for `path`; wait up to `timeout` seconds (0: don't wait), else raise `Busy`."""
    lp = lock_path(path)
    held = getattr(_held, "paths", None)
    if held is None:
        held = _held.paths = set()
    if lp in held:
        yield
        return
    lp.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lp, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        deadline = time.monotonic() + timeout
        while not _try(fd):
            if time.monotonic() >= deadline:
                raise Busy(f"{what or Path(path).name} is busy: another update is writing it")
            time.sleep(poll)
        held.add(lp)
        try:
            yield
        finally:
            held.discard(lp)
            _release(fd)
    finally:
        os.close(fd)
