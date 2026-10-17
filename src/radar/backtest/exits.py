"""Your real trades replayed day by day with the stop / take-profit rule (signals/levels.py) followed, from only what
was known each day (pit.Context): `overlay` (your trades as they were, the rule adds earlier exits) and `rules` (your
buys only, every exit from the rule), each written as a simulated portfolio per real one (simulate.write_run).
`RuleSpec` holds the variants the studies test, `ablation` the rule's halves. The method:
guide/laerebog/stop-og-storrelse.md (*Backtest af reglen*) and guide/brugervejledning/stop-simulering.md; for
developers docs/data-conventions.md, *Point-in-time backtests*.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import pandas as pd

from .. import money, performance, simulate, universe, userstore
from ..config import settings, write_text
from ..fees import SimFees, Terms
from ..jsonsafe import dumps
from ..model import paths as mpaths
from ..paths import REPORTS
from .pit import Context

VARIANTS = ("overlay", "rules")
RULES = ("both", "stop", "take_profit")
EPS = 1e-9
REPORT_FILE = "sim-exits.json"


STOP_KINDS = ("atr", "pct", "trend", "none")


@dataclass(frozen=True)
class RuleSpec:
    """A variant of the stop / take-profit rule for testing. `RuleSpec()` is the radar's rule as settings has it."""
    key: str = "rule"
    label: str = "The radar's rule (settings)"
    stops: tuple = ()             # (key, value) pairs over settings.stops, e.g. (("k_base", 4.0),)
    tp: str = "fixed"             # fixed: the rule's take-profit, set at the buy; off: none
    stop: str = "atr"             # atr: the rule's trailing ATR stop; pct: `pct` below the high; trend: a close
    pct: float = 0.2              # below the `sma`-day average; none: no stop
    sma: int = 200
    reentry: bool = False         # buy back after an exit: uptrend, score >= stops.strong_score, above the 50-day
    reentry_wait: int = 10        # sessions after an exit before a re-entry can trigger
    redeploy: str = "park"        # park: an exit's proceeds wait in backtest.park; score: they buy the picker's best name
    rotate: int = 0               # > 0: sell at month-end a holding ranked outside rotate x the picker's basket size
    cooldown: int = 21            # sessions after a sale before redeploy can buy the name again
    half: str = "both"            # both halves of the rule, or only its stop / take-profit (the ablation; see ablation)

    def __post_init__(self):
        if self.half not in RULES:
            raise ValueError(f"half must be one of {', '.join(RULES)}")
        if self.tp not in ("fixed", "off") or self.stop not in STOP_KINDS:
            raise ValueError(f"tp must be fixed or off, stop one of {', '.join(STOP_KINDS)}")
        if self.redeploy not in ("park", "score") or self.rotate < 0 or self.cooldown < 0:
            raise ValueError("redeploy must be park or score, rotate and cooldown >= 0")
        if self.rotate and self.redeploy != "score":
            raise ValueError("rotation needs redeploy: score (a rotated-out name's money buys the next one)")

    @property
    def overrides(self) -> dict | None:
        """The stops settings this variant changes. "rule" is settings as they are; the others fix the ATR mode
        and the take-profit they name, so they mean the same whatever settings says."""
        o = dict(self.stops)
        if self.key != "rule":
            if self.stop == "atr":
                o.setdefault("mode", "atr")
            o.setdefault("take_profit", self.tp == "fixed")
        return o or None


