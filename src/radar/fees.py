"""Broker fee schedules: an estimate of a trade's commission from its portfolio's schedule, shown while the trade
is typed. A schedule has one rule per market (a percentage of the trade's value, with a minimum and maximum in the
rule's currency) and an optional FX surcharge. Presets (config/fee_presets.yaml) are copied from the brokers'
public price lists and dated; they go out of date, so the schedule stays editable.

An estimate only: the fee you enter (from your statement) is what counts. No schedule, no rule for the market, or no
exchange rate for converting a minimum gives no estimate, never 0. The FX surcharge is reported apart and left out of
the fee: when the rate you enter is the broker's, its spread is already in it.

Simulations (`SimFees`) charge a real account's schedule on the trades they make for it (an exits replay, a fork's
own later trades), else the flat `backtest.fee_bps`. A simulated trade is booked at Yahoo's mid rate, so there the
FX surcharge is added on trades in another currency than DKK. A trade the schedule can't price (no rule for its
market, no exchange rate for its minimum) pays `fee_bps` too, and is counted, so it is never free."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from functools import cache

import yaml

from .config import CONFIG

MARKETS = ("DK", "NORDIC", "US", "EU", "UK", "OTHER")
MARKET_LABELS = {"DK": "Denmark", "NORDIC": "Nordic", "US": "USA", "EU": "Europe", "UK": "UK", "OTHER": "Other"}
_SUFFIXES = {
    "DK": (".CO",),
    "NORDIC": (".ST", ".OL", ".HE", ".IC"),
    "UK": (".L", ".IL"),
    "EU": (".DE", ".F", ".PA", ".AS", ".BR", ".MI", ".SW", ".MC", ".LS", ".VI", ".IR", ".WA"),
}


def market_of(symbol: str | None) -> str:
    """The market a Yahoo symbol trades on, from its suffix (none: a US listing)."""
    s = (symbol or "").strip().upper()
    for m, suffixes in _SUFFIXES.items():
        if s.endswith(suffixes):
            return m
    return "US" if s and "." not in s and "=" not in s and not s.startswith("^") else "OTHER"


@cache
def presets() -> list[dict]:
    """The broker presets, each with its schedule, the date of the price list and its source."""
    with open(CONFIG / "fee_presets.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)["presets"]


def rule_for(schedule: dict | None, market: str) -> dict | None:
    """The schedule's rule for this market, else its OTHER rule, else None."""
    rules = {r["market"]: r for r in (schedule or {}).get("markets") or []}
    return rules.get(market) or rules.get("OTHER")


def _amount(v: float, ccy: str) -> str:
    return f"{v:,.2f}".rstrip("0").rstrip(".") + f" {ccy}"


def estimate(schedule: dict | None, symbol: str, quantity: float | None, price: float | None, quote_ccy: str | None,
             convert: Callable[[float, str], float | None]) -> dict | None:
    """The estimated commission on a trade, in the quote currency (as trade fees are stored).

    `convert(amount, ccy)` turns an amount in another currency into the quote currency (None when there is no
    rate); minimums and maximums are in the rule's own currency."""
    if not schedule or not quantity or not price or quantity <= 0 or price <= 0 or not quote_ccy:
        return None
    market = market_of(symbol)
    t = terms(schedule, symbol, quote_ccy, convert)
    if t is None:
        return None
    rule = rule_for(schedule, market)
    assert rule is not None                       # terms() found one
    value = quantity * price
    fee = t.fee(value)                            # without the FX surcharge (fx_fee below)
    applied = "pct" if fee == value * t.rate else "min" if fee == t.lo else "max"
    ccy = rule.get("currency") or "DKK"
    basis = f"{float(rule.get('pct') or 0):g}%"
    extra = [f"min {_amount(float(rule['min']), ccy)}" if rule.get("min") is not None else "",
             f"max {_amount(float(rule['max']), ccy)}" if rule.get("max") is not None else ""]
    if any(extra):
        basis += f" ({', '.join(e for e in extra if e)})"
    fx_pct = schedule.get("fx_pct")
    fx_fee = round(value * float(fx_pct) / 100, 2) if fx_pct and quote_ccy != "DKK" else None
    return {"fee": round(fee, 2), "currency": quote_ccy, "market": market, "rule_market": rule["market"],
            "applied": applied, "basis": basis, "fx_pct": float(fx_pct) if fx_pct else None, "fx_fee": fx_fee,
            "preset": schedule.get("preset"), "as_of": schedule.get("as_of")}


