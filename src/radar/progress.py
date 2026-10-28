"""A long job's progress as whoever follows it sees it: which step of how many, the phase within the step (done of
total), and what has gone wrong so far, so a failing source or a ticker without data shows while the job runs, not
only in its log at the end.

The work reports through `tick` and `issue`, which take either a `Progress` or a plain `progress(done, total)`
callback (the discovery scan's, a test's) or None, so a data source never needs to know who follows it.
"""
from __future__ import annotations

import copy
import threading
from collections.abc import Callable
from typing import Any

ISSUES_MAX = 50   # the newest kept; `issues_total` still counts them all


class Progress:
    """Steps (planned up front, so "step 4 of 20" means something), the running phase, and the issues so far.
    `on_change(state, urgent)` is called after each change; `urgent` for a new step or issue, which a follower
    should see at once, rather than one more batch."""

    def __init__(self, label: str = "Working", on_change: Callable[[dict, bool], None] | None = None):
        self._lock = threading.Lock()
        self._label = label   # the phase's label when the work doesn't name one
        self._on_change = on_change
        self.state: dict[str, Any] = {"step": None, "steps": [], "phase": None, "issues": [], "issues_total": 0}

    def __call__(self, done: int, total: int) -> None:
        """A plain progress callback: the current phase, done of total."""
        label = (self.state["phase"] or {}).get("label") or self._label
        self.phase(done, total, label)

    def plan(self, steps: list[tuple[str, str]]) -> None:
        """The steps to come, as (key, label); keys already planned are left as they are."""
        with self._lock:
            have = {s["key"] for s in self.state["steps"]}
            self.state["steps"] += [{"key": k, "label": lb, "status": "pending", "message": None}
                                    for k, lb in steps if k not in have]
        self._changed(True)

    def step(self, key: str, label: str) -> None:
        """Step `key` starts (added at the end if it wasn't planned); the phase starts over."""
        with self._lock:
            steps = self.state["steps"]
            row = next((s for s in steps if s["key"] == key), None)
            if row is None:
                row = {"key": key, "label": label, "status": "pending", "message": None}
                steps.append(row)
            row["status"] = "running"
            self.state["step"] = {"i": steps.index(row) + 1, "n": len(steps), "key": key, "label": label}
            self.state["phase"] = None
        self._changed(True)

    def finish(self, key: str, ok: bool, message: str | None = None) -> None:
        with self._lock:
            for s in self.state["steps"]:
                if s["key"] == key:
                    s["status"], s["message"] = ("ok" if ok else "failed"), message
            if (self.state["step"] or {}).get("key") == key:
                self.state["step"], self.state["phase"] = None, None
        self._changed(True)

    def phase(self, done: int, total: int, label: str | None = None) -> None:
        with self._lock:
            self.state["phase"] = {"done": done, "total": total, "label": label or self._label}
        self._changed(False)

    def issue(self, level: str, message: str, source: str | None = None) -> None:
        """Something the follower should know now: `level` warn (data missing or late) or error (a step failed)."""
        with self._lock:
            src = source or (self.state["step"] or {}).get("key")
            self.state["issues"] = [*self.state["issues"], {"level": level, "source": src, "message": message}][-ISSUES_MAX:]
            self.state["issues_total"] += 1
        self._changed(True)

    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self.state)

    def _changed(self, urgent: bool) -> None:
        if self._on_change:
            self._on_change(self.snapshot(), urgent)


class Named:
    """A tracker whose phase has a name the work doesn't know: what `labelled` hands a worker that only ticks."""

    def __init__(self, progress: Progress, label: str):
        self._p, self._label = progress, label

    def __call__(self, done: int, total: int) -> None:
        self._p.phase(done, total, self._label)

    def phase(self, done: int, total: int, label: str | None = None) -> None:
        self._p.phase(done, total, label or self._label)

    def issue(self, level: str, message: str, source: str | None = None) -> None:
        self._p.issue(level, message, source)


Follower = Progress | Named | Callable[[int, int], None] | None


def labelled(progress: Follower, label: str) -> Follower:
    """`progress` with its phase named `label` (a plain callback or None is passed on as it is)."""
    return Named(progress, label) if isinstance(progress, Progress) else progress


def tick(progress: Follower, done: int, total: int, label: str | None = None) -> None:
    """Report done of total to whichever follower there is; `label` names the phase for a tracker."""
    if isinstance(progress, Progress | Named):
        progress.phase(done, total, label)
    elif progress is not None:
        progress(done, total)


def issue(progress: Follower, level: str, message: str, source: str | None = None) -> None:
    """Report an issue when the follower is a tracker (a plain callback has nowhere to put it)."""
    if isinstance(progress, Progress | Named):
        progress.issue(level, message, source)
