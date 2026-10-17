"""`radar abtest …`: the forward A/B test of kvalitet+værdi against momentum."""
import typer

from .common import fmt_num, fmt_pct, job, to_json
from .root import app

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
    from .. import abtest, profile

    try:
        with job("abtest") as log:
            res = abtest.create(profile.Market.load(), capital, n, max_per_sector, score)
            log(f"Started: picks recorded for {res['recorded']}; {len(res['runs'])} portfolios"
                + (f" ({'; '.join(res['notes'])})" if res["notes"] else ""))
    except ValueError as e:
        raise SystemExit(f"Not started: {e}")
    typer.echo("Follow it with `radar abtest status`, or on the Returns page (tag ab-qvm).")


@abtest_app.command("refresh")
def abtest_refresh():
    """Record this month's picks if due and replay the three portfolios now (each report does it too)."""
    from .. import abtest, profile

    with job("abtest") as log:
        res = abtest.refresh(profile.Market.load(), log=log)
    if not res["runs"] and res["recorded"] is None and not abtest.portfolios():
        typer.echo("No A/B test is running: radar abtest start")


@abtest_app.command("status")
def abtest_status(as_json: bool = typer.Option(False, "--json", help="As JSON (for the skills)")):
    """Where the test stands: each basket's return against ACWI since its first purchase, the correlation of
    their weekly returns, the latest picks and when the next are due."""

    from .. import abtest, profile

    v = abtest.view(profile.Market.load())
    if as_json:
        typer.echo(to_json(v, indent=1, ensure_ascii=False))
        return
    if not v["running"]:
        typer.echo("No A/B test is running: radar abtest start")
        return
    c = v["comparison"]
    typer.echo(f"From {c['start'] or '(not bought yet)'} to {c['asof']}; next picks due {v['next_due']}")
    for r in c["rows"]:
        s = r["stats"] or {}
        typer.echo(f"  {r['label']:<24} {fmt_pct(s.get('twr_total')):>8}  ACWI {fmt_pct(s.get('acwi_twr_total')):>8}  "
                   f"excess {fmt_pct(s.get('excess_twr')):>8}  max DD {fmt_pct(s.get('max_drawdown')):>8}")
    corr = v["correlation"]
    if corr:
        typer.echo("Correlation of weekly returns:")
        for name, row in zip(corr["symbols"], corr["matrix"]):
            typer.echo(f"  {name:<18} " + " ".join(f"{fmt_num(x, '+.2f'):>6}" for x in row))
    for note in v["notes"]:
        typer.echo(f"Note: {note}")
