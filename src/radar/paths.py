"""Where Market Radar keeps things: the one place that knows.

Four tiers, each with its own root:

- **home**: your own material: notes, briefs, research, journal, exports and broker files (`imports/`).
- **userdata**: `radar.db` (portfolios, transactions, views, ...) and its backups. Can't be re-downloaded.
- **history**: what builds up run by run and can't be downloaded again (rank snapshots, weekly valuation
  snapshots, analyst targets as fetched, FactSet reports, put/call beyond the backfill). Not private.
- **cache**: everything `radar run` can download or rebuild, and `reports/` built from it.

App files (code, `config/` defaults, `guide/`, `web/dist`, the positive list) stay in the install folder (`config.ROOT`).

Module-level constants elsewhere are `Lazy` paths: they resolve on each use, so `configure()` (tests, `--home`)
reaches them without patching every module. `REGISTRY` lists every file and folder the code writes, by tier.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .config import ROOT

TIERS = ("home", "imports", "userdata", "history", "cache", "reports")


@dataclass(frozen=True)
class Locations:
    home: Path
    imports: Path       # broker files and the legacy CSVs (personal, like home)
    userdata: Path
    history: Path
    cache: Path
    reports: Path

    @classmethod
    def legacy(cls, root: Path = ROOT) -> Locations:
        """Everything inside the install folder, as before the data home existed."""
        return cls(home=root, imports=root / "imports", userdata=root / "userdata", history=root / "data",
                   cache=root / "data", reports=root / "reports")

    @classmethod
    def flat(cls, root: Path) -> Locations:
        """One folder for everything (tests): history and cache share it, like the legacy data/."""
        return cls(home=root, imports=root, userdata=root / "userdata", history=root, cache=root,
                   reports=root / "reports")

    @classmethod
    def at(cls, home: Path, cache: Path | None = None) -> Locations:
        """The data home: your material and radar.db in `home`, history in `home/history`, the cache elsewhere."""
        home = Path(home).expanduser()
        cache = Path(cache).expanduser() if cache else default_cache()
        return cls(home=home, imports=home / "imports", userdata=home, history=home / "history", cache=cache,
                   reports=cache / "reports")


# ---------------- where the data home is ----------------

APP_DIR = "MarketRadar"
ENV_HOME, ENV_CACHE = "MARKET_RADAR_HOME", "MARKET_RADAR_CACHE"
ENV_CONFIG = "MARKET_RADAR_CONFIG"     # where the pointer file lives (the demo and smoke tests keep theirs apart)


class NotSetUp(RuntimeError):
    """No data home chosen yet (first start of this version): `radar setup`, or the app's setup screen."""

    def __init__(self):
        super().__init__("Market Radar has no data folder yet. Start the app (it shows the setup screen) or run: "
                         "uv run radar setup")


def default_home() -> Path:
    return Path.home() / "Market Radar"


def default_cache() -> Path:
    """`MARKET_RADAR_CACHE`, else the OS cache folder (%LOCALAPPDATA%, ~/Library/Caches, ~/.cache)."""
    import platformdirs

    env = os.environ.get(ENV_CACHE)
    return Path(env).expanduser() if env else Path(platformdirs.user_cache_dir(APP_DIR, appauthor=False))


def pointer_file() -> Path:
    """Where this computer remembers the data home: outside the install folder, so every unzipped version finds it."""
    import platformdirs

    d = os.environ.get(ENV_CONFIG)
    return (Path(d).expanduser() if d else Path(platformdirs.user_config_dir(APP_DIR, appauthor=False))) / "location.json"


def read_pointer() -> dict | None:
    import json

    f = pointer_file()
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        raise RuntimeError(f"{f} can't be read ({type(e).__name__}): fix or delete it, then start again") from e
    return d if d.get("home") else None


def remembers() -> bool:
    """Whether choosing a data home should be remembered in the pointer file: not when an environment variable or
    a portable.json decides where the data is (the demo must never move this computer's pointer)."""
    return source() not in ("env", "portable")


def write_pointer(home: Path, cache: Path | None = None) -> Path:
    import json

    f = pointer_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps({"home": str(Path(home).expanduser().resolve()),
                               "cache": str(Path(cache).expanduser().resolve()) if cache else None}, indent=1),
                   encoding="utf-8")
    tmp.replace(f)
    return f


PORTABLE = "portable.json"   # beside the program: data kept next to it (a USB stick, the marketing demo)


def resolve() -> tuple[Locations | None, str]:
    """Find the data home: `MARKET_RADAR_HOME` (and `MARKET_RADAR_CACHE`), else a portable.json in the install
    folder ({"home": "data", "cache": "cache"}, relative to it), else the pointer file, else none."""
    env = os.environ.get(ENV_HOME)
    if env:
        return Locations.at(Path(env)), "env"
    portable = ROOT / PORTABLE
    if portable.exists():
        import json

        d = json.loads(portable.read_text(encoding="utf-8"))
        return Locations.at(ROOT / d.get("home", "data"), ROOT / d.get("cache", "cache")), "portable"
    p = read_pointer()
    if p:
        return Locations.at(Path(p["home"]), os.environ.get(ENV_CACHE) or p.get("cache")), "pointer"
    return None, "unset"


