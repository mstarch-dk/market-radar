"""The tax estimate for an income year (Danish rules; an estimate, not tax advice: the årsopgørelse wins).

For each real account: an aktiesparekonto or a pension account is one pool, lager-taxed on its whole return
(value at year end − value at the start − money in + money out) at the year's rate, with a losing year's negative
tax carried forward. For each tax person, over all their frie midler accounts together (SKAT's average is per
person): realised gains on shares by the average-cost method in DKK, dividends, lager on positive-list funds
(share income), lager on funds off the list (capital income), the loss rules and the progression limit.

Values are at traded closes (dividends are income, not price), in DKK at each day's rate; a trade's DKK rate is
its own, else Yahoo's that day. Carried amounts are chained from each account's first year; an opening entered by
hand is the årsopgørelse's figure and replaces the chain from its year (so a year without rules before it doesn't
leave every later year unknown). A year without verified rules gives the bases and no tax; a holding the radar
can't classify is named with its value and left out; a missing value is missing, never 0: a dividend the prices say
was paid on a holding but isn't booked leaves the dividends unknown, and an unclassified holding the capital
income. Computed live, nothing written. The arithmetic is in model/tax.py, the rules in portfolios/taxrules.py,
the classes in portfolios/taxinputs.py."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import TYPE_CHECKING, Any

import pandas as pd

from . import userstore
from .model import tax as tm
from .portfolios import performance, taxinputs, taxrules
from .sources import positive_list

if TYPE_CHECKING:
    from .market import Market

TAX_KINDS = ("ask", "frie_midler", "pension")
SHARE_CLASSES = ("stock", "dk_distributing")          # realisation, share income
LAGER_CLASSES = ("pl_fund", "fund")                   # lager: share income on the list, capital income off it
DISCLAIMER = "An estimate from the radar's own records, not tax advice: your årsopgørelse wins."
DIV_STEP = 5e-4        # a rise in the dividend factor (adjusted / traded close) above this marks an ex-dividend day
PAY_DAYS = 45          # a dividend is looked for this long after its ex-day; a younger ex-day may be unpaid


def _at(s: pd.Series | None, day: pd.Timestamp) -> float | None:
    """The value at the last session on or before `day`: 0 before the series starts (not held yet), None when
    unknown."""
    if s is None or s.empty or day < s.index[0]:
        return 0.0                                   # zero: nothing held before the first row
    v = s[s.index <= day]
    x = v.iloc[-1]
    return None if pd.isna(x) else float(x)


def _year_end(year: int, last: pd.Timestamp) -> pd.Timestamp:
    return min(pd.Timestamp(year, 12, 31), last)


def _in_year(day, year: int) -> bool:
    return pd.Timestamp(str(day)[:10]).year == year


def _opening(openings: list[dict], year: int, pools: tuple[str, ...], **owner: int) -> dict[str, float] | None:
    """The årsopgørelse's carried amounts into `year` for these pools and this owner (a pool not entered carries 0),
    or None when no opening is entered for that year."""
    rows = [o for o in openings if o["year"] == year and o["pool"] in pools
            and all(o.get(k) == v for k, v in owner.items())]
    if not rows:
        return None
    return {k: sum(o["amount"] for o in rows if o["pool"] == k) for k in pools}


def _carry_note(year: int, broke: int | None) -> str:
    where = f"{broke} has no estimate" if broke is not None else "an earlier year has no estimate"
    return (f"no tax: what is carried into {year} is unknown ({where}): enter what your årsopgørelse for {year - 1} "
            f"carries into {year} under Losses carried in (0 if nothing)")


def _rules(year: int):
    try:
        return taxrules.rules(year)
    except taxrules.NoRules:
        return None


class _Ctx:
    """What every part of one report reads: the rows, books, instruments, the positive list and the market."""

    def __init__(self, market: Market, ports: list[dict]):
        self.market = market
        self.last = pd.Timestamp(market.closes.index[-1])
        self.ports = ports
        self.rows = {p["id"]: userstore.transactions(portfolios=[p["id"]]) for p in ports}
        syms = {r["symbol"] for rs in self.rows.values() for r in rs if r["symbol"]}
        self.inst = taxinputs.fill_instruments(sorted(syms))
        self.years = positive_list.load_years()
        self.kinds = {s: taxinputs.security_kind(s) for s in syms}
        self.books = {p["id"]: performance.book(self.rows[p["id"]], market, "cash") for p in ports}
        self.fx: dict[str, Any] = {}

    def cls(self, sym: str, year: int) -> tuple[str, str | None]:
        return taxinputs.classify(sym, year, self.inst.get(sym), self.years, self.kinds.get(sym))

    def rate(self, row: dict) -> float | None:
        sym = row["symbol"]
        if sym not in self.fx:
            self.fx[sym] = performance.fx_series(self.market, sym)
        return performance.trade_fx(row, self.fx[sym])

    def trade(self, row: dict) -> tm.Trade:
        return tm.Trade(date.fromisoformat(str(row["date"])[:10]), row["type"], float(row["quantity"]),
                        float(row["price"]), float(row.get("fee") or 0.0), self.rate(row), ref=(row["portfolio_id"], row["id"]))

    def first_year(self, pid: int) -> int | None:
        days = [str(r["date"])[:4] for r in self.rows[pid]]
        return int(min(days)) if days else None


# ---------------- aktiesparekonto and pension: one pool per account ----------------

def _pool_rate(kind: str, rules) -> float:
    return rules.ask.rate if kind == "ask" else rules.pension.pal_rate


def _account_pool(c: _Ctx, p: dict, year: int, openings: list[dict]) -> tuple[dict | None, list[str]]:
    """The pool for `year`, chained from the account's first year (negative tax carried); an opening replaces the
    chain from its year."""
    b, first = c.books[p["id"]], c.first_year(p["id"])
    notes: list[str] = []
    if b is None or first is None or first > year:
        return None, ["no rows in or before this year"]
    pool = "ask_negative_tax" if p["kind"] == "ask" else "pension_negative_tax"
    carried: float | None = 0.0
    broke: int | None = None
    out = None
    for y in range(first, year + 1):
        anchor = _opening(openings, y, (pool,), portfolio_id=p["id"])
        if anchor is not None:
            carried = anchor[pool]                   # the årsopgørelse wins over the chain
        start, end = pd.Timestamp(y - 1, 12, 31), _year_end(y, c.last)
        v0, v1 = _at(b.value, start), _at(b.value, end)
        win = (b.value.index > start) & (b.value.index <= end)
        inflow, outflow = float(b.inflow[win].sum()), float(b.outflow[win].sum())
        r = _rules(y)
        if v0 is None or v1 is None or r is None or carried is None:
            why = "no rules for " + str(y) if r is None else f"the account's value at the end of {y - 1 if v0 is None else y} is unknown"
            if y == year:
                out = {"v_start": v0, "v_end": v1, "deposits": inflow, "withdrawals": outflow,
                       "ret": None if v0 is None or v1 is None else v1 - v0 - inflow + outflow,
                       "carried_in": carried, "rate": None if r is None else _pool_rate(p["kind"], r),
                       "gross_tax": None, "used": None, "tax": None, "carried_out": None}
                notes.append(f"no tax: {why}" if carried is not None else _carry_note(year, broke))
            if carried is not None:
                broke = y
            carried = None
            continue
        res = tm.account_pool(v0, v1, inflow, outflow, carried, _pool_rate(p["kind"], r))
        carried = res.carried_out
        if y == year:
            out = {"v_start": v0, "v_end": v1, "deposits": inflow, "withdrawals": outflow, "ret": res.ret,
                   "carried_in": res.carried_in, "rate": res.rate, "gross_tax": res.gross_tax, "used": res.used,
                   "tax": res.tax, "carried_out": res.carried_out}
    return out, notes


def _ask_warnings(c: _Ctx, p: dict, year: int) -> list[str]:
    out = []
    b = c.books[p["id"]]
    end = _year_end(year, c.last)
    pos = b.positions if b is not None else pd.DataFrame()
    held = [s for s in pos.columns if (_at(pos[s], end) or 0) > 0]          # zero: an unknown value isn't warned on
    for s in held:
        k, why = c.cls(s, year)
        if p["kind"] == "ask" and k == "fund":
            out.append(f"{s}: not on the {year} positive list, so an aktiesparekonto may not hold it")
        elif p["kind"] == "ask" and k == taxinputs.UNKNOWN and c.kinds.get(s) != "stock":
            out.append(f"{s}: {why}; an aktiesparekonto may hold only shares and positive-list funds")
    jan = [r for r in c.rows[p["id"]] if r["type"] == "FEE" and str(r["date"])[:7] == f"{year}-01"]
    if jan:
        out.append(f"{len(jan)} fee row(s) in January {year}: if one is the account's tax for {year - 1}, book it as "
                   "a withdrawal, or it counts as a loss in the account's return")
    return out


# ---------------- frie midler: one person over all their accounts ----------------

def _lager_rows(c: _Ctx, p: dict, year: int) -> list[dict]:
    """Lager per held fund in a frie midler account for the year."""
    b = c.books[p["id"]]
    if b is None:
        return []
    start, end = pd.Timestamp(year - 1, 12, 31), _year_end(year, c.last)
    out = []
    for sym in b.positions.columns:
        k, _ = c.cls(sym, year)
        if k not in LAGER_CLASSES:
            continue
        s = b.positions[sym]
        v0, v1 = _at(s, start), _at(s, end)
        trades_ = [c.trade(r) for r in c.rows[p["id"]] if r["symbol"] == sym and r["type"] in ("BUY", "SELL")
                   and start < pd.Timestamp(str(r["date"])[:10]) <= end]
        if not trades_ and not v0 and not v1:
            continue
        buys = [t.dkk for t in trades_ if t.kind == "BUY"]
        sales = [t.dkk for t in trades_ if t.kind == "SELL"]
        out.append({"symbol": sym, "tax_class": k, "v_start": v0, "v_end": v1,
                    "buys": None if any(x is None for x in buys) else sum(x for x in buys if x is not None),
                    "sales": None if any(x is None for x in sales) else sum(x for x in sales if x is not None),
                    "gain": tm.lager(v0, v1, buys, sales)})
    return out


def _realised(c: _Ctx, fm: list[dict]) -> dict[int, list[dict]]:
    """Every sale of a share in the person's frie midler accounts, by year, from one average per security."""
    by_sym: dict[str, list[tm.Trade]] = {}
    for p in fm:
        for r in c.rows[p["id"]]:
            if r["type"] in ("BUY", "SELL") and r["symbol"]:
                by_sym.setdefault(r["symbol"], []).append(c.trade(r))
    out: dict[int, list[dict]] = {}
    names = {p["id"]: p["name"] for p in fm}
    for sym, ts in sorted(by_sym.items()):
        rep = tm.replay_dkk(ts)
        for s in rep.sales:
            k, why = c.cls(sym, s.day.year)
            if k in LAGER_CLASSES:
                continue                             # a fund on lager: its sales are in the year's lager
            pid = s.ref[0] if isinstance(s.ref, tuple) else None
            out.setdefault(s.day.year, []).append({
                "symbol": sym, "date": s.day.isoformat(), "portfolio_id": pid, "portfolio": names.get(pid),
                "quantity": s.quantity, "proceeds": s.proceeds, "basis": s.basis, "gain": s.gain, "tax_class": k,
                "reason": why})
        for w in rep.warnings:
            out.setdefault(0, []).append({"warning": f"{sym}: {w}"})
    return out


