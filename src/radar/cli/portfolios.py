"""Your portfolios and their transactions: the Yahoo import, `radar portfolio …`, returns over time, `radar portfolios …`."""
import typer

from .. import importers
from ..market import Market
from ..portfolios import trades
from .common import one_portfolio, portfolio_ids, to_json
from .root import app


@app.command(name="import-yahoo")
def import_yahoo(csv_path: str):
    """Import a Yahoo Finance portfolio CSV export as holdings/watchlist."""
    try:
        df, warnings = importers.import_yahoo_csv(csv_path)
    except ValueError as e:                                # not a Yahoo export, or rows that can't be read
        raise SystemExit(str(e))
    counts = df["status"].value_counts()
    typer.echo(f"Imported {counts.get('holding', 0)} holdings, {counts.get('sold', 0)} sold positions, "
               f"{counts.get('watch', 0)} watchlist names.")
    for sym, msgs in warnings.items():
        for m in msgs:
            typer.echo(f"  ! {sym}: {m}")
    typer.echo("Run `radar run` to fetch prices for any new symbols.")


portfolio_app = typer.Typer(help="Your transactions (the portfolio store): list, add, export.")


app.add_typer(portfolio_app, name="portfolio")


@portfolio_app.command("list")
def portfolio_list(symbol: str = typer.Option(None, help="Only this ticker"),
                   portfolio: list[str] = typer.Option(None, "--portfolio", help="Only these portfolios (repeatable; "
                                                       "default: your real ones)"),
                   tag: list[str] = typer.Option(None, "--tag", help="Portfolios carrying this tag"),
                   account: str = typer.Option(None, "--account", hidden=True)):
    """Stored transactions, oldest first."""
    from .. import userstore

    trades.ensure_migrated()
    names = [*(portfolio or []), *([account] if account else [])]
    sel = portfolio_ids(names, tag) if (names or tag) else userstore.portfolio_ids()
    rows = userstore.transactions(symbol.upper() if symbol else None, sel)
    for t in rows:
        what = (f"{t['quantity']:>10g} {t['symbol']:<12} @ {t['price']:<10g} fee {t['fee']:<6g}"
                if t["type"] in ("BUY", "SELL") else f"{t['amount']:>10g} {t['currency'] or 'DKK':<12} {t['symbol'] or '':<19}")
        typer.echo(f"{t['id']:>5}  {t['date']}  {t['type']:<8} {what} {t['portfolio']:<16} {t['source']}")
    typer.echo(f"{len(rows)} transactions.")


@portfolio_app.command("add")
def portfolio_add(type_: str = typer.Argument(..., metavar="BUY|SELL"), symbol: str = typer.Argument(...),
                  quantity: float = typer.Argument(...), price: float = typer.Argument(...),
                  date: str = typer.Option(None, help="Trade date YYYY-MM-DD (default: today)"),
                  fee: float = typer.Option(0.0, help="Commission, in the price's currency"),
                  portfolio_name: str = typer.Option(None, "--portfolio", help="e.g. ASK or 'frie midler' (default: "
                                                     "the default portfolio; see `radar portfolios list`)"),
                  account: str = typer.Option(None, "--account", hidden=True),
                  note: str = typer.Option(None),
                  yes: bool = typer.Option(False, "--yes", help="Save despite warnings (errors always block)")):
    """Add one trade, checked the same way as in the app."""
    from datetime import date as _date

    from .. import profile, userstore
    from ..portfolios import checks

    trades.ensure_migrated()
    symbol = symbol.strip().upper()
    row = {"symbol": symbol, "date": date or _date.today().isoformat(), "type": type_.upper(),
           "quantity": quantity, "price": price, "fee": fee, "portfolio": portfolio_name or account, "note": note}
    try:
        market = profile.ensure_prices(symbol)
    except profile.TickerNotFound as e:
        raise SystemExit(str(e))
    from ..errors import Invalid

    try:
        issues = checks.checked(row, market, confirm=yes)
    except Invalid as e:
        issues = e.issues
    for i in issues:
        typer.echo(f"  {i['level'].upper()}: {i['message']}")
    blocked = any(i["level"] == "error" for i in issues)
    if blocked or (issues and not yes):
        raise SystemExit("Not saved." + ("" if blocked else " Add --yes to save anyway."))
    tx_id = userstore.add_tx(row)
    eff = checks.effect(row, exclude_id=tx_id)
    saved = userstore.get_tx(tx_id) or {}
    typer.echo(f"Saved #{tx_id} in {saved.get('portfolio')}. {symbol}: {eff['before']['quantity']:g} → "
               f"{eff['after']['quantity']:g} shares.")


