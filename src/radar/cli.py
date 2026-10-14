import typer

from . import universe

app = typer.Typer(add_completion=False, help="Market radar: rotation, momentum, regime and holdings signals.")


@app.command()
def update(refresh_constituents: bool = typer.Option(False, help="Re-fetch the S&P 500 constituent list")):
    """Download new prices (incremental) and macro series. Each source is logged in data/sources.json."""
    from . import updater

    updater.update(typer.echo, refresh_constituents)


@app.command(name="report")
def build_report():
    """Build reports/dashboard.json (the web app's data) and reports/summary.json."""
    from . import updater

    res = updater.build_report(typer.echo)
    typer.echo(f"{res['dashboard']} – view it with `uv run radar serve --open`")


@app.command()
def run(refresh_constituents: bool = False):
    """update + report."""
    update(refresh_constituents)
    build_report()


@app.command()
def discover(refresh_universe: bool = typer.Option(False, "--refresh-universe",
                                                   help="Re-build the list of names now (otherwise monthly)")):
    """The discovery scan: Nordic and European stocks and positive-list ETFs beyond the radar's own lists
    (reports/discovery.json, the Discover page). Separate from `radar run`; run it about weekly."""
    from .discovery import scan

    def progress(done: int, total: int) -> None:
        typer.echo(f"  … {done} of {total}")

    scan.run(typer.echo, progress, refresh_universe)


@app.command()
def doctor(offline: bool = typer.Option(False, "--offline", help="Skip the network checks")):
    """Check that everything Market Radar needs is in place, and say how to fix what isn't."""
    from . import health

    checks = health.checks(offline=offline)
    marks = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL", "info": "info"}
    for c in checks:
        typer.echo(f"[{marks[c['status']]}] {c['name']}: {c['detail']}")
        if c.get("fix") and c["status"] in ("warn", "fail"):
            typer.echo(f"       → {c['fix']}")
    failed = [c for c in checks if c["status"] == "fail"]
    typer.echo("All good." if not failed else f"{len(failed)} problem(s) to fix (see → above).")
    raise typer.Exit(1 if failed else 0)


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
def info(tickers: list[str] = typer.Argument(..., help="One or more Yahoo symbols"),
         refresh: bool = typer.Option(False, help="Re-fetch Yahoo fundamentals and estimates now"),
         personal: bool = typer.Option(False, "--personal", help="With several tickers: include your positions, "
                                       "holdings rows and correlations with your holdings (left out by default)"),
         out: str = typer.Option(None, "--out", help="Write the JSON to this file instead of printing it")):
    """Everything the radar knows about one ticker, as JSON (fetches prices if it isn't tracked yet).

    With several tickers: a side-by-side comparison for /compare (profiles, ACWI as the benchmark candidate,
    correlations and a metrics table). Personal data is left out unless --personal is given."""
    import json
    from pathlib import Path

    from . import profile

    if len(tickers) == 1:
        try:
            data = profile.legacy_info(profile.build(tickers[0].strip().upper(), refresh=refresh))
        except profile.TickerNotFound as e:
            raise typer.Exit(str(e))
    else:
        data = profile.compare(tickers, personal=personal)
    text = json.dumps(data, indent=1, default=str)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
        typer.echo(f"Wrote {out} ({len(text) // 1024} KB).")
    else:
        typer.echo(text)


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

    from .api import WEB_DIST

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


BUNDLE_TX = "portfolio_transactions.csv"   # every stored transaction (userstore), as text
BUNDLE_WATCHLIST = "watchlist.csv"          # the web app's watchlist edits
BUNDLE_YAHOO_WATCH = "yahoo_watch.json"     # the watchlist of the last Yahoo import
LEGACY_FILES = ("holdings.csv", "transactions.csv")   # bundles made before the transaction store


@app.command(name="bundle-holdings")
def bundle_holdings(set_secret: bool = typer.Option(False, "--set-secret", help="Store it directly as the HOLDINGS_BUNDLE GitHub secret")):
    """Pack your portfolio (stored transactions, watchlists) as base64 for the HOLDINGS_BUNDLE secret.

    Usage: uv run radar bundle-holdings --set-secret   (needs the GitHub CLI, signed in)
    """
    import base64
    import io
    import json
    import zipfile

    from . import userstore

    universe.ensure_migrated()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(BUNDLE_TX, userstore.export_transactions_csv())
        z.writestr(BUNDLE_WATCHLIST, userstore.export_watchlist_csv())
        z.writestr(BUNDLE_YAHOO_WATCH, json.dumps(userstore.meta_get("yahoo_watch", [])))
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    if not set_secret:
        typer.echo(data)
        return
    import subprocess

    # passed on stdin, not through a shell pipe, so console encodings (e.g. PowerShell's BOM) can't corrupt it
    subprocess.run(["gh", "secret", "set", "HOLDINGS_BUNDLE"], input=data.encode("ascii"), check=True)