def key(variant: str, spec: RuleSpec | None = None) -> str:
    return f"exits-{variant}" if spec is None or spec.key == "rule" else f"exits-{variant}-{spec.key}"[:32]


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
    """One real portfolio replayed with the rule. Funding mirrors the real portfolio (`ledger`): with a cash ledger
    its deposits and withdrawals are copied; without one (every buy is new money) each buy is funded from the sim's
    cash, then the parked units, then a deposit (`fund`), and each sale's proceeds are withdrawn, as the real
    portfolio's are. With the rule switched off the sim's time-weighted return equals the real one's
    (tests/test_backtest_exits.py pins that)."""
    market: object
    ctx: Context
    variant: str
    ledger: bool
    fill: str
    park: str
    rule: str = "both"
    fees: SimFees = field(default_factory=lambda: SimFees(0.0))
    spec: RuleSpec = field(default_factory=RuleSpec)
    picker: object = None            # redeploy.Picker: n, pick(day, held, barred) -> name | None, rank(day, name) -> int | None
    sold: dict = field(default_factory=dict)            # symbol -> the session of its last rule / rotation sale
    redeploys: list[dict] = field(default_factory=list)
    watch: dict = field(default_factory=dict)          # exited symbols waiting for a re-entry
    reentries: list[dict] = field(default_factory=list)
    _sma: dict = field(default_factory=dict)
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
    _ccy: dict = field(default_factory=dict)
    seq: int = 0
    day_out: float = 0.0             # implicit funding: money taken out at the end of the day (netted, as performance.book does)

    # ---------------- prices ----------------

    def fx(self, sym: str) -> pd.Series | None:
        if sym not in self._fx:
            self._fx[sym] = performance.fx_series(self.market, sym)
        return self._fx[sym]

    def rate(self, sym: str, day: pd.Timestamp) -> float | None:
        fx = self.fx(sym)
        return money.rate_on(fx, day)

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

    @property
    def fee_bps(self) -> float:
        return self.fees.bps

    def terms(self, sym: str, day: pd.Timestamp, rate: float, count: bool = False) -> Terms:
        """What a rule or parking trade in `sym` pays on `day` (`rate`: DKK per unit of its price; `count`: the
        trade itself, not its sizing)."""
        if not self.fees.schedule:
            return self.fees.terms(sym, None, None)
        if sym not in self._ccy:
            self._ccy[sym] = universe.currencies([sym]).get(sym)

        def convert(amount: float, ccy: str) -> float | None:
            if ccy == "DKK":
                return amount / rate
            fx = universe.fx_to_dkk(self.market.closes, ccy)
            v = money.rate_on(fx, day)
            return amount * v / rate if v is not None else None
        return self.fees.terms(sym, self._ccy[sym], convert, count)

    def buy_qty(self, sym: str, day: pd.Timestamp, dkk: float, px: float, rate: float) -> float:
        """The shares `dkk` buys, the fee included (0 when the fee alone would take it)."""
        return self.terms(sym, day, rate).value_for_budget(dkk / rate) / px

    # ---------------- rows ----------------

    def _emit(self, row: dict) -> dict:
        self.seq += 1
        self.rows.append(row | {"ext_ref": f"exits:{self.variant}:{self.seq}"})
        return row

    def trade(self, typ: str, sym: str, day: pd.Timestamp, qty: float, price: float, rate: float, note: str,
              free: bool = False) -> float:
        """A rule or parking trade at a traded price, paying its fee (`fees`); returns its DKK cash effect
        (proceeds after the fee for a sale, the cost with the fee for a buy). `free`: a holding copied in, not
        traded."""
        fee = 0.0 if free else self.terms(sym, day, rate, count=True).fee(qty * price)
        self._emit({"symbol": sym, "date": day.date().isoformat(), "type": typ, "quantity": qty, "price": price,
                    "fee": fee, "fx_rate": rate, "note": note})
        dkk = (qty * price + (-fee if typ == "SELL" else fee)) * rate
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
                units = min(self.park_units, self.terms(self.park, day, rate).value_for_net(need / rate) / px)
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
        k = f" (k {p['k']:.2f})" if p.get("k") is not None else ""
        why = (f"rotation: rank {p['rank'] if p['rank'] is not None else 'none'} outside the top {p['keep']} on "
               f"{p['trigger_date']}" if p["trigger"] == "rotation" else
               f"rule: {p.get('stop_kind', p['trigger']).replace('_', '-')} at {p['level']:.2f}{k} on {p['trigger_date']}")
        dkk = self.trade("SELL", sym, day, qty, px, rate, why)
        del self.eps[sym]
        self.sold[sym] = day
        units, ppx, prate = 0.0, None, None
        if not (dkk > 0 and self.redeploy(sym, p, day, dkk)):
            ppx, prate = self.traded(self.park, day), self.rate(self.park, day)
            units = self.buy_qty(self.park, day, dkk, ppx, prate) if ppx and prate and dkk > 0 else 0.0
            if units > EPS:
                self.trade("BUY", self.park, day, units, ppx, prate, f"parked: money from the {sym} exit")
                self.park_units += units
            elif ppx and prate and dkk > 0:
                self.events.append({"date": day.date().isoformat(), "kind": "not parked", "symbol": sym,
                                    "detail": f"{dkk:,.0f} DKK doesn't cover the fee: kept as cash"})
        self.exits.append(p | {"symbol": sym, "fill_date": day.date().isoformat(), "quantity": qty, "fill_price": px,
                               "fx": rate, "proceeds_dkk": dkk, "park_units": units, "park_price": ppx, "park_fx": prate,
                               "episode_start": ep.start.date().isoformat()})
        if self.spec.reentry and units > 0:
            self.watch[sym] = {"exit": day, "units": units, "pending": None}

    def barred(self, day: pd.Timestamp) -> set[str]:
        """Names sold within the last `cooldown` sessions (up to `day`)."""
        s = self.ctx.sessions
        i = s.searchsorted(day)
        return {t for t, d in self.sold.items() if i - s.searchsorted(d) <= self.spec.cooldown}

    def redeploy(self, sym: str, p: dict, day: pd.Timestamp, dkk: float) -> bool:
        """Buy the picker's best name with an exit's proceeds at `day`'s close, ranked on the trigger day (known at
        that close). False (the money is then parked) without a picker, a candidate, a price or a DKK rate."""
        if self.spec.redeploy != "score" or self.picker is None:
            return False
        trig = pd.Timestamp(p["trigger_date"])
        new = self.picker.pick(trig, set(self.eps), self.barred(day))
        px, rate = (self.traded(new, day), self.rate(new, day)) if new else (None, None)
        if not new or not (px and rate) or not self.has_bar(new, day):
            self.events.append({"date": day.date().isoformat(), "kind": "redeploy skipped", "symbol": sym,
                                "detail": "no candidate" if not new else f"{new}: no traded price or DKK rate that day"})
            return False
        qty = self.buy_qty(new, day, dkk, px, rate)
        if qty <= EPS:
            self.events.append({"date": day.date().isoformat(), "kind": "redeploy skipped", "symbol": sym,
                                "detail": f"{dkk:,.0f} DKK doesn't cover the fee on {new}"})
            return False
        self.trade("BUY", new, day, qty, px, rate, f"redeploy: money from the {sym} {p['trigger'].replace('_', '-')}")
        self.eps[new] = Episode(qty, day)
        self.redeploys.append({"symbol": new, "from": sym, "trigger": p["trigger"], "trigger_date": p["trigger_date"],
                               "fill_date": day.date().isoformat(), "price": px, "quantity": qty, "amount_dkk": dkk})
        return True

    def month_end(self, day: pd.Timestamp) -> bool:
        s = self.ctx.sessions
        i = s.searchsorted(day)
        return i + 1 < len(s) and s[i] == day and s[i + 1].month != day.month

    def check_rotation(self, day: pd.Timestamp) -> None:
        """At a month-end: a holding ranked outside `rotate` x the basket size (or without a rank) is sold at the
        next fill and its money redeployed."""
        keep = self.spec.rotate * self.picker.n
        for sym, ep in list(self.eps.items()):
            if ep.pending is not None or not self.has_bar(sym, day):
                continue
            r = self.picker.rank(day, sym)
            if r is not None and r <= keep:
                continue
            ep.pending = {"trigger": "rotation", "stop_kind": "rotation", "trigger_date": day.date().isoformat(),
                          "level": float(r) if r is not None else float("nan"), "rank": r, "keep": keep, "k": None,
                          "close_adj": None, "stop": None, "take_profit": ep.tp, "tp_set": ep.tp_meta,
                          "anchor": ep.anchor, "atr": None, "reasons": [], "context": None}
            if self.fill == "same":
                self.execute(sym, ep, day)

    def sma(self, sym: str, day: pd.Timestamp) -> float | None:
        if sym not in self._sma:
            self._sma[sym] = mpaths.trend_level(self.market.closes[sym], self.spec.sma)
        v = self._sma[sym].get(day)
        return None if v is None or pd.isna(v) else float(v)

    def check_reentry(self, sym: str, w: dict, day: pd.Timestamp) -> None:
        """An uptrend again, a strong score and above the 50-day: buy back at the next close."""
        s = self.ctx.sessions
        if s.searchsorted(day) - s.searchsorted(w["exit"]) < self.spec.reentry_wait:
            return
        row, score = self.ctx.row(sym, day), self.ctx.score(sym, day)
        cfg = self.ctx.stops | (self.spec.overrides or {})
        if row and row["trend_ok"] and row["above50"] and score is not None and score >= cfg["strong_score"]:
            w["pending"] = {"trigger_date": day.date().isoformat(), "score": score}
            if self.fill == "same":
                self.reenter(sym, w, day)

    def reenter(self, sym: str, w: dict, day: pd.Timestamp) -> None:
        units = min(w["units"], self.park_units)
        px, rate = self.traded(sym, day), self.rate(sym, day)
        ppx, prate = self.traded(self.park, day), self.rate(self.park, day)
        del self.watch[sym]
        if units <= EPS or not (px and rate and ppx and prate):
            self.events.append({"date": day.date().isoformat(), "kind": "re-entry skipped", "symbol": sym,
                                "detail": "no parked money left" if units <= EPS else "no traded price or DKK rate"})
            return
        dkk = self.trade("SELL", self.park, day, units, ppx, prate, f"parked money back into {sym}")
        self.park_units -= units
        if self.park_units < 1e-7:
            self.park_units = 0.0
        qty = self.buy_qty(sym, day, dkk, px, rate)
        if qty <= EPS:
            self.events.append({"date": day.date().isoformat(), "kind": "re-entry skipped", "symbol": sym,
                                "detail": f"{dkk:,.0f} DKK doesn't cover the fee: kept as cash"})
            return
        self.trade("BUY", sym, day, qty, px, rate,
                   f"re-entry: uptrend and score {w['pending']['score']:.0f} on {w['pending']['trigger_date']}")
        self.eps[sym] = Episode(qty, day)
        self.reentries.append({"symbol": sym, "trigger_date": w["pending"]["trigger_date"],
                               "fill_date": day.date().isoformat(), "price": px, "quantity": qty, "amount_dkk": dkk})

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
        sp = self.spec
        lv = None
        if sp.stop == "atr" or sp.tp == "fixed":
            lv = self.ctx.levels(sym, day, ep.anchor, sp.overrides)
            if lv is None:
                self.counts["no_levels_days"] += 1
                return
            for m in lv["context"]["missing"]:
                self.counts["missing"][m] = self.counts["missing"].get(m, 0) + 1
        self.counts["rule_days"] += 1
        if ep.set_tp and lv is not None:
            ep.tp, ep.set_tp = (lv["take_profit"] if sp.tp == "fixed" else None), False
            ep.tp_meta = {"set": day.date().isoformat(), "source": lv["tp_source"], "k": lv["k"]}
        if sp.stop == "atr":
            stop = lv["stop"]
        elif sp.stop == "pct":
            stop = ep.anchor * (1 - sp.pct)
        elif sp.stop == "trend":
            stop = self.sma(sym, day)
        else:
            stop = None
        trig = None
        if stop is not None and (close < stop if sp.stop == "trend" else close <= stop):
            trig, level = "stop", stop
        elif sp.tp == "fixed" and ep.tp is not None and close >= ep.tp:
            trig, level = "take_profit", ep.tp
        if trig is None:
            return
        kind = "take_profit" if trig == "take_profit" else ("stop" if sp.stop == "atr" else f"{sp.stop}-stop")
        ep.pending = {"trigger": trig, "stop_kind": kind, "trigger_date": day.date().isoformat(), "level": level,
                      "close_adj": close, "k": lv["k"] if lv else None, "stop": stop, "take_profit": ep.tp,
                      "tp_set": ep.tp_meta, "anchor": ep.anchor, "atr": lv["atr"] if lv else None,
                      "reasons": lv["reasons"] if lv else [], "context": lv["context"] if lv else None}
        if self.fill == "same":
            self.execute(sym, ep, day)