@portfolio_app.command("export")
def portfolio_export(out: str = typer.Option(None, "--out", help="Write to this file instead of printing"),
                     portfolio: list[str] = typer.Option(None, "--portfolio", help="Only these portfolios (repeatable)"),
                     all_: bool = typer.Option(False, "--all", help="Virtual portfolios too")):
    """Transactions as CSV (a backup): your real portfolios unless chosen otherwise."""
    from pathlib import Path

    from .. import userstore

    trades.ensure_migrated()
    sel = portfolio_ids(portfolio, None) if portfolio else (userstore.portfolio_ids("all", include_archived=True)
                                                              if all_ else None)
    text = userstore.export_transactions_csv(sel)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        typer.echo(f"Wrote {out}.")
    else:
        typer.echo(text, nl=False)


@app.command()
def performance(names: list[str] = typer.Argument(None, help="Portfolio names (default: each of your real portfolios)"),
                tag: list[str] = typer.Option(None, "--tag", help="A tag group, pooled into one line (repeatable)"),
                start: str = typer.Option(None, help="Compare from this date (default: the latest first day)"),
                as_json: bool = typer.Option(False, "--json", help="As JSON")):
    """Portfolio returns in DKK against ACWI: time-weighted (the investments) and money-weighted (your timing),
    side by side from a common start. Virtual portfolios and tag groups only when named."""

    from .. import userstore
    from ..portfolios import performance as perf

    trades.ensure_migrated()
    ids = portfolio_ids(names, None) if names else userstore.compared_ids()
    res = perf.compare(Market.load(), ids, tag, start)
    if as_json:
        typer.echo(to_json(res, indent=1))
        return
    pct = lambda v: f"{v:+.1%}" if v is not None else "–"  # noqa: E731
    typer.echo(f"From {res['start']} to {res['asof']} (DKK; ACWI given the same cash flows)")
    typer.echo(f"{'':<22}{'value':>12} {'TWR':>8} {'p.a.':>8} {'MWR p.a.':>9} {'ACWI':>8} {'vs ACWI':>8} {'max DD':>8}")
    for r in res["rows"]:
        st = r["stats"] or {}
        v = f"{st['value_dkk']:,.0f}" if st.get("value_dkk") is not None else "–"
        typer.echo(f"{r['label'][:21]:<22}{v:>12} {pct(st.get('twr_total')):>8} {pct(st.get('twr_ann')):>8} "
                   f"{pct(st.get('mwr_ann')):>9} {pct(st.get('acwi_twr_total')):>8} {pct(st.get('excess_twr')):>8} "
                   f"{pct(st.get('max_drawdown')):>8}")
        if st.get("start") and st["start"] != res["start"]:
            typer.echo(f"    · from {st['start']}")
        for n in r["notes"] + r["missing"]:
            typer.echo(f"    · {n}")


portfolios_app = typer.Typer(help="Your portfolios: real ones (your accounts) and virtual ones (simulations, A/B "
                                  "tests), with tags. Only real ones count as yours unless chosen.")


app.add_typer(portfolios_app, name="portfolios")


@portfolios_app.command("list")
def portfolios_list(as_json: bool = typer.Option(False, "--json", help="As JSON (for the skills)"),
                    archived: bool = typer.Option(False, "--archived", help="Archived ones too")):
    """Every portfolio: mode, tax kind, tags and how many rows it has."""
    import json

    from .. import userstore

    trades.ensure_migrated()
    rows = userstore.portfolios(include_archived=archived)
    if as_json:
        typer.echo(json.dumps(rows, indent=1, ensure_ascii=False))
        return
    for p in rows:
        flags = "".join([" (default)" if p["is_default"] else "", " (archived)" if p["archived"] else ""])
        tags = f"  #{' #'.join(p['tags'])}" if p["tags"] else ""
        typer.echo(f"{p['name']:<20} {p['mode']:<8} {p['kind']:<12} {p['n_tx']:>5} rows{flags}{tags}")


@portfolios_app.command("add")
def portfolios_add(name: str, virtual: bool = typer.Option(False, "--virtual", help="A simulation / test, not yours"),
                   kind: str = typer.Option("other", help="Tax kind: ask | frie_midler | pension | other"),
                   tag: list[str] = typer.Option(None, "--tag", help="A tag (repeatable)"),
                   note: str = typer.Option(None)):
    """Add a portfolio."""
    from .. import userstore

    try:
        userstore.save_portfolio({"name": name, "mode": "virtual" if virtual else "real", "kind": kind,
                                  "note": note, "tags": tag or []})
    except ValueError as e:
        raise SystemExit(f"Not added: {e}.")
    typer.echo(f"Added {name} ({'virtual' if virtual else 'real'}, {kind}).")


