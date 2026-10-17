"""`radar propose …`: fee-aware basket proposals for one of your portfolios, and their follow-up."""
import typer

from .common import fmt_num, fmt_pct, to_json
from .root import app

propose_app = typer.Typer(help="Proposals: a fee-aware basket of new stocks for one of your portfolios, tested against "
                               "ACWI and the alternatives (analysis, not advice).", no_args_is_help=True)


app.add_typer(propose_app, name="propose")


def parse_amount(text: str) -> float:
    """money.parse_amount, as a command-line error."""
    from ..money import parse_amount as parse

    try:
        return parse(text)
    except ValueError as e:
        raise typer.BadParameter(str(e))


def _bp(v) -> str:
    return "–" if v is None else f"{v:.2%}"


def _write_out(text: str, out: str | None) -> None:
    from pathlib import Path

    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")


def _load_picks(path: str) -> dict:
    import json
    from pathlib import Path

    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SystemExit(f"Can't read the picks file: {e}")


@propose_app.command("candidates")
def propose_candidates(portfolio: str = typer.Option(..., "--portfolio", help="The portfolio to add to (by name)"),
                       amount: str = typer.Option(..., "--amount", help="DKK to put in (50000, 50.000, 50k)"),
                       tilt: str = typer.Option("mix", "--tilt", help="momentum | value | mix"),
                       mode: str = typer.Option("conviction", "--mode", help="conviction | fill-gaps"),
                       n: int = typer.Option(None, "--n", help="New names (default: amount ÷ the minimum ticket, capped)"),
                       weighting: str = typer.Option("equal", "--weighting", help="equal | inverse-vol"),
                       max_position: float = typer.Option(None, "--max-position", help="Largest position as a share of "
                                                          "your whole real book (0.1 = 10 %)"),
                       horizon: int = typer.Option(6, "--horizon", help="Months (3 or 6)"),
                       no_etf: bool = typer.Option(False, "--no-etf", help="Leave leftover cash as cash"),
                       top: int = typer.Option(40, "--top", help="Names in the shortlist"),
                       as_json: bool = typer.Option(False, "--json", help="As JSON (for the skill)"),
                       out: str = typer.Option(None, "--out", help="Also write the JSON here")):
    """The gated, scored shortlist for adding AMOUNT to PORTFOLIO, the rule-only basket sized with the portfolio's
    fees, and a draft picks file (`draft_picks`) with the standard exit criteria."""

    from .. import profile
    from .. import propose as pr

    try:
        rep = pr.candidates(profile.Market.load(), portfolio, parse_amount(amount), tilt, mode, n, weighting,
                            max_position, not no_etf, horizon, top)
    except ValueError as e:
        raise SystemExit(f"No candidates: {e}")
    text = to_json(rep, indent=1, ensure_ascii=False)
    _write_out(text, out)
    if as_json:
        typer.echo(text)
        return
    g = rep["gates"]
    typer.echo(f"{rep['portfolio']['name']}: {rep['amount']:,.0f} DKK as {rep['n']} names (~{rep['ticket_dkk']:,.0f} each), "
               f"tilt {rep['tilt']}, {rep['mode']}; regime {rep['regime'] or '–'}")
    typer.echo(f"Pool {g['pool']}, {g['kept']} pass the gates: "
               + ", ".join(f"{k} {v['count']}" for k, v in g["excluded"].items()))
    for note in rep["notes"]:
        typer.echo(f"Note: {note}")
    typer.echo(f"\n{'':<10} {'score':>5} {'mom':>4} {'K+V':>4} {'3m':>7} {'6m':>7} {'vol':>5} {'corr':>5}  sector / region  rule")
    for r in rep["shortlist"]:
        typer.echo(f"{r['ticker']:<10} {fmt_num(r['composite'], '.0f'):>5} {fmt_num(r['momentum_score'], '.0f'):>4} "
                   f"{fmt_num(r['qv'], '.0f'):>4} {fmt_pct(r['r3m']):>7} {fmt_pct(r['r6m']):>7} {fmt_pct(r['vol'], False):>5} "
                   f"{fmt_num(r['corr_book'], '.2f'):>5}  {r['sector']} / {r['region']}  "
                   f"{'*' if r['in_rule_basket'] else (r['passed_over'] or '')}")
    sz = rep["rule_basket"]["size"]
    typer.echo(f"\nRule basket: {', '.join(x['ticker'] for x in rep['rule_basket']['picks'])}; invested "
               f"{sz['invested_dkk']:,.0f} DKK, round-trip costs {_bp(sz['roundtrip_pct'])}, leftover "
               f"{sz['leftover_dkk']:,.0f} DKK")


@propose_app.command("freeze")
def propose_freeze(picks_file: str = typer.Argument(..., help="A picks file (the draft from `candidates`, edited)")):
    """Stamp a picks file as frozen and store it in exports/proposals/ (before `evaluate`, so the picks are fixed
    before the model's numbers are seen). Prints the stored file's path."""
    from .. import propose as pr

    try:
        f = pr.save_picks(_load_picks(picks_file))
    except ValueError as e:
        raise SystemExit(f"Not frozen: {e}")
    typer.echo(f)


