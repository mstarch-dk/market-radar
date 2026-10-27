"""The server: one MCPServer named `radar` with its tools (readings, jobs, engines and two narrow writes), run over
stdio by `radar mcp`."""
from __future__ import annotations

import inspect
from collections.abc import Callable

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from ..manifest import app_version
from . import book, engine, home, jobs, writes
from .common import UNITS, tool

INSTRUCTIONS = (
    "Market Radar: a Danish investor's local market radar (trends, sector and theme rotation, 1–6-month momentum) "
    "and their portfolios, benchmarked against MSCI ACWI. Read the user's investor notes before advising on "
    "placement. Everything here is analysis, not advice. The tools that are not read-only save into the user's data "
    "folder (a memo, a trade, a frozen proposal, virtual portfolios) or start a job. " + UNITS)

READS: tuple[Callable[..., object], ...] = (
    *home.TOOLS, *book.TOOLS, jobs.job_status, engine.propose_candidates, engine.propose_picks,
    engine.propose_review, engine.propose_check, engine.sim_picks_candidates)
TOOLS: tuple[Callable[..., object], ...] = (*home.TOOLS, *book.TOOLS, *jobs.TOOLS, *engine.TOOLS, *writes.TOOLS)
REPLACES = {writes.write_memo}          # may replace a document (only when asked to)
# download: an untracked ticker's prices and Yahoo's details (a profile, a trade's symbol), the update's sources
REACHES_OUT = {book.ticker_profile, jobs.job_start, writes.add_trade}


def description(fn: Callable[..., object]) -> str:
    """The docstring with the source's line breaks dropped (blank lines kept), then the units."""
    paras = inspect.cleandoc(fn.__doc__ or "").split("\n\n")
    return "\n\n".join([*(" ".join(p.split("\n")) for p in paras), UNITS])


def build() -> MCPServer:
    server = MCPServer("radar", title="Market Radar", instructions=INSTRUCTIONS, version=app_version())
    for fn in TOOLS:
        server.add_tool(tool(fn), description=description(fn), annotations=ToolAnnotations(
            read_only_hint=fn in READS, destructive_hint=fn in REPLACES, open_world_hint=fn in REACHES_OUT))
    return server


def run() -> None:
    build().run("stdio")
