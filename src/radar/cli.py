import typer

from . import ingest, report, universe

app = typer.Typer(add_completion=False, help="Market radar: rotation, momentum, regime and holdings signals.")


@app.command()
def update(refresh_constituents: bool = typer.Option(False, help="Re-fetch the S&P 500 constituent list")):
    """Download new prices (incremental) and macro series."""
    tickers = universe.all_price_tickers(refresh_constituents)
    typer.echo(f"Updating {len(tickers)} tickers…")
    res = ingest.update_prices(tickers)
    typer.echo(f"Prices: {res['rows']:,} rows, {res['new']} new tickers.")
    if res["missing"]:
        typer.echo(f"No data for {len(res['missing'])}: {', '.join(res['missing'])}")
    universe.names(tickers)  # warm the name cache
    ingest.update_fred(list(universe.macro_fred()))
    typer.echo("Macro (FRED) updated.")


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
def info(ticker: str):
    """Radar context for one ticker (fetches prices if it isn't tracked yet), as JSON."""
    import json

    from .config import settings
    from .signals import momentum

    prices = ingest.load_prices()
    if ticker not in set(prices["ticker"]):
        ingest.update_prices([ticker])
        prices = ingest.load_prices()
    if ticker not in set(prices["ticker"]):
        raise typer.Exit(f"No Yahoo data for {ticker}")
    closes, volumes = ingest.wide(prices), ingest.wide(prices, "volume")
    bench = universe.benchmark()
    m = momentum.metrics(closes, volumes, [ticker], settings()["momentum"]["min_history_days"]).iloc[0]
    b = closes[bench].dropna()
    def clean(v):
        if hasattr(v, "item"):  # numpy scalar -> python
            v = v.item()
        return round(v, 4) if isinstance(v, float) and not isinstance(v, bool) and v == v else (None if v != v else v)
    out = {k: clean(v) for k, v in m.items() if k != "history"}
    out["name"] = universe.names([ticker])[ticker]
    out["currency"] = universe.currencies([ticker])[ticker]
    for n, label in ((21, "rel_r1m"), (63, "rel_r3m"), (126, "rel_r6m")):
        s = closes[ticker].dropna()
        if len(s) > n:
            out[label] = round(float(s.iloc[-1] / s.iloc[-1 - n] - (b.iloc[-1] / b.iloc[-1 - n])), 4)
    groups = universe.stock_groups()
    region = next((g for g, t in groups.items() if ticker in t), None)
    if region:
        lead = momentum.leaders(closes, volumes, {region: groups[region]}, settings()["momentum"]["min_history_days"])
        row = lead[lead["ticker"] == ticker].iloc[0]
        out |= {"region": region, "score_in_region": row["score"], "rank_in_region": int(row["rank"]),
                "region_size": len(lead)}
    h = universe.holdings()
    hit = h[h["symbol"] == ticker]
    out["my_status"] = hit.iloc[0]["status"] if len(hit) else None
    typer.echo(json.dumps(out, indent=1, default=str))


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
