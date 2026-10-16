from contextlib import contextmanager

import typer

from . import universe

app = typer.Typer(add_completion=False, help="Market radar: rotation, momentum, regime and holdings signals.")

FREE = {"setup", "paths", "serve", "doctor", "openapi", "ticker"}     # run before a data folder is chosen


def _version(value: bool) -> None:
    if value:
        from .home import app_version

        typer.echo(f"Market Radar {app_version()}")
        raise typer.Exit()


@app.callback()
def _root(ctx: typer.Context,
          home: str = typer.Option(None, "--home", help="Use this data folder instead of the one this computer "
                                   "remembers (see `radar paths`)"),
          version: bool = typer.Option(False, "--version", is_eager=True, callback=_version,
                                       help="Show the version and exit")):
    """Every command but the FREE ones needs a usable data folder: set up, present, and not from a newer version."""
    from pathlib import Path

    from . import home as homes
    from . import paths

    if home:
        paths.configure(paths.Locations.at(Path(home)), source="option")
    if ctx.invoked_subcommand in FREE:
        return
    st = homes.status()
    if st["state"] == "unset":
        typer.echo("Market Radar has no data folder yet. Start the app (it shows a setup screen) or run: "
                   "uv run radar setup")
        raise typer.Exit(1)
    if st["state"] == "missing":
        typer.echo(f"Your data folder {st['home']} can't be found. If you moved it: uv run radar setup --use NEW_PATH")
        raise typer.Exit(1)
    if st["state"] == "newer":
        typer.echo(st["read_only"])
        raise typer.Exit(1)
    _first_use_of_version()


def _first_use_of_version() -> None:
    """A new app version's first use of the data: back it up, then record the version."""
    from . import backup, paths
    from . import home as homes

    if backup.before_upgrade():
        typer.echo(f"First use of Market Radar {homes.app_version()} with this data: backed up first.")
    if backup.is_home():
        homes.upgrade(paths.locations().home)
        homes.touch(paths.locations().home)


@app.command()
def setup(from_: str = typer.Option(None, "--from", help="An old Market Radar folder to copy your data from"),
          to: str = typer.Option(None, "--to", help="Where your data folder goes (default: ~/Market Radar)"),
          fresh: bool = typer.Option(False, "--fresh", help="Start with an empty data folder"),
          use: str = typer.Option(None, "--use", help="An existing data folder to use (moved, or from another version)"),
          no_market_data: bool = typer.Option(False, "--no-market-data",
                                              help="Don't copy the downloaded market data (it is downloaded again)"),
          yes: bool = typer.Option(False, "--yes", help="Don't ask")):
    """Choose the data folder: copy your data from an old version's folder into it, start empty, or point to one
    you already have. The old folder is never changed (it gets a MOVED.txt); the copy is checked file by file."""
    from pathlib import Path

    from . import home as homes
    from . import paths

    if use:
        loc = homes.use(Path(use))
        typer.echo(f"Using {loc.home}.")
        return
    st = homes.status()
    if st["state"] == "ok" and st["source"] in ("pointer", "env") and not (from_ or fresh):
        typer.echo(f"Already set up: your data is in {st['home']} (`radar paths` lists everything).")
        return
    target = Path(to).expanduser() if to else paths.default_home()
    if fresh:
        loc = homes.create(target)
        typer.echo(f"Created {loc.home}.")
        return
    if not from_:
        found = [f for f in st["found"] if not f["moved"]] or st["found"]
        if not found:
            typer.echo("No data from an earlier version found next to this folder. Use --from OLD_FOLDER, or "
                       "--fresh to start empty.")
            raise typer.Exit(1)
        for i, f in enumerate(found, 1):
            typer.echo(f"{i}. {f['path']}: {_describe(f)}")
        pick = 1 if yes or len(found) == 1 else typer.prompt("Copy from which folder?", type=int, default=1)
        from_ = found[pick - 1]["path"]
    summary = homes.legacy_summary(Path(from_))
    if summary is None:
        typer.echo(f"No Market Radar data in {from_}.")
        raise typer.Exit(1)
    typer.echo(f"From {from_}: {_describe(summary)}\nTo   {target}")
    if not yes and not typer.confirm("Copy your data there? (the old folder isn't changed)", default=True):
        raise typer.Exit(1)
    rep = homes.migrate(Path(from_), target, copy_cache=not no_market_data, progress=typer.echo)
    n = sum(rep["files"].values())
    typer.echo(f"Done: {n} files copied and checked, {rep.get('tables', {}).get('transactions', 0)} transactions. "
               f"Your data is in {rep['home']}.")


@app.command(name="backup")
def backup_now(reason: str = typer.Option("manual", help="A word or two saved in the file name"),
               mirror: str = typer.Option(None, "--mirror", help="Also copy every backup to this folder (a cloud-sync "
                                          "folder or a USB disk); 'off' stops it")):
    """Back up your data now: radar.db, your folders and the history (not the market data, which can be
    downloaded again). Backups are also taken by themselves once a day and before a new version first runs."""
    from pathlib import Path

    from . import backup

    if mirror:
        m = backup.set_mirror(None if mirror == "off" else Path(mirror))
        typer.echo(f"Second backup folder: {m or 'none'}")
    f = backup.create(reason)
    typer.echo(f"Wrote {f} ({f.stat().st_size // 1024} KB)" + (f"; copy in {backup.mirror()}" if backup.mirror() else ""))


@app.command()
def backups():
    """The backups in your data folder (and in the second backup folder, if one is set)."""
    from . import backup

    for where in filter(None, (backup.folder(), backup.mirror())):
        rows = backup.listing(where)
        typer.echo(f"{where} ({len(rows)})")
        for r in rows:
            typer.echo(f"  {r['created'].replace('T', ' ')}  {r['kind']:<8} {r['size'] // 1024:>7} KB  {r['name']}")


@app.command()
def restore(file: str = typer.Argument(..., help="A backup zip (from `radar backups`)"),
            yes: bool = typer.Option(False, "--yes", help="Don't ask")):
    """Put a backup back. What is there now is backed up first, so a restore can itself be undone."""
    from pathlib import Path

    from . import backup

    meta = backup.verify(Path(file))
    typer.echo(f"{Path(file).name}: made {meta['created']} by Market Radar {meta['app_version']}, "
               f"{len(meta['files'])} files, {meta.get('tables', {}).get('transactions', 0)} transactions.")
    if not yes and not typer.confirm("Replace your data with this backup?", default=False):
        raise typer.Exit(1)
    res = backup.restore(Path(file))
    typer.echo(f"Restored. What was there before is in {res['saved_first']}.")


