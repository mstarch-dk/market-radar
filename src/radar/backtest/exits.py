"""Your real trades replayed with the stop-loss / take-profit rule (signals/levels.py) followed, day by day, with
only what was known each day (pit.Context). Two variants, each written as a run of a simulated portfolio per
real portfolio (simulate.write_run), so the Returns page compares them with the real ones and ACWI:

- **overlay** (`exits-overlay`): your buys and sells as they happened; the rule only adds earlier exits. A later
  sale of a position the rule already sold is skipped (or cut to what is left).
- **rules** (`exits-rules`): your buys only; every exit comes from the rule, and positions it never sells are
  still held at the end.

The rule, per position (an "episode": from a buy while flat until it is sold out):
- **Stop**: highest adjusted close since the episode began − k × ATR, k recomputed every day from that day's
  inputs. **Take-profit**: fixed at the close of the buy (it is measured from the price, so recomputed daily it
  would always sit above it), and set again at each add.
- A close at or through a level triggers; the whole position is sold at the next session's traded close
  (`backtest.fill: next`; `same` = that close). Levels are compared on adjusted closes, where a dividend shifts
  price and level alike; the sale gets the traded price.
- Only holdings the radar gives levels (stocks, sector/theme funds; mine.level_universe) follow the rule; broad
  funds are held as in the real portfolio.
- The proceeds are parked in `backtest.park` (ACWI) and drawn on, before anything else, for your next buys.

Funding mirrors the real portfolio: with a cash ledger its deposits and withdrawals are copied; without one
(every buy is new money) each buy is funded from the sim's cash, then the parked units, then a deposit, and each
sale's proceeds are withdrawn, as the real portfolio's are. With the rule switched off the sim's time-weighted
return equals the real one's (tests/test_backtest_exits.py pins that).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import pandas as pd

from .. import performance, simulate, universe, userstore
from ..config import REPORTS, settings
from .pit import Context

VARIANTS = ("overlay", "rules")
EPS = 1e-9
REPORT_FILE = "sim-exits.json"


def key(variant: str) -> str:
    return f"exits-{variant}"


@dataclass
class Episode:
    qty: float
    start: pd.Timestamp
    anchor: float | None = None
    tp: float | None = None
    tp_meta: dict | None = None
    set_tp: bool = True
    pending: dict | None = None      # a triggered exit waiting for its fill


@dataclass
class Replay:
    market: object
    ctx: Context
    variant: str
    ledger: bool
    fill: str
    park: str
    rows: list[dict] = field(default_factory=list)
    exits: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)   # skipped / clipped / ignored real sells, top-ups, notes
    cash: float = 0.0
    park_units: float = 0.0
    eps: dict[str, Episode] = field(default_factory=dict)
    no_rule: set[str] = field(default_factory=set)
    counts: dict = field(default_factory=lambda: {"rule_days": 0, "no_levels_days": 0, "missing": {}})
    _fx: dict = field(default_factory=dict)
    _bars: dict = field(default_factory=dict)
    seq: int = 0
    day_out: float = 0.0             # implicit funding: money taken out at the end of the day (netted, as performance.book does)

    # ---------------- prices ----------------

    def fx(self, sym: str) -> pd.Series | None:
        if sym not in self._fx:
            self._fx[sym] = performance.fx_series(self.market, sym)
        return self._fx[sym]

    def rate(self, sym: str, day: pd.Timestamp) -> float | None:
        fx = self.fx(sym)
        v = fx.dropna().asof(day) if fx is not None else None
        return float(v) if v is not None and pd.notna(v) and v > 0 else None

    def bars(self, sym: str) -> pd.DataFrame:
        if sym not in self._bars:
            b = self.market.bars(sym)
            self._bars[sym] = b if "raw_close" in b else b.assign(raw_close=b["close"])
        return self._bars[sym]

    def traded(self, sym: str, day: pd.Timestamp) -> float | None:
        """The traded close on `day`, or the last one before it."""
        s = self.bars(sym)["raw_close"].dropna()[:day]
        return float(s.iloc[-1]) if len(s) else None

    def has_bar(self, sym: str, day: pd.Timestamp) -> bool:
        return day in self.bars(sym).index

    # ---------------- rows ----------------

    def _emit(self, row: dict) -> dict:
        self.seq += 1
        self.rows.append(row | {"ext_ref": f"exits:{self.variant}:{self.seq}"})
        return row

    def trade(self, typ: str, sym: str, day: pd.Timestamp, qty: float, price: float, rate: float, note: str) -> float:
        """A rule or parking trade at a traded price; returns its DKK cash effect."""
        self._emit({"symbol": sym, "date": day.date().isoformat(), "type": typ, "quantity": qty, "price": price,
                    "fee": 0.0, "fx_rate": rate, "note": note})
        dkk = qty * price * rate
        self.cash += dkk if typ == "SELL" else -dkk
        return dkk

    def cash_row(self, typ: str, day, amount: float, note: str) -> None:
        self._emit({"date": str(day)[:10], "type": typ, "amount": amount, "note": note})
        self.cash += amount if typ in ("DEPOSIT", "INTEREST") else -amount

    def fund(self, amount: float, day: pd.Timestamp, date_str: str, why: str) -> None:
        """Make `amount` DKK of cash available: the sim's cash, then parked units, then a deposit."""
        need = amount - self.cash
        if need > EPS and self.park_units > EPS:
            px, rate = self.traded(self.park, day), self.rate(self.park, day)
            if px and rate:
                units = min(self.park_units, need / (px * rate))
                self.trade("SELL", self.park, pd.Timestamp(date_str), units, px, rate, f"parked money used for {why}")
                self.park_units -= units
                if self.park_units < 1e-7:
                    self.park_units = 0.0
        need = amount - self.cash
        if need > 0.005:
            self.cash_row("DEPOSIT", date_str, need, f"new money for {why}")
            if self.ledger:
                self.events.append({"date": date_str, "kind": "top-up", "amount_dkk": need,
                                    "detail": f"the sim was short of cash for {why}"})

    # ---------------- the replay ----------------

    def real_row(self, r: dict, day: pd.Timestamp) -> None:
        t, ds = r["type"], str(r["date"])[:10]
        if t == "BUY":
            sym, q = r["symbol"], float(r["quantity"])
            row = {"symbol": sym, "date": ds, "type": "BUY", "quantity": q, "price": float(r["price"]),
                   "fee": float(r.get("fee") or 0), "fx_rate": r.get("fx_rate"), "note": "as your real buy"}
            dkk = performance.trade_cash_dkk(row, self.fx(sym))
            if dkk is None:
                self.events.append({"date": ds, "kind": "skipped buy", "symbol": sym, "detail": "no DKK rate"})
                return
            self.fund(-dkk, day, ds, f"your buy of {sym}")
            self._emit(row)
            self.cash += dkk
            ep = self.eps.get(sym)
            if ep is None:
                self.eps[sym] = Episode(q, day)
            else:
                ep.qty += q
                ep.set_tp = True
        elif t == "SELL":
            sym, q = r["symbol"], float(r["quantity"])
            if self.variant == "rules":
                self.events.append({"date": ds, "kind": "real sell ignored", "symbol": sym, "quantity": q})
                return
            ep = self.eps.get(sym)
            held = ep.qty if ep else 0.0
            sell = min(q, held)
            if sell <= EPS:
                self.events.append({"date": ds, "kind": "real sell skipped", "symbol": sym, "quantity": q,
                                    "detail": "already sold by the rule"})
                return
            if sell < q - EPS:
                self.events.append({"date": ds, "kind": "real sell cut", "symbol": sym, "quantity": q, "sold": sell,
                                    "detail": "partly sold by the rule already"})
            fee = float(r.get("fee") or 0) * sell / q
            row = {"symbol": sym, "date": ds, "type": "SELL", "quantity": sell, "price": float(r["price"]), "fee": fee,
                   "fx_rate": r.get("fx_rate"), "note": "as your real sale"}
            dkk = performance.trade_cash_dkk(row, self.fx(sym))
            if dkk is None:
                self.events.append({"date": ds, "kind": "skipped sell", "symbol": sym, "detail": "no DKK rate"})
                return
            self._emit(row)
            self.cash += dkk
            ep.qty -= sell
            if ep.qty <= EPS:
                if ep.pending:
                    self.events.append({"date": ds, "kind": "rule exit pre-empted", "symbol": sym,
                                        "detail": f"you sold before the triggered exit ({ep.pending['trigger_date']}) filled"})
                del self.eps[sym]
            if not self.ledger and dkk > 0:
                self.day_out += dkk
        elif t in ("DEPOSIT", "INTEREST"):
            self.cash_row(t, ds, float(r["amount"]), f"as your real {t.lower()}")
            if t == "INTEREST" and not self.ledger:
                self.day_out += float(r["amount"])
        elif t in ("WITHDRAW", "FEE"):
            amount = float(r["amount"])
            self.fund(amount, day, ds, f"your real {t.lower()}")
            self.cash_row(t, ds, amount, f"as your real {t.lower()}")
        # DIVIDEND: simulations count dividends as reinvested (adjusted prices), so the rows would count twice

    def execute(self, sym: str, ep: Episode, day: pd.Timestamp) -> None:
        p = ep.pending
        px, rate = self.traded(sym, day), self.rate(sym, day)
        if px is None or rate is None:
            self.events.append({"date": day.date().isoformat(), "kind": "fill failed", "symbol": sym,
                                "detail": "no traded price or DKK rate"})
            ep.pending = None
            return
        qty = ep.qty
        dkk = self.trade("SELL", sym, day, qty, px, rate,
                         f"rule: {p['trigger'].replace('_', '-')} at {p['level']:.2f} (k {p['k']:.2f}) on {p['trigger_date']}")
        ppx, prate = self.traded(self.park, day), self.rate(self.park, day)
        units = 0.0
        if ppx and prate and dkk > 0:
            units = dkk / (ppx * prate)
            self.trade("BUY", self.park, day, units, ppx, prate, f"parked: money from the {sym} exit")
            self.park_units += units
        self.exits.append(p | {"symbol": sym, "fill_date": day.date().isoformat(), "quantity": qty, "fill_price": px,
                               "fx": rate, "proceeds_dkk": dkk, "park_units": units, "park_price": ppx, "park_fx": prate,
                               "episode_start": ep.start.date().isoformat()})
        del self.eps[sym]

    def check(self, sym: str, ep: Episode, day: pd.Timestamp) -> None:
        if sym not in self.ctx.eligible:
            self.no_rule.add(sym)
            return
        if not self.has_bar(sym, day) or sym not in self.market.closes:
            return
        close = self.market.closes.at[day, sym]
        if pd.isna(close):
            return
        close = float(close)
        ep.anchor = close if ep.anchor is None else max(ep.anchor, close)
        lv = self.ctx.levels(sym, day, ep.anchor)
        if lv is None:
            self.counts["no_levels_days"] += 1
            return
        self.counts["rule_days"] += 1
        for m in lv["context"]["missing"]:
            self.counts["missing"][m] = self.counts["missing"].get(m, 0) + 1
        if ep.set_tp:
            ep.tp, ep.set_tp = lv["take_profit"], False
            ep.tp_meta = {"set": day.date().isoformat(), "source": lv["tp_source"], "k": lv["k"]}
        trig = None
        if close <= lv["stop"]:
            trig, level = "stop", lv["stop"]
        elif ep.tp is not None and close >= ep.tp:
            trig, level = "take_profit", ep.tp
        if trig is None:
            return
        ep.pending = {"trigger": trig, "trigger_date": day.date().isoformat(), "level": level, "close_adj": close,
                      "k": lv["k"], "stop": lv["stop"], "take_profit": ep.tp, "tp_set": ep.tp_meta,
                      "anchor": ep.anchor, "atr": lv["atr"], "reasons": lv["reasons"], "context": lv["context"]}
        if self.fill == "same":
            self.execute(sym, ep, day)


