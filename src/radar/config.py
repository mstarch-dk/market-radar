from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
DATA = ROOT / "data"
IMPORTS = ROOT / "imports"
REPORTS = ROOT / "reports"
USERDATA = ROOT / "userdata"  # your own edits (userstore.py): not re-downloadable, never committed

PRICES_FILE = DATA / "prices.parquet"
FRED_FILE = DATA / "fred.parquet"
SNAPSHOTS = DATA / "snapshots"
HOLDINGS_FILE = IMPORTS / "holdings.csv"
TRANSACTIONS_FILE = IMPORTS / "transactions.csv"
POSITIVE_LIST_FILE = IMPORTS / "positivliste.xlsx"


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
