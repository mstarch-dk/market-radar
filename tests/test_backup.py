"""Backups of the data folder: what goes in, proving a zip is whole, restoring it, and thinning out old ones."""
import json
import zipfile
from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from radar import manifest, paths, userstore
from radar.datahome import backup, home

pytestmark = pytest.mark.os          # file replacing, locks and paths: also run on Windows and macOS in CI


@pytest.fixture
def data(tmp_path):
    loc = home.create(tmp_path / "Mine Ø-filer" / "Market Radar", tmp_path / "c")   # a space and an ø, as on Windows
    pid = userstore.save_portfolio({"name": "Depot", "mode": "real", "kind": "ask"})
    userstore.add_tx({"portfolio_id": pid, "symbol": "MSFT", "date": "2026-01-05", "type": "BUY", "quantity": 1,
                      "price": 400.0})
    (loc.home / "notes" / "investor.md").write_text("# Mig", encoding="utf-8")
    (loc.history / "snapshots").mkdir(parents=True)
    pd.DataFrame({"a": [1]}).to_parquet(loc.history / "snapshots" / "2026-10-01_momentum.parquet")
    loc.cache.mkdir(parents=True)
    pd.DataFrame({"a": [1]}).to_parquet(loc.cache / "prices.parquet")
    return loc


def test_a_backup_holds_your_data_and_history_not_the_cache(data):
    f = backup.create("test")
    with zipfile.ZipFile(f) as z:
        names = set(z.namelist())
        meta = json.loads(z.read("backup.json"))
    assert {"radar.db", "notes/investor.md", "history/snapshots/2026-10-01_momentum.parquet"} <= names
    assert not any("prices" in n for n in names)
    assert meta["tables"]["transactions"] == 1 and meta["app_version"] == manifest.app_version()
    assert backup.listing()[0]["name"] == f.name and backup.listing()[0]["kind"] == "manual"


def test_restore_puts_it_back_and_keeps_what_was_there(data):
    f = backup.create("test")
    userstore.delete_tx(userstore.transactions()[0]["id"])
    (data.home / "notes" / "investor.md").unlink()
    (data.home / "notes" / "new.md").write_text("after", encoding="utf-8")
    res = backup.restore(f)
    assert [t["symbol"] for t in userstore.transactions()] == ["MSFT"]
    assert (data.home / "notes" / "investor.md").exists() and not (data.home / "notes" / "new.md").exists()
    assert (data.cache / "prices.parquet").exists()                       # the cache isn't touched
    with zipfile.ZipFile(backup.folder() / res["saved_first"]) as z:        # the restore can be undone
        assert "notes/new.md" in z.namelist()
    assert not (data.home / ".restore-staging").exists() and not (data.home / ".restore-old").exists()


def test_a_damaged_or_newer_backup_is_refused(data, tmp_path):
    f = backup.create("test")
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(f) as src, zipfile.ZipFile(bad, "w") as dst:
        for n in src.namelist():
            dst.writestr(n, b"changed" if n == "notes/investor.md" else src.read(n))
    with pytest.raises(backup.BackupError, match="damaged"):
        backup.restore(bad)
    newer = tmp_path / "newer.zip"
    with zipfile.ZipFile(f) as src, zipfile.ZipFile(newer, "w") as dst:
        for n in src.namelist():
            meta = json.loads(src.read(n)) | {"home_format": home.HOME_FORMAT + 1} if n == "backup.json" else None
            dst.writestr(n, json.dumps(meta) if meta else src.read(n))
    with pytest.raises(backup.BackupError, match="newer"):
        backup.restore(newer)
    assert [t["symbol"] for t in userstore.transactions()] == ["MSFT"]


def test_old_backups_are_thinned_out(data):
    d = backup.folder()
    today = date(2026, 10, 15)
    for i in range(120):                                                   # a daily backup for four months
        day = datetime.combine(today - timedelta(days=i), datetime.min.time()).replace(hour=9)
        (d / f"market-radar-{day:%Y%m%d-%H%M%S}-daily-daily.zip").write_bytes(b"")
    old_up = datetime(2026, 5, 1, 9)
    (d / f"market-radar-{old_up:%Y%m%d-%H%M%S}-upgrade-before-v0.2.0.zip").write_bytes(b"")
    backup.prune(today)
    kept = backup.listing()
    daily = [r for r in kept if r["kind"] == "daily"]
    assert 12 <= len(daily) <= 7 + 5 + 12                                  # days, then weeks, then months
    assert daily[0]["created"].startswith("2026-10-15") and daily[6]["created"].startswith("2026-10-09")
    assert not any(r["kind"] == "upgrade" for r in kept)                  # older than 90 days


def test_a_copy_goes_to_the_second_folder(data, tmp_path):
    with pytest.raises(backup.BackupError, match="outside"):
        backup.set_mirror(data.home / "sub")
    backup.set_mirror(tmp_path / "cloud")
    f = backup.create("test")
    assert (tmp_path / "cloud" / f.name).exists() and backup.listing(tmp_path / "cloud")[0]["name"] == f.name
    backup.set_mirror(None)
    assert backup.mirror() is None


def test_a_new_version_backs_up_before_its_first_use(data):
    m = manifest.read_manifest(data.home)
    manifest.write_manifest(data.home, m | {"last_app_version": "0.0.1"})
    f = backup.before_upgrade()
    assert f is not None and "-upgrade-before-v" in f.name
    home.touch(data.home)
    assert backup.before_upgrade() is None
    assert backup.daily() is not None and backup.daily() is None             # once a day


def test_the_old_layout_is_not_backed_up(tmp_path):
    paths.configure(paths.Locations.legacy(tmp_path))
    assert backup.daily() is None and backup.before_upgrade() is None
    with pytest.raises(backup.BackupError, match="radar setup"):
        backup.create()


def test_the_data_page_lists_folders_and_backups(data, tmp_path):
    from fastapi.testclient import TestClient

    from radar import api

    c = TestClient(api.app)
    d = c.get("/api/data-home").json()
    assert {f["key"]: f["tier"] for f in d["folders"]}["cache"] == "cache" and d["status"]["state"] == "ok"
    made = c.post("/api/data-home/backup").json()
    assert made["kind"] == "manual"
    assert c.put("/api/data-home/mirror", json={"path": str(tmp_path / "cloud")}).json()["mirror"] == str(tmp_path / "cloud")
    assert c.post("/api/data-home/restore", json={"name": "nope.zip"}).status_code == 404
    assert c.post("/api/data-home/restore", json={"name": made["name"]}).json()["tables"]["transactions"] == 1
    r = c.get("/api/data-home/export")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
