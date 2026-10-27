"""Your data folder: setup, backups and restore, the update check, where things are, the holdings bundle and the open export."""
import typer

from .root import app


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

    from .. import paths
    from ..datahome import home as homes

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

    from ..datahome import backup

    if mirror:
        m = backup.set_mirror(None if mirror == "off" else Path(mirror))
        typer.echo(f"Second backup folder: {m or 'none'}")
    f = backup.create(reason)
    typer.echo(f"Wrote {f} ({f.stat().st_size // 1024} KB)" + (f"; copy in {backup.mirror()}" if backup.mirror() else ""))


@app.command()
def backups():
    """The backups in your data folder (and in the second backup folder, if one is set)."""
    from ..datahome import backup

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

    from ..datahome import backup

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
    from .. import updates

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

    from .. import paths as p
    from ..datahome import home as homes

    st = homes.status()
    out = {k: st[k] for k in ("state", "source", "app_version", "home", "cache", "pointer", "read_only", "warning")}
    if st["state"] != "unset":
        loc = p.locations()
        out["folders"] = {key: str(d) for key, _label, d, _tier in p.folders(loc)}
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

    from ..datahome import export

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

    from ..datahome import export

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
    typer.echo(f"Restored {what}, {r['watchlist']} watchlist edits, {r['views']} market views and {r.get('rules', 0)} "
               "trading rules.")


@app.command(name="export")
def export_data(out: str = typer.Option(None, "--out", help="The zip to write (default: exports/ in your data folder)")):
    """Your data in open formats (CSV, JSON, Markdown), readable without Market Radar: every portfolio and
    transaction, market views, watchlist, and your notes, briefs, research and journal. EXPORT.md inside says
    what each file and column holds. It holds your holdings: keep it private."""
    from pathlib import Path

    from ..datahome import export

    f = export.write(Path(out) if out else None)
    typer.echo(f"Wrote {f} ({f.stat().st_size // 1024} KB). It holds your holdings: keep it private.")


@app.command(name="import-export")
def import_export(file: str = typer.Argument(..., help="A zip written by `radar export`"),
                  yes: bool = typer.Option(False, "--yes", help="Don't ask")):
    """Read an export back (another computer, a reinstall). The portfolios in it get exactly its rows; documents
    that aren't here yet are added, ones that are here are left alone. radar.db is backed up first."""
    from pathlib import Path

    from ..datahome import export

    pv = export.preview(Path(file))
    typer.echo(f"{file}: {pv['portfolios']} portfolios, {pv['transactions']} transactions, {len(pv['documents'])} "
               f"documents ({len(pv['new_documents'])} new here)" + (f", made {pv['meta']['created']}" if pv["meta"] else ""))
    if not yes and not typer.confirm("Load it? The portfolios it names are replaced by its rows.", default=False):
        raise typer.Exit(1)
    r = export.load(Path(file))
    typer.echo(f"Loaded {r['transactions']} transactions in {r['portfolios']} portfolios, {r['views']} market views, "
               f"{r['documents_added']} documents ({r['documents_kept']} already here, left as they were).")
