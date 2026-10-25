"""Running a study from the app (the Evidence page's Run button), so nobody needs a terminal for it.

The app never runs a study in its own process (the layer contract in pyproject.toml: the app reads the studies'
reports, it doesn't import radar.backtest). The run is the study's own command, `python -m radar study …`, as a
child process: the same command the Evidence card shows, its heavy work off the server, and it can be cancelled.
The child records itself in the operations log (cli/common.job) and takes LOCK, so a run in a terminal and one
from the app never write the same report at once.
"""
from __future__ import annotations

import atexit
import os
import subprocess
import sys
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

from . import errors, locks, ops, paths, updater
from .model import artifacts as art
from .paths import CACHE

LOCK = CACHE / "study.lock"   # one study at a time: the app's run, `radar study …` in a terminal
BUSY = "a study is already running (in the app or in a terminal): wait for it to finish"
KIND = "study"                # the kind the CLI records a study under in the operations log


def commands() -> dict[str, str]:
    """Every study the app may run, {run key: its command}: the score study once per signal
    ("score-study:quality"), the others by their report's name. The key is the Evidence head's `run_key`."""
    out = {art.run_key("score-study", k): s.command for k, s in art.SCORE_SIGNALS.items()}
    out |= {name: spec.command for name, spec in art.ARTIFACTS.items() if name != "score-study"}
    return out


def kill(proc: subprocess.Popen) -> None:
    """End a child and everything it started. On Windows a virtual environment's python.exe is a launcher that runs
    the real interpreter as its own child, so the whole tree goes (taskkill /T); elsewhere a terminate."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, check=False)
    else:
        proc.terminate()


def argv(command: str) -> list[str]:
    """`radar study …` as this interpreter runs it."""
    return [sys.executable, "-m", "radar", *command.split()[1:]]


class StudyJob:
    """One study at a time, run as a child process; its log can be polled and it can be cancelled."""

    def __init__(self, known: Callable[[], dict[str, str]] = commands, launch: Callable[[str], list[str]] = argv):
        self._lock = threading.Lock()
        self._known = known
        self._launch = launch
        self._proc: subprocess.Popen[str] | None = None
        self._since: str | None = None       # when the child started, for the operations log if it is stopped
        self._cancelled = False
        self.state: dict[str, Any] = {"status": "idle", "started": None, "finished": None, "log": [], "progress": None,
                                      "error": None, "study": None}

    def _log(self, line: str) -> None:
        self.state["log"] = [*self.state["log"], f"{datetime.now():%H:%M:%S} {line}"][-200:]

    @property
    def running(self) -> bool:
        return self.state["status"] == "running"

    def start(self, key: str) -> None:
        """Start the study `key`. NotFound for a study the app doesn't know; Conflict while a study, an update or a
        rebuild of the readings runs (here or, for a study, in a terminal)."""
        command = self._known().get(key)
        if command is None:
            raise errors.NotFound(f"No study called {key}.")
        if updater.JOB.state["status"] == "running":
            raise errors.Conflict("An update is running: start the study when it has finished.")
        if updater.REPORT_JOB.state["status"] == "running":
            raise errors.Conflict("The readings are being rebuilt: start the study when that has finished.")
        with self._lock:
            if self.running:
                raise errors.Conflict(f"A study is already running ({self.state['study']}).")
            try:                              # one in a terminal: say so now rather than from the child
                with locks.file_lock(LOCK, timeout=0, what=BUSY):
                    pass
            except locks.Busy as e:
                raise errors.Conflict(f"Not started: {e}.") from None
            self.state = {"status": "running", "started": datetime.now().isoformat(timespec="seconds"),
                          "finished": None, "log": [], "progress": None, "error": None, "study": key}
            self._cancelled = False
        threading.Thread(target=self._run, args=(command,), name="radar-study", daemon=True).start()

    def cancel(self) -> bool:
        """Stop the running study; False if none runs. Its report keeps the last finished run's numbers."""
        with self._lock:
            if not self.running or self._proc is None:
                return False
            self._cancelled = True
            kill(self._proc)
        return True

    def _run(self, command: str) -> None:
        loc = paths.locations()
        env = os.environ | {paths.ENV_HOME: str(loc.home), paths.ENV_CACHE: str(loc.cache),
                            "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        status, error, last = "done", None, None
        self._log(f"uv run {command}")
        try:
            self._since = ops.timestamp()
            with self._lock:
                self._proc = subprocess.Popen(self._launch(command), stdin=subprocess.DEVNULL,
                                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env, text=True,
                                              encoding="utf-8", errors="replace", creationflags=flags)
            assert self._proc.stderr is not None
            for raw in self._proc.stderr:        # the study's progress (cli/common.job writes it to stderr)
                if line := raw.rstrip():
                    self._log(line)
                    last = line
            code = self._proc.wait()
            if self._cancelled:
                status, error = "failed", "Cancelled"
                ops.interrupt(KIND, self._since, "cancelled in the app")
            elif code != 0:
                status, error = "failed", last or f"exit code {code}"
        except Exception as e:                   # the child couldn't start: report it, don't die
            status, error = "failed", f"{type(e).__name__}: {e}"
            ops.event("error", "job", f"study {self.state['study']} not started: {error}", exc=e)
        finally:
            if error:
                self._log(f"Stopped: {error}")
            with self._lock:
                self._proc = None
            # the status changes last, so whoever waits for it sees the log complete
            self.state.update(error=error, finished=datetime.now().isoformat(timespec="seconds"), status=status)

    def stop(self) -> None:
        """The server is stopping: a running study goes with it, recorded as interrupted."""
        with self._lock:
            proc, since = self._proc, self._since
        if proc is not None and proc.poll() is None:
            self._cancelled = True
            kill(proc)
            if since:
                ops.interrupt(KIND, since, "the app was closed")


STUDY_JOB = StudyJob()
atexit.register(STUDY_JOB.stop)
