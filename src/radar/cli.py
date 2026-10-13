import typer

from . import ingest, report, universe

app = typer.Typer(add_completion=False, help="Market radar: rotation, momentum, regime and holdings signals.")


@app.command()
def update(refresh_constituents: bool = typer.Option(False, help="Re-fetch the S&P 500 constituent list")):
    """Download new prices (incremental) and macro series. Each source is logged in data/sources.json."""
    tickers = universe.all_price_tickers(refresh_constituents)
    typer.echo(f"Updating {len(tickers)} tickers…")

    def prices():
        res = ingest.update_prices(tickers)
        msg = f"{res['rows']:,} rows, {res['new']} new tickers"
        if res["rebased"]:
            msg += f"; re-downloaded after a dividend/split re-based the history: {', '.join(res['rebased'])}"
        if res["missing"]:
            msg += f"; no data for {len(res['missing'])}: {', '.join(res['missing'])}"
        return msg

    def fred():
        failed = ingest.update_fred(list(universe.macro_fred()))
        if failed:
            raise RuntimeError(f"failed: {', '.join(failed)}; those series keep their cached values")
        return f"{len(universe.macro_fred())} series"

    _run_steps({"prices": ("Prices", prices)})
    universe.names(tickers)  # warm the name cache
    universe.sectors(sorted({t for g in universe.stock_groups().values() for t in g}))  # warm the sector cache
    _run_steps({"fred": ("Macro (FRED)", fred)})
    update_external()


def update_external():
    """Non-price sources. A failure keeps the previous cached file, so the report still builds."""
    from . import external
    from .config import settings

    h = universe.holdings()
    mine = sorted(h.loc[h["status"].isin(["holding", "watch"]), "symbol"].dropna()) if not h.empty else []
    _run_steps({
        "cftc": ("CFTC positioning", lambda: f"{external.update_cot()} new rows"),
        "oecd": ("OECD leading indicators", external.update_oecd_cli),
        "factset": ("FactSet earnings insight",
                    lambda: f"report {d}" if (d := external.update_factset()) else "no new report"),
        "analyst": ("Analyst targets", lambda: external.update_analyst(mine, settings()["analyst"]["max_age_days"])),
    })


def _run_steps(steps: dict) -> None:
    """Run update steps {source key: (label, fn)}; a failure is logged and the cached data is kept."""
    from . import coverage

    for key, (label, step) in steps.items():
        try:
            msg = step()
            typer.echo(f"{label}: {msg}.")
            coverage.record(key, True, msg)
        except Exception as e:  # network/format problems shouldn't block the rest of the radar
            typer.echo(f"{label}: FAILED ({type(e).__name__}: {e}); using cached data.")
            coverage.record(key, False, error=f"{type(e).__name__}: {e}")


@app.command(name="report")
def build_report():
    """Build reports/radar.html and reports/summary.json."""
    res = report.build()
    typer.echo(f"Regime: {res['regime']} (data as of {res['asof']}). Stale tickers: {res['stale']}")
    typer.echo(res["html"])


@app.command()
def run(refresh_constituents: bool = False):
    """update + report."""
    update(refresh_constituents)
    build_report()


@app.command(name="import-yahoo")
def import_yahoo(csv_path: str):
    """Import a Yahoo Finance portfolio CSV export as holdings/watchlist."""
    df, warnings = universe.import_yahoo_csv(csv_path)
    counts = df["status"].value_counts()
    typer.echo(f"Imported {counts.get('holding', 0)} holdings, {counts.get('sold', 0)} sold positions, "
               f"{counts.get('watch', 0)} watchlist names.")
    for sym, msgs in warnings.items():
        for m in msgs:
            typer.echo(f"  ! {sym}: {m}")
    typer.echo("Run `radar run` to fetch prices for any new symbols.")


@app.command()
def info(ticker: str, refresh: bool = typer.Option(False, help="Re-fetch Yahoo fundamentals and estimates now")):
    """Everything the radar knows about one ticker, as JSON (fetches prices if it isn't tracked yet)."""
    import json

    from . import profile

    try:
        p = profile.build(ticker.strip().upper(), refresh=refresh)
    except profile.TickerNotFound as e:
        raise typer.Exit(str(e))
    typer.echo(json.dumps(profile.legacy_info(p), indent=1, default=str))


@app.command()
def serve(port: int = 8780, open_browser: bool = typer.Option(False, "--open", help="Open the app in the browser")):
    """Run the web app (ticker profiles) on http://127.0.0.1:<port>."""
    import uvicorn

    from .api import WEB_DIST

    if not WEB_DIST.exists():
        typer.echo("web/dist is missing: run `pnpm -C web install` and `pnpm -C web build` first (the API still runs).")
    if open_browser:
        import threading
        import webbrowser

        threading.Timer(1.5, webbrowser.open, [f"http://127.0.0.1:{port}/"]).start()
    uvicorn.run("radar.api:app", host="127.0.0.1", port=port, log_level="warning")


@app.command()
def openapi():
    """Print the web API's OpenAPI schema (web/ generates its TypeScript types from it: `pnpm gen:api`)."""
    import json

    from .api import app as api_app

    typer.echo(json.dumps(api_app.openapi(), indent=1))


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


BUNDLE_FILES = ("holdings.csv", "transactions.csv")


@app.command(name="bundle-holdings")
def bundle_holdings(set_secret: bool = typer.Option(False, "--set-secret", help="Store it directly as the HOLDINGS_BUNDLE GitHub secret")):
    """Pack imports/holdings.csv + transactions.csv as base64 for the HOLDINGS_BUNDLE secret.

    Usage: uv run radar bundle-holdings --set-secret   (needs the GitHub CLI, signed in)
    """
    import base64
    import io
    import zipfile

    from .config import IMPORTS

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in BUNDLE_FILES:
            z.write(IMPORTS / name, name)
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    if not set_secret:
        typer.echo(data)
        return
    import subprocess

    # passed on stdin, not through a shell pipe, so console encodings (e.g. PowerShell's BOM) can't corrupt it
    subprocess.run(["gh", "secret", "set", "HOLDINGS_BUNDLE"], input=data.encode("ascii"), check=True)


@app.command(name="unbundle-holdings")
def unbundle_holdings():
    """Restore holdings from the HOLDINGS_BUNDLE environment variable (used in CI)."""
    import base64
    import io
    import os
    import zipfile

    from .config import IMPORTS

    import re

    # keep only base64 characters: tolerates BOMs/CRLF/whitespace added by shells when the secret was set
    data = re.sub(r"[^A-Za-z0-9+/=]", "", os.environ.get("HOLDINGS_BUNDLE", ""))
    if not data:
        typer.echo("HOLDINGS_BUNDLE not set – running without holdings.")
        return
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(data))) as z:
        for name in BUNDLE_FILES:
            (IMPORTS / name).write_bytes(z.read(name))
    typer.echo(f"Restored {', '.join(BUNDLE_FILES)}.")


if __name__ == "__main__":
    app()
