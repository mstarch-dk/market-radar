"""The data folder's market-radar.json (the manifest: its format, the app versions that opened it, a log of
events such as upgrades, backups and the update-check choice) and this app's version."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import ROOT, write_text

MANIFEST = "market-radar.json"


def app_version() -> str:
    """From pyproject.toml beside the code (a release zip and a checkout both have it, and it can't be stale like an
    installed package's metadata), else the installed metadata."""
    import tomllib

    try:
        return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    except (OSError, KeyError, ValueError):
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("market-radar")
        except PackageNotFoundError:
            return "0.0.0"


def version_tuple(v: str) -> tuple:
    """A version as numbers, so versions compare right: "0.2.10" is (0, 2, 10); a part that isn't a number is 0."""
    return tuple(int(p) if p.isdigit() else 0 for p in v.split("."))


def read_manifest(home: Path) -> dict | None:
    f = Path(home) / MANIFEST
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def write_manifest(home: Path, m: dict) -> None:
    """Write the data home's market-radar.json."""
    f = Path(home) / MANIFEST
    write_text(f, json.dumps(m, indent=1, ensure_ascii=False))


def add_log(m: dict, event: str, **kw) -> dict:
    """Append an event (with the time and this app version) to a manifest's log; returns the manifest."""
    m.setdefault("log", []).append({"at": datetime.now().isoformat(timespec="seconds"),
                                    "app_version": app_version(), "event": event} | kw)
    return m
