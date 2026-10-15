"""The data home: first start, copying an old version's data into it, and the guard against an older app."""
import json
import sqlite3
from contextlib import closing

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from radar import api, cli, home, paths, userstore


def _old_install(root, with_data=True):
    """A Market Radar folder from before the data home: data inside the install folder."""
    (root / "src" / "radar").mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname = "market-radar"\n', encoding="utf-8")
    (root / "imports").mkdir()
    (root / "imports" / "README.md").write_text("shipped with the app", encoding="utf-8")
    if not with_data:
        return root
    paths.configure(paths.Locations.legacy(root))
    pid = userstore.save_portfolio({"name": "Depot", "mode": "real", "kind": "ask"})
    userstore.add_tx({"portfolio_id": pid, "symbol": "NOVO-B.CO", "date": "2026-01-05", "type": "BUY",
                      "quantity": 3, "price": 700.0})
    userstore.watch("MSFT")
    (root / "notes").mkdir()
    (root / "notes" / "investor.md").write_text("# Mig\næøå", encoding="utf-8")
    (root / "research" / "compare").mkdir(parents=True)
    (root / "research" / "NOVO-B.CO.md").write_text("# Novo", encoding="utf-8")
    (root / "imports" / "nordnet.csv").write_text("a;b\n1;2\n", encoding="utf-8")
    snaps = root / "data" / "snapshots"
    snaps.mkdir(parents=True)
    pd.DataFrame({"ticker": ["A"], "rank": [1]}).to_parquet(snaps / "2026-10-01_momentum.parquet")
    pd.DataFrame({"ticker": ["A"]}).to_parquet(root / "data" / "analyst.parquet")
    pd.DataFrame({"ticker": ["A"], "close": [1.0]}).to_parquet(root / "data" / "prices.parquet")
    (root / "reports").mkdir()
    (root / "reports" / "dashboard.json").write_text("{}", encoding="utf-8")
    paths.configure(None)
    return root


@pytest.fixture
def unset():
    paths.configure(None)
    return paths


def test_a_first_start_finds_the_old_version_next_to_the_new_one(tmp_path, unset):
    old = _old_install(tmp_path / "market-radar-v0.1")
    new = _old_install(tmp_path / "market-radar-v0.2", with_data=False)
    found = home.find_legacy(new)
    assert [f["path"] for f in found] == [str(old)]
    f = found[0]
    assert f["counts"]["transactions"] == 1 and f["personal"]["notes"] == 1 and f["personal"]["research"] == 1
    assert f["imports"] == 1 and f["history_files"] == 2                # the app's own README isn't yours
    assert home.status()["state"] == "unset"


def test_migrate_copies_and_verifies_and_leaves_the_old_folder(tmp_path, unset):
    old = _old_install(tmp_path / "old")
    before = sorted(p.relative_to(old) for p in old.rglob("*"))
    target, cache = tmp_path / "Market Radar", tmp_path / "cache"
    rep = home.migrate(old, target, cache)
    assert rep["tables"]["transactions"] == 1
    assert (target / "radar.db").exists() and (target / "notes" / "investor.md").read_text(encoding="utf-8") == "# Mig\næøå"
    assert (target / "history" / "snapshots" / "2026-10-01_momentum.parquet").exists()
    assert (target / "history" / "analyst.parquet").exists()
    assert (cache / "prices.parquet").exists() and (cache / "reports" / "dashboard.json").exists()
    assert (target / "imports" / "nordnet.csv").exists() and not (target / "imports" / "README.md").exists()
    assert (target / "README.txt").exists() and not (tmp_path / "Market Radar.incoming").exists()
    m = home.read_manifest(target)
    assert m["home_format"] == home.HOME_FORMAT and m["log"][0]["event"] == "migrated"
    # the old folder: exactly as it was, plus a note
    assert sorted(p.relative_to(old) for p in old.rglob("*")) == sorted([*before, old.joinpath("MOVED.txt").relative_to(old)])
    assert str(target) in (old / "MOVED.txt").read_text(encoding="utf-8")
    # remembered, and in use: the app reads the copy
    assert json.loads(paths.pointer_file().read_text(encoding="utf-8"))["home"] == str(target.resolve())
    paths.configure(None)
    assert paths.locations().home == target.resolve() and paths.source() == "pointer"
    assert [t["symbol"] for t in userstore.transactions()] == ["NOVO-B.CO"]
    assert home.status()["state"] == "ok"


def test_migrate_refuses_a_folder_that_holds_something(tmp_path, unset):
    old = _old_install(tmp_path / "old")
    (tmp_path / "busy").mkdir()
    (tmp_path / "busy" / "x.txt").write_text("x", encoding="utf-8")
    with pytest.raises(home.HomeError, match="not empty"):
        home.migrate(old, tmp_path / "busy")
    with pytest.raises(home.HomeError, match="no Market Radar data"):
        home.migrate(_old_install(tmp_path / "empty", with_data=False), tmp_path / "new")
    assert not paths.pointer_file().exists()


