from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]   # the install folder: app files only; data lives where paths.py says
CONFIG = ROOT / "config"
POSITIVE_LIST_FILE = ROOT / "imports" / "positivliste.xlsx"   # SKAT's list, shipped with the app


def _load(name: str) -> dict:
    with open(CONFIG / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


@cache
def settings() -> dict:
    return _load("settings.yaml")


@cache
def universe_config() -> dict:
    return _load("universe.yaml")


@cache
def discovery_config() -> dict:
    return _load("discovery.yaml")


def write_parquet(df, path: Path, **kw) -> None:
    """Write to a temp file and swap it in, so a running `radar serve` never reads a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, **kw)
    tmp.replace(path)
