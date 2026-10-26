"""The MCP server on the synthetic world: every tool answers through a real client (in memory), with the same view
the CLI's --json prints, JSON without NaN, and what the domain refuses as a tool error with its message."""
import json

import anyio
import pytest
from mcp.client import Client

import world
from radar import agenda, notebook, paths, xray
from radar.market import Market
from radar.mcp import common, server
from radar.reporting import dashboard, report
from radar.sources import ingest

JOURNAL = """---
date: 2026-09-01
ticker: S1
action: buy
account: ASK
horizon: 3 months
status: open
review_by: 2026-10-01
---
# Buy S1
"""


@pytest.fixture
def radar(tmp_data, monkeypatch):
    world.install(tmp_data, monkeypatch)
    monkeypatch.setattr(ingest, "update_prices", lambda tickers: {})   # Yahoo knows nothing new
    common.reset()
    dashboard.reset()
    return tmp_data


@pytest.fixture
def built(radar):
    report.build()
    return radar


def call(tool: str, /, **args) -> tuple[bool, str]:
    """(is_error, text) of one tool call through the protocol."""
    async def go():
        async with Client(server.build()) as c:
            r = await c.call_tool(tool, args)
            return r.is_error, "".join(getattr(x, "text", "") for x in r.content)
    return anyio.run(go)


def ok(tool: str, /, **args):
    err, text = call(tool, **args)
    assert not err, text
    assert "NaN" not in text and "Infinity" not in text
    return json.loads(text)


def refused(tool: str, /, **args) -> str:
    err, text = call(tool, **args)
    assert err, text
    return text


def test_the_tools_are_read_only_and_say_their_units():
    async def go():
        async with Client(server.build()) as c:
            return (await c.list_tools()).tools
    tools = {t.name: t for t in anyio.run(go)}
    assert set(tools) == {fn.__name__ for fn in server.TOOLS}
    for t in tools.values():
        assert t.annotations.read_only_hint and not t.annotations.destructive_hint
        assert common.UNITS in t.description and "\n" not in t.description.split("\n\n")[0]
    assert tools["ticker_profile"].annotations.open_world_hint and not tools["summary"].annotations.open_world_hint
    assert "symbols" in tools["calendar"].input_schema["properties"]


def test_summary_in_slices(built):
    index = ok("summary")
    assert {"regime", "rotation", "calendar", "coverage"} <= set(index["sections"])
    assert index["age_days"] >= 0 and index["stale"] is False and "regime" not in index
    one = ok("summary", sections=["regime", "rotation"])
    assert set(one) == {"asof", "age_days", "stale", "regime", "rotation"}
    assert "No section nope in summary.json (known: " in refused("summary", sections=["nope"])


def test_no_report_yet_says_what_to_run(radar):
    assert "uv run radar run" in refused("summary")
    assert "uv run radar run" in refused("calendar")


def test_the_views_are_the_clis(built):
    from world import IDX

    assert ok("portfolio_xray") == json.loads(json.dumps(xray.cached(Market.load()), default=str))
    world.calendar_reads(IDX[-1])
    full = ok("calendar")
    assert full == json.loads(json.dumps(agenda.cached(Market.load(), dashboard.load(), None, None, None),
                                         default=str))
    assert {i["symbol"] for i in full["items"]} == {"S1", "E2"}
    e2 = ok("calendar", symbols=["e2"])
    assert [i["symbol"] for i in e2["items"]] == ["E2"] and e2["soon"] == []
    assert "days must be from 1 to 366" in refused("calendar", days=0)


def test_portfolios_by_name(built):
    names = [p["name"] for p in ok("portfolios")["portfolios"]]
    assert names
    assert ok("portfolio_xray", portfolios=[names[0]])["selection"]["names"] == [names[0]]
    assert ok("portfolio_xray", tags=["no-such-tag"])["classes"] == []
    msg = refused("portfolio_xray", portfolios=["Nope"])
    assert "No portfolio called 'Nope'" in msg and names[0] in msg
    assert "scope must be one of" in refused("attribution", scope="mine")
    assert "start must be a date" in refused("attribution", start="last year")
    assert ok("performance")["rows"]
    assert "regression" in ok("attribution")
    assert len(ok("evidence_view")["scores"]) == 4


def test_ticker_profile(built):
    one = ok("ticker_profile", symbols=["s1"])
    assert one["ticker"] == "S1" and one["my_status"] == "holding"
    two = ok("ticker_profile", symbols=["S1", "S2"])
    assert "table" in two
    assert "Give at least one symbol" in refused("ticker_profile", symbols=[])


def test_notes_views_and_paths(radar):
    assert "investor.example.md" in refused("investor_notes")
    f = paths.NOTES.now() / "investor.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("# Me\nHorizon: 10 years\n", encoding="utf-8")
    assert "Horizon: 10 years" in ok("investor_notes")["markdown"]
    assert ok("market_views")["views"] == [] and ok("market_views")["disclaimer"]
    where = ok("data_paths")
    assert where["state"] in ("ok", "unset", "missing", "newer")


def test_the_notebook(radar):
    j = notebook.FOLDERS["journal"].now()
    j.mkdir(parents=True, exist_ok=True)
    (j / "2026-09-01-S1-buy.md").write_text(JOURNAL, encoding="utf-8")
    (j / "2026-08-01-S2-buy.md").write_text(JOURNAL.replace("S1", "S2").replace("open", "closed"), encoding="utf-8")
    assert [e["ticker"] for e in ok("journal_entries", status="open")["entries"]] == ["S1"]
    assert [e["ticker"] for e in ok("journal_entries", ticker="s2")["entries"]] == ["S2"]
    assert set(ok("documents")) == set(notebook.FOLDERS)
    assert list(ok("documents", kind="journal")) == ["journal"]
    doc = ok("read_document", kind="journal", name="2026-09-01-S1-buy")
    assert doc["markdown"].startswith("# Buy S1") and doc["meta"]["status"] == "open"
    assert "No research document called 'NVDA'" in refused("read_document", kind="research", name="NVDA")
    assert "No research document" in refused("read_document", kind="research", name="../journal/2026-09-01-S1-buy")
    assert "kind must be one of" in refused("documents", kind="nope")


def test_study_reports(radar):
    studies = {s["key"]: s for s in ok("study_reports")["studies"]}
    assert {"score-study:momentum", "score-study:qv", "longrun-study", "propose-study", "exit-study"} <= set(studies)
    assert all(s["status"] == "missing" and s["age_days"] is None for s in studies.values())
    assert studies["score-study:qv"]["command"] == "uv run radar study score --signal qv"