def _opening(rp: Replay, rows: list[dict], start: pd.Timestamp) -> list[dict]:
    """Start the replay at `start` from what the real portfolio held then (as simulate.fork): one deposit of its
    value, one buy per holding at that day's traded close. Returns the rows after `start`."""
    before = [r for r in rows if pd.Timestamp(str(r["date"])[:10]) <= start]
    after = [r for r in rows if pd.Timestamp(str(r["date"])[:10]) > start]
    qty: dict[str, float] = {}
    for r in before:
        if r["type"] in ("BUY", "SELL"):
            qty[r["symbol"]] = qty.get(r["symbol"], 0.0) + (1 if r["type"] == "BUY" else -1) * float(r["quantity"])
    total, buys = 0.0, []
    for sym, q in sorted(qty.items()):
        if q <= EPS:
            continue
        px, rate = rp.traded(sym, start), rp.rate(sym, start)
        if px is None or rate is None:
            raise ValueError(f"{sym}: no price or DKK rate on {start:%Y-%m-%d}")
        buys.append((sym, q, px, rate))
        total += q * px * rate
    if rp.ledger:
        bal, problems = performance.cash_balance(before, rp.market)
        if problems:
            raise ValueError("its cash that day is unknown: " + "; ".join(problems))
        total += float(bal.iloc[-1]) if len(bal) else 0.0
    if total > 0:
        rp.cash_row("DEPOSIT", start.date().isoformat(), total, f"what the portfolio held at the close of {start:%Y-%m-%d}")
    for sym, q, px, rate in buys:
        rp.trade("BUY", sym, start, q, px, rate, "held at the start")
        rp.eps[sym] = Episode(q, start)
    return after


