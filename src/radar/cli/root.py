"""The `radar` command: the Typer app, `--version`, `--home`, and the gate before a command touches the data folder."""
import typer

app = typer.Typer(add_completion=False, help="Market radar: rotation, momentum, regime and holdings signals.")


FREE = {"setup", "paths", "serve", "doctor", "openapi", "ticker"}     # run before a data folder is chosen


def _version(value: bool) -> None:
    if value:
        from ..home import app_version

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

    from .. import home as homes
    from .. import paths

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
    from .. import backup, paths
    from .. import home as homes

    if backup.before_upgrade():
        typer.echo(f"First use of Market Radar {homes.app_version()} with this data: backed up first.")
    if backup.is_home():
        homes.upgrade(paths.locations().home)
        homes.touch(paths.locations().home)