def _dividends(c: _Ctx, fm: list[dict], year: int) -> list[dict]:
    out = []
    for p in fm:
        for r in c.rows[p["id"]]:
            if r["type"] == "DIVIDEND" and _in_year(r["date"], year):
                k, why = c.cls(r["symbol"], year)
                out.append({"symbol": r["symbol"], "date": str(r["date"])[:10], "portfolio_id": p["id"],
                            "portfolio": p["name"], "amount": float(r["amount"]), "tax_class": k, "reason": why})
    return out


def _missing_dividends(c: _Ctx, fm: list[dict], year: int) -> list[tuple[str, str]]:
    """Dividends the prices say were paid while no DIVIDEND row is booked, as (class, note). An ex-dividend day is a
    step up in the dividend factor (adjusted / traded close) on a day the account held the security (by its trades,
    so a gap in another holding's prices doesn't hide it); a booking from a week before to PAY_DAYS after counts, and
    an ex-day younger than PAY_DAYS may be unpaid, so it is skipped."""
    raw = c.market.raw_closes()
    if raw is None:
        return []
    booked: dict[str, list[pd.Timestamp]] = {}
    for p in fm:
        for r in c.rows[p["id"]]:
            if r["type"] == "DIVIDEND" and r["symbol"]:
                booked.setdefault(r["symbol"], []).append(pd.Timestamp(str(r["date"])[:10]))
    start, end = pd.Timestamp(year - 1, 12, 31), _year_end(year, c.last)
    wait, before = pd.Timedelta(days=PAY_DAYS), pd.Timedelta(days=7)
    out = []
    for p in fm:
        trades_: dict[str, list[tuple[pd.Timestamp, float]]] = {}
        for r in c.rows[p["id"]]:
            if r["type"] in ("BUY", "SELL") and r["symbol"]:
                q = float(r["quantity"]) * (1 if r["type"] == "BUY" else -1)
                trades_.setdefault(r["symbol"], []).append((pd.Timestamp(str(r["date"])[:10]), q))
        for sym, ts in sorted(trades_.items()):
            if sym not in raw or sym not in c.market.closes:
                continue
            f = (c.market.closes[sym] / raw[sym]).dropna()
            step = f / f.shift(1) - 1
            for d in step[(step > DIV_STEP) & (step.index > start) & (step.index <= end)].index:
                held = sum(q for t, q in ts if t < d)             # held at the close before the ex-day
                if held <= 1e-9 or d > c.last - wait:
                    continue
                if any(d - before <= x <= d + wait for x in booked.get(sym, [])):
                    continue
                out.append((c.cls(sym, year)[0], f"{sym} in {p['name']}: ex-dividend {d.date()} while held, but no "
                                                 "dividend is booked: add it, or the dividends stay unknown"))
    return out