def _opening(rp: Replay, rows: list[dict], start: pd.Timestamp) -> list[dict]:
    """Start the replay at `start` from what the real portfolio held then (as simulate.fork): one deposit of its
    value, one buy per holding at that day's traded close, without a fee (a copy, not a trade). Returns the rows after `start`."""
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
        rp.trade("BUY", sym, start, q, px, rate, "held at the start", free=True)
        rp.eps[sym] = Episode(q, start)
    return after


def ablation(rule: str, spec: RuleSpec | None = None) -> RuleSpec:
    """`spec` (default: the radar's rule) with only one half of the rule: "stop" (no take-profit),
    "take_profit" (no stop) or "both"."""
    spec = spec or RuleSpec()
    if rule == "stop":
        return replace(spec, tp="off", half=rule)
    if rule == "take_profit":
        return replace(spec, stop="none", half=rule)
    return replace(spec, half=rule)


def replay(real_rows: list[dict], ctx: Context, variant: str, start=None, end=None, fill: str | None = None,
           fee_bps: float | None = None, spec: RuleSpec | None = None, picker=None,
           fees: SimFees | None = None) -> dict:
    """The simulated rows and the report for one real portfolio's rows. `spec`: the rule (default: the radar's;
    one half only: ablation); `fees` per rule or parking trade, default `fee_bps` of its value, default settings
    backtest.fee_bps; `picker`: the candidates for `spec.redeploy` / `spec.rotate`."""
    if variant not in VARIANTS:
        raise ValueError(f"variant must be one of {', '.join(VARIANTS)}")
    spec = spec or RuleSpec()
    if spec.reentry and variant != "rules":
        raise ValueError("re-entry needs the rules variant (your own sales would mix with the rule's buys)")
    if spec.redeploy == "score" and (variant != "rules" or picker is None):
        raise ValueError("redeploy needs the rules variant and a picker")
    bt = settings().get("backtest") or {}
    market = ctx.market
    rows = sorted([r for r in real_rows if r["type"] in userstore.TYPES],
                  key=lambda r: (str(r["date"])[:10], r.get("id") or 0))
    rp = Replay(market, ctx, variant, performance.has_ledger(rows), fill or bt.get("fill", "next"),
                bt.get("park") or universe.benchmark(), spec.half,
                fees or SimFees(money.fee_bps(bt) if fee_bps is None else float(fee_bps)), spec, picker)
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
        for sym, w in list(rp.watch.items()):              # and yesterday's re-entry signals buy back
            if w["pending"] and rp.has_bar(sym, day) and w["pending"]["trigger_date"] < day.date().isoformat():
                rp.reenter(sym, w, day)
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
        if spec.rotate and rp.month_end(day):
            rp.check_rotation(day)
        for sym, w in list(rp.watch.items()):
            if w["pending"] is None and sym not in rp.eps and rp.has_bar(sym, day):
                rp.check_reentry(sym, w, day)

    open_triggers = [{"symbol": s, **ep.pending} for s, ep in rp.eps.items() if ep.pending]
    return {"rows": rp.rows, "exits": _evaluate(rp, real_rows, days[-1]), "events": rp.events,
            "pending": open_triggers, "no_rule": sorted(rp.no_rule), "counts": rp.counts, "funding":
            "ledger" if rp.ledger else "implicit", "park": rp.park, "fill": rp.fill, "rule": rp.rule, "fee_bps": rp.fee_bps,
            "fee_model": rp.fees.report(),
            "spec": rp.spec.key, "reentries": rp.reentries, "redeploys": rp.redeploys,
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

def _sim_for(p: dict, variant: str, params: dict, spec: RuleSpec | None = None) -> int:
    k = key(variant, spec)
    sim = simulate.find_sim(p["id"], k)
    if sim:
        tags = sorted(set(sim["tags"]) | {k})
        userstore.save_portfolio({"kind": p["kind"], "params": params, "tags": tags}, sim["id"])
        return sim["id"]
    label = variant if spec is None or spec.key == "rule" else f"{variant} {spec.key}"
    name, n = f"{p['name']} · exits {label}", 2
    while userstore.portfolio_by_name(name):
        name, n = f"{p['name']} · exits {label} {n}", n + 1
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
            write: bool = True, spec: RuleSpec | None = None) -> dict:
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
            if spec is not None and spec.reentry and v != "rules":
                continue
            fees = SimFees.for_portfolio(p, money.fee_bps(bt))
            rep = replay(rows[p["id"]], ctx, v, start, end, fill, spec=spec, fees=fees)
            params = {"variant": v, "fill": fill or bt.get("fill", "next"), "start": start, "end": end,
                      "fee_bps": fees.bps, "fee_model": fees.report(), "spec": spec.key if spec else "rule"}
            sid = _sim_for(p, v, params, spec)
            s = summary(rep)
            msg = (f"{s['stops']} stops, {s['take_profits']} take-profits; saved at the end "
                   f"{s['at_end']['saved_dkk']:,.0f} DKK" if s["at_end"]["saved_dkk"] is not None else
                   f"{s['stops']} stops, {s['take_profits']} take-profits")
            res = simulate.write_run(sid, key(v, spec), params, rep["start"], rep["end"], rep["rows"], market, msg)
            entry["variants"][v] = {"portfolio_id": sid, "name": userstore.get_portfolio(sid)["name"], "run_id": res["run_id"],
                                    "summary": s} | {k: rep[k] for k in ("start", "end", "funding", "park", "fill", "exits",
                                                                          "events", "pending")}
        sims = [entry["variants"][v]["portfolio_id"] for v in entry["variants"]]
        entry["start"] = next(iter(entry["variants"].values()))["start"]
        entry["compare"] = performance.compare(market, [p["id"], *sims], start=entry["start"])
        out["portfolios"].append(entry)
    if write:
        REPORTS.mkdir(parents=True, exist_ok=True)
        f = REPORTS / (REPORT_FILE if spec is None or spec.key == "rule" else f"sim-exits-{spec.key}.json")
        write_text(f, dumps(out, indent=1))
    return out