def test_a_missing_home_is_never_replaced_silently(tmp_path, unset):
    home.create(tmp_path / "h", tmp_path / "c")
    (tmp_path / "h").rename(tmp_path / "moved")
    paths.configure(None)
    assert home.status()["state"] == "missing"
    with pytest.raises(home.HomeError, match="not a Market Radar data folder"):
        home.use(tmp_path / "nowhere")
    home.use(tmp_path / "moved")
    assert home.status()["state"] == "ok"


def test_data_from_a_newer_version_is_read_only(tmp_path, unset):
    home.create(tmp_path / "h", tmp_path / "c")
    m = home.read_manifest(tmp_path / "h")
    home._write_manifest(tmp_path / "h", m | {"home_format": home.HOME_FORMAT + 1, "last_app_version": "9.0.0"})
    assert home.gate()[0] == "newer" and "9.0.0" in home.read_only()
    home._write_manifest(tmp_path / "h", m)
    userstore.watch("A")                                                  # creates radar.db at today's schema
    with closing(sqlite3.connect(tmp_path / "h" / "radar.db")) as con:
        con.execute(f"PRAGMA user_version = {home.schema_known() + 1}")
    assert "newer Market Radar" in home.read_only()


def test_the_cli_asks_for_setup_first(tmp_path, unset):
    _old_install(tmp_path / "old")
    r = CliRunner().invoke(cli.app, ["portfolios", "list"])
    assert r.exit_code == 1 and "radar setup" in r.output
    r = CliRunner().invoke(cli.app, ["paths", "--json"])
    assert r.exit_code == 0 and json.loads(r.output)["state"] == "unset"
    r = CliRunner().invoke(cli.app, ["setup", "--from", str(tmp_path / "old"), "--to", str(tmp_path / "h"), "--yes"])
    assert r.exit_code == 0, r.output
    assert "1 transactions" in r.output
    r = CliRunner().invoke(cli.app, ["paths", "--json"])
    assert json.loads(r.output)["folders"]["notes"] == str((tmp_path / "h" / "notes").resolve())
    assert CliRunner().invoke(cli.app, ["--version"]).output.startswith("Market Radar ")


def test_the_app_shows_setup_until_a_folder_is_chosen(tmp_path, unset):
    old = _old_install(tmp_path / "old")
    c = TestClient(api.app)
    r = c.get("/api/me")
    assert r.status_code == 409 and r.json()["detail"]["setup"] == "unset"
    assert c.get("/api/setup").json()["state"] == "unset"
    assert c.get("/api/setup/scan", params={"path": str(old)}).json()["counts"]["transactions"] == 1
    assert c.get("/api/setup/scan", params={"path": str(tmp_path)}).status_code == 404
    r = c.post("/api/setup", json={"action": "migrate", "source": str(old), "home": str(tmp_path / "h")})
    assert r.status_code == 200 and r.json()["status"]["state"] == "ok"
    assert c.get("/api/portfolio/transactions").status_code == 200
    assert c.post("/api/setup", json={"action": "create"}).status_code == 409    # only once


def test_the_app_refuses_writes_to_newer_data(tmp_path, unset, monkeypatch):
    home.create(tmp_path / "h", tmp_path / "c")
    m = home.read_manifest(tmp_path / "h")
    home._write_manifest(tmp_path / "h", m | {"home_format": home.HOME_FORMAT + 1})
    monkeypatch.setattr(api, "_gate", None)
    c = TestClient(api.app)
    assert c.get("/api/portfolios").status_code == 200
    r = c.put("/api/watchlist/MSFT")
    assert r.status_code == 409 and "newer version" in r.json()["detail"]["read_only"]


def test_a_layout_change_runs_once_after_the_backup(tmp_path, unset, monkeypatch):
    from radar import backup

    home.create(tmp_path / "h", tmp_path / "c")
    moved = []
    monkeypatch.setattr(home, "HOME_MIGRATIONS", [lambda h: moved.append(h)])
    monkeypatch.setattr(home, "HOME_FORMAT", 2)
    m = home.read_manifest(tmp_path / "h")
    home._write_manifest(tmp_path / "h", m | {"last_app_version": "0.0.1"})
    assert backup.before_upgrade() is not None                           # first the copy, then the change
    assert home.upgrade(tmp_path / "h") == [2] and home.upgrade(tmp_path / "h") == []
    assert moved == [tmp_path / "h"] and home.read_manifest(tmp_path / "h")["home_format"] == 2