@app.command(name="updates")
def updates_cmd(on: bool = typer.Option(None, "--on/--off", help="Switch the daily check for a new version on or off")):
    """Is a newer Market Radar out? The check is off until you switch it on; then it asks GitHub at most once a day."""
    from . import updates

    if on is not None:
        updates.set_enabled(on)
    s = updates.status()
    if not s["enabled"]:
        typer.echo(f"Market Radar {s['current']}. The check for new versions is off (radar updates --on).")
    elif not s["repo"]:
        typer.echo("The check is on, but settings.yaml updates.repo names no repo to check.")
    elif s["newer"]:
        typer.echo(f"Market Radar {s['latest']} is out (you have {s['current']}): {s['url']}")
    else:
        typer.echo(f"Market Radar {s['current']} is the newest" + (f" ({s['error']})" if s["error"] else "") + ".")


def _describe(f: dict) -> str:
    c = f.get("counts", {})
    bits = [f"{c['transactions']} transactions" if "transactions" in c else None,
            f"{c['portfolios']} portfolios" if "portfolios" in c else None,
            *(f"{n} {k}" for k, n in f["personal"].items() if n),
            f"{f['history_files']} history files" if f["history_files"] else None,
            f"last change {f['newest']}" if f["newest"] else None, "already moved" if f["moved"] else None]
    return ", ".join(b for b in bits if b)


@app.command()
def paths(as_json: bool = typer.Option(False, "--json", help="As JSON (for the skills)")):
    """Where your data, the history and the market-data cache are, and how the app found them."""
    import json

    from . import home as homes
    from . import paths as p

    st = homes.status()
    out = {k: st[k] for k in ("state", "source", "app_version", "home", "cache", "pointer", "read_only", "warning")}
    if st["state"] != "unset":
        loc = p.locations()
        out["folders"] = {"data": str(loc.home), "database": str(loc.userdata / homes.DB_NAME),
                          "notes": str(loc.home / "notes"), "briefs": str(loc.home / "briefs"),
                          "research": str(loc.home / "research"), "journal": str(loc.home / "journal"),
                          "exports": str(loc.home / "exports"), "imports": str(loc.imports),
                          "history": str(loc.history), "backups": str(loc.userdata / "backups"),
                          "cache": str(loc.cache), "reports": str(loc.reports)}
    else:
        out["found"] = st["found"]
    if as_json:
        typer.echo(json.dumps(out, indent=1, ensure_ascii=False))
        return
    typer.echo(f"Market Radar {out['app_version']}: {out['state']} (found via {out['source']})")
    for k, v in out.get("folders", {}).items():
        typer.echo(f"  {k:<9} {v}")
    for f in out.get("found", []):
        typer.echo(f"  old data: {f['path']}: {_describe(f)}")
    for k in ("read_only", "warning"):
        if out[k]:
            typer.echo(f"  ! {out[k]}")


@contextmanager
def _job(kind: str):
    """Record a CLI run in the operations log (ops.db in the cache) like the app's jobs; yields its log function.
    An update or scan that is already running elsewhere ends the command with its message and exit code 1."""
    from datetime import datetime

    from . import locks, ops

    lines: list[str] = []

    def log(line: str) -> None:
        typer.echo(line)
        lines.append(f"{datetime.now():%H:%M:%S} {line}")
    try:
        with ops.job(kind, lines):
            yield log
    except locks.Busy as e:
        typer.echo(f"Not started: {e}.", err=True)
        raise typer.Exit(1) from None


@app.command()
def update(refresh_constituents: bool = typer.Option(False, help="Re-fetch the S&P 500 constituent list")):
    """Download new prices (incremental) and macro series. Each source is logged in sources.json (in the cache folder)."""
    from . import updater

    with _job("cli_update") as log:
        updater.update(log, refresh_constituents)


@app.command(name="report")
def build_report():
    """Build reports/dashboard.json (the web app's data) and reports/summary.json from the data already
    downloaded. Refused while another build runs (in the app or a terminal)."""
    from . import updater

    with _job("cli_report") as log:
        res = updater.build_report(log, wait=0)
    typer.echo(f"{res['dashboard']} – view it with `uv run radar serve --open`")


@app.command()
def run(refresh_constituents: bool = False):
    """update + report."""
    from . import updater

    from . import backup

    with _job("cli_run") as log:
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
    from .discovery import scan

    def progress(done: int, total: int) -> None:
        typer.echo(f"  … {done} of {total}")

    with _job("cli_discover") as log:
        scan.run(log, progress, refresh_universe)


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


@app.command(name="ops")
def ops_summary(days: int = typer.Option(7, help="Look back this many days"),
                errors: bool = typer.Option(False, "--errors", help="Also list the latest error events")):
    """External requests per host and source (count, errors, 429s, latency), paused hosts and the last jobs, from
    the operations log (ops.db in the cache folder)."""
    from . import net, ops

    s = ops.summary(days, net.limits)
    lu = s["last_update"]
    typer.echo(f"Last {days} days. Requests in 24 h: {s['requests_24h']:,} ({s['errors_24h']:,} failed); "
               f"error events in 24 h: {s['error_events_24h']}.")
    typer.echo("Last update: " + (f"{lu['status']} ({lu['kind']}, started {lu['started'][:16].replace('T', ' ')})"
                                  if lu else "none recorded"))
    for c in s["cooldowns"]:
        typer.echo(f"PAUSED {c['host']} until {c['until'][:16].replace('T', ' ')}: {c['reason']}")
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
            typer.echo(f"{e['ts'][:16].replace('T', ' ')} [{e['kind']}] {e['source'] or '–'}: {e['message'][:120]}")


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


@app.command(name="bundle-holdings")
def bundle_holdings(out: str = typer.Option(None, "--out", help="Write the bundle to this file instead of printing it"),
                    include_virtual: bool = typer.Option(False, "--include-virtual",
                                                         help="Pack virtual portfolios too (left out by default)")):
    """Pack your portfolios (real ones: stored transactions, kinds and tags), watchlists, market views and regime
    vote choices into one base64 text, to carry them to another machine (`unbundle-holdings` there). It holds
    your holdings: keep it private. (`radar export` writes the same, plus your documents, as a readable zip.)

    Usage: uv run radar bundle-holdings --out my-radar.bundle
    """
    import base64
    import io
    import zipfile

    from . import export

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        export.holdings_zip(z, include_virtual)
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    if not out:
        typer.echo(data)
        return
    from pathlib import Path

    Path(out).write_text(data, encoding="ascii")     # written by Python, so no shell can add a BOM or re-encode it
    typer.echo(f"Wrote {out}. It holds your holdings: keep it private.")


@app.command(name="unbundle-holdings")
def unbundle_holdings(file: str = typer.Option(None, "--file", help="Read the bundle from this file "
                                               "(default: the HOLDINGS_BUNDLE environment variable)")):
    """Restore what `bundle-holdings` packed: portfolios and their transactions, watchlists, market views and vote
    choices. Each portfolio in the bundle gets exactly its rows; a backup of the database is taken first."""
    import base64
    import io
    import os
    import re
    import zipfile
    from pathlib import Path

    from . import export

    raw = Path(file).read_text(encoding="utf-8-sig") if file else os.environ.get("HOLDINGS_BUNDLE", "")
    # keep only base64 characters: tolerates BOMs/CRLF/whitespace added by shells or editors
    data = re.sub(r"[^A-Za-z0-9+/=]", "", raw)
    if not data:
        typer.echo("No bundle: pass --file, or set HOLDINGS_BUNDLE.")
        return
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(data))) as z:
        r = export.restore_holdings(z)
    what = (f"{r['transactions']} transactions in {r['portfolios'] or 'their'} portfolios" if not r["legacy_files"]
            else ", ".join(r["legacy_files"]))
    typer.echo(f"Restored {what}, {r['watchlist']} watchlist edits and {r['views']} market views.")