_current: Locations | None = None
_source = "unset"


def locations() -> Locations:
    global _current, _source
    if _current is None:
        _current, _source = resolve()
        if _current is None:
            raise NotSetUp()
    return _current


def source() -> str:
    """How the current locations were chosen: configured (tests, the demo), option (--home), env, portable,
    pointer or unset."""
    try:
        locations()
    except NotSetUp:
        pass
    return _source


def configure(loc: Locations | None, source: str = "configured") -> None:
    """Use these locations from now on (None: resolve again on next use). `source` "option" (--home) is checked
    like a remembered home; "configured" (tests, the demo) is taken as it is."""
    global _current, _source
    _current, _source = loc, (source if loc else "unset")


class Lazy(os.PathLike):
    """A path under one tier's root, resolved each time it is used. Behaves like the `Path` it resolves to."""
    __slots__ = ("_tier", "_parts")

    def __init__(self, tier: str, *parts: str):
        if tier not in TIERS:
            raise ValueError(f"unknown tier {tier!r}")
        self._tier, self._parts = tier, parts

    def now(self) -> Path:
        return getattr(locations(), self._tier).joinpath(*self._parts)

    def __fspath__(self) -> str:
        return str(self.now())

    def __truediv__(self, other) -> Lazy:
        return Lazy(self._tier, *self._parts, str(other))

    def __getattr__(self, name):
        return getattr(self.now(), name)

    def __str__(self) -> str:
        return str(self.now())

    def __repr__(self) -> str:
        return f"Lazy({self._tier}:{'/'.join(self._parts)} -> {self.now()})"

    def __eq__(self, other) -> bool:
        return self.now() == (other.now() if isinstance(other, Lazy) else other)

    def __hash__(self) -> int:
        return hash(self.now())


HOME = Lazy("home")
USERDATA = Lazy("userdata")
HISTORY = Lazy("history")
CACHE = Lazy("cache")
REPORTS = Lazy("reports")

IMPORTS = Lazy("imports")
NOTES = HOME / "notes"
PRICES_FILE = CACHE / "prices.parquet"
FRED_FILE = CACHE / "fred.parquet"
SNAPSHOTS = HISTORY / "snapshots"
HOLDINGS_FILE = IMPORTS / "holdings.csv"            # legacy CSVs, moved into radar.db on first use
TRANSACTIONS_FILE = IMPORTS / "transactions.csv"

# Everything the code writes, by tier (relative to the tier's root; a trailing / is a folder). tests/test_paths.py
# checks that each module's paths are listed here, so a new file has to be placed in a tier on purpose.
REGISTRY: dict[str, tuple[str, ...]] = {
    "home": ("notes/", "briefs/", "research/", "journal/", "exports/"),
    "imports": ("*",),
    "userdata": ("radar.db", "backups/"),
    "history": (
        "snapshots/",                   # rank snapshots: "new", "dropped", "Δ rank"
        "discovery/snapshots/",         # discovery scores per scan
        "analyst.parquet",              # analyst consensus as fetched, kept to see targets raised or cut
        "valuation/stocks.parquet",     # weekly P/E and EPS snapshots
        "valuation/etfs.parquet",
        "factset.parquet",              # the source only looks 14 days back
        "putcall.parquet",              # the backfill reaches one year back
        "fundamentals/yahoo.parquet",   # Yahoo's statements: it shows ~4 years, what scrolls out is gone
        "fundamentals/scores.parquet",  # weekly kvalitets- and værdiscore per stock
    ),
    "cache": (
        "prices.parquet", "prices_from.json", "fred.parquet", "cot.parquet", "oecd_cli.parquet", "ecb.parquet",
        "aaii.parquet", "valuation/market.parquet", "factset_latest.txt", "profiles/", "constituents_us.csv",
        "names.csv", "sectors.csv", "currencies.csv", "sources.json", "ops.db", "updates.json",
        "discovery/universe.csv", "discovery/isin_map.csv", "discovery/prices.parquet",
        "fundamentals/edgar.parquet", "fundamentals/cik.csv", "fundamentals/edgar_log.csv",
        "fundamentals/yahoo_log.csv",
        "*.lock",                       # locks.file_lock: one writer at a time, next to the file it guards
    ),
    "reports": ("dashboard.json", "summary.json", "discovery.json", "score-study.json", "score-study-*.json", "exit-study.json",
                "redeploy-study.json", "sim-exits.json", "sim-exits-*.json", "sim-picks/"),
}
