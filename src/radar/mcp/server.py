"""The server: one MCPServer named `radar` with the read-only tools, run over stdio by `radar mcp`."""
from __future__ import annotations

import inspect
from collections.abc import Callable

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from ..manifest import app_version
from . import book, home
from .common import UNITS, tool

INSTRUCTIONS = (
    "Market Radar: a Danish investor's local market radar (trends, sector and theme rotation, 1–6-month momentum) "
    "and their portfolios, benchmarked against MSCI ACWI. Read the user's investor notes before advising on "
    "placement. Everything here is analysis, not advice. " + UNITS)

TOOLS: tuple[Callable[..., object], ...] = (*home.TOOLS, *book.TOOLS)
REACHES_OUT = {book.ticker_profile}     # downloads an untracked ticker's prices and Yahoo's details


def description(fn: Callable[..., object]) -> str:
    """The docstring with the source's line breaks dropped (blank lines kept), then the units."""
    paras = inspect.cleandoc(fn.__doc__ or "").split("\n\n")
    return "\n\n".join([*(" ".join(p.split("\n")) for p in paras), UNITS])


def build() -> MCPServer:
    server = MCPServer("radar", title="Market Radar", instructions=INSTRUCTIONS, version=app_version())
    for fn in TOOLS:
        server.add_tool(tool(fn), description=description(fn), annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=fn in REACHES_OUT))
    return server


def run() -> None:
    build().run("stdio")
