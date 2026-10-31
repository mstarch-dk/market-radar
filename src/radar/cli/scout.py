"""`radar scout …`: the follow-up on /scout's frozen hypothesis candidates (the skill freezes them)."""
import typer

from ..market import Market
from .common import fmt_pct, to_json
from .root import app

scout_app = typer.Typer(help="/scout's hypothesis candidates, frozen when shown, against ACWI since (analysis, not "
                             "advice).", no_args_is_help=True)


app.add_typer(scout_app, name="scout")


@scout_app.command("review")
def scout_review(as_json: bool = typer.Option(False, "--json", help="As JSON (for the skills)")):
    """Every frozen candidate since its day: its proxy basket against ACWI, and the means per decision (adopted,
    dismissed, watch) and per stage (whisper, confirming, consensus) once enough are old enough."""

    from .. import evidence

    rep = evidence.scout_review(Market.load())
    if as_json:
        typer.echo(to_json(rep, indent=1, ensure_ascii=False))
        return
    if not rep["candidates"]:
        typer.echo("No /scout candidates frozen yet.")
        return
    for r in rep["candidates"]:
        miss = f"  no prices: {', '.join(r['missing'])}" if r.get("missing") else ""
        typer.echo(f"{r.get('date') or '':<10} {r.get('slug') or r['id']:<24} {r.get('decision') or '':<9} "
                   f"{r.get('stage') or '':<10} ret {fmt_pct(r.get('ret')):>7} vs ACWI {fmt_pct(r.get('excess')):>7}"
                   f"  DD {fmt_pct(r.get('max_dd')):>7}{miss}{'  ' + r['note'] if r.get('note') else ''}")
    for key in ("by_decision", "by_stage"):
        parts = [f"{g[key.removeprefix('by_')]} {fmt_pct(g['mean_excess'])} (n={g['count']})" if g["enough"]
                 else f"{g[key.removeprefix('by_')]} n={g['count']} of {g['need']}" for g in rep[key]]
        typer.echo(f"{key.removeprefix('by_').capitalize()}: " + ", ".join(parts)
                   + f"  (candidates at least {rep['min_months']} months old)")
