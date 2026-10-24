"""The app and its health: serve, the OpenAPI schema, doctor, the operations log."""
import typer

from .root import app


@app.command()
def doctor(offline: bool = typer.Option(False, "--offline", help="Skip the network checks")):
    """Check that everything Market Radar needs is in place, and say how to fix what isn't."""
    from .. import health

    checks = health.checks(offline=offline)
    marks = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL", "info": "info"}
    for c in checks:
        typer.echo(f"[{marks[c['status']]}] {c['name']}: {c['detail']}")
        if c.get("fix") and c["status"] in ("warn", "fail"):
            typer.echo(f"       → {c['fix']}")
    failed = [c for c in checks if c["status"] == "fail"]
    typer.echo("All good." if not failed else f"{len(failed)} problem(s) to fix (see → above).")
    raise typer.Exit(1 if failed else 0)


@app.command(name="ops")
def ops_summary(days: int = typer.Option(7, help="Look back this many days"),
                errors: bool = typer.Option(False, "--errors", help="Also list the latest error events")):
    """External requests per host and source (count, errors, 429s, latency), paused hosts and the last jobs, from
    the operations log (ops.db in the cache folder)."""
    from .. import net, ops

    _when = lambda t: ops.local(t).strftime("%Y-%m-%d %H:%M") if t else "–"   # stored in UTC, shown in local time
    s = ops.summary(days, net.limits)
    lu = s["last_update"]
    typer.echo(f"Last {days} days. Requests in 24 h: {s['requests_24h']:,} ({s['errors_24h']:,} failed); "
               f"error events in 24 h: {s['error_events_24h']}.")
    typer.echo("Last update: " + (f"{lu['status']} ({lu['kind']}, started {_when(lu['started'])})"
                                  if lu else "none recorded"))
    for c in s["cooldowns"]:
        typer.echo(f"PAUSED {c['host']} until {_when(c['until'])}: {c['reason']}")
    for h in s["over_budget"]:
        typer.echo(f"OVER BUDGET {h} (today)")
    if not s["rows"]:
        typer.echo("No requests recorded in this period.")
    else:
        def ms(v):
            return "–" if v is None else f"{v:,.0f}"
        typer.echo(f"{'host':32} {'source':20} {'requests':>8} {'err %':>6} {'429':>5} {'p50 ms':>7} {'p95 ms':>7}  last error")
        for r in s["rows"]:
            typer.echo(f"{r['host'][:32]:32} {(r['source'] or '–')[:20]:20} {r['requests']:>8,} {r['error_pct']:>6.1f} "
                       f"{r['throttled']:>5} {ms(r['p50_ms']):>7} {ms(r['p95_ms']):>7}  {(r['last_error'] or '')[:60]}")
    if errors:
        typer.echo("")
        evs = ops.events(level="error", limit=20)
        if not evs:
            typer.echo("No error events.")
        for e in evs:
            typer.echo(f"{_when(e['ts'])} [{e['kind']}] {e['source'] or '–'}: {e['message'][:120]}")


@app.command()
def serve(port: int = 8780, open_browser: bool = typer.Option(False, "--open", help="Open the app in the browser")):
    """Run the web app (dashboard, ticker profiles, watchlist) on http://127.0.0.1:<port>."""
    import socket
    import webbrowser

    url = f"http://127.0.0.1:{port}/"
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", port)) == 0:   # already running (e.g. the start script double-clicked twice)
            typer.echo(f"Market Radar is already running at {url}")
            if open_browser:
                webbrowser.open(url)
            return

    import uvicorn

    from ..api import WEB_DIST

    if not WEB_DIST.exists():
        typer.echo("web/dist is missing: run `pnpm -C web install` and `pnpm -C web build` first (the API still runs).")
    if open_browser:
        import threading

        threading.Timer(1.5, webbrowser.open, [url]).start()
    uvicorn.run("radar.api:app", host="127.0.0.1", port=port, log_level="warning")


@app.command()
def openapi():
    """Print the web API's OpenAPI schema (web/ generates its TypeScript types from it: `pnpm gen:api`)."""
    import json

    from ..api import app as api_app

    typer.echo(json.dumps(api_app.openapi(), indent=1))
