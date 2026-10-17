"""Every `radar` command runs: one invocation each on the synthetic world (or a fresh data folder), checked for its
exit code and one line of what it prints. Network sources, the web server and the browser are stand-ins; the
code behind each command runs for real, so the printers are exercised too. Commands with their own fixtures:
test_cli_studies.py (sim, study), test_cli_propose.py (propose)."""
from __future__ import annotations

import json
import socket

import pytest
from typer.testing import CliRunner

import world
from radar import cli, home, report, userstore
from world import IDX


def run(*args: str, code: int = 0) -> str:
    res = CliRunner().invoke(cli.app, list(args))
    assert res.exit_code == code, (args, res.output, res.exception)
    return res.output


def run_json(*args: str):
    """A command's --json output: stdout only (progress goes to stderr)."""
    res = CliRunner().invoke(cli.app, list(args))
    assert res.exit_code == 0, (args, res.output, res.exception)
    return json.loads(res.stdout)


@pytest.fixture
def built(tmp_data, monkeypatch):
    """The synthetic world with a report built (S1 held in your real portfolio, E2 on the watchlist)."""
    world.install(tmp_data, monkeypatch)
    report.build()
    return tmp_data


@pytest.fixture
def fresh(tmp_path):
    """A real data folder (backups need one) with one portfolio and a trade."""
    loc = home.create(tmp_path / "h", tmp_path / "c")
    pid = userstore.save_portfolio({"name": "Depot", "mode": "real", "kind": "ask"})
    userstore.add_tx({"portfolio_id": pid, "symbol": "MSFT", "date": "2026-01-05", "type": "BUY", "quantity": 1,
                      "price": 400.0})
    return loc


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------- the data folder ----------------

def test_backup_backups_and_restore(fresh):
    out = run("backup", "--reason", "smoke")
    assert out.startswith("Wrote ") and "smoke" in out
    listing = run("backups")
    zip_name = next(w for w in listing.split() if w.endswith(".zip"))
    assert "manual" in listing
    path = next(fresh.home.rglob(zip_name))
    assert "Restored." in run("restore", str(path), "--yes")


def test_updates_says_the_check_is_off(fresh):
    assert "check for new versions is off" in run("updates")


# ---------------- market data and readings ----------------

def test_run_updates_then_builds_the_report(built, monkeypatch):
    from radar import updater

    monkeypatch.setattr(updater, "update", lambda log, refresh=False: log("updated (stand-in)"))
    assert "radar serve --open" in run("run")


def test_discover_runs_the_scan(built, monkeypatch):
    from radar.discovery import scan

    seen = {}
    monkeypatch.setattr(scan, "run", lambda log, progress, refresh: seen.update(refresh=refresh) or progress(1, 1))
    assert "1 of 1" in run("discover", "--refresh-universe") and seen == {"refresh": True}


def test_views_with_and_without_views(built):
    assert "No market views yet" in run("views")
    from radar.userstore import viewstore

    viewstore.save_view({"statement": "Chips keep leading", "conviction": 4, "horizon": "6m", "rationale": "AI capex",
                         "falsifier": "SOX below its 200d", "status": "active",
                         "exposures": [{"kind": "ticker", "key": "S1", "effect": 1}], "indicators": []})
    out = run("views")
    assert "Chips keep leading" in out and "would change my mind: SOX below its 200d" in out
    assert run_json("views", "--json")["views"][0]["conviction"] == 4


def test_ticker_starts_the_app_and_opens_the_profile(built, monkeypatch):
    import webbrowser

    import uvicorn

    opened, served = [], []
    monkeypatch.setattr(webbrowser, "open", opened.append)
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: served.append(k["port"]))
    port = _free_port()
    run("ticker", "s1", "--port", str(port))
    assert served == [port]


# ---------------- the app and its health ----------------

def test_serve_starts_uvicorn(built, monkeypatch):
    import uvicorn

    served = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **k: served.append((app, k["port"])))
    port = _free_port()
    run("serve", "--port", str(port))
    assert served == [("radar.api:app", port)]


def test_openapi_prints_the_schema():
    assert "/api/regime" in run_json("openapi")["paths"]


def test_ops_summarises_the_log(built):
    out = run("ops", "--errors")
    assert out.startswith("Last 7 days.") and "No error events." in out


# ---------------- portfolios ----------------