def replay(real_rows: list[dict], ctx: Context, variant: str, start=None, end=None, fill: str | None = None) -> dict:
    """The simulated rows and the report for one real portfolio's rows."""
    if variant not in VARIANTS:
        raise ValueError(f"variant must be one of {', '.join(VARIANTS)}")
    bt = settings().get("backtest") or {}
    market = ctx.market
    rows = sorted([r for r in real_rows if r["type"] in ("BUY", "SELL", "DEPOSIT", "WITHDRAW", "FEE", "INTEREST", "DIVIDEND")],
                  key=lambda r: (str(r["date"])[:10], r.get("id") or 0))
    rp = Replay(market, ctx, variant, performance.has_ledger(rows), fill or bt.get("fill", "next"),
                bt.get("park") or universe.benchmark())
    if rp.fill not in ("next", "same"):
        raise ValueError("fill must be next or same")
    if not rows:
        return {"rows": [], "exits": [], "events": [], "start": None, "end": None}
    sessions = ctx.sessions
    end_ts = pd.Timestamp(end) if end else sessions[-1]
    if end:
        rows = [r for r in rows if pd.Timestamp(str(r["date"])[:10]) <= end_ts]
    first = pd.Timestamp(str(rows[0]["date"])[:10])
    if start is not None and pd.Timestamp(start) > first:
        s = sessions[sessions <= pd.Timestamp(start)]
        if s.empty:
            raise ValueError(f"no prices on or before {start}")
        first = s[-1]
        rows = _opening(rp, rows, first)
    days = sessions[(sessions >= first.normalize()) & (sessions <= end_ts)]
    if days.empty:
        raise ValueError("no benchmark sessions in the period")
    by_day: dict[pd.Timestamp, list[dict]] = {}
    for r in rows:
        i = days.searchsorted(pd.Timestamp(str(r["date"])[:10]))
        by_day.setdefault(days[min(i, len(days) - 1)], []).append(r)
    dividends = [r for r in rows if r["type"] == "DIVIDEND"]
    if dividends:
        rp.events.append({"kind": "note", "detail": f"{len(dividends)} dividend rows not copied: the simulation counts "
                                                    "dividends as reinvested (adjusted prices)"})

    for day in days:
        for sym, ep in list(rp.eps.items()):               # yesterday's triggers sell at today's close
            if ep.pending and rp.has_bar(sym, day) and ep.pending["trigger_date"] < day.date().isoformat():
                rp.execute(sym, ep, day)
        today = by_day.get(day, [])
        if not rp.ledger:   # without a ledger a day's sales and buys net (performance.book): sales first, so buys use them
            today = sorted(today, key=lambda r: r["type"] != "SELL")
        for r in today:
            rp.real_row(r, day)
        if rp.day_out > 0.005 and rp.cash > 0.005:
            rp.cash_row("WITHDRAW", day.date().isoformat(), min(rp.day_out, rp.cash),
                        "the day's sales taken out, as in the real portfolio")
        rp.day_out = 0.0
        for sym, ep in list(rp.eps.items()):
            if ep.pending is None:
                rp.check(sym, ep, day)

    open_triggers = [{"symbol": s, **ep.pending} for s, ep in rp.eps.items() if ep.pending]
    return {"rows": rp.rows, "exits": _evaluate(rp, real_rows, days[-1]), "events": rp.events,
            "pending": open_triggers, "no_rule": sorted(rp.no_rule), "counts": rp.counts, "funding":
            "ledger" if rp.ledger else "implicit", "park": rp.park, "fill": rp.fill,
            "start": days[0].date().isoformat(), "end": days[-1].date().isoformat()}


