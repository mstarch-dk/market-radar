"""Every `radar` command runs: one invocation each on the synthetic world (or a fresh data folder), checked for its
exit code and one line of what it prints. Network sources, the web server and the browser are stand-ins; the
code behind each command runs for real, so the printers are exercised too. Commands with their own fixtures:
test_cli_studies.py (sim, study), test_cli_propose.py (propose)."""
from __future__ import annotations

import io
import json
import socket
import sys

import pytest
from typer.testing import CliRunner

import world
from radar import cli, userstore
from radar.datahome import home
from radar.reporting import report
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
    monkeypatch.setattr(scan, "run", lambda tracked, log, progress, refresh: seen.update(refresh=refresh) or progress(1, 1))
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


def test_mcp_runs_the_server_over_stdio(built, monkeypatch):
    """`radar mcp` runs the MCP server over stdio and prints nothing first: stdout is the protocol."""
    from mcp.server.mcpserver import MCPServer

    ran = []
    monkeypatch.setattr(MCPServer, "run", lambda self, transport="stdio", **k: ran.append((self.name, transport)))
    assert run("mcp") == ""
    assert ran == [("radar", "stdio")]


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
    other = tmp_path / "prices.csv"
    other.write_text("Date,Open,Close\n2026-01-01,1,2\n", encoding="utf-8")
    res = CliRunner().invoke(cli.app, ["import-yahoo", str(other)])      # checked like the app's import
    assert res.exit_code != 0 and "Yahoo Finance portfolio export" in res.output


def test_performance(built):
    out = run("performance")
    assert "ACWI" in out
    assert run_json("performance", "--json")


def test_cli_calendar(built):
    """radar calendar prints its weeks, --json the AgendaView; a held stock without a date is listed, not dropped."""
    from radar import api_models

    out = run("calendar")
    assert "Calendar of" in out and "No earnings date known" in out and "S1" in out
    v = api_models.AgendaView.model_validate(run_json("calendar", "--json"))
    assert "S1" in {r.symbol for r in v.no_date} and v.items == []                # nothing read yet: no guess
    assert run_json("calendar", "--days", "10", "--json")["days"] == 10
    assert "--scope must be one of" in run("calendar", "--scope", "isk", code=1)


def test_cli_xray(built):
    """radar xray prints its tables, --json the XrayView; names, tags and scopes resolve as radar performance's."""
    from radar import api_models

    assert "Sector (top active weights" in run("xray")
    v = api_models.XrayView.model_validate(run_json("xray", "--json"))
    assert v.selection.names and v.classes
    assert run_json("xray", v.selection.names[0], "--json")["selection"]["names"] == v.selection.names[:1]
    assert run_json("xray", "--tag", "no-such-tag", "--json")["classes"] == []
    assert run_json("xray", "--scope", "all", "--json")["selection"]["scope"] == "all"
    assert "No portfolio called" in run("xray", "Nope", code=1)
    assert "--scope must be one of" in run("xray", "--scope", "isk", code=1)


def test_cli_attribution(built):
    """radar attribution runs on a history too short to attribute: notes, not numbers; --json is the
    AttributionView; bad flags are refused."""
    from radar import api_models
    assert "Attribution of" in run("attribution")
    v = api_models.AttributionView.model_validate(run_json("attribution", "--json"))
    assert v.dims == {} and v.notes
    assert run_json("attribution", "--scope", "all", "--json")["selection"]["scope"] == "all"
    assert "--start must be a date" in run("attribution", "--start", "2026-13-01", code=1)
    assert "--scope must be one of" in run("attribution", "--scope", "isk", code=1)


def test_cli_tax(built):
    """radar tax: the year's estimate (the --json view is the API's), the classes, an ISIN, persons and openings."""
    from radar import api_models
    from radar.market import Market
    from radar.tax import year_report

    year = IDX[-1].year
    assert f"Tax estimate for {year}" in run("tax", "year")
    v = run_json("tax", "year", str(year), "--json")
    api_models.TaxYearView.model_validate(v)
    assert v["accounts"] == year_report(Market.load(), year)["accounts"]
    assert "S1" in run("tax", "classify")
    assert "THEME1: IE00B4L5Y983" in run("tax", "isin", "THEME1", "IE00B4L5Y983")
    assert "S1: stock" in run("tax", "classify", "S1", "stock")
    assert "isn't an ISIN" in run("tax", "isin", "THEME1", "nope", code=1)
    assert "Saved Partner" in run("tax", "person", "add", "Partner", "--capital-rate", "0.37")
    assert "Saved Partner" in run("tax", "person", "set", "Partner", "--account", "frie midler")
    assert "Partner" in run("tax", "person", "list")
    assert "Added opening #1" in run("tax", "opening", "add", "--pool", "listed_loss", "--year", str(year),
                                     "--amount", "500", "--person", "Partner")
    assert "listed_loss" in run("tax", "opening", "list")
    assert "Removed opening #1" in run("tax", "opening", "remove", "--id", "1")


def test_cli_evidence(built):
    """radar evidence prints each report's status and the scoreboard; --json is the EvidenceView."""
    from radar import api_models

    out = run("evidence")
    assert "Momentum score: not run yet: run `radar study score`" in out and "Frozen proposals:" in out
    v = api_models.EvidenceView.model_validate(run_json("evidence", "--json"))
    assert [c.head.signal for c in v.scores] == ["momentum", "quality", "value", "qv"] and v.forward is not None


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

    monkeypatch.setattr(edgar, "update_edgar", lambda *a, force=False, tickers=None: "0 companies (stand-in)")
    monkeypatch.setattr(yahoo, "update_yahoo", lambda *a, force=False, tickers=None: "0 companies (stand-in)")
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


def test_a_console_on_another_code_page_gets_utf8(monkeypatch):
    """Windows consoles and CI runners default to cp1252: text with → must not stop a command (radar doctor did)."""
    out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", out)
    from radar.cli.root import utf8_console

    utf8_console()
    print("Data → cache, ø")
    out.flush()
    assert out.buffer.getvalue().decode("utf-8").startswith("Data → cache, ø")
