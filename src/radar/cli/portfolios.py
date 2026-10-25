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


@app.command()
def xray(names: list[str] = typer.Argument(None, help="Portfolio names (default: your real portfolios)"),
         tag: list[str] = typer.Option(None, "--tag", help="Portfolios carrying this tag (repeatable)"),
         scope: str = typer.Option(None, "--scope", help="real | virtual | all, when no name or tag is given"),
         as_json: bool = typer.Option(False, "--json", help="The XrayView as JSON (for the skills)")):
    """The portfolio X-ray: exposure by sector, region and currency against ACWI, where the risk sits (ex-ante and
    realised), concentration and the stress windows, of the chosen portfolios pooled. Analysis, not advice."""
    from .. import userstore
    from .. import xray as xr

    trades.ensure_migrated()
    if scope and scope not in userstore.SCOPES:
        raise SystemExit(f"--scope must be one of {', '.join(userstore.SCOPES)}")
    ids = (portfolio_ids(names, tag) if (names or tag) else
           userstore.portfolio_ids(scope) if scope else None)
    v = xr.build(Market.load(), ids, scope)
    if as_json:
        typer.echo(to_json(v, indent=1))
        return
    pct = lambda x, signed=False: "–" if x is None else (f"{x:+.1%}" if signed else f"{x:.1%}")  # noqa: E731
    t = v["totals"]
    cash = f"{t['cash_dkk']:,.0f} DKK" if t["cash_dkk"] is not None else "unknown"
    typer.echo(f"X-ray of {', '.join(v['selection']['names']) or 'no portfolios'} as of {v['asof']}: "
               f"{t['invested_dkk']:,.0f} DKK invested, cash {cash}")
    for d, ex in v["exposure"].items():
        cov = f", coverage {pct(ex['coverage'])}" if ex["coverage"] is not None and ex["coverage"] < 1 else ""
        typer.echo(f"\n{d.capitalize()} (top active weights{cov})")
        typer.echo(f"  {'':<26}{'weight':>8} {'ACWI':>8} {'active':>8}")
        for r in ex["rows"][:6]:
            typer.echo(f"  {r['key'][:25]:<26}{pct(r['weight']):>8} {pct(r['acwi']):>8} {pct(r['active'], True):>8}")
    rk = v["risk"]
    if rk:
        typer.echo(f"\nRisk (ex-ante, {rk['window_weeks']} weeks, coverage {pct(rk['coverage'])}"
                   f"{', partial' if rk['warn'] else ''})")
        beta = f"{rk['beta']:.2f}" if rk["beta"] is not None else "–"
        div = f"{rk['div_ratio']:.2f}" if rk["div_ratio"] is not None else "–"
        typer.echo(f"  vol {pct(rk['vol_ann'])}  beta {beta}  tracking error {pct(rk['te_ann'])}  "
                   f"diversification ratio {div}")
        typer.echo(f"  realised last year: vol {pct(rk['realised_vol_1y'])}  max drawdown "
                   f"{pct(rk['realised_max_dd_1y'], True)}")
        typer.echo(f"  {'':<14}{'weight':>8} {'of risk':>8} {'of active':>10} {'MCTR':>8}")
        for p in rk["positions"][:5]:
            typer.echo(f"  {p['symbol'][:13]:<14}{pct(p['weight']):>8} {pct(p['share_total']):>8} "
                       f"{pct(p['share_active'], True):>10} {pct(p['mctr_ann']):>8}")
    c = v["concentration"]
    if c["effective_n"] is not None:
        largest = f"{c['largest']['symbol']} {pct(c['largest']['weight'])}"
        ctr = f", most risk: {c['largest_ctr']['symbol']} {pct(c['largest_ctr']['share'])}" if c["largest_ctr"] else ""
        typer.echo(f"\nConcentration: effective N {c['effective_n']:.1f}, top 5 {pct(c['top5_share'])}, "
                   f"largest {largest}{ctr}")
        for pr in c["pairs"]:
            typer.echo(f"  {pr['a']} & {pr['b']}: correlation {pr['corr']:.2f}, together {pct(pr['weight'])}")
    if v["stress"]:
        typer.echo(f"\nStress (today's weights)\n  {'':<30}{'return':>8} {'max DD':>8} {'ACWI':>8} {'coverage':>9}")
        for w in v["stress"]:
            typer.echo(f"  {w['label'][:29]:<30}{pct(w['ret'], True):>8} {pct(w['max_dd'], True):>8} "
                       f"{pct(w['acwi_ret'], True):>8} {pct(w['coverage']):>9}")
    if v["notes"]:
        typer.echo("")
    for n in v["notes"]:
        typer.echo(f"  · {n}")