@dataclass(frozen=True)
class Terms:
    """A rule in the trade's quote currency: `rate` of the value (a fraction), at least `lo`, at most `hi`, plus
    `fx` of the value (an FX surcharge, outside the minimum and maximum)."""
    rate: float
    lo: float | None = None
    hi: float | None = None
    fx: float = 0.0

    def fee(self, value: float) -> float:
        f = value * self.rate
        if self.lo is not None:
            f = max(f, self.lo)
        if self.hi is not None:
            f = min(f, self.hi)
        return f + value * self.fx

    def value_for_budget(self, budget: float) -> float:
        """The trade value a buy can have when value + fee may cost `budget` (0 when the fee alone eats it)."""
        v = budget / (1 + self.rate + self.fx)
        if self.lo is not None and v * self.rate < self.lo:
            v = (budget - self.lo) / (1 + self.fx)
        elif self.hi is not None and v * self.rate > self.hi:
            v = (budget - self.hi) / (1 + self.fx)
        return max(v, 0.0)

    def value_for_net(self, net: float) -> float:
        """The trade value a sale needs so that value − fee comes to `net`."""
        v = net / (1 - self.rate - self.fx)
        if self.lo is not None and v * self.rate < self.lo:
            v = (net + self.lo) / (1 - self.fx)
        elif self.hi is not None and v * self.rate > self.hi:
            v = (net + self.hi) / (1 - self.fx)
        return v


def terms(schedule: dict | None, symbol: str, quote_ccy: str | None,
          convert: Callable[[float, str], float | None]) -> Terms | None:
    """The schedule's rule for this symbol in its quote currency, or None (no schedule, no rule for the market,
    no quote currency, or no rate for converting a minimum or maximum)."""
    rule = rule_for(schedule, market_of(symbol)) if schedule and quote_ccy else None
    if rule is None:
        return None
    ccy = rule.get("currency") or "DKK"
    limits = {}
    for k in ("min", "max"):
        if rule.get(k) is not None:
            v = float(rule[k]) if ccy == quote_ccy else convert(float(rule[k]), ccy)
            if v is None:
                return None                       # can't tell whether the minimum applies
            limits[k] = v
    return Terms(float(rule.get("pct") or 0) / 100, limits.get("min"), limits.get("max"))


@dataclass
class SimFees:
    """What a simulated trade pays: `schedule` (a real account's, from `for_portfolio`) when it has a rule for the
    trade (with its FX surcharge on a trade not in DKK: the simulation books Yahoo's mid rate), else `bps` of the
    trade's value (settings backtest.fee_bps). `fallbacks` counts the trades that had a schedule but paid `bps`,
    per symbol, with why."""
    bps: float
    schedule: dict | None = None
    source: dict | None = None                    # the portfolio the schedule came from: id, name
    fallbacks: dict = field(default_factory=dict)

    @classmethod
    def for_portfolio(cls, p: dict | None, bps: float) -> SimFees:
        """The fees a simulation of portfolio `p` pays: its own schedule, else its parent's (a fork's source),
        else the flat `bps`."""
        from . import userstore

        seen = set()
        while p and p["id"] not in seen:
            seen.add(p["id"])
            if p.get("fee_schedule"):
                return cls(float(bps), p["fee_schedule"], {"id": p["id"], "name": p["name"]})
            p = userstore.get_portfolio(p["parent_id"]) if p.get("parent_id") else None
        return cls(float(bps))

    def describe(self) -> dict:
        """The fee model, for a run's params."""
        if not self.schedule:
            return {"kind": "bps", "bps": self.bps}
        return {"kind": "schedule", "portfolio_id": self.source["id"] if self.source else None,
                "portfolio": self.source["name"] if self.source else None, "preset": self.schedule.get("preset"),
                "as_of": self.schedule.get("as_of"), "fx_pct": self.schedule.get("fx_pct"), "schedule": self.schedule,
                "fallback_bps": self.bps}

    def report(self) -> dict:
        """describe() plus the trades that fell back to `bps`."""
        return self.describe() | ({"fallbacks": self.fallbacks} if self.schedule else {})

    def terms(self, symbol: str, quote_ccy: str | None, convert: Callable[[float, str], float | None],
              count: bool = True) -> Terms:
        """The terms a trade in `symbol` pays (`count`: it is the trade itself, not its sizing)."""
        flat = Terms(self.bps / 1e4)
        if not self.schedule:
            return flat
        t = terms(self.schedule, symbol, quote_ccy, convert)
        if t is None:
            why = ("no quote currency" if not quote_ccy else
                   f"no rule for {market_of(symbol)}" if rule_for(self.schedule, market_of(symbol)) is None else
                   "no exchange rate for the minimum")
            if count:
                f = self.fallbacks.setdefault(symbol, {"trades": 0, "why": why})
                f["trades"] += 1
            return flat
        fx_pct = self.schedule.get("fx_pct")
        return replace(t, fx=float(fx_pct) / 100) if fx_pct and quote_ccy != "DKK" else t