@app.command(name="export")
def export_data(out: str = typer.Option(None, "--out", help="The zip to write (default: exports/ in your data folder)")):
    """Your data in open formats (CSV, JSON, Markdown), readable without Market Radar: every portfolio and
    transaction, market views, watchlist, and your notes, briefs, research and journal. EXPORT.md inside says
    what each file and column holds. It holds your holdings: keep it private."""
    from pathlib import Path

    from . import export

    f = export.write(Path(out) if out else None)
    typer.echo(f"Wrote {f} ({f.stat().st_size // 1024} KB). It holds your holdings: keep it private.")


@app.command(name="import-export")
def import_export(file: str = typer.Argument(..., help="A zip written by `radar export`"),
                  yes: bool = typer.Option(False, "--yes", help="Don't ask")):
    """Read an export back (another computer, a reinstall). The portfolios in it get exactly its rows; documents
    that aren't here yet are added, ones that are here are left alone. radar.db is backed up first."""
    from pathlib import Path

    from . import export

    pv = export.preview(Path(file))
    typer.echo(f"{file}: {pv['portfolios']} portfolios, {pv['transactions']} transactions, {len(pv['documents'])} "
               f"documents ({len(pv['new_documents'])} new here)" + (f", made {pv['meta']['created']}" if pv["meta"] else ""))
    if not yes and not typer.confirm("Load it? The portfolios it names are replaced by its rows.", default=False):
        raise typer.Exit(1)
    r = export.load(Path(file))
    typer.echo(f"Loaded {r['transactions']} transactions in {r['portfolios']} portfolios, {r['views']} market views, "
               f"{r['documents_added']} documents ({r['documents_kept']} already here, left as they were).")


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


sim_app = typer.Typer(help="Simulations on your own trades, into virtual portfolios (never yours).", no_args_is_help=True)
app.add_typer(sim_app, name="sim")


@sim_app.command("exits")
def sim_exits(names: list[str] = typer.Argument(None, help="Real portfolios to replay (default: each of yours with trades)"),
              variant: str = typer.Option("both", help="overlay (your trades + the rule's exits), rules (your buys, "
                                                       "the rule's exits only) or both"),
              start: str = typer.Option(None, help="Start from what the portfolio held at this day's close"),
              end: str = typer.Option(None, help="Stop at this day (default: the latest prices)"),
              fill: str = typer.Option(None, help="next | same: when a triggered exit sells (default: settings)"),
              rule_spec: str = typer.Option(None, "--rule-spec", help="A variant of the rule from `radar study exits` "
                                                                      "(e.g. k5, sma200), into its own portfolios"),
              as_json: bool = typer.Option(False, "--json", help="The full report as JSON"),
              out: str = typer.Option(None, "--out", help="Also write the JSON report here")):
    """Your real trades replayed with the radar's stop-loss / take-profit rule followed, using only what was known
    each day. Writes one simulated portfolio per real portfolio and variant (tags exits-overlay / exits-rules, so
    the Returns page can show them) and reports.json/sim-exits.json with every exit and what it saved or cost."""
    import json
    from pathlib import Path

    from . import profile, userstore
    from .backtest import exits

    universe.ensure_migrated()
    variants = exits.VARIANTS if variant == "both" else (variant,)
    if any(v not in exits.VARIANTS for v in variants):
        raise typer.Exit("--variant must be overlay, rules or both")
    ids = _portfolio_ids(names, None) if names else [p["id"] for p in userstore.portfolios(include_archived=False)
                                                     if p["mode"] == "real" and p["n_tx"]]
    with _job("sim") as log:
        market = profile.Market.load()
        need = universe.history_start()
        have = market.closes[universe.benchmark()].dropna().index[0].date()
        if have > need:
            log(f"Note: prices start {have}, your trades need them from {need}: run `radar update` to fetch the "
                "deeper history (early decisions lack the 200-day average and momentum until then).")
        try:
            spec = None
            if rule_spec:
                from .backtest import study

                spec = next((x for x in study._exit_variants() if x.key == rule_spec), None)
                if spec is None:
                    raise ValueError(f"no rule variant {rule_spec} (known: {', '.join(x.key for x in study._exit_variants())})")
            rep = exits.refresh(ids, market, variants, start, end, fill, spec=spec)
        except ValueError as e:
            raise typer.Exit(f"Not simulated: {e}")
    if out:
        Path(out).write_text(json.dumps(rep, indent=1, default=exits._json), encoding="utf-8")
    if as_json:
        typer.echo(json.dumps(rep, indent=1, default=exits._json))
        return
    pct = lambda v: f"{v:+.1%}" if v is not None else "–"  # noqa: E731
    dkk = lambda v: f"{v:+,.0f}" if v is not None else "–"  # noqa: E731
    for p in rep["portfolios"]:
        typer.echo(f"\n{p['name']}: from {p['start']} to {rep['asof']} (DKK)")
        typer.echo(f"  {'':<34}{'value':>12} {'TWR':>8} {'vs ACWI':>8} {'max DD':>8}")
        for r in p["compare"]["rows"]:
            st = r["stats"] or {}
            v = f"{st['value_dkk']:,.0f}" if st.get("value_dkk") is not None else "–"
            typer.echo(f"  {r['label'][:33]:<34}{v:>12} {pct(st.get('twr_total')):>8} {pct(st.get('excess_twr')):>8} "
                       f"{pct(st.get('max_drawdown')):>8}")
        for v, res in p["variants"].items():
            s = res["summary"]
            typer.echo(f"\n  {v}: {s['stops']} stop exits, {s['take_profits']} take-profit exits; saved vs holding on "
                       f"(parked in {res['park']}): {dkk(s['at_end']['saved_dkk'])} DKK to the end, "
                       f"{dkk(s['at_your_sale']['saved_dkk'])} DKK to your next sale ({s['at_end']['helped']} of "
                       f"{s['at_end']['exits']} exits helped to the end)")
            for e in res["exits"]:
                a = e["after"]
                k = f"k {e['k']:.2f}" if e.get("k") is not None else "      "
                typer.echo(f"    {e['trigger_date']} {e['symbol']:<10} {e.get('stop_kind', e['trigger']).replace('_', '-'):<11} {k}  "
                           f"sold {e['fill_date']} at {e['fill_price']:.2f}  {e['proceeds_dkk']:>10,.0f} DKK  "
                           f"saved {dkk(a['end']['saved_dkk'])} (end)"
                           + (f", {dkk(a['your_sale']['saved_dkk'])} (your sale {a['your_sale']['date']})" if "your_sale" in a else ""))
            if s["events"]:
                typer.echo("    · " + ", ".join(f"{k}: {n}" for k, n in s["events"].items()))
            if s["no_rule"]:
                typer.echo(f"    · no rule (funds outside the sector/theme groups, held as in the real portfolio): {', '.join(s['no_rule'])}")
            c = s["counts"] or {}
            if c.get("rule_days"):
                miss = ", ".join(f"{k} {n / c['rule_days']:.0%}" for k, n in c["missing"].items())
                typer.echo(f"    · {c['rule_days']} position-days checked; inputs missing (no k adjustment): {miss or 'none'}")
    sims = sorted({res['portfolio_id'] for p in rep["portfolios"] for res in p["variants"].values()})
    if rep["portfolios"]:
        ids_q = ",".join(str(i) for i in [*(p["id"] for p in rep["portfolios"]), *sims])
        typer.echo(f"\nReturns page: /returns?pf={ids_q}&from={rep['portfolios'][0]['start']}  "
                   f"(or radar performance --tag exits-overlay --tag exits-rules)")
    typer.echo("Report: reports/sim-exits.json")