def test_import_yahoo(built, tmp_path):
    f = tmp_path / "quotes.csv"
    f.write_text("Symbol,Trade Date,Purchase Price,Quantity,Commission,Transaction Type\n"
                 f"S2,{IDX[60]:%Y%m%d},100,5,0,BUY\nE2,,,,,\n", encoding="utf-8")
    assert "Imported 1 holdings, 0 sold positions, 1 watchlist names." in run("import-yahoo", str(f))


def test_performance(built):
    out = run("performance")
    assert "ACWI" in out
    assert run_json("performance", "--json")


def test_portfolios_lifecycle(built):
    assert "Added Try (virtual, other)" in run("portfolios", "add", "Try", "--virtual", "--tag", "x")
    assert "kind must be one of" in run("portfolios", "add", "Bad", "--kind", "isk", code=1)   # the store's rule
    assert "Updated Try2" in run("portfolios", "edit", "Try", "--rename", "Try2", "--dividends", "cash")
    run("portfolios", "tag", "Try2", "y")
    run("portfolios", "untag", "Try2", "x")
    assert userstore.portfolio_by_name("Try2")["tags"] == ["y"]
    mine = next(p["name"] for p in userstore.portfolios() if p["mode"] == "real" and p["n_tx"])   # S1 is held here
    assert "default portfolio" in run("portfolios", "default", mine)
    run("portfolios", "fork", mine, "Fork", "--date", IDX[200].date().isoformat())
    assert userstore.portfolio_by_name("Fork")["mode"] == "virtual"
    run("portfolios", "move", mine, "--to", "Try2", "--symbol", "S1")
    assert {t["symbol"] for t in userstore.transactions(portfolios=[userstore.portfolio_by_name("Try2")["id"]])} == {"S1"}
    run("portfolios", "archive", "Fork")
    assert userstore.portfolio_by_name("Fork")["archived"]
    run("portfolios", "archive", "Fork", "--undo")
    assert "Deleted Fork" in run("portfolios", "delete", "Fork", "--yes")


# ---------------- fundamentals ----------------

def test_fundamentals_update_show_check_and_contact(built, monkeypatch):
    from radar.fundamentals import edgar, yahoo

    monkeypatch.setattr(edgar, "update_edgar", lambda force=False, tickers=None: "0 companies (stand-in)")
    monkeypatch.setattr(yahoo, "update_yahoo", lambda force=False, tickers=None: "0 companies (stand-in)")
    assert "SEC EDGAR: 0 companies (stand-in)" in run("fundamentals", "update")
    assert "S1" in run("fundamentals", "show", "S1")
    assert run_json("fundamentals", "show", "S1", "--json")
    assert "from both sources" in run("fundamentals", "check", code=1)      # the world has Yahoo statements only
    assert "you@example.com" in run("fundamentals", "contact", "you@example.com")
    assert "you@example.com" in run("fundamentals", "contact")
    run("fundamentals", "contact", "--clear")


# ---------------- the A/B test ----------------

def test_abtest_start_status_refresh(built):
    from radar.fundamentals import context as fcontext

    fcontext.reset()
    assert "radar abtest status" in run("abtest", "start", "--capital", "30000", "--n", "3", "--max-per-sector", "3")
    out = run("abtest", "status")
    assert "ab-momentum" in out or "momentum" in out.lower()
    assert run_json("abtest", "status", "--json")
    run("abtest", "refresh")


def test_every_command_has_a_test_that_runs_it():
    """A new command comes with a test that invokes it (here, test_cli_studies.py, test_cli_propose.py, or a
    feature's own test file): each leaf command must appear as the arguments of a run(...) / invoke(...) call."""
    import re
    from pathlib import Path

    import typer.main

    def leaves(c, path=()):
        for name, sub in getattr(c, "commands", {}).items():
            yield from (leaves(sub, path + (name,)) if getattr(sub, "commands", None) else [path + (name,)])

    text = "\n".join(p.read_text(encoding="utf-8") for p in Path(__file__).parent.glob("test_*.py"))
    calls = re.findall(r"""(?:run(?:_json)?\(|invoke\(cli\.app, \[)((?:\s*["'][^"']*["'],?)+)""", text)
    invoked = {tuple(re.findall(r"""["']([^"']*)["']""", c)) for c in calls}
    missing = [" ".join(cmd) for cmd in leaves(typer.main.get_command(cli.app))
               if not any(args[:len(cmd)] == cmd for args in invoked)]
    assert not missing, "commands no test runs: " + ", ".join(sorted(missing))
