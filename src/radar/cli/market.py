"""Market data and readings: update, report, run, discover, your market views, ticker profiles."""
import typer

from .common import job, portfolio_ids, to_json
from .root import app
from .server import serve


@app.command()
def update(refresh_constituents: bool = typer.Option(False, help="Re-fetch the S&P 500 constituent list")):
    """Download new prices (incremental) and macro series. Each source is logged in sources.json (in the cache folder)."""
    from .. import updater

    with job("cli_update") as log:
        updater.update(log, refresh_constituents)


@app.command(name="report")
def build_report():
    """Build reports/dashboard.json (the web app's data) and reports/summary.json from the data already
    downloaded. Refused while another build runs (in the app or a terminal)."""
    from .. import updater

    with job("cli_report") as log:
        res = updater.build_report(log, wait=0)
    typer.echo(f"{res['dashboard']} – view it with `uv run radar serve --open`")


@app.command()
def run(refresh_constituents: bool = False):
    """update + report."""
    from .. import updater
    from ..datahome import backup

    with job("cli_run") as log:
        if (b := backup.daily()):
            log(f"Backup: {b.name}")
        updater.update(log, refresh_constituents)
        res = updater.build_report(log)
    typer.echo(f"{res['dashboard']} – view it with `uv run radar serve --open`")


@app.command()
def discover(refresh_universe: bool = typer.Option(False, "--refresh-universe",
                                                   help="Re-build the list of names now (otherwise monthly)")):
    """The discovery scan: Nordic and European stocks and positive-list ETFs beyond the radar's own lists
    (reports/discovery.json, the Discover page). Separate from `radar run`; run it about weekly."""
    from .. import updater

    def progress(done: int, total: int) -> None:
        typer.echo(f"  … {done} of {total}")

    with job("cli_discover") as log:
        updater.discover(log, progress, refresh_universe)


@app.command()
def views(as_json: bool = typer.Option(False, "--json", help="Machine-readable output (for the skills)"),
          archived: bool = typer.Option(False, "--archived", help="Include archived views")):
    """Your market views (subjective beliefs) with what the radar's data says about each. Personal."""

    from .. import market_views as mv

    vs = mv.with_evidence(None if archived else "active")
    if as_json:
        typer.echo(to_json({"disclaimer": mv.DISCLAIMER, "views": vs}, indent=1, ensure_ascii=False))
        return
    if not vs:
        typer.echo("No market views yet: add them on the My market views page of the app.")
        return
    typer.echo(mv.DISCLAIMER)
    typer.echo("")
    for v in vs:
        ev = v["evidence"]
        typer.echo(f"#{v['id']} [{v['status']}] conviction {v['conviction']}/5, {v['horizon']}: {v['statement']}")
        helps = ", ".join(e["key"] for e in v["exposures"] if e["effect"] > 0) or "–"
        hurts = ", ".join(e["key"] for e in v["exposures"] if e["effect"] < 0) or "–"
        typer.echo(f"    helps: {helps} | hurts: {hurts}")
        typer.echo(f"    evidence: {ev['verdict']} (" + ", ".join(f"{i['label']}: {i['state']}" for i in ev["items"]) + ")")
        if v.get("falsifier"):
            typer.echo(f"    would change my mind: {v['falsifier']}")


@app.command()
def info(tickers: list[str] = typer.Argument(..., help="One or more Yahoo symbols"),
         refresh: bool = typer.Option(False, help="Re-fetch Yahoo fundamentals and estimates now"),
         personal: bool = typer.Option(False, "--personal", help="With several tickers: include your positions, "
                                       "holdings rows and correlations with your holdings (left out by default)"),
         portfolio: list[str] = typer.Option(None, "--portfolio", help="With --personal: these portfolios count as "
                                             "your holdings (repeatable; default: your real portfolios)"),
         tag: list[str] = typer.Option(None, "--tag", help="With --personal: portfolios carrying this tag"),
         out: str = typer.Option(None, "--out", help="Write the JSON to this file instead of printing it")):
    """Everything the radar knows about one ticker, as JSON (fetches prices if it isn't tracked yet).

    With several tickers: a side-by-side comparison for /compare (profiles, ACWI as the benchmark candidate,
    correlations and a metrics table). Personal data is left out unless --personal is given."""
    from pathlib import Path

    from .. import profile

    if len(tickers) == 1:
        try:
            data = profile.legacy_info(profile.build(tickers[0].strip().upper(), refresh=refresh))
        except profile.TickerNotFound as e:
            raise SystemExit(str(e))
    else:
        sel = portfolio_ids(portfolio, tag) if (portfolio or tag) else None
        data = profile.compare(tickers, personal=personal, portfolios=sel)
    text = to_json(data, indent=1)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
        typer.echo(f"Wrote {out} ({len(text) // 1024} KB).")
    else:
        typer.echo(text)


@app.command()
def ticker(symbol: str, port: int = 8780):
    """Open the profile page for one ticker (starts the web app if it isn't running)."""
    import socket
    import webbrowser

    url = f"http://127.0.0.1:{port}/ticker/{symbol.strip().upper()}"
    with socket.socket() as sock:
        running = sock.connect_ex(("127.0.0.1", port)) == 0
    if running:
        webbrowser.open(url)
        return
    import threading

    threading.Timer(1.5, webbrowser.open, [url]).start()
    serve(port, False)