def _pct(v, signed: bool = True) -> str:
    return "–" if v is None else (f"{v:+.1%}" if signed else f"{v:.0%}")


def _num(v, fmt: str = "+.2f") -> str:
    return "–" if v is None else format(v, fmt)


def _picks_meta(n, max_per_sector, max_per_group, trend, weighting, basis) -> dict:
    return {"n": n, "max_per_sector": max_per_sector, "max_per_group": max_per_group, "trend": trend,
            "weighting": weighting, "basis": basis}


@sim_app.command("picks-candidates")
def sim_picks_candidates(asof: str = typer.Option(..., "--asof", help="1M, 3M, 6M, 1Y (back from the latest prices), "
                                                                      "today, or a date"),
                         top: int = typer.Option(None, "--top", help="Only the best N by score"),
                         blind: bool = typer.Option(False, "--blind", help="Hide tickers and names (ids C001… by rank)"),
                         views: bool = typer.Option(False, "--views", help="Add your market views created by then "
                                                                           "(personal)"),
                         model_cutoff: str = typer.Option(None, "--model-cutoff", help="The picker's knowledge cutoff "
                                                                                       "(YYYY-MM), to flag hindsight"),
                         fund: bool = typer.Option(False, "--fund", help="Add K+V, kvalitet and værdi as known on the "
                                                                         "day (US stocks, SEC EDGAR)"),
                         as_json: bool = typer.Option(False, "--json", help="Machine-readable output (for the skills)"),
                         out: str = typer.Option(None, "--out", help="Also write the JSON here")):
    """The stock universe ranked by momentum score as the radar saw it on a past day: only data up to that day
    (sectors are today's). For picking a hindsight basket (`radar sim picks`)."""
    import json
    from pathlib import Path

    from . import profile
    from .backtest import picks

    try:
        rep = picks.candidates(profile.Market.load(), asof, blind, views, top, model_cutoff, fund=fund)
    except ValueError as e:
        raise typer.Exit(str(e))
    text = json.dumps(rep, indent=1, ensure_ascii=False, default=str)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
    if as_json:
        typer.echo(text)
        return
    typer.echo(f"Ranked on {rep['asof']} ({rep['ranked']} of {rep['universe']} with a score); buy at {rep['fill'] or '–'}")
    if rep["note"]:
        typer.echo(rep["note"])
    typer.echo(f"{'rank':>4}  {'':<10} {'score':>5} {'3m':>7} {'6m':>7} {'12-1':>7}  {'trend':<5} {'group':<7} sector")
    for r in rep["candidates"][: top or 40]:
        trend = "yes" if r["trend_ok"] else "no" if r["trend_ok"] is False else "–"
        typer.echo(f"{_num(r['rank'], '.0f'):>4}  {(r['ticker'] or r['id']):<10} {_num(r['score'], '.0f'):>5} "
                   f"{_pct(r['r3m']):>7} {_pct(r['r6m']):>7} {_pct(r['r12_1']):>7}  "
                   f"{trend:<5} {r['group'] or '':<7} {r['sector'] or ''}")


