"""`radar tax …`: the tax estimate for an income year, and its inputs (persons, instruments, openings)."""
from datetime import date

import typer

from ..market import Market
from ..portfolios import trades
from .common import one_portfolio, to_json
from .root import app

tax_app = typer.Typer(help="The Danish tax estimate per account and person, and what it needs from you (an estimate, "
                           "not tax advice: your årsopgørelse wins).", no_args_is_help=True)
app.add_typer(tax_app, name="tax")


def _dkk(x) -> str:
    return "–" if x is None else f"{x:,.0f}".replace(",", ".")


def _person(name: str) -> dict:
    from .. import userstore

    p = next((x for x in userstore.tax_persons() if x["name"].lower() == name.strip().lower()), None)
    if not p:
        raise SystemExit(f"No tax person called {name!r}: see `radar tax person list`.")
    return p


@tax_app.command("year")
def year(year_: int = typer.Argument(None, metavar="YEAR", help="Income year (default: this year)"),
         portfolio: list[str] = typer.Option(None, "--portfolio", help="Only this account (repeatable)"),
         person: str = typer.Option(None, "--person", help="Only this tax person's accounts"),
         as_json: bool = typer.Option(False, "--json", help="The TaxYearView as JSON (for the skills)")):
    """The estimate for a year: each aktiesparekonto's and pension account's pool, and each person's share income
    (realised gains, dividends, positive-list lager, the loss rules, the progression limit) and capital income
    from their frie midler accounts. Holdings the radar can't classify are listed and left out."""
    from .. import tax as taxes

    trades.ensure_migrated()
    ids = [one_portfolio(n)["id"] for n in portfolio] if portfolio else None
    pid = _person(person)["id"] if person else None
    v = taxes.year_report(Market.load(), year_ or date.today().year, ids, pid)
    if as_json:
        typer.echo(to_json(v, indent=1))
        return
    r = v["rules"]
    typer.echo(f"Tax estimate for {v['year']} (data to {v['asof']}); rules "
               + (f"checked {r['verified']}" if r else "missing for this year"))
    typer.echo(f"  {v['disclaimer']}")
    for p in v["persons"]:
        si, ci = p["share_income"], p["capital_income"]
        typer.echo(f"\n{p['name']} (frie midler: {', '.join(p['accounts'])})")
        if si:
            typer.echo(f"  Share income {_dkk(si['net'])} of the limit {_dkk(si['limit'])}: tax {_dkk(si['tax'])} "
                       f"({_dkk(si['tax_low'])} at the low rate, {_dkk(si['tax_high'])} above the limit)")
            typer.echo(f"  realised {_dkk(si['realised_gains'])} gains / {_dkk(si['realised_losses'])} losses, "
                       f"dividends {_dkk(si['dividends'])}, positive-list lager {_dkk(si['pl_gains'] - si['pl_losses'])}; "
                       f"carried out: listed losses {_dkk(si['listed_loss_out'])}, negative {_dkk(si['negative_out'])}")
        elif p["bases"]:
            b = p["bases"]
            typer.echo(f"  realised {_dkk(b['realised_gains'])} gains / {_dkk(b['realised_losses'])} losses, "
                       f"dividends {_dkk(b['dividends'])}, positive-list lager {_dkk(b['pl_gains'] - b['pl_losses'])}")
        if ci:
            typer.echo(f"  Capital income {_dkk(ci['base'])}: tax {_dkk(ci['tax'])}")
        for n in p["notes"]:
            typer.echo(f"  · {n}")
    for a in v["accounts"]:
        typer.echo(f"\n{a['name']} ({a['kind']})")
        pool = a["pool"]
        if pool:
            typer.echo(f"  return {_dkk(pool['ret'])} = {_dkk(pool['v_end'])} − {_dkk(pool['v_start'])} − deposits "
                       f"{_dkk(pool['deposits'])} + withdrawals {_dkk(pool['withdrawals'])}; tax {_dkk(pool['tax'])}, "
                       f"negative tax carried out {_dkk(pool['carried_out'])}")
        for s in a["realised"]:
            typer.echo(f"  sold {s['quantity']:g} {s['symbol']} {s['date']}: gain {_dkk(s['gain'])}")
        for x in a["lager"]:
            typer.echo(f"  lager {x['symbol']} ({x['tax_class']}): {_dkk(x['gain'])}")
        for w in a["warnings"]:
            typer.echo(f"  ! {w}")
        for n in a["notes"]:
            typer.echo(f"  · {n}")
    if v["unknown"]:
        typer.echo("\nNot in the estimate (unknown classification):")
        for u in v["unknown"]:
            typer.echo(f"  {u['symbol']} in {u['portfolio']}, {_dkk(u['value_dkk'])} DKK: {u['reason']}")
    for n in v["notes"]:
        typer.echo(f"  · {n}")


