"""`radar sim …`: simulations on your own trades and hindsight baskets, into virtual portfolios."""
import typer

from .. import universe
from ..market import Market
from ..model import panels as mp
from ..portfolios import trades
from .common import fmt_num, fmt_pct, job, portfolio_ids, to_json
from .root import app

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
    from pathlib import Path

    from .. import userstore
    from ..backtest import exits

    trades.ensure_migrated()
    variants = exits.VARIANTS if variant == "both" else (variant,)
    if any(v not in exits.VARIANTS for v in variants):
        raise SystemExit("--variant must be overlay, rules or both")
    ids = portfolio_ids(names, None) if names else userstore.compared_ids()
    with job("sim") as log:
        market = Market.load()
        gap = universe.history_gap(market.closes)
        if gap:
            have, need = gap
            log(f"Note: prices start {have}, your trades need them from {need}: run `radar update` to fetch the "
                "deeper history (early decisions lack the 200-day average and momentum until then).")
        try:
            spec = None
            if rule_spec:
                from ..backtest import exit_rules

                spec = exit_rules.variant(rule_spec)
            rep = exits.refresh(ids, market, variants, start, end, fill, spec=spec)
        except ValueError as e:
            raise SystemExit(f"Not simulated: {e}")
    if out:
        Path(out).write_text(to_json(rep, indent=1), encoding="utf-8")
    if as_json:
        typer.echo(to_json(rep, indent=1))
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
            for x in res["exits"]:
                a = x["after"]
                k = f"k {x['k']:.2f}" if x.get("k") is not None else "      "
                typer.echo(f"    {x['trigger_date']} {x['symbol']:<10} {x.get('stop_kind', x['trigger']).replace('_', '-'):<11} {k}  "
                           f"sold {x['fill_date']} at {x['fill_price']:.2f}  {x['proceeds_dkk']:>10,.0f} DKK  "
                           f"saved {dkk(a['end']['saved_dkk'])} (end)"
                           + (f", {dkk(a['your_sale']['saved_dkk'])} (your sale {a['your_sale']['date']})" if "your_sale" in a else ""))
            if s["events"]:
                typer.echo("    · " + ", ".join(f"{k}: {n}" for k, n in s["events"].items()))
            if s["no_rule"]:
                typer.echo("    · no rule (funds outside the sector/theme groups, held as in the real portfolio): "
                           + ", ".join(s["no_rule"]))
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
    from pathlib import Path

    from ..backtest import picks

    try:
        rep = picks.candidates(Market.load(), asof, blind, views, top, model_cutoff, fund=fund)
    except ValueError as e:
        raise SystemExit(str(e))
    text = to_json(rep, indent=1, ensure_ascii=False)
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
        typer.echo(f"{fmt_num(r['rank'], '.0f'):>4}  {(r['ticker'] or r['id']):<10} {fmt_num(r['score'], '.0f'):>5} "
                   f"{fmt_pct(r['r3m']):>7} {fmt_pct(r['r6m']):>7} {fmt_pct(r['r12_1']):>7}  "
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

    from ..backtest import picks

    trades.ensure_migrated()
    with job("sim") as log:
        market = Market.load()
        p = mp.panels(market)
        try:
            if rerun:
                hs = picks.find(rerun)
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
            raise SystemExit(f"Not simulated: {e}")
        for r in reps:
            log(f"{r['name']}: picked {r['asof']}, bought {r['fill']}, to {r['end']}")
    if as_json:
        typer.echo(to_json(reps[0] if len(reps) == 1 else reps, indent=1, ensure_ascii=False))
        return
    for r in reps:
        y = r["yardsticks"]
        typer.echo(f"\n{r['name']}: picked on {r['asof']}, bought {r['fill']}, to {r['end']} ({r['sessions']} sessions, DKK)")
        for kind, pf in r["portfolios"].items():
            st = pf["stats"] or {}
            typer.echo(f"  {kind:<8} {pf['name'][:40]:<41} {fmt_pct(pf['return_dkk']):>8}  vs ACWI {fmt_pct(pf['excess_dkk']):>8}"
                       f"  max DD {fmt_pct(st.get('max_drawdown')):>7}")
        typer.echo(f"  ACWI {fmt_pct(y['acwi_dkk'])}, equal-weight universe {fmt_pct(y['universe_ew_dkk'])}; "
                   f"basket before fees {fmt_pct(y['basket_gross_dkk'])}")
        rnd = y["random"]
        if rnd.get("percentile") is not None:
            typer.echo(f"  Among {rnd['draws']} random baskets of the same size and caps: percentile {rnd['percentile']:.0f} "
                       f"(median {fmt_pct(rnd['median'])}, 10–90 % {fmt_pct(rnd['p10'])} to {fmt_pct(rnd['p90'])})")
        sc = r["score_check"]
        if sc:
            typer.echo(f"  Score check that day ({sc['n']} names): IC {fmt_num(sc['ic'])}, quintile excess "
                       + " ".join(fmt_pct(q) for q in sc["q"]) + f"; the score's own top {len(r['picks'])} (no caps) beat the "
                       f"average stock {fmt_pct(sc['top_hit'], False)} of the time")
        s = r["exits"]["summary"]
        typer.echo(f"  Rule: {s['stops']} stop and {s['take_profits']} take-profit exits")
        if r["same_as_control"]:
            typer.echo("  (the basket is the score's own top N, so it is its own control)")
        typer.echo(f"  Returns page: {r['returns_link']}")
    typer.echo("\nOne basket over one period is an illustration, not evidence: `radar study score` tests the score "
               "across every month.")