@sim_app.command("picks")
def sim_picks(asof: str = typer.Option(None, "--asof", help="1M, 3M, 6M, 1Y, today, or a date"),
              name: str = typer.Option(None, "--name", help="The basket's name (its portfolios are '<name> · hold' etc.)"),
              picks_file: str = typer.Option(None, "--picks", help="JSON: a list (or {picks: […], meta: {…}}) of "
                                                                   "{ticker or id, weight?, why?}"),
              rule: str = typer.Option(None, "--rule", help="top-n: the score's own top N instead of a picks file"),
              n: int = typer.Option(15, "--n", help="Names in a top-n basket (and in the control)"),
              max_per_sector: int = typer.Option(None, "--max-per-sector"),
              max_per_group: int = typer.Option(None, "--max-per-group", help="At most this many per region group"),
              trend: bool = typer.Option(False, "--trend", help="Only names in an uptrend (top-n)"),
              weighting: str = typer.Option("equal", "--weighting", help="equal | score (top-n)"),
              capital: float = typer.Option(100_000.0, "--capital", help="DKK"),
              end: str = typer.Option(None, "--end", help="Stop at this day (default: the latest prices)"),
              model_cutoff: str = typer.Option(None, "--model-cutoff", help="The picker's knowledge cutoff (YYYY-MM)"),
              tag: list[str] = typer.Option(None, "--tag", help="Extra tags (e.g. picks-live)"),
              rerun: str = typer.Option(None, "--rerun", help="Run stored baskets again on the latest prices: a "
                                                              "basket's name, or tag:<tag>"),
              as_json: bool = typer.Option(False, "--json", help="The report as JSON")):
    """A basket picked on a past day, simulated from there: kept, with the stop/take-profit rule followed, and the
    score's own top N as a control (virtual portfolios, on the Returns page with ACWI). Reports the equal-weight
    universe, the percentile among random baskets and that day's score check; writes
    reports/sim-picks/<name>.json."""
    import json
    from pathlib import Path

    from . import profile
    from .backtest import picks, study

    universe.ensure_migrated()
    with _job("sim") as log:
        market = profile.Market.load()
        p = study.panels(market)
        try:
            if rerun:
                hs = picks.baskets(rerun[4:]) if rerun.startswith("tag:") else \
                    [h for h in picks.baskets() if h["name"] == f"{rerun} · hold"]
                if not hs:
                    raise ValueError(f"no stored basket {rerun}")
                reps = [picks.rerun(market, h, p) for h in hs]
            else:
                if not (asof and name):
                    raise ValueError("give --asof and --name (or --rerun)")
                meta = _picks_meta(n, max_per_sector, max_per_group, trend, weighting, "score")
                if rule:
                    if rule != "top-n":
                        raise ValueError("--rule must be top-n")
                    chosen = None
                elif picks_file:
                    data = json.loads(Path(picks_file).read_text(encoding="utf-8"))
                    chosen = data["picks"] if isinstance(data, dict) else data
                    given = (data.get("meta") or {}) if isinstance(data, dict) else {}
                    meta = _picks_meta(len(chosen), max_per_sector, max_per_group, trend, "equal", "judgment") | given
                else:
                    raise ValueError("give --picks FILE or --rule top-n")
                reps = [picks.run(market, asof, chosen, name, capital, meta, end, model_cutoff, tag or (), p=p)]
        except (ValueError, KeyError) as e:
            raise typer.Exit(f"Not simulated: {e}")
        for r in reps:
            log(f"{r['name']}: picked {r['asof']}, bought {r['fill']}, to {r['end']}")
    if as_json:
        typer.echo(json.dumps(reps[0] if len(reps) == 1 else reps, indent=1, ensure_ascii=False, default=study._json))
        return
    for r in reps:
        y = r["yardsticks"]
        typer.echo(f"\n{r['name']}: picked on {r['asof']}, bought {r['fill']}, to {r['end']} ({r['sessions']} sessions, DKK)")
        for kind, pf in r["portfolios"].items():
            st = pf["stats"] or {}
            typer.echo(f"  {kind:<8} {pf['name'][:40]:<41} {_pct(pf['return_dkk']):>8}  vs ACWI {_pct(pf['excess_dkk']):>8}"
                       f"  max DD {_pct(st.get('max_drawdown')):>7}")
        typer.echo(f"  ACWI {_pct(y['acwi_dkk'])}, equal-weight universe {_pct(y['universe_ew_dkk'])}; "
                   f"basket before fees {_pct(y['basket_gross_dkk'])}")
        rnd = y["random"]
        if rnd.get("percentile") is not None:
            typer.echo(f"  Among {rnd['draws']} random baskets of the same size and caps: percentile {rnd['percentile']:.0f} "
                       f"(median {_pct(rnd['median'])}, 10–90 % {_pct(rnd['p10'])} to {_pct(rnd['p90'])})")
        sc = r["score_check"]
        if sc:
            typer.echo(f"  Score check that day ({sc['n']} names): IC {_num(sc['ic'])}, quintile excess "
                       + " ".join(_pct(q) for q in sc["q"]) + f"; the score's own top {len(r['picks'])} (no caps) beat the "
                       f"average stock {_pct(sc['top_hit'], False)} of the time")
        s = r["exits"]["summary"]
        typer.echo(f"  Rule: {s['stops']} stop and {s['take_profits']} take-profit exits")
        if r["same_as_control"]:
            typer.echo("  (the basket is the score's own top N, so it is its own control)")
        typer.echo(f"  Returns page: {r['returns_link']}")
    typer.echo("\nOne basket over one period is an illustration, not evidence: `radar study score` tests the score "
               "across every month.")


study_app = typer.Typer(help="Tests of the radar's signals on past data (analysis, not advice).", no_args_is_help=True)
app.add_typer(study_app, name="study")


@study_app.command("score")
def study_score(horizons: str = typer.Option("1,3,6,12", help="Forward horizons in months (from 1, 3, 6, 12)"),
                variants: str = typer.Option("all", help="all, or a comma list of variant keys"),
                n: int = typer.Option(15, "--n", help="Size of the top-N basket per date"),
                exits_months: int = typer.Option(None, "--exits", help="Also test the stop/take-profit rule on each "
                                                                       "date's top N over this many months (slow)"),
                seasoned: bool = typer.Option(False, "--seasoned", help="Leave out names listed less than a year by then"),
                since: str = typer.Option(None, "--since", help="First formation date"),
                no_regime: bool = typer.Option(False, "--no-regime", help="Skip the split by regime (faster)"),
                signal: str = typer.Option("momentum", "--signal", help="momentum, or quality, value or qv (K+V): "
                                           "US stocks from SEC EDGAR, point in time"),
                as_json: bool = typer.Option(False, "--json", help="The full report as JSON"),
                out: str = typer.Option(None, "--out", help="Also write the JSON here")):
    """How well a score ranked stocks at every past month-end, on the returns that followed: rank correlation (IC)
    with Newey-West t, quintile spreads, the top N against the universe and ACWI, splits by year, regime, group and
    holdout, and variants tested fairly. The momentum score by default (reports/score-study.json); --signal
    quality|value|qv tests the kvalitetsscore, værdiscore or K+V on US stocks from SEC EDGAR
    (reports/score-study-<signal>.json)."""
    import json
    from pathlib import Path

    from . import profile
    from .backtest import study

    try:
        hs = tuple(int(x) for x in horizons.split(","))
        keys = None if variants == "all" else [v.strip() for v in variants.split(",") if v.strip()]
        with _job("study") as log:
            rep = study.run(profile.Market.load(), hs, keys, n, exits_months, seasoned, since, not no_regime, log,
                            signal=signal)
            study.write(rep)
    except ValueError as e:
        raise typer.Exit(f"Not studied: {e}")
    text = json.dumps(rep, indent=1, default=study._json)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
    if as_json:
        typer.echo(text)
        return
    u = rep["universe"]
    bk = next(v["key"] for v in rep["variants"] if v["baseline"])
    sig = study.SIGNALS[rep["signal"]]
    names = f"{u['fund_names']} US stocks with SEC EDGAR statements" if sig.fund else f"{u['tickers']} stocks"
    typer.echo(f"\n{sig.label}: {names}, formation dates {u['first']} to {u['last']}; holdout from "
               f"{rep['settings']['holdout_from']}; {rep['variants_tried']} variants tried against {bk}")
    labels = {v["key"]: v for v in rep["variants"]}
    for h, res in rep["results"].items():
        typer.echo(f"\n{h} month(s) ahead: excess over the equal-weight universe")
        typer.echo(f"  {'':<14}{'dates':>5} {'IC':>6} {'t':>6} {'IC>0':>5}  {'Q1':>7} {'Q3':>7} {'Q5':>7} {'Q5-Q1':>7} {'t':>6}"
                   f"  {'top N':>7} {'hit':>4}  {'holdout IC':>10}  verdict")
        for k, r in res.items():
            a, o = r["all"] or {}, r["holdout"] or {}
            q = a.get("q") or [None] * 5
            v = rep["verdicts"][h].get(k, {}).get("label", "baseline")
            pit = "" if labels[k]["pit"] else " (not point-in-time)"
            typer.echo(f"  {k:<14}{a.get('dates', 0):>5} {_num(a.get('ic_mean')):>6} {_num(a.get('ic_t'), '+.1f'):>6} "
                       f"{_pct(a.get('ic_pos'), False):>5}  {_pct(q[0]):>7} {_pct(q[2]):>7} {_pct(q[4]):>7} "
                       f"{_pct(a.get('spread')):>7} {_num(a.get('spread_t'), '+.1f'):>6}  {_pct(a.get('top_excess')):>7} "
                       f"{_pct(a.get('top_hit'), False):>4}  {_num(o.get('ic_mean')):>10}  {v}{pit}")
        base = res[bk]
        reg = {g: s for g, s in (base.get("by_regime") or {}).items() if s}
        if reg:
            typer.echo(f"  {bk} IC by regime on D: " + ", ".join(f"{g} {_num(s['ic_mean'])} ({s['dates']})" for g, s in reg.items()))
        grp = {g: s for g, s in (base.get("by_group") or {}).items() if s}
        if grp:
            typer.echo(f"  {bk} IC within each group: " + ", ".join(f"{g} {_num(s['ic_mean'])}" for g, s in grp.items()))
        a = base["all"] or {}
        if a.get("top_dkk") is not None:
            typer.echo(f"  top {n} in DKK: mean {_pct(a['top_dkk'])} against ACWI {_pct(a['acwi_dkk'])}, "
                       f"ahead on {_pct(a['top_beats_acwi'], False)} of dates")
    typer.echo(f"\nIC decay ({bk}): " + ", ".join(f"{h}m {_num(v)}" for h, v in rep["decay"][bk].items()))
    typer.echo(f"Top-quintile turnover per month ({bk}): {_pct(rep['turnover'][bk], False)}")
    mc = rep.get("momentum_corr")
    if mc and mc.get("mean") is not None:
        typer.echo(f"Rank correlation with the momentum score: {_num(mc['mean'])} on average over {mc['dates']} dates "
                   "(near 0 or below: the two pick different stocks)")
    e = rep.get("exits")
    if e and e.get("summary"):
        s = e["summary"]
        typer.echo(f"\nStop/take-profit rule on each date's top {e['n_top']}, {e['months']} months, fees {e['fee_bps']:g} bp:")
        typer.echo(f"  held: mean {_pct(s['hold']['mean'])} (ACWI {_pct(s['hold']['acwi_mean'])}), ahead of ACWI on "
                   f"{_pct(s['hold']['beats_acwi'], False)} of {s['both']['dates']} dates")
        for rule in ("both", "stop", "take_profit"):
            x = s[rule]
            typer.echo(f"  {rule:<12} vs held: mean {_pct(x['mean_diff'])} (t {_num(x['t'], '+.1f')}), helped on "
                       f"{_pct(x['helped'], False)} of dates, worst {_pct(x['worst'])}, best {_pct(x['best'])}, "
                       f"{_num(x['exits_mean'], '.1f')} exits per basket")
        if e.get("inputs_missing"):
            typer.echo("  inputs missing on rule days: " + ", ".join(f"{k} {v:.0%}" for k, v in e["inputs_missing"].items()))
    typer.echo("\nCaveats: " + " ".join(rep["caveats"][:2]))
    typer.echo(f"Report: reports/{sig.report}")


