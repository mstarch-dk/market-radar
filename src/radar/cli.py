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
def views(as_json: bool = typer.Option(False, "--json", help="Machine-readable output (for the skills)"),
          archived: bool = typer.Option(False, "--archived", help="Include archived views")):
    """Your market views (subjective beliefs) with what the radar's data says about each. Personal."""
    import json

    from . import market_views as mv

    vs = mv.with_evidence(None if archived else "active")
    if as_json:
        typer.echo(json.dumps({"disclaimer": mv.DISCLAIMER, "views": vs}, indent=1, ensure_ascii=False, default=str))
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
         portfolio: list[str] = typer.Option(None, "--portfolio", help="With --personal: these portfolios count as "
                                             "your holdings (repeatable; default: your real portfolios)"),
         tag: list[str] = typer.Option(None, "--tag", help="With --personal: portfolios carrying this tag"),
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
        sel = _portfolio_ids(portfolio, tag) if (portfolio or tag) else None
        data = profile.compare(tickers, personal=personal, portfolios=sel)
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
BUNDLE_VIEWS = "views.json"                 # your market views (the /views page)
BUNDLE_PORTFOLIOS = "portfolios.json"       # the portfolios: kind, mode, tags (real ones unless --include-virtual)
LEGACY_FILES = ("holdings.csv", "transactions.csv")   # bundles made before the transaction store


