"""The MCP server: the radar's feature functions as tools for the Claude skills, over stdio (`radar mcp`).

The same functions the CLI and the web API call (docs/architecture.md), as typed tools that return JSON: no shell
calls, no file paths, freshness in the answer. Local only: the server talks to the Claude client that started it
and never listens on a port. Plan and increments: plans/mcp_server.md.
"""
