import fnmatch
import importlib
import pkgutil
import re
from pathlib import Path

import pandas as pd
import pytest

import radar
from radar import paths
from radar.config import ROOT

pytestmark = pytest.mark.os          # file replacing, locks and paths: also run on Windows and macOS in CI


def _modules():
    for m in pkgutil.walk_packages(radar.__path__, "radar."):
        yield importlib.import_module(m.name)


def _registered(tier: str, rel: str) -> bool:
    for entry in paths.REGISTRY.get(tier, ()):
        if entry.endswith("/") and (rel + "/").startswith(entry):
            return True
        if entry.startswith(rel + "/"):                     # a folder that holds registered files
            return True
        if fnmatch.fnmatch(rel, entry):
            return True
    return False


def test_every_module_path_is_placed_in_a_tier():
    """A new file the code writes must be put in a tier on purpose (paths.REGISTRY): personal, history or cache
    decides whether it is backed up, moved and kept on an update."""
    missing = []
    for mod in _modules():
        for name, value in vars(mod).items():
            if isinstance(value, paths.Lazy) and value._parts:
                rel = "/".join(value._parts)
                if not _registered(value._tier, rel):
                    missing.append(f"{mod.__name__}.{name} = {value._tier}:{rel}")
    assert not missing, "not in paths.REGISTRY:\n" + "\n".join(missing)


def test_no_data_path_is_built_from_the_install_folder():
    """Only app files hang off config.ROOT; everything else goes through paths."""
    allowed = {"config.py", "paths.py"}
    app_files = re.compile(r'ROOT / "(web|guide|config|pyproject\.toml|imports" / "positivliste\.xlsx)')
    bad = []
    for f in Path(radar.__file__).parent.rglob("*.py"):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if f.name not in allowed and "ROOT /" in line and not app_files.search(line):
                bad.append(f"{f.name}:{i}: {line.strip()}")
    assert not bad, "\n".join(bad)


def test_configure_reaches_module_constants(tmp_path):
    from radar import external

    paths.configure(paths.Locations(home=tmp_path / "h", imports=tmp_path / "h" / "imports", userdata=tmp_path / "h",
                                    history=tmp_path / "h" / "history", cache=tmp_path / "c",
                                    reports=tmp_path / "c" / "reports"))
    assert tmp_path / "c" / "prices.parquet" == paths.PRICES_FILE
    assert tmp_path / "h" / "history" / "analyst.parquet" == external.ANALYST_FILE
    df = pd.DataFrame({"a": [1, 2]})
    df.to_parquet(paths.PRICES_FILE.parent.mkdir(parents=True) or paths.PRICES_FILE)    # pandas takes a Lazy
    assert pd.read_parquet(paths.PRICES_FILE)["a"].tolist() == [1, 2]
    assert Path(paths.PRICES_FILE).exists() and str(paths.PRICES_FILE).endswith("prices.parquet")


def test_legacy_layout_is_the_install_folder():
    loc = paths.Locations.legacy()
    assert loc.cache == ROOT / "data" and loc.userdata == ROOT / "userdata" and loc.home == ROOT