def _person_year(c: _Ctx, person: dict, fm: list[dict], year: int, openings: list[dict]) -> dict:
    """The person's share and capital income for `year`, the carried losses chained from their first year; an
    opening (either pool) replaces the chain from its year."""
    realised = _realised(c, fm)
    firsts = [y for p in fm if (y := c.first_year(p["id"])) is not None]
    listed: float | None = 0.0
    negative: float | None = 0.0
    broke: int | None = None
    notes: list[str] = [w["warning"] for w in realised.get(0, [])]
    res: dict[str, Any] = {"share_income": None, "capital_income": None, "bases": None, "complete": False}
    for y in range(min(firsts) if firsts else year, year + 1):
        anchor = _opening(openings, y, ("listed_loss", "negative_share_income"), tax_person_id=person["id"])
        if anchor is not None:                       # the årsopgørelse wins over the chain
            listed, negative = anchor["listed_loss"], anchor["negative_share_income"]
        sales = realised.get(y, [])
        divs = _dividends(c, fm, y)
        unpaid = _missing_dividends(c, fm, y) if y == year else []
        lager = [dict(row, portfolio_id=p["id"], portfolio=p["name"]) for p in fm for row in _lager_rows(c, p, y)]
        known_sales = [s["gain"] for s in sales if s["tax_class"] in SHARE_CLASSES and s["gain"] is not None]
        share_div = sum(d["amount"] for d in divs if d["tax_class"] in (*SHARE_CLASSES, "pl_fund"))
        capital_div = sum(d["amount"] for d in divs if d["tax_class"] == "fund")
        pl = [x["gain"] for x in lager if x["tax_class"] == "pl_fund" and x["gain"] is not None]
        capital = sum(x["gain"] for x in lager if x["tax_class"] == "fund" and x["gain"] is not None) + capital_div
        missing = [f"{s['symbol']} sold {s['date']}: gain unknown (a trade's DKK rate is missing)"
                   for s in sales if s["tax_class"] in SHARE_CLASSES and s["gain"] is None]
        missing += [f"{x['symbol']} in {x['portfolio']}: lager unknown (a value or rate is missing)"
                    for x in lager if x["gain"] is None]
        unknown = [f"{s['symbol']} sold {s['date']}: {s['reason']}" for s in sales if s["tax_class"] == taxinputs.UNKNOWN]
        unknown += [f"{d['symbol']} dividend {d['date']}: {d['reason']}" for d in divs if d["tax_class"] == taxinputs.UNKNOWN]
        held_unknown = [u["symbol"] for u in _unknown_holdings(c, fm, y)] if y == year else []
        # capital income can't be told while a holding has no class, or a fund's lager or dividend is missing
        capital_open = (bool(unknown) or bool(held_unknown) or any(k == "fund" for k, _ in unpaid)
                        or any(x["gain"] is None for x in lager if x["tax_class"] == "fund"))
        r = _rules(y)
        bases = {"realised_gains": sum(g for g in known_sales if g > 0), "realised_losses": -sum(g for g in known_sales if g < 0),
                 "dividends": None if unpaid else share_div, "pl_gains": sum(g for g in pl if g > 0),
                 "pl_losses": -sum(g for g in pl if g < 0), "capital_base": None if capital_open else capital}
        si = None
        if r is not None and listed is not None and negative is not None:
            si = tm.share_income(known_sales, share_div, pl, listed_loss_in=listed, negative_in=negative,
                                 low_rate=r.share_income.low_rate, high_rate=r.share_income.high_rate,
                                 limit=r.share_income.progression_limit, listed_offsets=r.losses.listed_offsets)
            listed, negative = si.listed_loss_out, si.negative_out
        else:
            if listed is not None:
                broke = y
            listed = negative = None
        if y == year:
            rate = person.get("capital_income_rate")
            base = bases["capital_base"]
            res = {"share_income": asdict(si) if si else None, "bases": bases,
                   "capital_income": {"base": base, "rate": rate,
                                      "tax": None if base is None else tm.capital_tax(base, rate)},
                   "realised": sales, "dividends": divs, "lager": lager,
                   "complete": si is not None and not missing and not unknown and not unpaid and not capital_open}
            if r is None:
                notes.append(f"no tax: no rules for {year} in config/tax_dk.yaml")
            elif si is None:
                notes.append(_carry_note(year, broke))
            if base is None:
                notes.append("capital income unknown: a holding has no class, or a fund's lager or dividend is missing")
            elif rate is None and base:
                notes.append("capital income has no tax here: set your marginal rate on capital income")
            elif base < 0:
                notes.append("negative capital income: no tax on it; it lowers the tax on your other income by an "
                             "amount that depends on that income (not in the estimate)")
            notes += missing + unknown + [f"{s} at the end of {year}: no class, see Not in the estimate" for s in held_unknown]
            notes += [m for _, m in unpaid]
    return res | {"notes": notes}