@app.command()
def attribution(names: list[str] = typer.Argument(None, help="Portfolio names (default: your real portfolios)"),
                tag: list[str] = typer.Option(None, "--tag", help="Portfolios carrying this tag (repeatable)"),
                scope: str = typer.Option(None, "--scope", help="real | virtual | all, when no name or tag is given"),
                start: str = typer.Option(None, "--start", help="From this day, YYYY-MM-DD (default: the start)"),
                end: str = typer.Option(None, "--end", help="To this day, YYYY-MM-DD (default: the last close)"),
                as_json: bool = typer.Option(False, "--json", help="The AttributionView as JSON (for the skills)")):
    """Attribution vs ACWI: the active return split into trading and fees, benchmark proxies vs ACWI, allocation,
    selection and interaction by sector and by region, the currency effect, and the factor regression's alpha with
    its t, of the chosen portfolios pooled. Analysis, not advice."""
    from datetime import date as _date

    from .. import attribution as attr
    from .. import userstore

    trades.ensure_migrated()
    if scope and scope not in userstore.SCOPES:
        raise SystemExit(f"--scope must be one of {', '.join(userstore.SCOPES)}")
    for flag, d in (("--start", start), ("--end", end)):
        try:
            if d:
                _date.fromisoformat(d)
        except ValueError:
            raise SystemExit(f"{flag} must be a date, YYYY-MM-DD") from None
    ids = (portfolio_ids(names, tag) if (names or tag) else
           userstore.portfolio_ids(scope) if scope else None)
    v = attr.build(Market.load(), ids, scope, start, end)
    if as_json:
        typer.echo(to_json(v, indent=1))
        return
    pct = lambda x: "–" if x is None else f"{x:+.1%}"  # noqa: E731
    w = lambda x: "–" if x is None else f"{x:.1%}"  # noqa: E731
    p = v["period"]
    span = f" from {p['start']} to {p['end']} ({p['months']:.0f} months)" if p else ""
    typer.echo(f"Attribution of {', '.join(v['selection']['names']) or 'no portfolios'} vs ACWI{span} (DKK)")
    rec = v["reconciliation"]
    if rec:
        typer.echo(f"\n  TWR {pct(rec['twr'])}  ACWI {pct(rec['acwi'])}  active {pct(rec['active'])}")
        typer.echo(f"  = trading and fees {pct(rec['trading_fees'])} + benchmark proxies vs ACWI "
                   f"{pct(rec['proxy_vs_acwi'])} + attributed {pct(rec['attributed'])}")
    for dim, d in v["dims"].items():
        t = d["totals"]
        typer.echo(f"\nBy {dim} ({d['days']} days, {d['days_missing']} left out): allocation {pct(t['allocation'])}, "
                   f"selection {pct(t['selection'])}, interaction {pct(t['interaction'])}, currency "
                   f"{pct(t['currency'])}, cross {pct(t['cross'])}")
        typer.echo(f"  {'':<24}{'w':>7} {'ACWI w':>7} {'r':>8} {'ACWI r':>8} {'alloc':>7} {'select':>7} "
                   f"{'inter':>7} {'total':>7}")
        for r in d["rows"][:8]:
            typer.echo(f"  {r['key'][:23]:<24}{w(r['w_p']):>7} {w(r['w_b']):>7} {pct(r['r_p']):>8} "
                       f"{pct(r['r_b']):>8} {pct(r['allocation']):>7} {pct(r['selection']):>7} "
                       f"{pct(r['interaction']):>7} {pct(r['total']):>7}")
    c = v["currency"]
    if c:
        by = ", ".join(f"{r['currency']} {pct(r['effect'])}" for r in c["rows"][:5])
        typer.echo(f"\nCurrency effect {pct(c['effect'])} ({by}); cross term {pct(c['cross'])}")
    g = v["regression"]
    if g:
        t2 = ("reached" if g["reached"] else f"about {g['months_to_t2']:.0f} months more for t = 2"
              if g["months_to_t2"] is not None else "t = 2 out of reach")
        a_t = f"{g['alpha_t']:.2f}" if g["alpha_t"] is not None else "–"
        typer.echo(f"\nFactor regression ({g['n_weeks']} weeks, {g['start']} to {g['end']}, factors to "
                   f"{g['factors_to']}): alpha {pct(g['alpha_ann'])} p.a., t {a_t} ({t2})")
        typer.echo("  " + "  ".join(f"{f['factor']} {f['beta']:.2f}" if f["beta"] is not None else f"{f['factor']} –"
                                    for f in g["loadings"]))
    if v["unclassified"]:
        typer.echo("\nUnclassified: " + ", ".join(u["symbol"] for u in v["unclassified"]))
    if v["notes"]:
        typer.echo("")
    for n in v["notes"]:
        typer.echo(f"  · {n}")


