import os
import threading
import time
from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]   # the install folder: app files only; data lives where paths.py says
CONFIG = ROOT / "config"
POSITIVE_LIST_FILE = ROOT / "imports" / "positivliste.xlsx"   # SKAT's list, shipped with the app


def load_yaml(name: str) -> dict:
    """One of the config/ YAML files."""
    with open(CONFIG / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


@cache
def settings() -> dict:
    return load_yaml("settings.yaml")


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


def write_atomic(path: Path, write) -> None:
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


def write_parquet(df, path: Path, **kw) -> None:
    """Write to a temp file and swap it in, so a running `radar serve` never reads a half-written file."""
    write_atomic(path, lambda tmp: df.to_parquet(tmp, **kw))


def write_csv(df, path: Path, **kw) -> None:
    write_atomic(path, lambda tmp: df.to_csv(tmp, **kw))


def write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    write_atomic(path, lambda tmp: tmp.write_text(text, encoding=encoding))