# ---------------- the report ----------------

def _unknown_holdings(c: _Ctx, ports: list[dict], year: int) -> list[dict]:
    out = []
    end = _year_end(year, c.last)
    for p in ports:
        b = c.books[p["id"]]
        if b is None or p["kind"] != "frie_midler":
            continue
        for sym in b.positions.columns:
            k, why = c.cls(sym, year)
            v = _at(b.positions[sym], end)
            held = v is None or v > 0
            if k == taxinputs.UNKNOWN and held:
                out.append({"symbol": sym, "portfolio_id": p["id"], "portfolio": p["name"], "value_dkk": v,
                            "reason": why})
    return out


def year_report(market: Market, year: int, portfolio_ids: list[int] | None = None,
                person_id: int | None = None) -> dict:
    """The estimate for `year` for your real accounts (or these portfolio ids, or one person's accounts)."""
    last = pd.Timestamp(market.closes.index[-1])
    real = [p for p in userstore.portfolios() if p["mode"] == "real"]
    persons = userstore.tax_persons()
    rules = _rules(year)
    head: dict[str, Any] = {
        "year": year, "asof": last.date().isoformat(), "complete_year": last >= pd.Timestamp(year, 12, 31),
        "rules": {"year": year, "verified": rules.verified.isoformat() if rules.verified else None,
                  "sources": taxrules.sources(year)} if rules else None,
        "disclaimer": DISCLAIMER, "persons": [], "accounts": [], "unknown": [], "notes": []}
    if year > last.year:
        head["notes"].append(f"{year} hasn't started in the data (prices to {last.date()})")
        return head
    if not head["complete_year"]:
        head["notes"].append(f"{year} isn't over: values as of {last.date()}, so the estimate moves until 31 December")
    if rules is None:
        head["notes"].append(f"no rules for {year} in config/tax_dk.yaml: the bases are shown, no tax")
    c = _Ctx(market, real)
    openings = userstore.tax_openings()
    chosen = [p for p in real if (portfolio_ids is None or p["id"] in portfolio_ids)
              and (person_id is None or p["tax_person_id"] == person_id)]
    for p in chosen:
        acc: dict[str, Any] = {"id": p["id"], "name": p["name"], "kind": p["kind"], "person_id": p["tax_person_id"],
                               "pool": None, "realised": [], "lager": [], "dividends": [], "complete": False,
                               "warnings": [], "notes": []}
        if p["kind"] in ("ask", "pension"):
            acc["pool"], acc["notes"] = _account_pool(c, p, year, openings)
            acc["complete"] = bool(acc["pool"] and acc["pool"]["tax"] is not None)
            acc["warnings"] = _ask_warnings(c, p, year)
        elif p["kind"] == "other":
            acc["notes"] = ["kind other: no tax estimate (set the account's kind: aktiesparekonto, frie midler or pension)"]
        elif p["tax_person_id"] is None:
            acc["notes"] = ["no tax person: choose who owns the account"]
        head["accounts"].append(acc)
    for person in persons:
        if person_id is not None and person["id"] != person_id:
            continue
        fm = [p for p in real if p["kind"] == "frie_midler" and p["tax_person_id"] == person["id"]]
        if not fm:
            continue
        py = _person_year(c, person, fm, year, openings)
        for acc in head["accounts"]:
            if acc["kind"] == "frie_midler" and acc["person_id"] == person["id"]:
                acc["realised"] = [s for s in py.get("realised", []) if s["portfolio_id"] == acc["id"]]
                acc["lager"] = [x for x in py.get("lager", []) if x["portfolio_id"] == acc["id"]]
                acc["dividends"] = [d for d in py.get("dividends", []) if d["portfolio_id"] == acc["id"]]
                acc["complete"] = py["complete"]
        head["persons"].append({"id": person["id"], "name": person["name"],
                                "accounts": [p["name"] for p in fm], "share_income": py["share_income"],
                                "bases": py["bases"], "capital_income": py["capital_income"],
                                "complete": py["complete"], "notes": py["notes"]})
    head["unknown"] = _unknown_holdings(c, chosen, year)
    return head
