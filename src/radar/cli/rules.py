"""`radar rules …`: your trading rules, and whether an action breaks them (a mirror, never a gate)."""
import json
from pathlib import Path

import typer

from .common import to_json
from .root import app

rules_app = typer.Typer(help="Your trading rules, and whether an action breaks them: a mirror, never a gate. Personal.",
                        invoke_without_command=True)
app.add_typer(rules_app, name="rules")

MARK = {"breaks": "BREAKS", "near": "near", "unknown": "unknown", "judgment": "ask", "complies": "ok",
        "not_applicable": "n/a"}


def _scope(s: dict) -> str:
    p = s.get("portfolios", "real")
    out = "real portfolios" if p == "real" else "all portfolios" if p == "all" else f"portfolios {p}"
    return out + "".join(f", {k} {s[k]}" for k in ("kind", "tag", "style") if s.get(k))


@rules_app.callback()
def rules(ctx: typer.Context,
          as_json: bool = typer.Option(False, "--json", help="Machine-readable output (for the skills)"),
          archived: bool = typer.Option(False, "--archived", help="Include archived rules")):
    """Your trading rules (active ones; --archived for all). Subcommands: check, standing, add, replay."""
    if ctx.invoked_subcommand is not None:
        return
    from .. import trading_rules as tr
    from ..userstore import rulestore

    rs = rulestore.rules(None if archived else "active")
    if as_json:
        typer.echo(to_json({"disclaimer": tr.DISCLAIMER, "rules": rs}, indent=1, ensure_ascii=False))
        return
    if not rs:
        typer.echo("No trading rules yet: add them on the My trading rules page of the app, or with /rules.")
        return
    typer.echo(tr.DISCLAIMER + "\n")
    for r in rs:
        label = tr.kinds()[r["kind"]]["label"]
        params = ", ".join(f"{k} {v}" for k, v in r["params"].items() if k != "exposures")
        typer.echo(f"#{r['id']} [{r['severity']}{'' if r['status'] == 'active' else ', archived'}] {r['statement']}")
        typer.echo(f"    {label}" + (f" ({params})" if params else "") + f"; {_scope(r['scope'])}")
        if r["kind"] == "max_exposure_weight":
            typer.echo("    counts: " + ", ".join(f"{e['kind']} {e['key']}" for e in r["params"]["exposures"]))
        if r.get("rationale"):
            typer.echo(f"    why: {r['rationale']}")


def _print_rows(rows: list[dict]) -> None:
    for v in rows:
        typer.echo(f"  {MARK[v['status']]:<7} [{v['severity']}] #{v['rule_id']} {v['statement']}")
        typer.echo(f"          {v['message']}")
        if v.get("comply"):
            typer.echo(f"          → {v['comply']}")


@rules_app.command("check")
def check(side: str = typer.Argument(..., help="buy or sell"),
          ticker: str = typer.Argument(..., help="Yahoo symbol, e.g. NOVO-B.CO"),
          amount: str = typer.Argument(..., help="DKK (20000), shares (50sh) or, for a sale, a fraction (half, all, "
                                                 "0.25)"),
          portfolio: str = typer.Option(None, "--portfolio", help="The portfolio (default: your default one)"),
          style: str = typer.Option(None, "--style", help="momentum, value, core or tactical"),
          horizon: str = typer.Option(None, "--horizon", help="1m, 3m, 6m, 12m or 3y"),
          day: str = typer.Option(None, "--date", help="As of this day (YYYY-MM-DD; default today)"),
          price: float = typer.Option(None, "--price", help="Price per share in the quote currency (default: the "
                                                            "day's close)"),
          log: bool = typer.Option(False, "--log", help="Store the check (the journal and the skills do)"),
          as_json: bool = typer.Option(False, "--json", help="Machine-readable output (for the skills)")):
    """Whether a buy or sell breaks any of your active rules, comes close or complies, rule by rule, with the
    numbers and the way to comply. Exit code 0 whatever the verdicts: a check that finds breaks has succeeded."""
    from .. import rulecheck
    from ..errors import Invalid
    from ..market import Market

    a = amount.strip().lower()
    action: dict = {"side": side, "ticker": ticker, "portfolio": portfolio, "style": style, "horizon": horizon,
                    "date": day, "price": price}
    if a in ("all", "half"):
        action["fraction"] = 1.0 if a == "all" else 0.5
    elif a.endswith("sh"):
        action["quantity"] = float(a[:-2])
    elif side.lower() == "sell" and 0 < float(a) <= 1:
        action["fraction"] = float(a)
    else:
        action["amount_dkk"] = float(a)
    try:
        r = rulecheck.check(Market.load(), action, log=log)
    except Invalid as e:
        raise SystemExit(str(e)) from None
    if as_json:
        typer.echo(to_json(r, indent=1, ensure_ascii=False))
        return
    act = r["action"]
    value = "–" if act["amount_dkk"] is None else f"{act['amount_dkk']:,.0f} DKK".replace(",", ".")
    typer.echo(f"{act['side'].upper()} {act['symbol']} in {act['portfolio']} on {act['date']}: {value}"
               + (f" ({act['quantity']:g} at {act['price']:.2f} {act['currency'] or ''})"
                  if act["quantity"] and act["price"] else ""))
    typer.echo(f"  {r['disclaimer']}")
    for n in r["notes"]:
        typer.echo(f"  note: {n}")
    if not r["verdicts"]:
        typer.echo("No active rules.")
        return
    _print_rows(r["verdicts"])
    if r["check_id"]:
        typer.echo(f"Logged as check {r['check_id']}.")