@app.command(name="bundle-holdings")
def bundle_holdings(set_secret: bool = typer.Option(False, "--set-secret", help="Store it directly as the HOLDINGS_BUNDLE GitHub secret"),
                    include_virtual: bool = typer.Option(False, "--include-virtual",
                                                         help="Pack virtual portfolios too (left out by default)")):
    """Pack your portfolios (real ones: stored transactions, kinds and tags), watchlists and market views as
    base64 for the HOLDINGS_BUNDLE secret.

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
        scope = "all" if include_virtual else "real"
        z.writestr(BUNDLE_PORTFOLIOS, userstore.export_portfolios_json(scope))
        z.writestr(BUNDLE_TX, userstore.export_transactions_csv(userstore.portfolio_ids(scope, include_archived=True)))
        z.writestr(BUNDLE_WATCHLIST, userstore.export_watchlist_csv())
        z.writestr(BUNDLE_YAHOO_WATCH, json.dumps(userstore.meta_get("yahoo_watch", [])))
        z.writestr(BUNDLE_VIEWS, userstore.export_views_json())
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
        n_pf = userstore.import_portfolios_json(z.read(BUNDLE_PORTFOLIOS).decode("utf-8")) \
            if BUNDLE_PORTFOLIOS in names else 0           # before the rows, so they find their portfolio
        if BUNDLE_TX in names:
            n_tx = userstore.import_transactions_csv(z.read(BUNDLE_TX).decode("utf-8"))
            if BUNDLE_YAHOO_WATCH in names:
                userstore.meta_set("yahoo_watch", json.loads(z.read(BUNDLE_YAHOO_WATCH)))
            userstore.meta_set("legacy_csv", {"status": "migrated", "at": "bundle"})
            what = f"{n_tx} transactions in {n_pf or 'their'} portfolios"
        else:                                     # an older bundle: the CSV files, moved into the store on first use
            IMPORTS.mkdir(exist_ok=True)
            for name in LEGACY_FILES:
                (IMPORTS / name).write_bytes(z.read(name))
            universe.ensure_migrated()
            what = ", ".join(LEGACY_FILES)
        n = userstore.import_watchlist_csv(z.read(BUNDLE_WATCHLIST).decode("utf-8")) if BUNDLE_WATCHLIST in names else 0
        n_views = userstore.import_views_json(z.read(BUNDLE_VIEWS).decode("utf-8")) if BUNDLE_VIEWS in names else 0
    typer.echo(f"Restored {what}, {n} watchlist edits and {n_views} market views.")


portfolio_app = typer.Typer(help="Your transactions (the portfolio store): list, add, export.")
app.add_typer(portfolio_app, name="portfolio")


@portfolio_app.command("list")
def portfolio_list(symbol: str = typer.Option(None, help="Only this ticker"),
                   portfolio: list[str] = typer.Option(None, "--portfolio", help="Only these portfolios (repeatable; "
                                                       "default: your real ones)"),
                   tag: list[str] = typer.Option(None, "--tag", help="Portfolios carrying this tag"),
                   account: str = typer.Option(None, "--account", hidden=True)):
    """Stored transactions, oldest first."""
    from . import userstore

    universe.ensure_migrated()
    names = [*(portfolio or []), *([account] if account else [])]
    sel = _portfolio_ids(names, tag) if (names or tag) else userstore.portfolio_ids()
    rows = userstore.transactions(symbol.upper() if symbol else None, sel)
    for t in rows:
        what = (f"{t['quantity']:>10g} {t['symbol']:<12} @ {t['price']:<10g} fee {t['fee']:<6g}"
                if t["type"] in ("BUY", "SELL") else f"{t['amount']:>10g} {t['currency'] or 'DKK':<12} {t['symbol'] or '':<19}")
        typer.echo(f"{t['id']:>5}  {t['date']}  {t['type']:<8} {what} {t['portfolio']:<16} {t['source']}")
    typer.echo(f"{len(rows)} transactions.")


@portfolio_app.command("add")
def portfolio_add(type_: str = typer.Argument(..., metavar="BUY|SELL"), symbol: str = typer.Argument(...),
                  quantity: float = typer.Argument(...), price: float = typer.Argument(...),
                  date: str = typer.Option(None, help="Trade date YYYY-MM-DD (default: today)"),
                  fee: float = typer.Option(0.0, help="Commission, in the price's currency"),
                  portfolio_name: str = typer.Option(None, "--portfolio", help="e.g. ASK or 'frie midler' (default: "
                                                     "the default portfolio; see `radar portfolios list`)"),
                  account: str = typer.Option(None, "--account", hidden=True),
                  note: str = typer.Option(None),
                  yes: bool = typer.Option(False, "--yes", help="Save despite warnings (errors always block)")):
    """Add one trade, checked the same way as in the app."""
    from datetime import date as _date

    from . import portfolio, profile, userstore

    universe.ensure_migrated()
    row = {"symbol": symbol.strip().upper(), "date": date or _date.today().isoformat(), "type": type_.upper(),
           "quantity": quantity, "price": price, "fee": fee, "portfolio": portfolio_name or account, "note": note}
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
    saved = userstore.get_tx(tx_id)
    typer.echo(f"Saved #{tx_id} in {saved['portfolio']}. {row['symbol']}: {eff['before']['quantity']:g} → "
               f"{eff['after']['quantity']:g} shares.")


@portfolio_app.command("export")
def portfolio_export(out: str = typer.Option(None, "--out", help="Write to this file instead of printing"),
                     portfolio: list[str] = typer.Option(None, "--portfolio", help="Only these portfolios (repeatable)"),
                     all_: bool = typer.Option(False, "--all", help="Virtual portfolios too")):
    """Transactions as CSV (a backup): your real portfolios unless chosen otherwise."""
    from pathlib import Path

    from . import userstore

    universe.ensure_migrated()
    sel = _portfolio_ids(portfolio, None) if portfolio else (userstore.portfolio_ids("all", include_archived=True)
                                                              if all_ else None)
    text = userstore.export_transactions_csv(sel)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        typer.echo(f"Wrote {out}.")
    else:
        typer.echo(text, nl=False)


@app.command()
def performance(names: list[str] = typer.Argument(None, help="Portfolio names (default: each of your real portfolios)"),
                tag: list[str] = typer.Option(None, "--tag", help="A tag group, pooled into one line (repeatable)"),
                start: str = typer.Option(None, help="Compare from this date (default: the latest first day)"),
                as_json: bool = typer.Option(False, "--json", help="As JSON")):
    """Portfolio returns in DKK against ACWI: time-weighted (the investments) and money-weighted (your timing),
    side by side from a common start. Virtual portfolios and tag groups only when named."""
    import json

    from . import performance as perf
    from . import profile, userstore

    universe.ensure_migrated()
    ids = _portfolio_ids(names, None) if names else [p["id"] for p in userstore.portfolios(include_archived=False)
                                                     if p["mode"] == "real" and p["n_tx"]]
    res = perf.compare(profile.Market.load(), ids, tag, start)
    if as_json:
        typer.echo(json.dumps(res, indent=1, default=str))
        return
    pct = lambda v: f"{v:+.1%}" if v is not None else "–"  # noqa: E731
    typer.echo(f"From {res['start']} to {res['asof']} (DKK; ACWI given the same cash flows)")
    typer.echo(f"{'':<22}{'value':>12} {'TWR':>8} {'p.a.':>8} {'MWR p.a.':>9} {'ACWI':>8} {'vs ACWI':>8} {'max DD':>8}")
    for r in res["rows"]:
        st = r["stats"] or {}
        v = f"{st['value_dkk']:,.0f}" if st.get("value_dkk") is not None else "–"
        typer.echo(f"{r['label'][:21]:<22}{v:>12} {pct(st.get('twr_total')):>8} {pct(st.get('twr_ann')):>8} "
                   f"{pct(st.get('mwr_ann')):>9} {pct(st.get('acwi_twr_total')):>8} {pct(st.get('excess_twr')):>8} "
                   f"{pct(st.get('max_drawdown')):>8}")
        if st.get("start") and st["start"] != res["start"]:
            typer.echo(f"    · from {st['start']}")
        for n in r["notes"] + r["missing"]:
            typer.echo(f"    · {n}")


def _portfolio_ids(names: list[str] | None, tags: list[str] | None) -> list[int]:
    """Portfolio names (and tags) as ids; an unknown name stops the command."""
    from . import userstore

    ids = []
    for n in names or []:
        p = userstore.portfolio_by_name(n)
        if not p:
            raise typer.Exit(f"No portfolio called {n!r}: see `radar portfolios list`.")
        ids.append(p["id"])
    return userstore.portfolio_ids(ids=ids, tags=tags) if (ids or tags) else []


def _one_portfolio(name: str) -> dict:
    from . import userstore

    p = userstore.portfolio_by_name(name)
    if not p:
        raise typer.Exit(f"No portfolio called {name!r}: see `radar portfolios list`.")
    return p


portfolios_app = typer.Typer(help="Your portfolios: real ones (your accounts) and virtual ones (simulations, A/B "
                                  "tests), with tags. Only real ones count as yours unless chosen.")
app.add_typer(portfolios_app, name="portfolios")


@portfolios_app.command("list")
def portfolios_list(as_json: bool = typer.Option(False, "--json", help="As JSON (for the skills)"),
                    archived: bool = typer.Option(False, "--archived", help="Archived ones too")):
    """Every portfolio: mode, tax kind, tags and how many rows it has."""
    import json

    from . import userstore

    universe.ensure_migrated()
    rows = userstore.portfolios(include_archived=archived)
    if as_json:
        typer.echo(json.dumps(rows, indent=1, ensure_ascii=False))
        return
    for p in rows:
        flags = "".join([" (default)" if p["is_default"] else "", " (archived)" if p["archived"] else ""])
        tags = f"  #{' #'.join(p['tags'])}" if p["tags"] else ""
        typer.echo(f"{p['name']:<20} {p['mode']:<8} {p['kind']:<12} {p['n_tx']:>5} rows{flags}{tags}")


@portfolios_app.command("add")
def portfolios_add(name: str, virtual: bool = typer.Option(False, "--virtual", help="A simulation / test, not yours"),
                   kind: str = typer.Option("other", help="Tax kind: ask | frie_midler | pension | other"),
                   tag: list[str] = typer.Option(None, "--tag", help="A tag (repeatable)"),
                   note: str = typer.Option(None)):
    """Add a portfolio."""
    from . import userstore

    if kind not in userstore.PORTFOLIO_KINDS:
        raise typer.Exit(f"kind must be one of {', '.join(userstore.PORTFOLIO_KINDS)}")
    try:
        userstore.save_portfolio({"name": name, "mode": "virtual" if virtual else "real", "kind": kind,
                                  "note": note, "tags": tag or []})
    except ValueError as e:
        raise typer.Exit(f"Not added: {e}.")
    typer.echo(f"Added {name} ({'virtual' if virtual else 'real'}, {kind}).")


@portfolios_app.command("edit")
def portfolios_edit(name: str, rename: str = typer.Option(None, help="New name"),
                    kind: str = typer.Option(None, help="ask | frie_midler | pension | other"),
                    dividends: str = typer.Option(None, help="reinvested | cash"),
                    note: str = typer.Option(None)):
    """Rename a portfolio or change its tax kind, dividend policy or note."""
    from . import userstore

    p = _one_portfolio(name)
    change = {k: v for k, v in {"name": rename, "kind": kind, "dividends": dividends, "note": note}.items() if v}
    if kind and kind not in userstore.PORTFOLIO_KINDS:
        raise typer.Exit(f"kind must be one of {', '.join(userstore.PORTFOLIO_KINDS)}")
    if dividends and dividends not in userstore.DIVIDEND_POLICIES:
        raise typer.Exit(f"dividends must be one of {', '.join(userstore.DIVIDEND_POLICIES)}")
    try:
        userstore.save_portfolio(change, p["id"])
    except ValueError as e:
        raise typer.Exit(f"Not changed: {e}.")
    typer.echo(f"Updated {rename or name}.")


@portfolios_app.command("tag")
def portfolios_tag(name: str, tags: list[str]):
    """Add tags to a portfolio."""
    from . import userstore

    p = _one_portfolio(name)
    typer.echo(f"{name}: #{' #'.join(userstore.set_tags(p['id'], [*p['tags'], *tags]))}")


@portfolios_app.command("untag")
def portfolios_untag(name: str, tags: list[str]):
    """Remove tags from a portfolio."""
    from . import userstore

    p = _one_portfolio(name)
    drop = {userstore.norm_tag(t) for t in tags}
    left = userstore.set_tags(p["id"], [t for t in p["tags"] if t not in drop])
    typer.echo(f"{name}: " + (f"#{' #'.join(left)}" if left else "no tags"))


@portfolios_app.command("default")
def portfolios_default(name: str):
    """Make a real portfolio the one new trades and imports go into."""
    from . import userstore

    try:
        userstore.set_default_portfolio(_one_portfolio(name)["id"])
    except ValueError as e:
        raise typer.Exit(str(e))
    typer.echo(f"{name} is now the default portfolio.")


@portfolios_app.command("move")
def portfolios_move(name: str, to: str = typer.Option(..., "--to", help="The portfolio to move to"),
                    symbol: list[str] = typer.Option(None, "--symbol", help="Only this ticker (repeatable)")):
    """Move trades to another portfolio (e.g. from Main to ASK). Refused if a sale would lose its buy."""
    from . import portfolio, userstore

    src, dst = _one_portfolio(name), _one_portfolio(to)
    symbols = [s.strip().upper() for s in symbol] if symbol else None
    problems = portfolio.check_move(src["id"], dst["id"], None, symbols)
    if problems:
        raise typer.Exit("Not moved: " + "; ".join(problems[:5]))
    typer.echo(f"Moved {userstore.move_transactions(src['id'], dst['id'], None, symbols)} rows to {to}.")


@portfolios_app.command("fork")
def portfolios_fork(name: str, new_name: str, date: str = typer.Option(..., "--date", help="Copy it as it stood at this day's close"),
                    cash: float = typer.Option(0.0, "--cash", help="Extra cash (DKK) to put in the copy"),
                    tag: list[str] = typer.Option(None, "--tag", help="A tag for the copy (repeatable)")):
    """A virtual copy of a portfolio at a day's close, to A/B-test changes against the original from there on."""
    from . import profile, simulate

    try:
        simulate.fork(_one_portfolio(name)["id"], new_name, date, profile.Market.load(), cash, tag or [])
    except ValueError as e:
        raise typer.Exit(f"Not forked: {e}")
    typer.echo(f"Forked {name} into {new_name} (virtual). Compare: radar performance {name!r} {new_name!r} --start {date}")


@portfolios_app.command("archive")
def portfolios_archive(name: str, undo: bool = typer.Option(False, "--undo", help="Bring it back")):
    """Archive a portfolio: it keeps its rows but no longer counts as yours by default."""
    from . import userstore

    userstore.save_portfolio({"archived": not undo}, _one_portfolio(name)["id"])
    typer.echo(f"{name} {'is back' if undo else 'is archived'}.")


@portfolios_app.command("delete")
def portfolios_delete(name: str, yes: bool = typer.Option(False, "--yes", help="Don't ask")):
    """Delete a virtual portfolio with its rows (a backup is taken first), or an empty real one."""
    from . import userstore

    p = _one_portfolio(name)
    if p["n_tx"] and not yes:
        typer.confirm(f"Delete {name} and its {p['n_tx']} rows?", abort=True)
    try:
        userstore.delete_portfolio(p["id"])
    except ValueError as e:
        raise typer.Exit(str(e))
    typer.echo(f"Deleted {name}.")


if __name__ == "__main__":
    app()