@app.command(name="unbundle-holdings")
def unbundle_holdings():
    """Restore your portfolio from the HOLDINGS_BUNDLE environment variable (used in CI)."""
    import base64
    import io
    import json
    import os
    import re
    import zipfile

    from . import userstore
    from .config import IMPORTS

    # keep only base64 characters: tolerates BOMs/CRLF/whitespace added by shells when the secret was set
    data = re.sub(r"[^A-Za-z0-9+/=]", "", os.environ.get("HOLDINGS_BUNDLE", ""))
    if not data:
        typer.echo("HOLDINGS_BUNDLE not set – running without holdings.")
        return
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(data))) as z:
        names = set(z.namelist())
        if BUNDLE_TX in names:
            n_tx = userstore.import_transactions_csv(z.read(BUNDLE_TX).decode("utf-8"))
            if BUNDLE_YAHOO_WATCH in names:
                userstore.meta_set("yahoo_watch", json.loads(z.read(BUNDLE_YAHOO_WATCH)))
            userstore.meta_set("legacy_csv", {"status": "migrated", "at": "bundle"})
            what = f"{n_tx} transactions"
        else:                                     # an older bundle: the CSV files, moved into the store on first use
            IMPORTS.mkdir(exist_ok=True)
            for name in LEGACY_FILES:
                (IMPORTS / name).write_bytes(z.read(name))
            universe.ensure_migrated()
            what = ", ".join(LEGACY_FILES)
        n = userstore.import_watchlist_csv(z.read(BUNDLE_WATCHLIST).decode("utf-8")) if BUNDLE_WATCHLIST in names else 0
    typer.echo(f"Restored {what} and {n} watchlist edits.")


portfolio_app = typer.Typer(help="Your transactions (the portfolio store): list, add, export.")
app.add_typer(portfolio_app, name="portfolio")


@portfolio_app.command("list")
def portfolio_list(symbol: str = typer.Option(None, help="Only this ticker"),
                   account: str = typer.Option(None, help="Only this account")):
    """Stored transactions, oldest first."""
    from . import userstore

    universe.ensure_migrated()
    rows = userstore.transactions(symbol.upper() if symbol else None, account)
    for t in rows:
        typer.echo(f"{t['id']:>5}  {t['date']}  {t['type']:<4} {t['quantity']:>10g} {t['symbol']:<12} @ {t['price']:<10g}"
                   f" fee {t['fee']:<6g} {t['account'] or '-':<12} {t['source']}")
    typer.echo(f"{len(rows)} transactions.")


@portfolio_app.command("add")
def portfolio_add(type_: str = typer.Argument(..., metavar="BUY|SELL"), symbol: str = typer.Argument(...),
                  quantity: float = typer.Argument(...), price: float = typer.Argument(...),
                  date: str = typer.Option(None, help="Trade date YYYY-MM-DD (default: today)"),
                  fee: float = typer.Option(0.0, help="Commission, in the price's currency"),
                  account: str = typer.Option(None, help="e.g. ASK or 'frie midler'"),
                  note: str = typer.Option(None),
                  yes: bool = typer.Option(False, "--yes", help="Save despite warnings (errors always block)")):
    """Add one trade, checked the same way as in the app."""
    from datetime import date as _date

    from . import portfolio, profile, userstore

    universe.ensure_migrated()
    row = {"symbol": symbol.strip().upper(), "date": date or _date.today().isoformat(), "type": type_.upper(),
           "quantity": quantity, "price": price, "fee": fee, "account": account, "note": note}
    try:
        market = profile.ensure_prices(row["symbol"])
    except profile.TickerNotFound as e:
        raise typer.Exit(str(e))
    issues = portfolio.validate(row, market)
    for i in issues:
        typer.echo(f"  {i['level'].upper()}: {i['message']}")
    if any(i["level"] == "error" for i in issues) or (issues and not yes):
        raise typer.Exit("Not saved." + ("" if any(i["level"] == "error" for i in issues) else " Add --yes to save anyway."))
    tx_id = userstore.add_tx(row)
    eff = portfolio.effect(row, exclude_id=tx_id)
    typer.echo(f"Saved #{tx_id}. {row['symbol']}: {eff['before']['quantity']:g} → {eff['after']['quantity']:g} shares.")


@portfolio_app.command("export")
def portfolio_export(out: str = typer.Option(None, "--out", help="Write to this file instead of printing")):
    """Every transaction as CSV (a backup)."""
    from pathlib import Path

    from . import userstore

    universe.ensure_migrated()
    text = userstore.export_transactions_csv()
    if out:
        Path(out).write_text(text, encoding="utf-8")
        typer.echo(f"Wrote {out}.")
    else:
        typer.echo(text, nl=False)


if __name__ == "__main__":
    app()
