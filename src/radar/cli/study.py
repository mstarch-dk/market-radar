"""`radar study …`: the radar's signals tested on past data."""
import typer

from .common import fmt_num, fmt_pct, job, to_json
from .root import app

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
    from pathlib import Path

    from .. import profile
    from ..backtest import exits, study

    try:
        hs = tuple(int(x) for x in horizons.split(","))
        keys = None if variants == "all" else [v.strip() for v in variants.split(",") if v.strip()]
        with job("study") as log:
            rep = study.run(profile.Market.load(), hs, keys, n, exits_months, seasoned, since, not no_regime, log,
                            signal=signal)
            study.write(rep)
    except ValueError as e:
        raise typer.Exit(f"Not studied: {e}")
    text = to_json(rep, indent=1)
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
            typer.echo(f"  {k:<14}{a.get('dates', 0):>5} {fmt_num(a.get('ic_mean')):>6} {fmt_num(a.get('ic_t'), '+.1f'):>6} "
                       f"{fmt_pct(a.get('ic_pos'), False):>5}  {fmt_pct(q[0]):>7} {fmt_pct(q[2]):>7} {fmt_pct(q[4]):>7} "
                       f"{fmt_pct(a.get('spread')):>7} {fmt_num(a.get('spread_t'), '+.1f'):>6}  {fmt_pct(a.get('top_excess')):>7} "
                       f"{fmt_pct(a.get('top_hit'), False):>4}  {fmt_num(o.get('ic_mean')):>10}  {v}{pit}")
        base = res[bk]
        reg = {g: s for g, s in (base.get("by_regime") or {}).items() if s}
        if reg:
            typer.echo(f"  {bk} IC by regime on D: " + ", ".join(f"{g} {fmt_num(s['ic_mean'])} ({s['dates']})" for g, s in reg.items()))
        grp = {g: s for g, s in (base.get("by_group") or {}).items() if s}
        if grp:
            typer.echo(f"  {bk} IC within each group: " + ", ".join(f"{g} {fmt_num(s['ic_mean'])}" for g, s in grp.items()))
        a = base["all"] or {}
        if a.get("top_dkk") is not None:
            typer.echo(f"  top {n} in DKK: mean {fmt_pct(a['top_dkk'])} against ACWI {fmt_pct(a['acwi_dkk'])}, "
                       f"ahead on {fmt_pct(a['top_beats_acwi'], False)} of dates")
    typer.echo(f"\nIC decay ({bk}): " + ", ".join(f"{h}m {fmt_num(v)}" for h, v in rep["decay"][bk].items()))
    typer.echo(f"Top-quintile turnover per month ({bk}): {fmt_pct(rep['turnover'][bk], False)}")
    mc = rep.get("momentum_corr")
    if mc and mc.get("mean") is not None:
        typer.echo(f"Rank correlation with the momentum score: {fmt_num(mc['mean'])} on average over {mc['dates']} dates "
                   "(near 0 or below: the two pick different stocks)")
    e = rep.get("exits")
    if e and e.get("summary"):
        s = e["summary"]
        typer.echo(f"\nStop/take-profit rule on each date's top {e['n_top']}, {e['months']} months, fees {e['fee_bps']:g} bp:")
        typer.echo(f"  held: mean {fmt_pct(s['hold']['mean'])} (ACWI {fmt_pct(s['hold']['acwi_mean'])}), ahead of ACWI on "
                   f"{fmt_pct(s['hold']['beats_acwi'], False)} of {s['both']['dates']} dates")
        for rule in exits.RULES:
            x = s[rule]
            typer.echo(f"  {rule:<12} vs held: mean {fmt_pct(x['mean_diff'])} (t {fmt_num(x['t'], '+.1f')}), helped on "
                       f"{fmt_pct(x['helped'], False)} of dates, worst {fmt_pct(x['worst'])}, best {fmt_pct(x['best'])}, "
                       f"{fmt_num(x['exits_mean'], '.1f')} exits per basket")
        if e.get("inputs_missing"):
            typer.echo("  inputs missing on rule days: " + ", ".join(f"{k} {v:.0%}" for k, v in e["inputs_missing"].items()))
    typer.echo("\nCaveats: " + " ".join(rep["caveats"][:2]))
    typer.echo(f"Report: reports/{sig.report}")