@tax_app.command("classify")
def classify(symbol: str = typer.Argument(None, help="Set this symbol's class (with CLASS)"),
             cls: str = typer.Argument(None, metavar="CLASS", help="stock | pl_fund | fund | dk_distributing | auto"),
             year_: int = typer.Option(None, "--year", help="Show the classes in this year (default: this year)"),
             unknown: bool = typer.Option(False, "--unknown", help="Only the holdings the radar can't classify")):
    """The instruments your real accounts have traded, with ISIN, source and class in a year; or set a symbol's
    class by hand (`auto`: from its ISIN and the positive list again)."""
    from .. import userstore
    from ..portfolios import taxinputs
    from ..sources import positive_list

    if symbol and cls:
        try:
            userstore.save_instrument(symbol, "manual", tax_class=None if cls == "auto" else cls)
        except ValueError as e:
            raise SystemExit(str(e)) from None
        typer.echo(f"{symbol.upper()}: {cls}")
        return
    trades.ensure_migrated()
    real = [p["id"] for p in userstore.portfolios() if p["mode"] == "real"]      # simulations pay no tax
    syms = sorted({t["symbol"] for t in userstore.transactions(portfolios=real) if t["symbol"]}) if real else []
    inst = taxinputs.fill_instruments(syms)
    years, y = positive_list.load_years(), year_ or date.today().year
    for s in syms:
        k, why = taxinputs.classify(s, y, inst.get(s), years, taxinputs.security_kind(s))
        if unknown and k != taxinputs.UNKNOWN:
            continue
        i = inst.get(s) or {}
        typer.echo(f"  {s:<12} {i.get('isin') or '–':<13} {k:<16} {i.get('source') or '':<10} {why or ''}")


@tax_app.command("isin")
def isin(symbol: str, code: str = typer.Argument(..., metavar="ISIN")):
    """Set a symbol's ISIN by hand (it decides the positive-list status of a fund)."""
    from .. import userstore

    try:
        userstore.save_instrument(symbol, "manual", isin=code)
    except ValueError as e:
        raise SystemExit(str(e)) from None
    typer.echo(f"{symbol.upper()}: {code.upper()}")


@tax_app.command("person")
def person(action: str = typer.Argument("list", help="list | add | set"),
           name: str = typer.Argument(None, help="The person's name"),
           rate: float = typer.Option(None, "--capital-rate", help="Marginal rate on capital income, e.g. 0.37"),
           account: list[str] = typer.Option(None, "--account", help="With set: this account belongs to the person"),
           rename: str = typer.Option(None, "--rename", help="With set: a new name")):
    """Tax persons: who owns which account (SKAT's average is per person over their frie midler accounts)."""
    from .. import userstore

    if action == "list":
        names = {p["id"]: p["name"] for p in userstore.portfolios()}
        for p in userstore.tax_persons():
            r = "–" if p["capital_income_rate"] is None else f"{p['capital_income_rate']:.0%}"
            typer.echo(f"  {p['name']:<16} capital-income rate {r:<5} {', '.join(names[i] for i in p['portfolio_ids'])}")
        return
    if not name:
        raise SystemExit("Name the person.")
    try:
        if action == "add":
            pid = userstore.save_tax_person({"name": name, "capital_income_rate": rate})
        elif action == "set":
            pid = _person(name)["id"]
            vals: dict[str, object] = {"name": rename} if rename else {}
            if rate is not None:
                vals["capital_income_rate"] = rate
            userstore.save_tax_person(vals, pid)
        else:
            raise SystemExit("Action: list, add or set.")
        for a in account or []:
            userstore.save_portfolio({"tax_person_id": pid}, one_portfolio(a)["id"])
    except ValueError as e:
        raise SystemExit(str(e)) from None
    typer.echo(f"Saved {rename or name}.")


@tax_app.command("opening")
def opening(action: str = typer.Argument("list", help="list | add | remove"),
            pool: str = typer.Option(None, "--pool", help="ask_negative_tax | pension_negative_tax | listed_loss | "
                                                         "negative_share_income"),
            year_: int = typer.Option(None, "--year", help="The year it is carried into"),
            amount: float = typer.Option(None, "--amount", help="DKK"),
            portfolio: str = typer.Option(None, "--portfolio", help="The account (ASK or pension pools)"),
            person_: str = typer.Option(None, "--person", help="The person (listed losses, negative share income)"),
            oid: int = typer.Option(None, "--id", help="With remove: the opening's id"),
            note: str = typer.Option(None, "--note")):
    """Losses carried in, from your årsopgørelse for the year before: an ASK's or pension's negative tax, a person's
    listed-share loss or negative share income. An opening replaces the radar's own chain from its year (a person's
    pool not entered carries 0), so one from your last årsopgørelse is enough; 0 says nothing is carried."""
    from .. import userstore

    if action == "list":
        for o in userstore.tax_openings():
            typer.echo(f"  #{o['id']} {o['year']} {o['pool']:<22} {_dkk(o['amount']):>10} {o['note'] or ''}")
        return
    try:
        if action == "add":
            oid = userstore.add_tax_opening({
                "year": year_, "pool": pool, "amount": amount, "note": note,
                "portfolio_id": one_portfolio(portfolio)["id"] if portfolio else None,
                "tax_person_id": _person(person_)["id"] if person_ else None})
            typer.echo(f"Added opening #{oid}.")
        elif action == "remove":
            if oid is None or not userstore.delete_tax_opening(oid):
                raise SystemExit("No such opening: see `radar tax opening list`.")
            typer.echo(f"Removed opening #{oid}.")
        else:
            raise SystemExit("Action: list, add or remove.")
    except ValueError as e:
        raise SystemExit(str(e)) from None
