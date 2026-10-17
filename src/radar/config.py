from __future__ import annotations

import os
import threading
import time
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from .config_schema import Settings

ROOT = Path(__file__).resolve().parents[2]   # the install folder: app files only; data lives where paths.py says
CONFIG = ROOT / "config"
POSITIVE_LIST_FILE = ROOT / "imports" / "positivliste.xlsx"   # SKAT's list, shipped with the app


def load_yaml(name: str) -> dict:
    """One of the config/ YAML files."""
    with open(CONFIG / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


@cache
def load_settings() -> tuple[dict, Settings]:
    from .config_schema import check

    raw = load_yaml("settings.yaml")
    return raw, check(raw)


def settings() -> dict:
    """config/settings.yaml as written, checked against config_schema when it is first loaded (SettingsError
    otherwise). For what records or hashes the file, and the readings that take a section as a dict."""
    return load_settings()[0]


def typed() -> Settings:
    """config/settings.yaml as the checked model: read values through this."""
    return load_settings()[1]


def reload() -> None:
    """Read config/settings.yaml again on next use."""
    load_settings.cache_clear()


@cache
def universe_config() -> dict:
    return load_yaml("universe.yaml")


@cache
def discovery_config() -> dict:
    return load_yaml("discovery.yaml")


def _tmp(path: Path) -> Path:
    """A temp name of this process and thread, so two writers never share one (it still ends in .tmp, which
    copies of the data folder skip)."""
    return path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")


def _swap(tmp: Path, path: Path, tries: int = 5, wait: float = 0.2) -> None:
    """Replace `path` with `tmp`. On Windows a reader holding `path` open makes the replace fail for a moment:
    try again a few times before giving up (the temp file is removed then)."""
    for i in range(tries):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if i == tries - 1:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(wait)


AnyPath = str | os.PathLike


def write_atomic(path: AnyPath, write) -> None:
    """`write(tmp)` writes the new content to a temp file, which is then swapped in: a reader sees the old file or
    the new one, never half of one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp(path)
    try:
        write(tmp)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    _swap(tmp, path)


def write_parquet(df, path: AnyPath, **kw) -> None:
    """Write to a temp file and swap it in, so a running `radar serve` never reads a half-written file."""
    write_atomic(path, lambda tmp: df.to_parquet(tmp, **kw))


def write_csv(df, path: AnyPath, **kw) -> None:
    write_atomic(path, lambda tmp: df.to_csv(tmp, **kw))


def write_text(path: AnyPath, text: str, encoding: str = "utf-8") -> None:
    write_atomic(path, lambda tmp: tmp.write_text(text, encoding=encoding))
