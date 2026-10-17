"""`radar fundamentals …`: financial statements from SEC EDGAR and Yahoo."""
import typer

from .. import sourcelog
from .common import job, to_json
from .root import app

fundamentals_app = typer.Typer(help="Financial statements: SEC EDGAR (US) and Yahoo (all tracked stocks).",
                               no_args_is_help=True)


app.add_typer(fundamentals_app, name="fundamentals")


@fundamentals_app.command("update")
def fundamentals_update(tickers: list[str] = typer.Argument(None, help="Only these tickers (default: those due)"),
                        source: str = typer.Option("all", help="edgar, yahoo or all"),
                        all_: bool = typer.Option(False, "--all", help="Every tracked stock, due or not (slow)")):
    """Fetch statements now: the companies that are due (a new report expected, or not fetched for a while), the
    tickers named, or with --all every one. `radar update` fetches the due ones each day."""
    from functools import partial

    from .. import ops, universe, userstore
    from ..fundamentals import edgar, yahoo

    stocks = universe.tracked_stocks()
    steps = {"fundamentals_edgar": ("SEC EDGAR", partial(edgar.update_edgar, stocks, userstore.sec_contact())),
             "fundamentals_yahoo": ("Yahoo", partial(yahoo.update_yahoo, stocks))}
    if source != "all":
        steps = {k: v for k, v in steps.items() if k.endswith(source)}
        if not steps:
            raise typer.Exit("--source is edgar, yahoo or all")
    failed = False
    with job("fundamentals") as log:
        for key, (label, fn) in steps.items():
            try:
                with ops.context(source=key):
                    msg = fn(force=all_, tickers=[t.upper() for t in tickers] if tickers else None)
                log(f"{label}: {msg}.")
                sourcelog.record(key, True, msg)
            except Exception as e:  # noqa: BLE001 (report it and go on to the other source)
                failed = True
                log(f"{label}: FAILED ({type(e).__name__}: {e})")
                sourcelog.record(key, False, error=f"{type(e).__name__}: {e}", exc=e)
    raise typer.Exit(1 if failed else 0)


def _fmt_value(v) -> str:
    if v is None:
        return "–"
    a = abs(v.value)
    s = f"{v.value / 1e9:,.2f} bn" if a >= 1e8 else f"{v.value / 1e6:,.1f} m" if a >= 1e5 else f"{v.value:,.2f}"
    return f"{s} {v.currency or ''}".strip()


@fundamentals_app.command("show")
def fundamentals_show(ticker: str, as_json: bool = typer.Option(False, "--json", help="As JSON")):
    """One ticker's statement items as they are read: the last twelve months of each flow (and how it was built),
    the latest balance, the fiscal years stored and the source's name for each value."""

    from .. import fundamentals
    from ..fundamentals import items, store

    t = ticker.upper()
    f = fundamentals.facts(t)
    if f.empty:
        raise typer.Exit(f"No statements stored for {t}: is it tracked? Fetch them with `radar fundamentals update {t}`.")
    rows = []
    for it in items.ITEMS:
        v = store.ttm(f, it.key) if it.flow else store.instant(f, it.key)
        rows.append({"item": it.key, "value": None if v is None else v.value,
                     "end": None if v is None else f"{v.end:%Y-%m-%d}", "basis": None if v is None else v.basis,
                     "tag": None if v is None else v.tag, "currency": None if v is None else v.currency,
                     "fiscal_years": len(store.annual(f, it.key)), "_v": v})
    src = f["source"].iloc[0]
    if as_json:
        out = {"ticker": t, "source": src, "latest_end": f"{store.latest_end(f):%Y-%m-%d}",
               "items": [{k: v for k, v in r.items() if k != "_v"} for r in rows]}
        typer.echo(to_json(out, indent=1))
        return
    typer.echo(f"{t}: {'SEC EDGAR' if src == 'edgar' else 'Yahoo'}; latest period {store.latest_end(f):%d %b %Y}")
    typer.echo(f"  {'item':<20}{'value':>18}  {'period end':<11}{'basis':<10}{'years':>5}  tag")
    for r in rows:
        typer.echo(f"  {r['item']:<20}{_fmt_value(r['_v']):>18}  {r['end'] or '–':<11}{r['basis'] or '':<10}"
                   f"{r['fiscal_years']:>5}  {r['tag'] or ''}")


@fundamentals_app.command("check")
def fundamentals_check(tolerance: float = typer.Option(0.10, help="List differences larger than this share")):
    """US companies with both sources: SEC EDGAR against Yahoo for the last twelve months of revenue, operating
    income and operating cash flow, where both end on the same quarter. A large difference points at a mis-read
    tag or line."""
    from ..fundamentals import store

    e, y = store.load_edgar(), store.load_yahoo()
    both = sorted(set(e["ticker"]) & set(y["ticker"]))
    if not both:
        raise typer.Exit("No company has statements from both sources yet.")
    off, compared = [], 0
    for t in both:
        fe, fy = e[e["ticker"] == t], y[y["ticker"] == t]
        for item in ("revenue", "operating_income", "cfo"):
            a, b = store.ttm(fe, item), store.ttm(fy, item)
            if a is None or b is None or abs((a.end - b.end).days) > 20 or not b.value:
                continue
            compared += 1
            d = a.value / b.value - 1
            if abs(d) > tolerance:
                off.append((t, item, a, b, d))
    typer.echo(f"{len(both)} companies, {compared} comparisons; {len(off)} differ by more than {tolerance:.0%}:")
    for t, item, a, b, d in off:
        typer.echo(f"  {t:<8} {item:<17} EDGAR {_fmt_value(a)} ({a.tag}, {a.basis})  Yahoo {_fmt_value(b)} "
                   f"({b.tag}, {b.basis})  {d:+.0%}")


@fundamentals_app.command("contact")
def fundamentals_contact(email: str = typer.Argument(None, help="Your e-mail address"),
                         clear: bool = typer.Option(False, "--clear", help="Remove it (SEC EDGAR is then skipped)")):
    """The contact e-mail sent to SEC with each EDGAR request (SEC's fair-access rule asks automated clients to say
    who they are). Stored in your own database; without it, US statements come from Yahoo only."""
    from .. import userstore

    if clear:
        userstore.set_sec_contact(None)
        typer.echo("Removed: SEC EDGAR is skipped until a contact is set.")
        return
    if not email:
        c = userstore.sec_contact()
        typer.echo(f"SEC contact: {c}" if c else "No SEC contact set: radar fundamentals contact you@example.com")
        return
    try:
        typer.echo(f"SEC contact set to {userstore.set_sec_contact(email)}.")
    except ValueError as e:
        raise typer.Exit(str(e))