@study_app.command("exits")
def study_exits(horizons: str = typer.Option("3,6", help="Horizons in months (from 1, 3, 6, 12)"),
                n: int = typer.Option(15, "--n", help="Size of each month's top-N basket"),
                variants: str = typer.Option("all", help="all, or a comma list of variant keys"),
                since: str = typer.Option(None, "--since", help="First formation date"),
                no_reentry: bool = typer.Option(False, "--no-reentry", help="Skip the re-entry run of the best variant"),
                as_json: bool = typer.Option(False, "--json", help="The full report as JSON")):
    """Variants of the stop/take-profit rule on every month-end's top-N basket, against simply holding it: return
    and risk (max drawdown, volatility, worst 20 sessions, the 10 % worst outcome), in-sample and in the holdout,
    with a verdict per variant. Slow (10-20 minutes). Writes reports/exit-study.json."""
    import json

    from . import profile
    from .backtest import study

    try:
        hs = tuple(int(x) for x in horizons.split(","))
        keys = None if variants == "all" else [v.strip() for v in variants.split(",") if v.strip()]
        with _job("study") as log:
            rep = study.exit_variants(profile.Market.load(), n, hs, keys, since, not no_reentry, log)
            study.write_exits(rep)
    except ValueError as e:
        raise typer.Exit(f"Not studied: {e}")
    if as_json:
        typer.echo(json.dumps(rep, indent=1, default=study._json))
        return
    st = rep["settings"]
    typer.echo(f"\nEach month-end's top {st['n_top']} (equal weights, {st['fee_bps']:g} bp per trade), exits parked in "
               f"{st['park']}; holdout from {st['holdout_from']}. Pass: costs at most {st['cost_per_6m']:.0%} per 6 months, "
               f"cuts mean max drawdown by {st['dd_cut']:.0%} and lifts the 10 % worst outcome, in-sample and holdout.")
    labels = {v["key"]: v["label"] for v in rep["variants"]}
    for h, res in rep["results"].items():
        first = next(iter(res.values()))["all"] or {}
        hold = first.get("hold") or {}
        typer.echo(f"\n{h} months ({first.get('dates', 0)} dates). Held: return {_pct(hold.get('ret_mean'))}, worst 10 % "
                   f"{_pct(hold.get('ret_p10'))}, max DD {_pct(hold.get('dd_mean'))} (worst {_pct(hold.get('dd_worst'))})")
        typer.echo(f"  {'':<14}{'return':>8} {'vs held':>8} {'t':>5} {'helped':>6}  {'worst10%':>8} {'max DD':>7} "
                   f"{'worstDD':>8} {'exits':>5}  {'holdout vs held':>15}  verdict")
        for k, r in res.items():
            a, o = r["all"] or {}, r["holdout"] or {}
            v = r["verdict"]
            typer.echo(f"  {k:<14}{_pct(a.get('ret_mean')):>8} {_pct(a.get('diff_mean')):>8} {_num(a.get('diff_t'), '+.1f'):>5} "
                       f"{_pct(a.get('helped'), False):>6}  {_pct(a.get('ret_p10')):>8} {_pct(a.get('dd_mean')):>7} "
                       f"{_pct(a.get('dd_worst')):>8} {_num(a.get('exits_mean'), '.1f'):>5}  {_pct(o.get('diff_mean')):>15}  "
                       f"{v['label']}")
    typer.echo("\nVariants: " + "; ".join(f"{k} = {lab}" for k, lab in labels.items()))
    fails = {k: r["verdict"]["why"] for k, r in rep["results"][str(max(int(x) for x in rep["results"]))].items() if r["verdict"]["why"]}
    if fails:
        typer.echo("Why not (longest horizon): " + " | ".join(f"{k}: {w[0]}" for k, w in fails.items()))
    typer.echo("Report: reports/exit-study.json")