@rules_app.command("standing")
def standing(as_json: bool = typer.Option(False, "--json", help="Machine-readable output (for the skills)")):
    """What your portfolios break right now, without any action: name and theme caps, the core floor, the number
    of names."""
    from .. import rulecheck
    from ..market import Market

    r = rulecheck.standing(Market.load())
    if as_json:
        typer.echo(to_json(r, indent=1, ensure_ascii=False))
        return
    typer.echo(r["disclaimer"])
    if not r["rows"]:
        typer.echo("Nothing you hold breaks or is close to a rule.")
    _print_rows(r["rows"])
    for n in r["notes"]:
        typer.echo(f"  note: {n}")


@rules_app.command("add")
def add(from_json: Path = typer.Option(..., "--from-json", help="A JSON file with one rule or a list of rules "
                                                                 "(statement, kind, params, scope, severity, "
                                                                 "rationale)")):
    """Add rules from JSON (the /rules skill writes only after you have confirmed each one)."""
    from .. import trading_rules as tr
    from ..errors import Invalid
    from ..userstore import rulestore

    raw = json.loads(from_json.read_text(encoding="utf-8"))
    try:
        rows = [tr.validate(r) for r in (raw if isinstance(raw, list) else [raw])]
    except Invalid as e:
        raise SystemExit(str(e)) from None
    for r in rows:
        typer.echo(f"Added rule #{rulestore.save_rule(r)}: {r['statement']}")


@rules_app.command("decision")
def decision(check_id: int = typer.Argument(..., help="The logged check's id"),
             what: str = typer.Argument(..., help="went_ahead, changed or dropped"),
             reason: str = typer.Option(None, "--reason", help="Why (when going ahead against a rule)")):
    """What you did after a logged check, and why."""
    from ..userstore import rulestore

    try:
        ok = rulestore.set_decision(check_id, what, reason)
    except ValueError as e:
        raise SystemExit(str(e)) from None
    if not ok:
        raise SystemExit(f"No logged check {check_id}.")
    typer.echo(f"Check {check_id}: {what}.")


@rules_app.command("replay")
def replay(start: str = typer.Option(None, "--start", help="From this trade date (YYYY-MM-DD)"),
           end: str = typer.Option(None, "--end", help="To this trade date"),
           as_json: bool = typer.Option(False, "--json", help="Machine-readable output (for the skills)")):
    """Would your rules have helped? Your real trades, each checked against today's rules as of its own day, and
    what the name did afterwards against ACWI. Descriptive and small-n: no significance is claimed."""
    from .. import rulecheck
    from ..market import Market
    from .common import fmt_pct

    r = rulecheck.replay(Market.load(), start, end)
    if as_json:
        typer.echo(to_json(r, indent=1, ensure_ascii=False))
        return
    typer.echo(f"{r['n_trades']} trades replayed against {len({x['rule_id'] for x in r['rules']})} rules.")
    typer.echo(f"  {r['note']}")
    for x in r["rules"]:
        typer.echo(f"\n#{x['rule_id']} [{x['severity']}] {x['statement']} ({x['side']}s)")
        typer.echo(f"  flagged {x['n_flagged']} (afterwards vs ACWI {fmt_pct(x['flagged_rel'])}), let through "
                   f"{x['n_passed']} ({fmt_pct(x['passed_rel'])}), unknown {x['n_unknown']}")
        for f in x["flagged"]:
            typer.echo(f"    {f['date']} {f['symbol']}: {f['status']}, afterwards vs ACWI {fmt_pct(f['rel'])}")
