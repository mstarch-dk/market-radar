"""The open-format export: readable on its own, and readable back on another computer."""
import csv
import io
import json
import zipfile

import pytest
from typer.testing import CliRunner

from radar import cli, paths, userstore
from radar.datahome import export, home

pytestmark = pytest.mark.os          # file replacing, locks and paths: also run on Windows and macOS in CI


def _seed(loc):
    pid = userstore.save_portfolio({"name": "Frie", "mode": "real", "kind": "frie_midler", "tags": ["lang"]})
    userstore.add_tx({"portfolio_id": pid, "symbol": "NOVO-B.CO", "date": "2026-01-05", "type": "BUY",
                      "quantity": 3, "price": 700.0, "note": "første køb"})
    userstore.watch("MSFT")
    (loc.home / "research" / "NOVO-B.CO.md").write_text("# Novo\nTese", encoding="utf-8")
    (loc.home / "notes" / "investor.md").write_text("# Mig", encoding="utf-8")


def test_the_export_is_readable_without_market_radar(tmp_path):
    loc = home.create(tmp_path / "Mine Ø-filer" / "Market Radar", tmp_path / "c")
    _seed(loc)
    f = export.write()
    assert f.parent == loc.home / "exports"
    with zipfile.ZipFile(f) as z:
        names = set(z.namelist())
        raw = z.read("transactions.csv")
        assert raw.startswith("﻿".encode())                      # Excel on Windows reads æøå
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        assert json.loads(z.read("export.json"))["export_format"] == export.EXPORT_FORMAT
        assert "| `portfolio` |" in z.read("EXPORT.md").decode("utf-8")
    assert {"portfolios.json", "views.json", "watchlist.csv", "research/NOVO-B.CO.md", "notes/investor.md"} <= names
    novo = next(r for r in rows if r["symbol"] == "NOVO-B.CO")
    assert novo["portfolio"] == "Frie" and novo["note"] == "første køb"


def test_an_export_loads_on_another_computer(tmp_path):
    loc = home.create(tmp_path / "Mine Ø-filer" / "Market Radar", tmp_path / "c")
    _seed(loc)
    f = export.write(tmp_path / "out.zip")
    paths.configure(None)
    other = home.create(tmp_path / "other", tmp_path / "c2")
    (other.home / "notes" / "investor.md").write_text("# Allerede her", encoding="utf-8")
    pv = export.preview(f)
    assert pv["transactions"] >= 1 and "research/NOVO-B.CO.md" in pv["new_documents"]
    r = export.load(f)
    assert [t["symbol"] for t in userstore.transactions(portfolios=[userstore.portfolio_by_name("Frie")["id"]])] == ["NOVO-B.CO"]
    assert userstore.portfolio_by_name("Frie")["tags"] == ["lang"]
    assert (other.home / "research" / "NOVO-B.CO.md").read_text(encoding="utf-8") == "# Novo\nTese"
    assert (other.home / "notes" / "investor.md").read_text(encoding="utf-8") == "# Allerede her"   # left alone
    assert r["documents_kept"] == 1 and userstore.watchlist_overlay() == {"MSFT": "add"}


def test_export_and_import_from_the_command_line(tmp_path):
    home.create(tmp_path / "h", tmp_path / "c")
    _seed(paths.locations())
    out = tmp_path / "x.zip"
    r = CliRunner().invoke(cli.app, ["export", "--out", str(out)])
    assert r.exit_code == 0 and out.exists() and "keep it private" in r.output
    r = CliRunner().invoke(cli.app, ["import-export", str(out), "--yes"])
    assert r.exit_code == 0 and "1 documents already here" not in r.output and "2 already here" in r.output