def _evaluate(rp: Replay, real_rows: list[dict], last: pd.Timestamp) -> list[dict]:
    """Each exit with what happened afterwards: the position's value (dividends reinvested) against the parked
    units', at your next real sale of the symbol after the exit and at the end. saved_dkk > 0: the rule helped."""
    closes = rp.market.closes
    out = []
    for e in rp.exits:
        sym, fill = e["symbol"], pd.Timestamp(e["fill_date"])
        sells = sorted(str(r["date"])[:10] for r in real_rows
                       if r["type"] == "SELL" and r["symbol"] == sym and str(r["date"])[:10] >= e["fill_date"])
        horizons = {"end": last}
        if sells:
            horizons["your_sale"] = pd.Timestamp(sells[0])
        after = {}
        for name, x in horizons.items():
            a0, a1 = closes[sym].loc[:fill].dropna(), closes[sym].loc[:x].dropna()
            p0 = closes[rp.park].loc[:fill].dropna() if rp.park in closes else pd.Series(dtype=float)
            p1 = closes[rp.park].loc[:x].dropna() if rp.park in closes else pd.Series(dtype=float)
            fx1, pfx1 = rp.rate(sym, x), rp.rate(rp.park, x)
            pos = (e["quantity"] * e["fill_price"] * float(a1.iloc[-1] / a0.iloc[-1]) * fx1
                   if len(a0) and len(a1) and fx1 else None)
            park = (e["park_units"] * e["park_price"] * float(p1.iloc[-1] / p0.iloc[-1]) * pfx1
                    if e["park_units"] and len(p0) and len(p1) and pfx1 else None)
            after[name] = {"date": x.date().isoformat(), "position_dkk": pos, "parked_dkk": park,
                           "saved_dkk": park - pos if pos is not None and park is not None else None,
                           "symbol_return": float(a1.iloc[-1] / a0.iloc[-1] - 1) if len(a0) and len(a1) else None,
                           "park_return": float(p1.iloc[-1] / p0.iloc[-1] - 1) if len(p0) and len(p1) else None}
        out.append(e | {"after": after})
    return out


