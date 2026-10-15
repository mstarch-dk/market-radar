"""Every released data folder opens with the current code, with nothing lost.

tests/fixtures/homes/ holds one small data folder per release (scripts/release.py fixture), and the layout from
before the data folder existed (legacy-*: data inside the install folder). A fixture is never changed once
released: when a version can't read what an earlier one wrote, this fails instead of a user's data.
"""
import json
import shutil
from pathlib import Path

import pytest

from radar import backup, export, home, paths, universe, userstore

HOMES = Path(__file__).parent / "fixtures" / "homes"
FIXTURES = sorted(p for p in HOMES.iterdir() if (p / "expected.json").exists())


@pytest.mark.parametrize("fixture", FIXTURES, ids=[p.name for p in FIXTURES])
def test_a_released_data_folder_opens_with_nothing_lost(fixture, tmp_path):
    exp = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))
    src = tmp_path / fixture.name
    shutil.copytree(fixture, src)
    paths.configure(None)
    if exp["layout"] == "legacy":
        (src / "src" / "radar").mkdir(parents=True, exist_ok=True)       # empty folders aren't in git
        home.migrate(src, tmp_path / "Market Radar", tmp_path / "cache")
        loc = paths.locations()
    else:
        loc = home.use(src, tmp_path / "cache")
    assert home.gate() == ("ok", None)
    if exp["layout"] == "home":                     # a moved folder starts fresh; the old one is its backup
        assert backup.before_upgrade() is not None or exp["made_by"] == home.app_version()

    tables = home.table_counts(loc.userdata / home.DB_NAME)               # the schema may have grown since
    for t, n in exp["tables"].items():
        assert tables.get(t, 0) >= n if t == "meta" else tables.get(t) == n, t
    pf = userstore.portfolio_by_name("Testdepot")
    assert pf and pf["tags"] == ["lang"] and pf["kind"] == "frie_midler"
    rows = userstore.transactions(portfolios=[pf["id"]])
    assert sorted(r["type"] for r in rows) == ["BUY", "BUY", "DEPOSIT", "SELL"]
    assert "ASML.AS" in set(universe.holdings()["symbol"])
    assert (loc.home / "notes" / "investor.md").read_text(encoding="utf-8").endswith("Æøå.")
    assert (loc.history / "snapshots" / "2025-09-01_momentum.parquet").exists()

    backup.create("upgrade-test")                                           # and the usual work goes on
    assert export.preview(export.write(tmp_path / "x.zip"))["transactions"] == len(userstore.transactions())