@study_app.command("redeploy")
def study_redeploy(horizons: str = typer.Option("6,12", help="Horizons in months (from 1, 3, 6, 12)"),
                   n: int = typer.Option(15, "--n", help="Size of each month's top-N basket"),
                   buffer: int = typer.Option(3, "--buffer", help="Rotation: sell a holding ranked outside buffer x N at month-end"),
                   cooldown: int = typer.Option(21, "--cooldown", help="Sessions before a sold name can be bought again"),
                   max_per_sector: int = typer.Option(None, "--max-per-sector", help="Caps on the basket and each new name"),
                   max_per_group: int = typer.Option(None, "--max-per-group", help="At most this many per region group"),
                   no_trend: bool = typer.Option(False, "--no-trend", help="Let a new name be bought without an uptrend"),
                   arms: str = typer.Option("all", help="all, or a comma list of arm keys"),
                   since: str = typer.Option(None, "--since", help="First formation date"),
                   as_json: bool = typer.Option(False, "--json", help="The full report as JSON"),
                   out: str = typer.Option(None, "--out", help="Also write the JSON here")):
    """The stop/take-profit rule with its money redeployed into the next momentum name instead of parked in ACWI,
    and a month-end rotation with and without the rule, on every month-end's top-N basket: return, risk and
    risk-adjusted return (Sharpe, Sortino, Calmar, information ratio), in-sample and holdout. Slow. Writes
    reports/redeploy-study.json."""
    import json
    from pathlib import Path

    from . import profile
    from .backtest import study

    try:
        hs = tuple(int(x) for x in horizons.split(","))
        keys = None if arms == "all" else [v.strip() for v in arms.split(",") if v.strip()]
        with _job("study") as log:
            rep = study.redeploy_study(profile.Market.load(), n, hs, buffer, cooldown, max_per_sector, max_per_group,
                                       not no_trend, since, keys, log)
            study.write_redeploy(rep)
    except ValueError as e:
        raise typer.Exit(f"Not studied: {e}")
    text = json.dumps(rep, indent=1, default=study._json)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
    if as_json:
        typer.echo(text)
        return
    st = rep["settings"]
    typer.echo(f"\nEach month-end's top {st['n_top']} (equal weights, {st['fee_bps']:g} bp per trade); redeploy buys the best "
               f"name not held{' in an uptrend' if st['trend'] else ''}, not sold in {st['cooldown']} sessions; rotation "
               f"sells outside the top {st['buffer']}xN. Sharpe over {st['rf'] or 'nothing (missing)'}; holdout from "
               f"{st['holdout_from']}.")
    for h, res in rep["results"].items():
        first = next(iter(res.values()))["all"] or {}
        hold = first.get("hold") or {}
        typer.echo(f"\n{h} months ({first.get('dates', 0)} dates). Held: return {_pct(hold.get('ret_mean'))}, Sharpe "
                   f"{_num(hold.get('sharpe_mean'))}, Sortino {_num(hold.get('sortino_mean'))}, max DD {_pct(hold.get('dd_mean'))}, "
                   f"IR {_num(hold.get('ir_mean'))}")
        typer.echo(f"  {'':<17}{'return':>8} {'vs held':>8} {'Sharpe':>7} {'Sortino':>7} {'Calmar':>7} {'max DD':>7} "
                   f"{'IR':>6} {'trades':>6} {'fees':>6}  {'Sharpe vs twin':>14} {'holdout':>8}  verdict")
        for k, r in res.items():
            a, o = r["all"] or {}, r["holdout"] or {}
            act, tw = r.get("activity") or {}, ((r.get("vs_twin") or {}).get("all") or {}).get("sharpe") or {}
            twin = f"{_num(tw.get('mean'))} t{_num(tw.get('t'), '+.1f')}" if tw else ""
            typer.echo(f"  {k:<17}{_pct(a.get('ret_mean')):>8} {_pct(a.get('diff_mean')):>8} {_num(a.get('sharpe_mean')):>7} "
                       f"{_num(a.get('sortino_mean')):>7} {_num(a.get('calmar_mean')):>7} {_pct(a.get('dd_mean')):>7} "
                       f"{_num(a.get('ir_mean')):>6} {_num(act.get('trades'), '.0f'):>6} {_pct(act.get('fees_pct')):>6}  "
                       f"{twin:>14} {_num(o.get('sharpe_mean')):>8}  {(r['verdict'] or {}).get('label', '')}")
    typer.echo("\nArms: " + "; ".join(f"{a['key']} = {a['label']}" for a in rep["arms"]))
    typer.echo("Caveat: " + rep["caveats"][0])
    typer.echo("Report: reports/redeploy-study.json")


fundamentals_app = typer.Typer(help="Financial statements: SEC EDGAR (US) and Yahoo (all tracked stocks).",
                               no_args_is_help=True)
app.add_typer(fundamentals_app, name="fundamentals")


@fundamentals_app.command("update")
def fundamentals_update(tickers: list[str] = typer.Argument(None, help="Only these tickers (default: those due)"),
                        source: str = typer.Option("all", help="edgar, yahoo or all"),
                        all_: bool = typer.Option(False, "--all", help="Every tracked stock, due or not (slow)")):
    """Fetch statements now: the companies that are due (a new report expected, or not fetched for a while), the
    tickers named, or with --all every one. `radar update` fetches the due ones each day."""
    from . import coverage, ops
    from .fundamentals import edgar, yahoo

    steps = {"fundamentals_edgar": ("SEC EDGAR", edgar.update_edgar),
             "fundamentals_yahoo": ("Yahoo", yahoo.update_yahoo)}
    if source != "all":
        steps = {k: v for k, v in steps.items() if k.endswith(source)}
        if not steps:
            raise typer.Exit("--source is edgar, yahoo or all")
    failed = False
    with _job("fundamentals") as log:
        for key, (label, fn) in steps.items():
            try:
                with ops.context(source=key):
                    msg = fn(force=all_, tickers=[t.upper() for t in tickers] if tickers else None)
                log(f"{label}: {msg}.")
                coverage.record(key, True, msg)
            except Exception as e:  # noqa: BLE001 (report it and go on to the other source)
                failed = True
                log(f"{label}: FAILED ({type(e).__name__}: {e})")
                coverage.record(key, False, error=f"{type(e).__name__}: {e}", exc=e)
    raise typer.Exit(1 if failed else 0)


def _fmt_value(v) -> str:
    if v is None:
        return "–"
    a = abs(v.value)
    s = f"{v.value / 1e9:,.2f} bn" if a >= 1e8 else f"{v.value / 1e6:,.1f} m" if a >= 1e5 else f"{v.value:,.2f}"
    return f"{s} {v.currency or ''}".strip()