# ---------------- runs into simulated portfolios ----------------

def _sim_for(p: dict, variant: str, params: dict) -> int:
    k = key(variant)
    sim = simulate.find_sim(p["id"], k)
    if sim:
        tags = sorted(set(sim["tags"]) | {k})
        userstore.save_portfolio({"kind": p["kind"], "params": params, "tags": tags}, sim["id"])
        return sim["id"]
    name, n = f"{p['name']} · exits {variant}", 2
    while userstore.portfolio_by_name(name):
        name, n = f"{p['name']} · exits {variant} {n}", n + 1
    return simulate.new_sim_portfolio(name, k, params, tags=[k], kind=p["kind"], parent_id=p["id"])


def summary(rep: dict) -> dict:
    ex = rep["exits"]

    def total(h):
        v = [e["after"][h]["saved_dkk"] for e in ex if h in e["after"] and e["after"][h]["saved_dkk"] is not None]
        return {"exits": len(v), "saved_dkk": sum(v) if v else None, "helped": sum(x > 0 for x in v)}
    kinds = {}
    for ev in rep["events"]:
        kinds[ev["kind"]] = kinds.get(ev["kind"], 0) + 1
    return {"stops": sum(e["trigger"] == "stop" for e in ex), "take_profits": sum(e["trigger"] == "take_profit" for e in ex),
            "at_end": total("end"), "at_your_sale": total("your_sale"), "events": kinds,
            "pending": len(rep.get("pending") or []), "no_rule": rep.get("no_rule") or [], "counts": rep.get("counts")}