@app.command()
def calendar(names: list[str] = typer.Argument(None, help="Portfolio names (default: your real portfolios)"),
             tag: list[str] = typer.Option(None, "--tag", help="Portfolios carrying this tag (repeatable)"),
             scope: str = typer.Option(None, "--scope", help="real | virtual | all, when no name or tag is given"),
             days: int = typer.Option(None, "--days", min=1, max=366, help="Window in days (default calendar.days)"),
             as_json: bool = typer.Option(False, "--json", help="The AgendaView as JSON (for the skills)")):
    """The calendar: earnings and ex-dividend dates of what you hold and watch, your journal reviews and the
    proposals' time stops, each with why it is highlighted. Dates are Yahoo's. Analysis, not advice."""
    from datetime import date as _date
    from datetime import timedelta

    from .. import agenda, userstore
    from ..reporting import dashboard

    trades.ensure_migrated()
    if scope and scope not in userstore.SCOPES:
        raise SystemExit(f"--scope must be one of {', '.join(userstore.SCOPES)}")
    d = dashboard.load()
    if d is None:
        raise SystemExit("No dashboard yet: run `uv run radar run` (or `radar report`) first.")
    ids = (portfolio_ids(names, tag) if (names or tag) else
           userstore.portfolio_ids(scope) if scope else userstore.portfolio_ids())
    v = agenda.collect(Market.load(), d, ids, scope, days)
    if as_json:
        typer.echo(to_json(v, indent=1))
        return
    by_id = {i["id"]: i for i in v["items"]}
    mark = {"high": "!", "normal": "·", "info": " "}

    def line(i):
        when = i["date"] + (f"–{i['date_end'][5:]}" if i["date_end"] else "")
        who = {"holding": "held", "watch": "watch", "own": "own"}[i["status"]]
        reasons = "; ".join(r["text"] for r in i["reasons"] if r["key"] != "held")
        return f"  {mark[i['level']]} {when:<17} {(i['symbol'] or '')[:10]:<11}{i['kind']:<12}{who:<6} {reasons}"

    typer.echo(f"Calendar of {', '.join(v['selection']['names']) or 'no portfolios'}: {v['days']} days from "
               f"{v['today']}")
    nxt = f"Next {v['soon_days']} days"
    typer.echo(f"\n{nxt} ({len(v['soon'])} to look at first)" if v["soon"] else f"\n{nxt}: nothing high")
    for k in v["soon"]:
        typer.echo(line(by_id[k]))
    week = None
    for i in v["items"]:
        d0 = _date.fromisoformat(i["date"])
        monday = d0 - timedelta(days=d0.weekday())
        if monday != week:
            week = monday
            typer.echo(f"\nWeek of {monday.isoformat()}")
        typer.echo(line(i))
    if v["no_date"]:
        typer.echo("\nNo earnings date known")
        for r in v["no_date"]:
            typer.echo(f"    {r['symbol']:<11}{r['status']:<8} {r['reason']}")
    if v["excluded_funds"]:
        typer.echo(f"\n{v['excluded_funds']} fund(s) left out: funds have no earnings")
    typer.echo("")
    for n in v["notes"]:
        typer.echo(f"  · {n}")


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
