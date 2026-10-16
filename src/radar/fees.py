"""Broker fee schedules: an estimate of a trade's commission from its portfolio's schedule, shown while the trade
is typed. A schedule has one rule per market (a percentage of the trade's value, with a minimum and maximum in the
rule's currency) and an optional FX surcharge. Presets (config/fee_presets.yaml) are copied from the brokers'
public price lists and dated; they go out of date, so the schedule stays editable.

An estimate only: the fee you enter (from your statement) is what counts. No schedule, no rule for the market, or no
exchange rate for converting a minimum gives no estimate, never 0. The FX surcharge is reported apart and left out of
the fee: when the rate you enter is the broker's, its spread is already in it."""
from __future__ import annotations

from collections.abc import Callable
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
    rule = rule_for(schedule, market)
    if rule is None:
        return None
    value = quantity * price
    fee = value * float(rule.get("pct") or 0) / 100
    applied = "pct"
    ccy = rule.get("currency") or "DKK"
    limits = {}
    for k in ("min", "max"):
        if rule.get(k) is not None:
            v = float(rule[k]) if ccy == quote_ccy else convert(float(rule[k]), ccy)
            if v is None:
                return None                       # can't tell whether the minimum applies
            limits[k] = v
    if "min" in limits and fee < limits["min"]:
        fee, applied = limits["min"], "min"
    if "max" in limits and fee > limits["max"]:
        fee, applied = limits["max"], "max"
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