def refresh(real_ids: list[int], market, variants=VARIANTS, start=None, end=None, fill: str | None = None,
            write: bool = True) -> dict:
    """Replay each real portfolio with each variant into its simulated portfolio (found again by parent and
    strategy, created the first time) and build the report; written to reports/sim-exits.json."""
    portfolios = [userstore.get_portfolio(i) for i in real_ids]
    portfolios = [p for p in portfolios if p]
    for p in portfolios:
        if p["mode"] != "real":
            raise ValueError(f"{p['name']} isn't one of your real portfolios")
    rows = {p["id"]: userstore.transactions(portfolios=[p["id"]]) for p in portfolios}
    held = {r["symbol"] for rs in rows.values() for r in rs if r["symbol"]}
    bt = settings().get("backtest") or {}
    ctx = Context.build(market, held | {bt.get("park") or universe.benchmark()})
    out = {"generated": pd.Timestamp.now().isoformat(timespec="seconds"),
           "asof": ctx.sessions[-1].date().isoformat(), "portfolios": []}
    for p in portfolios:
        if not rows[p["id"]]:
            continue
        entry = {"id": p["id"], "name": p["name"], "variants": {}}
        for v in variants:
            params = {"variant": v, "fill": fill or bt.get("fill", "next"), "start": start, "end": end}
            rep = replay(rows[p["id"]], ctx, v, start, end, fill)
            sid = _sim_for(p, v, params)
            s = summary(rep)
            msg = (f"{s['stops']} stops, {s['take_profits']} take-profits; saved at the end "
                   f"{s['at_end']['saved_dkk']:,.0f} DKK" if s["at_end"]["saved_dkk"] is not None else
                   f"{s['stops']} stops, {s['take_profits']} take-profits")
            res = simulate.write_run(sid, key(v), params, rep["start"], rep["end"], rep["rows"], market, msg)
            entry["variants"][v] = {"portfolio_id": sid, "name": userstore.get_portfolio(sid)["name"], "run_id": res["run_id"],
                                    "summary": s} | {k: rep[k] for k in ("start", "end", "funding", "park", "fill", "exits",
                                                                          "events", "pending")}
        sims = [entry["variants"][v]["portfolio_id"] for v in entry["variants"]]
        entry["start"] = next(iter(entry["variants"].values()))["start"]
        entry["compare"] = performance.compare(market, [p["id"], *sims], start=entry["start"])
        out["portfolios"].append(entry)
    if write:
        REPORTS.mkdir(exist_ok=True)
        f = REPORTS / REPORT_FILE
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, indent=1, default=_json), encoding="utf-8")
        tmp.replace(f)
    return out


def _json(v):
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat()
    if hasattr(v, "item"):
        return v.item()
    return str(v)