@portfolios_app.command("edit")
def portfolios_edit(name: str, rename: str = typer.Option(None, help="New name"),
                    kind: str = typer.Option(None, help="ask | frie_midler | pension | other"),
                    dividends: str = typer.Option(None, help="reinvested | cash"),
                    note: str = typer.Option(None)):
    """Rename a portfolio or change its tax kind, dividend policy or note."""
    from .. import userstore

    p = one_portfolio(name)
    change = {k: v for k, v in {"name": rename, "kind": kind, "dividends": dividends, "note": note}.items() if v}
    try:
        userstore.save_portfolio(change, p["id"])
    except ValueError as e:
        raise SystemExit(f"Not changed: {e}.")
    typer.echo(f"Updated {rename or name}.")


@portfolios_app.command("tag")
def portfolios_tag(name: str, tags: list[str]):
    """Add tags to a portfolio."""
    from .. import userstore

    p = one_portfolio(name)
    typer.echo(f"{name}: #{' #'.join(userstore.set_tags(p['id'], [*p['tags'], *tags]))}")


@portfolios_app.command("untag")
def portfolios_untag(name: str, tags: list[str]):
    """Remove tags from a portfolio."""
    from .. import userstore

    p = one_portfolio(name)
    drop = {userstore.norm_tag(t) for t in tags}
    left = userstore.set_tags(p["id"], [t for t in p["tags"] if t not in drop])
    typer.echo(f"{name}: " + (f"#{' #'.join(left)}" if left else "no tags"))


@portfolios_app.command("default")
def portfolios_default(name: str):
    """Make a real portfolio the one new trades and imports go into."""
    from .. import userstore

    try:
        userstore.set_default_portfolio(one_portfolio(name)["id"])
    except ValueError as e:
        raise SystemExit(str(e))
    typer.echo(f"{name} is now the default portfolio.")


@portfolios_app.command("move")
def portfolios_move(name: str, to: str = typer.Option(..., "--to", help="The portfolio to move to"),
                    symbol: list[str] = typer.Option(None, "--symbol", help="Only this ticker (repeatable)")):
    """Move trades to another portfolio (e.g. from Main to ASK). Refused if a sale would lose its buy."""
    from .. import userstore
    from ..portfolios import checks

    src, dst = one_portfolio(name), one_portfolio(to)
    symbols = [s.strip().upper() for s in symbol] if symbol else None
    problems = checks.check_move(src["id"], dst["id"], None, symbols)
    if problems:
        raise SystemExit("Not moved: " + "; ".join(problems[:5]))
    typer.echo(f"Moved {userstore.move_transactions(src['id'], dst['id'], None, symbols)} rows to {to}.")


@portfolios_app.command("fork")
def portfolios_fork(name: str, new_name: str, date: str = typer.Option(..., "--date", help="Copy it as it stood at this day's close"),
                    cash: float = typer.Option(0.0, "--cash", help="Extra cash (DKK) to put in the copy"),
                    tag: list[str] = typer.Option(None, "--tag", help="A tag for the copy (repeatable)")):
    """A virtual copy of a portfolio at a day's close, to A/B-test changes against the original from there on."""
    from ..portfolios import simulate

    try:
        simulate.fork(one_portfolio(name)["id"], new_name, date, Market.load(), cash, tag or [])
    except ValueError as e:
        raise SystemExit(f"Not forked: {e}")
    typer.echo(f"Forked {name} into {new_name} (virtual). Compare: radar performance {name!r} {new_name!r} --start {date}")


@portfolios_app.command("archive")
def portfolios_archive(name: str, undo: bool = typer.Option(False, "--undo", help="Bring it back")):
    """Archive a portfolio: it keeps its rows but no longer counts as yours by default."""
    from .. import userstore

    userstore.save_portfolio({"archived": not undo}, one_portfolio(name)["id"])
    typer.echo(f"{name} {'is back' if undo else 'is archived'}.")


@portfolios_app.command("delete")
def portfolios_delete(name: str, yes: bool = typer.Option(False, "--yes", help="Don't ask")):
    """Delete a virtual portfolio with its rows (a backup is taken first), or an empty real one."""
    from .. import userstore

    p = one_portfolio(name)
    if p["n_tx"] and not yes:
        typer.confirm(f"Delete {name} and its {p['n_tx']} rows?", abort=True)
    try:
        userstore.delete_portfolio(p["id"])
    except ValueError as e:
        raise SystemExit(str(e))
    typer.echo(f"Deleted {name}.")