@study_app.command("longrun")
def study_longrun(panels: str = typer.Option("all", "--panel", help="all, or a comma list of panels (longrun.panels: "
                                             "french49, countries)"),
                  horizons: str = typer.Option(None, help="Forward horizons in months (default longrun.horizons)"),
                  variants: str = typer.Option("all", help="all, or a comma list of variant keys"),
                  since: str = typer.Option(None, "--since", help="First formation month (YYYY or YYYY-MM-DD)"),
                  fetch: bool = typer.Option(False, "--fetch", help="Download the French and JKP histories first "
                                                                    "(they are part of `radar update` too)"),
                  as_json: bool = typer.Option(False, "--json", help="The full report as JSON"),
                  out: str = typer.Option(None, "--out", help="Also write the JSON here")):
    """The momentum score's rule over decades, on portfolios without survivorship bias: US industries since 1926
    (Fama-French 49) and developed-market countries since 1986 (JKP). Variants of the lookbacks and weights with the
    verdict rule of `radar study score`, splits by decade, market trend and recession, the long-run base rates of the
    momentum, value and quality factors, and a rough gauge of the survivorship bias in `radar study score`. Writes
    reports/longrun-study.json."""
    from pathlib import Path

    from .. import factors
    from ..backtest import longrun

    try:
        with job("study") as log:
            if fetch:
                log(f"Long histories: {factors.update_factors(force=True)}")
            hs = [int(x) for x in horizons.split(",")] if horizons else None
            keys = None if variants == "all" else [v.strip() for v in variants.split(",") if v.strip()]
            ps = None if panels == "all" else [x.strip() for x in panels.split(",") if x.strip()]
            rep = longrun.build(ps, hs, keys, since, log)
            longrun.write(rep)
    except (ValueError, RuntimeError) as e:
        raise typer.Exit(f"Not studied: {e}")
    text = to_json(rep, indent=1)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
    if as_json:
        typer.echo(text)
        return
    typer.echo("\nData to: " + ", ".join(f"{k} {m}" for k, m in rep["datasets_asof"].items()))
    for pr in rep["panels"].values():
        typer.echo(f"\n{pr['label']}: {pr['members']} members, top {pr['n_top']}, {pr['months']} formation months "
                   f"{pr['first']:%Y-%m} to {pr['last']:%Y-%m}; holdout from {rep['settings']['holdout_from']}; "
                   f"{pr['variants_tried']} variants tried")
        for h, res in pr["results"].items():
            typer.echo(f"\n  {h} month(s) ahead: excess over the panel's equal weight")
            typer.echo(f"    {'':<12}{'dates':>6} {'eff N':>6} {'IC':>6} {'t':>6}  {'Q5-Q1':>7} {'t':>6}  {'top N':>7} {'t':>6}"
                       f"  {'vs mkt':>7}  {'holdout IC':>10}  verdict")
            for k, r in res.items():
                a, o = r["all"] or {}, r["holdout"] or {}
                v = pr["verdicts"][h].get(k, {}).get("label", "baseline")
                typer.echo(f"    {k:<12}{a.get('dates', 0):>6} {fmt_num(a.get('eff_n'), '.0f'):>6} {fmt_num(a.get('ic_mean')):>6} "
                           f"{fmt_num(a.get('ic_t'), '+.1f'):>6}  {fmt_pct(a.get('spread')):>7} {fmt_num(a.get('spread_t'), '+.1f'):>6}  "
                           f"{fmt_pct(a.get('top_excess')):>7} {fmt_num(a.get('top_excess_t'), '+.1f'):>6}  "
                           f"{fmt_pct(a.get('top_vs_market')):>7}  {fmt_num(o.get('ic_mean')):>10}  {v}")
            base = res["score"]
            dec = {d: s for d, s in (base.get("by_decade") or {}).items() if s}
            typer.echo("    score IC by decade: " + ", ".join(f"{d} {fmt_num(s['ic_mean'])}" for d, s in dec.items()))
            for split in ("by_trend", "by_recession"):
                parts = {g: s for g, s in (base.get(split) or {}).items() if s}
                if parts:
                    typer.echo(f"    score {split.replace('_', ' ')}: " + ", ".join(
                        f"{g} IC {fmt_num(s['ic_mean'])}, top N {fmt_pct(s['top_excess'])} ({s['dates']} dates)"
                        for g, s in parts.items()))
    for k, e in rep["errors"].items():
        typer.echo(f"\n{k}: not studied ({e})")
    typer.echo("\nBase rates of the long-short factors (annualised; share of 6- and 12-month windows that lost):")
    for label, b in rep["base_rates"].items():
        if not b:
            typer.echo(f"  {label}: no data")
            continue
        d = b["drawdown"]
        rec = f"{d['months_to_recover']} months to recover" if d["months_to_recover"] is not None else "not recovered"
        typer.echo(f"  {label}: {b['first']:%Y}-{b['last']:%Y}, {fmt_pct(b['ann_return'])} a year (t {fmt_num(b['t'], '+.1f')}), "
                   f"last 10y {fmt_pct(b['last_10y_ann'])}; lost in {fmt_pct(b['roll6']['share_negative'], False)} / "
                   f"{fmt_pct(b['roll12']['share_negative'], False)} of windows; worst drawdown {fmt_pct(d['max'])} "
                   f"({d['peak']:%Y-%m}, {rec})")
    s = rep.get("survivorship")
    if s:
        typer.echo(f"\nSurvivorship gauge ({s['window']['first']:%Y-%m} to {s['window']['last']:%Y-%m}): top-quintile "
                   f"excess a month {fmt_pct(s['study_top_quintile_excess_1m'])} in `radar study score` against "
                   f"{fmt_pct(s['survivorship_free_same_months'])} for all US stocks without survivorship bias "
                   f"({fmt_pct(s['survivorship_free_since_1927'])} since 1927); implied haircut "
                   f"{fmt_pct(s['implied_haircut'], False)}, configured {fmt_pct(s['configured_haircut'], False)}. {s['note']}.")
    typer.echo("\nCaveats: " + " ".join(rep["caveats"][:2]))
    typer.echo(f"Report: reports/{longrun.REPORT_FILE}")


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

    from .. import profile
    from ..backtest import exit_rules

    try:
        hs = tuple(int(x) for x in horizons.split(","))
        keys = None if variants == "all" else [v.strip() for v in variants.split(",") if v.strip()]
        with job("study") as log:
            rep = exit_rules.exit_variants(profile.Market.load(), n, hs, keys, since, not no_reentry, log)
            exit_rules.write_exits(rep)
    except ValueError as e:
        raise typer.Exit(f"Not studied: {e}")
    if as_json:
        typer.echo(to_json(rep, indent=1))
        return
    st = rep["settings"]
    typer.echo(f"\nEach month-end's top {st['n_top']} (equal weights, {st['fee_bps']:g} bp per trade), exits parked in "
               f"{st['park']}; holdout from {st['holdout_from']}. Pass: costs at most {st['cost_per_6m']:.0%} per 6 months, "
               f"cuts mean max drawdown by {st['dd_cut']:.0%} and lifts the 10 % worst outcome, in-sample and holdout.")
    labels = {v["key"]: v["label"] for v in rep["variants"]}
    for h, res in rep["results"].items():
        first = next(iter(res.values()))["all"] or {}
        hold = first.get("hold") or {}
        typer.echo(f"\n{h} months ({first.get('dates', 0)} dates). Held: return {fmt_pct(hold.get('ret_mean'))}, worst 10 % "
                   f"{fmt_pct(hold.get('ret_p10'))}, max DD {fmt_pct(hold.get('dd_mean'))} (worst {fmt_pct(hold.get('dd_worst'))})")
        typer.echo(f"  {'':<14}{'return':>8} {'vs held':>8} {'t':>5} {'helped':>6}  {'worst10%':>8} {'max DD':>7} "
                   f"{'worstDD':>8} {'exits':>5}  {'holdout vs held':>15}  verdict")
        for k, r in res.items():
            a, o = r["all"] or {}, r["holdout"] or {}
            v = r["verdict"]
            typer.echo(f"  {k:<14}{fmt_pct(a.get('ret_mean')):>8} {fmt_pct(a.get('diff_mean')):>8} {fmt_num(a.get('diff_t'), '+.1f'):>5} "
                       f"{fmt_pct(a.get('helped'), False):>6}  {fmt_pct(a.get('ret_p10')):>8} {fmt_pct(a.get('dd_mean')):>7} "
                       f"{fmt_pct(a.get('dd_worst')):>8} {fmt_num(a.get('exits_mean'), '.1f'):>5}  {fmt_pct(o.get('diff_mean')):>15}  "
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
    from pathlib import Path

    from .. import profile
    from ..backtest import redeploy

    try:
        hs = tuple(int(x) for x in horizons.split(","))
        keys = None if arms == "all" else [v.strip() for v in arms.split(",") if v.strip()]
        with job("study") as log:
            rep = redeploy.redeploy_study(profile.Market.load(), n, hs, buffer, cooldown, max_per_sector, max_per_group,
                                       not no_trend, since, keys, log)
            redeploy.write_redeploy(rep)
    except ValueError as e:
        raise typer.Exit(f"Not studied: {e}")
    text = to_json(rep, indent=1)
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
        typer.echo(f"\n{h} months ({first.get('dates', 0)} dates). Held: return {fmt_pct(hold.get('ret_mean'))}, Sharpe "
                   f"{fmt_num(hold.get('sharpe_mean'))}, Sortino {fmt_num(hold.get('sortino_mean'))}, "
                   f"max DD {fmt_pct(hold.get('dd_mean'))}, "
                   f"IR {fmt_num(hold.get('ir_mean'))}")
        typer.echo(f"  {'':<17}{'return':>8} {'vs held':>8} {'Sharpe':>7} {'Sortino':>7} {'Calmar':>7} {'max DD':>7} "
                   f"{'IR':>6} {'trades':>6} {'fees':>6}  {'Sharpe vs twin':>14} {'holdout':>8}  verdict")
        for k, r in res.items():
            a, o = r["all"] or {}, r["holdout"] or {}
            act, tw = r.get("activity") or {}, ((r.get("vs_twin") or {}).get("all") or {}).get("sharpe") or {}
            twin = f"{fmt_num(tw.get('mean'))} t{fmt_num(tw.get('t'), '+.1f')}" if tw else ""
            typer.echo(f"  {k:<17}{fmt_pct(a.get('ret_mean')):>8} {fmt_pct(a.get('diff_mean')):>8} {fmt_num(a.get('sharpe_mean')):>7} "
                       f"{fmt_num(a.get('sortino_mean')):>7} {fmt_num(a.get('calmar_mean')):>7} {fmt_pct(a.get('dd_mean')):>7} "
                       f"{fmt_num(a.get('ir_mean')):>6} {fmt_num(act.get('trades'), '.0f'):>6} {fmt_pct(act.get('fees_pct')):>6}  "
                       f"{twin:>14} {fmt_num(o.get('sharpe_mean')):>8}  {(r['verdict'] or {}).get('label', '')}")
    typer.echo("\nArms: " + "; ".join(f"{a['key']} = {a['label']}" for a in rep["arms"]))
    typer.echo("Caveat: " + rep["caveats"][0])
    typer.echo("Report: reports/redeploy-study.json")


@study_app.command("propose")
def study_propose(tilts: str = typer.Option("momentum,value,mix", help="Tilts to test (momentum, value, mix)"),
                  ns: str = typer.Option(None, "--ns", help="Basket sizes (default: settings.yaml propose.study_ns)"),
                  horizons: str = typer.Option(None, help="Horizons in months (default: propose.horizons)"),
                  since: str = typer.Option(None, "--since", help="First formation date"),
                  no_regime: bool = typer.Option(False, "--no-regime", help="Skip the split by regime (faster)"),
                  as_json: bool = typer.Option(False, "--json", help="The full report as JSON")):
    """The proposal rule (`radar propose`: gates, proposal score, caps, equal weights, costs) at every past
    month-end, held 3 and 6 months and with the proposal's exits, in DKK against ACWI: the only source of a
    proposal's modelled excess and one of its drawdown lenses. Value and mix: US stocks only (SEC EDGAR). Writes
    reports/propose-study.json."""

    from .. import profile
    from ..backtest import propose_study as ps

    try:
        with job("study") as log:
            rep = ps.run(profile.Market.load(), [t.strip() for t in tilts.split(",") if t.strip()],
                         [int(x) for x in ns.split(",")] if ns else None,
                         [int(x) for x in horizons.split(",")] if horizons else None, since, not no_regime, log)
            ps.write(rep)
    except ValueError as e:
        raise typer.Exit(f"Not studied: {e}")
    if as_json:
        typer.echo(to_json(rep, indent=1))
        return
    u = rep["universe"]
    typer.echo(f"\n{u['dates']} month-ends, {u['first']} to {u['last']}; costs {rep['cost_bps']} bp each way; holdout from "
               f"{rep['holdout_from']}; settings {rep['settings_hash']}")
    for tilt, by_n in rep["results"].items():
        ic = rep["ic"][tilt]
        typer.echo(f"\n{tilt}{' (US only)' if rep['us_only'][tilt] else ''}: composite IC with 6 months "
                   f"{fmt_num(ic['mean'])} (t {fmt_num(ic['t'], '+.1f')}, {ic['dates']} dates)")
        typer.echo(f"  {'n':>2} {'h':>2}  {'excess':>7} {'t':>5} {'eff N':>5} {'hit':>4}  {'holdout':>7} {'max DD':>7} "
                   f"{'bad DD':>7}  {'exits':>7} {'vs kept':>7}")
        for n, by_h in by_n.items():
            for h, arms in by_h.items():
                a = (arms["kept"] or {}).get("all") or {}
                o = (arms["kept"] or {}).get("holdout") or {}
                x = (arms["exits"] or {}).get("all") or {}
                typer.echo(f"  {n:>2} {h:>2}  {fmt_pct(a.get('mean')):>7} {fmt_num(a.get('t'), '+.1f'):>5} "
                           f"{fmt_num(a.get('effective_n'), '.1f'):>5} {fmt_pct(a.get('hit'), False):>4}  {fmt_pct(o.get('mean')):>7} "
                           f"{fmt_pct(a.get('dd_median')):>7} {fmt_pct(a.get('dd_p10')):>7}  {fmt_pct(x.get('mean')):>7} "
                           f"{fmt_pct(x.get('vs_kept_mean')):>7}")
    typer.echo("\nExcess: over ACWI in DKK after costs. Read the effective N: overlapping windows. Caveat: " + rep["caveats"][0])
    typer.echo("Report: reports/propose-study.json")
