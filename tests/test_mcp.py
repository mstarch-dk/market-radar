"""The MCP server on the synthetic world: every tool answers through a real client (in memory), with the same view
the CLI's --json prints, JSON without NaN, and what the domain refuses as a tool error with its message."""
import json
import threading
import time

import anyio
import pytest
from mcp.client import Client

import world
from radar import agenda, locks, notebook, ops, paths, studyrun, updater, userstore, xray
from radar.market import Market
from radar.mcp import common, server, writes
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


def test_the_tools_say_what_they_touch_and_their_units():
    async def go():
        async with Client(server.build()) as c:
            return (await c.list_tools()).tools
    tools = {t.name: t for t in anyio.run(go)}
    assert set(tools) == {fn.__name__ for fn in server.TOOLS}
    reads = {fn.__name__ for fn in server.READS}
    for t in tools.values():
        assert t.annotations.read_only_hint == (t.name in reads)
        assert t.annotations.destructive_hint == (t.name == "write_memo")
        assert common.UNITS in t.description and "\n" not in t.description.split("\n\n")[0]
    assert {"summary", "ticker_profile", "propose_check", "job_status"} <= reads
    assert not reads & {"job_start", "propose_freeze", "propose_evaluate", "propose_shadow", "sim_picks",
                        "write_memo", "add_trade"}
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
    lr = ok("evidence_view", sections=["longrun"])
    assert "longrun" in lr and "scores" not in lr and "forward" not in lr
    assert "No section nope" in refused("evidence_view", sections=["nope"])


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


# ---------------- jobs ----------------

@pytest.fixture
def held():
    """Hold a lock from another thread, as the app or a terminal would from another process, until the test ends."""
    stop, threads = threading.Event(), []

    def hold(path):
        ready = threading.Event()

        def run():
            with locks.file_lock(path):
                ready.set()
                stop.wait(10)
        t = threading.Thread(target=run)
        t.start()
        ready.wait(5)
        threads.append(t)
    yield hold
    stop.set()
    [t.join(5) for t in threads]


def test_a_job_running_elsewhere_is_reported_not_started(radar, monkeypatch, held):
    ran = []
    monkeypatch.setattr(updater, "JOB", updater.UpdateJob(lambda log, progress: ran.append("update")))
    monkeypatch.setattr(updater, "REPORT_JOB", updater.UpdateJob(lambda log, progress: ran.append("report"),
                                                                 "Building", "report"))
    held(updater.UPDATE_LOCK)
    held(updater.REPORT_LOCK)
    assert "update is already running" in refused("job_start", kind="update")
    assert "readings are already being built" in refused("job_start", kind="report")
    assert ok("job_status", kind="update")["status"] == "idle" and ran == []
    assert "kind must be one of" in refused("job_start", kind="backup")
    assert "Name the study" in refused("job_start", kind="study")
    assert "No study called nope" in refused("job_start", kind="study", study="nope")


def test_a_study_running_elsewhere_blocks_an_update(radar, monkeypatch, held):
    monkeypatch.setattr(updater, "JOB", updater.UpdateJob(lambda log, progress: None))
    held(studyrun.LOCK)
    assert "a study is already running" in refused("job_start", kind="update")


def test_a_job_started_here_is_in_the_operations_log(radar, monkeypatch):
    def work(log, progress):
        log("rebuilt")
    monkeypatch.setattr(updater, "REPORT_JOB", updater.UpdateJob(work, "Building", "report"))
    assert ok("job_start", kind="report")["status"] in ("running", "done")
    for _ in range(100):
        if updater.REPORT_JOB.state["status"] != "running":
            break
        time.sleep(0.05)
    st = ok("job_status", kind="report")
    assert st["status"] == "done" and st["log"][-1].endswith("rebuilt")
    assert ok("job_status", kind="report", tail=0)["log"] == []
    assert any(j["kind"] == "report" and j["status"] == "done" for j in ops.jobs())


# ---------------- writes ----------------

def test_write_memo_writes_only_its_folders_whole(radar):
    got = ok("write_memo", kind="research", name="NVDA", markdown="# NVIDIA\n\nA memo.")
    f = paths.HOME.now() / "research" / "NVDA.md"
    assert got["file"] == str(f) and not got["replaced"]
    assert f.read_text(encoding="utf-8") == "# NVIDIA\n\nA memo.\n"
    assert "A memo." in ok("read_document", kind="research", name="NVDA")["markdown"]
    assert "exists" in refused("write_memo", kind="research", name="NVDA", markdown="# Again")
    assert ok("write_memo", kind="research", name="NVDA", markdown="# Again", replace=True)["replaced"]
    assert ok("write_memo", kind="hindsight", name="2026-10-27_top-n", markdown="# H")["file"].endswith(
        "2026-10-27_top-n.md")
    for name in ("../NVDA", "a/b", "..", ""):
        assert "isn't a file name" in refused("write_memo", kind="research", name=name, markdown="# x")
    assert "kind must be one of" in refused("write_memo", kind="exports", name="x", markdown="# x")
    assert "empty" in refused("write_memo", kind="briefs", name="2026-10-27", markdown="  ")
    home = paths.HOME.now()
    for d in writes.FOLDERS.values():
        rel = d.relative_to(home).as_posix().split("/")[0] + "/"
        assert rel in paths.REGISTRY["home"]


def test_add_trade_saves_only_when_confirmed(built):
    rows = len(userstore.transactions())
    px = float(Market.load().closes["S1"].dropna().iloc[-1])
    preview = ok("add_trade", type="buy", symbol="s1", quantity=10, price=px)
    assert not preview["saved"] and preview["trade"]["symbol"] == "S1" and "effect" in preview
    assert len(userstore.transactions()) == rows
    assert not preview["blocked"], preview["issues"]
    saved = ok("add_trade", type="buy", symbol="S1", quantity=10, price=px, confirm=True)
    assert saved["saved"] and saved["id"]
    assert len(userstore.transactions()) == rows + 1
    assert saved["effect"]["after"]["quantity"] == saved["effect"]["before"]["quantity"] + 10
