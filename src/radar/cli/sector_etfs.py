"""`radar sector-etfs …`: the go-to UCITS ETF per sector from /sector-etfs' latest record (the skill writes it),
with today's returns, costs and Danish tax status (analysis, not advice)."""
import typer

from .common import fmt_pct, to_json
from .root import app

sector_app = typer.Typer(help="The go-to UCITS ETF per sector and its peers, from /sector-etfs' latest record, "
                              "with returns in DKK, TER and the tax status (analysis, not advice).",
                         invoke_without_command=True)
app.add_typer(sector_app, name="sector-etfs")

TAX = {"aktiebaseret": "PL", "kapitalindkomst": "off", "ukendt": "?"}


def _market():
    from ..market import Market

    try:
        return Market.load()
    except SystemExit:                       # no price data yet: returns are n/a
        return None


def _ter(v) -> str:
    return "–" if v is None else f"{v * 100:.2f}%"


@sector_app.callback()
def sector_etfs(ctx: typer.Context,
                as_json: bool = typer.Option(False, "--json", help="As JSON (for the skills)")):
    """Every sector with its go-to ETF (*) and peers in the ranking's order. Subcommands: candidates, history."""
    if ctx.invoked_subcommand is not None:
        return
    from .. import sector_etf_view

    v = sector_etf_view.view(_market())
    if as_json:
        typer.echo(to_json(v, indent=1, ensure_ascii=False))
        return
    if v["as_of"] is None:
        typer.echo("No sector ETF record yet: run /sector-etfs in Claude Code.")
        return
    stale = f"  (older than {v['stale_days']} days: run /sector-etfs again)" if v["stale"] else ""
    typer.echo(f"Record {v['record_id']} ({v['age_days']} days old){stale}. PL: on SKAT's positive list "
               f"{v['tax_year']} (share income, ASK allowed); off: capital income. Analysis, not advice.")
    for p in v["problems"]:
        typer.echo(f"  ! {p['id']}: {p['problem']}")
    scope = v["run_scope"]
    if scope["mode"] == "replace":
        typer.echo(f"The next /sector-etfs run re-selects: {', '.join(scope['sectors'])}")
    for s in v["sectors"]:
        if not s["etfs"]:
            continue
        flag = "  re-check: the pick is no longer first" if s["recheck"] else ""
        if s["replace"]:
            why = f" ({s['replace']['reason']})" if s["replace"]["reason"] else ""
            flag += f"  marked for replacement {s['replace']['flagged_at'][:10]}{why}"
        typer.echo(f"\n{s['key']} ({s['label']}), updated {s['updated']}{flag}")
        for e in s["etfs"]:
            r, vs = e["returns_dkk"], e["vs_acwi"]
            gone = "  [rejected as go-to]" if e.get("rejected") else ""
            typer.echo(f" {'*' if e['pick'] else ' '}{e['rank']} {e['ticker']:<9} {e['isin']} {e['scope']:<6} "
                       f"TER {_ter(e['ter']):>6} {TAX[e['tax']['tax_class']]:<3} 3m {fmt_pct(r['r3m']):>7} "
                       f"1y {fmt_pct(r['r1y']):>7} vs ACWI 3m {fmt_pct(vs['r3m']):>7}  {e['name']}{gone}")
        if s["reason"]:
            typer.echo(f"   why: {s['reason']}")


@sector_app.command("candidates")
def candidates(sector: str = typer.Argument(..., help="A sector key, e.g. Technology or Banks"),
               as_json: bool = typer.Option(False, "--json", help="As JSON (for the skills)")):
    """Where /sector-etfs starts for one sector: the record's ETFs, the seeds and discovery-pool funds, ranked."""
    from .. import sector_etf_view

    c = sector_etf_view.candidates(sector, _market())
    if as_json:
        typer.echo(to_json(c, indent=1, ensure_ascii=False))
        return
    typer.echo(f"{c['key']} ({c['label']}): pick now {c['current_pick'] or 'none'}")
    ask = c["replace_requested"]
    if ask:
        typer.echo(f"  marked for replacement: {ask['isin']}{' (' + ask['reason'] + ')' if ask['reason'] else ''}")
    for e in c["candidates"]:
        gone = "  [rejected as go-to]" if e["rejected"] else ""
        typer.echo(f"  {e['rank']} {e['ticker']:<9} {e['isin']} {e['source']:<6} TER {_ter(e['ter']):>6} "
                   f"Yahoo {_ter(e['yahoo_ter']):>6} {TAX[e['tax']['tax_class']]:<3} {e['name']}{gone}")
    for e in c["pool"]:
        typer.echo(f"  - {e['ticker']:<9} {e['isin']} pool   {TAX[e['tax']['tax_class']]:<3} {e['name']}")


@sector_app.command("history")
def history(as_json: bool = typer.Option(False, "--json", help="As JSON (for the skills)")):
    """What each /sector-etfs run picked, by date (a sector carried over from an earlier run is marked)."""
    from .. import sector_etf_view

    h = sector_etf_view.history()
    if as_json:
        typer.echo(to_json(h, indent=1, ensure_ascii=False))
        return
    if not h:
        typer.echo("No sector ETF record yet: run /sector-etfs in Claude Code.")
    for r in h:
        if "problem" in r:
            typer.echo(f"{r['id']}: {r['problem']}")
            continue
        picks = ", ".join(f"{k} {p['ticker']}{' (carried)' if p['carried'] else ''}" for k, p in r["picks"].items())
        typer.echo(f"{r['date']}: {picks}")