@propose_app.command("evaluate")
def propose_evaluate(picks_file: str = typer.Argument(..., help="A frozen picks file (exports/proposals/…)"),
                     max_position: float = typer.Option(None, "--max-position", help="Largest position as a share of "
                                                        "your whole real book (default: the picks file's)"),
                     tolerance: float = typer.Option(None, "--tolerance", help="The largest drawdown you accept "
                                                     "(0.25 = 25 %): part of the decision rule"),
                     light: bool = typer.Option(False, "--light", help="Skip the alternatives (faster)"),
                     as_json: bool = typer.Option(False, "--json", help="As JSON (for the skill)"),
                     out: str = typer.Option(None, "--out", help="Also write the JSON here")):
    """Sizing, constraints, exposures before and after vs ACWI, risk, the drawdown three ways, the modelled
    return from the rule study, the alternatives A0-A6 and the decision rule. Saved next to the picks file as
    <name>-evaluation.json (review and check read it)."""

    from .. import profile
    from .. import propose as pr

    doc = _load_picks(picks_file)
    if not (doc.get("meta") or {}).get("frozen_at"):
        raise SystemExit("Freeze the picks first: radar propose freeze FILE (the picks are fixed before the numbers)")
    try:
        rep = pr.evaluate(profile.Market.load(), doc, max_position, tolerance, light=light)
    except ValueError as e:
        raise SystemExit(f"Not evaluated: {e}")
    pr.keep_evaluation(picks_file, rep)
    text = to_json(rep, indent=1, ensure_ascii=False)
    _write_out(text, out)
    if as_json:
        typer.echo(text)
        return
    d, mo, dd = rep["decision"], rep["model"], rep["drawdown"]
    typer.echo(f"Verdict: {d['verdict']} ({d['why']})")
    for c in rep["constraints"]:
        typer.echo(f"  {'ok ' if c['ok'] else 'NO '} {c['check']}: {c['detail']}")
    b = mo["bootstrap"] or {}
    typer.echo(f"Modelled {mo['horizon']}M excess vs ACWI after costs: {fmt_pct(mo['drift_net'])} "
               f"(band {fmt_pct((b.get('excess') or {}).get('p10'))} to {fmt_pct((b.get('excess') or {}).get('p90'))}, "
               f"P(beat) {fmt_pct(b.get('p_beat'), False)}); costs {_bp(mo['cost_pct'])}")
    typer.echo(f"Max drawdown: expected {fmt_pct(dd['expected'])}, bad case {fmt_pct(dd['bad_case'])}")
    for k, a in rep["alternatives"].items():
        if "risk" in a:
            dd = ((a["bootstrap"] or {}).get("max_dd") or {}).get("median")
            typer.echo(f"  {k:<12} {a['label'][:44]:<45} net {fmt_pct(a['drift_net']):>7}  vol {fmt_pct(a['risk']['vol_ann'], False):>5} "
                       f"TE {fmt_pct(a['risk']['te_ann'], False):>5}  DD {fmt_pct(dd):>7}")


@propose_app.command("shadow")
def propose_shadow(picks_file: str = typer.Argument(..., help="A frozen picks file"),
                   name: str = typer.Option(..., "--name", help="The shadow portfolio's name (also '<name> · ACWI' and "
                                                                "'<name> · rule')")):
    """Virtual copies of the portfolio plus the amount: the proposal, ACWI and the rule-only basket, bought at the
    latest close (tags proposal, proposal-<date>). Never a real portfolio."""
    from .. import profile
    from .. import propose as pr

    try:
        res = pr.shadow(profile.Market.load(), _load_picks(picks_file), name)
    except ValueError as e:
        raise SystemExit(f"No shadow: {e}")
    typer.echo("Created: " + ", ".join(res["names"].values()))
    typer.echo(f"Returns page: {res['returns_link']}  (or radar performance --tag {res['tags'][1]})")


@propose_app.command("review")
def propose_review(as_json: bool = typer.Option(False, "--json", help="As JSON (for the skill)")):
    """Every frozen proposal since its day: return vs ACWI and vs its rule basket, its drawdown against the
    modelled band, and what the trend exit would have done."""

    from .. import profile
    from .. import propose as pr

    rep = pr.review(profile.Market.load())
    if as_json:
        typer.echo(to_json(rep, indent=1, ensure_ascii=False))
        return
    for r in rep["proposals"]:
        typer.echo(f"{r['date']} {r['portfolio']:<14} {r.get('tilt') or '':<8} ret {fmt_pct(r.get('ret')):>7} vs ACWI "
                   f"{fmt_pct(r.get('excess')):>7}  vs rule {fmt_pct(r.get('judgment_vs_rule')):>7}  DD {fmt_pct(r.get('max_dd')):>7}"
                   f"  in band {r.get('dd_inside_band')}")
    if rep["note"]:
        typer.echo(rep["note"])


@propose_app.command("check")
def propose_check(portfolio: str = typer.Option(None, "--portfolio", help="Only proposals for this portfolio"),
                  as_json: bool = typer.Option(False, "--json", help="As JSON (for the skills)")):
    """Each open proposal's exit criteria today (review level, signal exit, thesis checks, time stop, basket
    drawdown): Intact, Weakening or Triggered, with the evidence."""

    from .. import profile
    from .. import propose as pr

    rep = pr.check(profile.Market.load(), portfolio)
    if as_json:
        typer.echo(to_json(rep, indent=1, ensure_ascii=False))
        return
    for pp in rep["proposals"]:
        typer.echo(f"\n{pp['date']} {pp['portfolio']}"
                   + (f"  (older rule: {'; '.join(pp['older_rule'])})" if pp["older_rule"] else ""))
        for x in pp["names"]:
            ev = "; ".join(f"{i['criterion']}: {i['status']}" for i in x["items"])
            typer.echo(f"  {x['ticker']:<10} {x['status']:<10} {ev}")
        b = pp["basket"]
        if b.get("status"):
            typer.echo(f"  basket drawdown {fmt_pct(b['max_dd'])} vs bad case {fmt_pct(b['bad_case'])}: {b['status']}")