@fundamentals_app.command("show")
def fundamentals_show(ticker: str, as_json: bool = typer.Option(False, "--json", help="As JSON")):
    """One ticker's statement items as they are read: the last twelve months of each flow (and how it was built),
    the latest balance, the fiscal years stored and the source's name for each value."""
    import json

    from . import fundamentals
    from .fundamentals import items, store

    t = ticker.upper()
    f = fundamentals.facts(t)
    if f.empty:
        raise typer.Exit(f"No statements stored for {t}: is it tracked? Fetch them with `radar fundamentals update {t}`.")
    rows = []
    for it in items.ITEMS:
        v = store.ttm(f, it.key) if it.flow else store.instant(f, it.key)
        rows.append({"item": it.key, "value": None if v is None else v.value,
                     "end": None if v is None else f"{v.end:%Y-%m-%d}", "basis": None if v is None else v.basis,
                     "tag": None if v is None else v.tag, "currency": None if v is None else v.currency,
                     "fiscal_years": len(store.annual(f, it.key)), "_v": v})
    src = f["source"].iloc[0]
    if as_json:
        out = {"ticker": t, "source": src, "latest_end": f"{store.latest_end(f):%Y-%m-%d}",
               "items": [{k: v for k, v in r.items() if k != "_v"} for r in rows]}
        typer.echo(json.dumps(out, indent=1, default=str))
        return
    typer.echo(f"{t}: {'SEC EDGAR' if src == 'edgar' else 'Yahoo'}; latest period {store.latest_end(f):%d %b %Y}")
    typer.echo(f"  {'item':<20}{'value':>18}  {'period end':<11}{'basis':<10}{'years':>5}  tag")
    for r in rows:
        typer.echo(f"  {r['item']:<20}{_fmt_value(r['_v']):>18}  {r['end'] or '–':<11}{r['basis'] or '':<10}"
                   f"{r['fiscal_years']:>5}  {r['tag'] or ''}")


@fundamentals_app.command("check")
def fundamentals_check(tolerance: float = typer.Option(0.10, help="List differences larger than this share")):
    """US companies with both sources: SEC EDGAR against Yahoo for the last twelve months of revenue, operating
    income and operating cash flow, where both end on the same quarter. A large difference points at a mis-read
    tag or line."""
    from .fundamentals import store

    e, y = store.load_edgar(), store.load_yahoo()
    both = sorted(set(e["ticker"]) & set(y["ticker"]))
    if not both:
        raise typer.Exit("No company has statements from both sources yet.")
    off, compared = [], 0
    for t in both:
        fe, fy = e[e["ticker"] == t], y[y["ticker"] == t]
        for item in ("revenue", "operating_income", "cfo"):
            a, b = store.ttm(fe, item), store.ttm(fy, item)
            if a is None or b is None or abs((a.end - b.end).days) > 20 or not b.value:
                continue
            compared += 1
            d = a.value / b.value - 1
            if abs(d) > tolerance:
                off.append((t, item, a, b, d))
    typer.echo(f"{len(both)} companies, {compared} comparisons; {len(off)} differ by more than {tolerance:.0%}:")
    for t, item, a, b, d in off:
        typer.echo(f"  {t:<8} {item:<17} EDGAR {_fmt_value(a)} ({a.tag}, {a.basis})  Yahoo {_fmt_value(b)} "
                   f"({b.tag}, {b.basis})  {d:+.0%}")


@fundamentals_app.command("contact")
def fundamentals_contact(email: str = typer.Argument(None, help="Your e-mail address"),
                         clear: bool = typer.Option(False, "--clear", help="Remove it (SEC EDGAR is then skipped)")):
    """The contact e-mail sent to SEC with each EDGAR request (SEC's fair-access rule asks automated clients to say
    who they are). Stored in your own database; without it, US statements come from Yahoo only."""
    from .fundamentals import edgar

    if clear:
        edgar.set_contact(None)
        typer.echo("Removed: SEC EDGAR is skipped until a contact is set.")
        return
    if not email:
        c = edgar.contact()
        typer.echo(f"SEC contact: {c}" if c else "No SEC contact set: radar fundamentals contact you@example.com")
        return
    try:
        typer.echo(f"SEC contact set to {edgar.set_contact(email)}.")
    except ValueError as e:
        raise typer.Exit(str(e))


abtest_app = typer.Typer(help="The forward A/B test: kvalitet+værdi vs momentum vs 50/50, against ACWI (virtual "
                              "portfolios; analysis, not advice).", no_args_is_help=True)
app.add_typer(abtest_app, name="abtest")


@abtest_app.command("start")
def abtest_start(capital: float = typer.Option(None, help="DKK per basket (default: settings.yaml abtest.capital)"),
                 n: int = typer.Option(None, "--n", help="Names per basket"),
                 max_per_sector: int = typer.Option(None, help="At most this many from one sector"),
                 score: str = typer.Option(None, help="The value basket ranks on qv (kvalitet + værdi) or value")):
    """Start the test: three virtual portfolios tagged ab-qvm, each with this month's picks, bought at the next
    session. After that, the first report of each month records new picks; `radar run` keeps them up to date."""
    from . import abtest, profile

    try:
        with _job("abtest") as log:
            res = abtest.create(profile.Market.load(), capital, n, max_per_sector, score)
            log(f"Started: picks recorded for {res['recorded']}; {len(res['runs'])} portfolios"
                + (f" ({'; '.join(res['notes'])})" if res["notes"] else ""))
    except ValueError as e:
        raise typer.Exit(f"Not started: {e}")
    typer.echo("Follow it with `radar abtest status`, or on the Returns page (tag ab-qvm).")


@abtest_app.command("refresh")
def abtest_refresh():
    """Record this month's picks if due and replay the three portfolios now (each report does it too)."""
    from . import abtest, profile

    with _job("abtest") as log:
        res = abtest.refresh(profile.Market.load(), log=log)
    if not res["runs"] and res["recorded"] is None and not abtest.portfolios():
        typer.echo("No A/B test is running: radar abtest start")


@abtest_app.command("status")
def abtest_status(as_json: bool = typer.Option(False, "--json", help="As JSON (for the skills)")):
    """Where the test stands: each basket's return against ACWI since its first purchase, the correlation of
    their weekly returns, the latest picks and when the next are due."""
    import json

    from . import abtest, profile

    v = abtest.view(profile.Market.load())
    if as_json:
        typer.echo(json.dumps(v, indent=1, default=str, ensure_ascii=False))
        return
    if not v["running"]:
        typer.echo("No A/B test is running: radar abtest start")
        return
    c = v["comparison"]
    typer.echo(f"From {c['start'] or '(not bought yet)'} to {c['asof']}; next picks due {v['next_due']}")
    for r in c["rows"]:
        s = r["stats"] or {}
        typer.echo(f"  {r['label']:<24} {_pct(s.get('twr_total')):>8}  ACWI {_pct(s.get('acwi_twr_total')):>8}  "
                   f"excess {_pct(s.get('excess_twr')):>8}  max DD {_pct(s.get('max_drawdown')):>8}")
    corr = v["correlation"]
    if corr:
        typer.echo("Correlation of weekly returns:")
        for name, row in zip(corr["symbols"], corr["matrix"]):
            typer.echo(f"  {name:<18} " + " ".join(f"{_num(x, '+.2f'):>6}" for x in row))
    for note in v["notes"]:
        typer.echo(f"Note: {note}")
