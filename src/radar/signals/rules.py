"""Your trading rules read against a proposed action or against what you hold now: one pure function per rule
kind, `(params, ctx) -> verdict`. `ctx` is a plain dict of numbers, dates and labels built by rulecheck.py; nothing
here reads a file.

A verdict is {status, value, limit, unit, message, comply}. status: breaks, near (inside the kind's band of the
limit), complies, not_applicable (the wrong side, or the action doesn't touch what the rule is about), unknown (an
input is missing, named in the message) or judgment (a question only you can answer). Unknown never counts as
complying. Weights are shares of the invested DKK value of the rule's portfolios (cash is not counted), and the
message says so.

ctx: side (buy/sell; None when standing), symbol, date (YYYY-MM-DD), amount_dkk (the trade's DKK value), values
(DKK per held name in the rule's portfolios, before the action), unvalued (held names without a DKK value),
selection (what the weights are a share of, in words), meta (per name: ticker, sector, industry, region, country,
ucits_of, corr) and theme_corr, trades (past trades in the rule's portfolios: symbol, date, type, value_dkk),
avg_cost and price (the name's average cost and the day's close, quote currency), sma ({50: .., 200: ..}), ret_3m,
score, horizon_months, account_kind, journal ({open, exit_rules} or None when unknown), only (the names a
style-scoped standing check covers), world (broad world funds: spread over thousands of names, never one name
to cap)."""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from . import views as sv

EPS = 1e-9
Verdict = dict


def verdict(status: str, message: str, value=None, limit=None, unit: str | None = None,
            comply: str | None = None, symbol: str | None = None) -> Verdict:
    return {"status": status, "value": value, "limit": limit, "unit": unit, "message": message, "comply": comply,
            "symbol": symbol}


def pct(x: float | None) -> str:
    return "–" if x is None else f"{x * 100:.1f} %"


def dkk(x: float | None) -> str:
    return "–" if x is None else f"{x:,.0f} DKK".replace(",", ".")


def _day(s: str) -> date:
    return date.fromisoformat(str(s)[:10])


def _of(ctx: dict) -> str:
    """What a weight is a share of, said every time."""
    total = sum(ctx["values"].values())
    out = f"of {ctx.get('selection') or 'your portfolios'} ({dkk(total)} invested, cash not counted"
    if ctx.get("unvalued"):
        out += f"; {', '.join(ctx['unvalued'])} without a DKK value left out"
    return out + ")"


def _max_status(value: float, limit: float, band: float) -> str:
    return "breaks" if value > limit + EPS else "near" if value >= limit * (1 - band) - EPS else "complies"


def _min_status(value: float, limit: float, band: float) -> str:
    return "breaks" if value < limit - EPS else "near" if value <= limit * (1 + band) + EPS else "complies"


def _amount(ctx: dict) -> Verdict | None:
    if ctx.get("amount_dkk") is None:
        return verdict("unknown", f"No DKK value for the trade in {ctx['symbol']}: no price or exchange rate on "
                                  f"{ctx['date']}.")
    return None


def _cap(label: str, held: float, lim: float, band: float, ctx: dict) -> Verdict:
    """A buy adding to `held` (DKK) against a cap of `lim` (a share) of the selection."""
    total, x = sum(ctx["values"].values()), ctx["amount_dkk"]
    post = (held + x) / (total + x) if total + x > 0 else None
    if post is None:
        return verdict("unknown", "Nothing valued in these portfolios, so there is no weight to check.")
    status = _max_status(post, lim, band)
    fits = (lim * total - held) / (1 - lim) if lim < 1 else None
    comply = None
    if status != "complies":
        comply = (f"{label} is already at {pct(held / total if total else None)}: no buy fits under the cap"
                  if fits is not None and fits <= 0 else
                  f"At most {dkk(fits)} fits under the cap" if fits is not None else None)
    return verdict(status, f"{label} would be {pct(post)} {_of(ctx)}; the cap is {pct(lim)}", post, lim, "pct", comply)


# ---------------- action kinds ----------------

def max_position_weight(p: dict, ctx: dict, band: float) -> Verdict:
    if (miss := _amount(ctx)) is not None:
        return miss
    if ctx["symbol"] in ctx.get("world", ()):
        return verdict("not_applicable", f"{ctx['symbol']} is a world or index fund: spread over a whole index")
    if ctx["symbol"] in ctx.get("unvalued", []):
        return verdict("unknown", f"{ctx['symbol']} is held without a DKK value, so its weight is unknown.")
    return _cap(ctx["symbol"], ctx["values"].get(ctx["symbol"], 0.0), p["pct"] / 100, band, ctx)


def matches(p: dict, ctx: dict, sym: str) -> bool | None:
    """Whether a name counts towards a theme cap; None when its data can't tell: none of the sector, industry,
    region or correlation the exposures ask about is known for it."""
    m = {"ticker": sym, **((ctx.get("meta") or {}).get(sym) or {})}
    if any(sv.match(e, m, ctx.get("theme_corr", 0.5)) for e in p["exposures"]):
        return True
    corr = m.get("corr") or {}
    known = {"sector": bool(m.get("sector")), "industry": bool(m.get("industry")),
             "region": bool(m.get("region") or m.get("country")),
             "etf": any(corr.get(e["key"]) == corr.get(e["key"]) and corr.get(e["key"]) is not None
                        for e in p["exposures"] if e["kind"] == "etf")}
    asks = {e["kind"] for e in p["exposures"]} - {"ticker"}
    return None if asks and not any(known[k] for k in asks) else False


def _theme(p: dict, ctx: dict, names) -> tuple[float, list[str], list[str]]:
    held, inside, unsure = 0.0, [], []
    for s in names:
        hit = matches(p, ctx, s)
        if hit:
            held += ctx["values"][s]
            inside.append(s)
        elif hit is None:
            unsure.append(s)
    return held, inside, unsure


def _theme_label(p: dict) -> str:
    return " / ".join(e["key"] for e in p["exposures"])


def max_exposure_weight(p: dict, ctx: dict, band: float) -> Verdict:
    if (miss := _amount(ctx)) is not None:
        return miss
    sym, label = ctx["symbol"], _theme_label(p)
    hit = matches(p, ctx, sym)
    if hit is None:
        return verdict("unknown", f"Can't tell whether {sym} counts towards {label}: its sector, industry, region "
                                  "or returns are unknown.")
    held, inside, unsure = _theme(p, ctx, [s for s in ctx["values"] if s != sym])
    if hit is False:
        total = sum(ctx["values"].values())
        return verdict("not_applicable", f"{sym} doesn't count towards {label} (it stands at "
                                         f"{pct(held / total if total else None)})", symbol=sym)
    v = _cap(label, held + ctx["values"].get(sym, 0.0), p["pct"] / 100, band, ctx)
    if unsure:
        v["message"] += f". Unknown whether {', '.join(unsure)} count"
    return v


def min_core_weight(p: dict, ctx: dict, band: float) -> Verdict:
    if (miss := _amount(ctx)) is not None:
        return miss
    core, lim = set(p["core"]), p["pct"] / 100
    sym, x, side = ctx["symbol"], ctx["amount_dkk"], ctx["side"]
    total = sum(ctx["values"].values())
    c = sum(v for s, v in ctx["values"].items() if s in core)
    in_core = sym in core
    if side == "sell":
        x = min(x, ctx["values"].get(sym, 0.0))
    post_total = total + x if side == "buy" else total - x
    post_c = c + x if side == "buy" and in_core else c - x if side == "sell" and in_core else c
    pre = c / total if total > 0 else None
    post = post_c / post_total if post_total > 0 else None
    if post is None:
        return verdict("unknown", "Nothing valued in these portfolios after the trade, so there is no core weight.")
    msg = f"The core ({', '.join(sorted(core))}) would be {pct(post)} {_of(ctx)}; the floor is {pct(lim)}"
    if pre is not None and post >= pre - EPS:
        return verdict("complies", msg + (" (the trade moves it up)" if post > pre + EPS else ""), post, lim, "pct")
    status = _min_status(post, lim, band)
    comply = None
    if status != "complies":
        fits = c / lim - total if side == "buy" else (c - lim * total) / (1 - lim) if lim < 1 else None
        comply = ("No amount keeps the core above its floor" if fits is None or fits <= 0
                  else f"At most {dkk(fits)} keeps the core at its floor")
    return verdict(status, msg, post, lim, "pct", comply)


def min_ticket(p: dict, ctx: dict, band: float) -> Verdict:
    if (miss := _amount(ctx)) is not None:
        return miss
    x, lim = ctx["amount_dkk"], float(p["dkk"])
    status = "breaks" if x < lim - EPS else "complies"
    return verdict(status, f"The trade is {dkk(x)}; the minimum is {dkk(lim)}", x, lim, "dkk",
                   f"Trade at least {dkk(lim)}, or skip it" if status == "breaks" else None)


def _count(ctx: dict) -> int:
    return len(ctx["values"]) + len(ctx.get("unvalued") or [])


def max_positions(p: dict, ctx: dict, band: float) -> Verdict:
    sym = ctx["symbol"]
    if sym in ctx["values"] or sym in (ctx.get("unvalued") or []):
        return verdict("not_applicable", f"{sym} is already held: no new name")
    n = _count(ctx) + 1
    status = "breaks" if n > p["n"] else "near" if n == p["n"] else "complies"
    return verdict(status, f"{sym} would be name number {n} in {ctx.get('selection') or 'your portfolios'}; the "
                           f"maximum is {p['n']}", n, p["n"], "count",
                   "Sell a name first, or add to one you hold" if status == "breaks" else None)


def no_rebuy_within(p: dict, ctx: dict, band: float) -> Verdict:
    sym, day = ctx["symbol"], _day(ctx["date"])
    sales = [_day(t["date"]) for t in ctx.get("trades") or [] if t["symbol"] == sym and t["type"] == "SELL"
             and _day(t["date"]) <= day]
    if not sales:
        return verdict("complies", f"No sale of {sym} in {ctx.get('selection') or 'your portfolios'}")
    last = max(sales)
    since = (day - last).days
    if since >= p["days"]:
        return verdict("complies", f"{sym} was last sold {last.isoformat()}, {since} days ago; the pause is "
                                   f"{p['days']} days", since, p["days"], "days")
    allowed = last + timedelta(days=p["days"])
    return verdict("breaks", f"{sym} was sold {last.isoformat()}, {since} days ago; the pause is {p['days']} days",
                   since, p["days"], "days", f"Allowed from {allowed.isoformat()}")


def sell_cooling(p: dict, ctx: dict, band: float) -> Verdict:
    if (miss := _amount(ctx)) is not None:
        return miss
    day, lim = _day(ctx["date"]), p["pct"] / 100
    start = day - timedelta(days=p["days"])
    window = [t for t in ctx.get("trades") or [] if t["type"] == "SELL" and start < _day(t["date"]) <= day]
    if any(t.get("value_dkk") is None for t in window):
        bad = sorted({t["symbol"] for t in window if t.get("value_dkk") is None})
        return verdict("unknown", f"No DKK value for the recent sale of {', '.join(bad)}, so the week's sales are "
                                  "unknown.")
    sold = sum(t["value_dkk"] for t in window)
    base = sum(ctx["values"].values()) + sold
    if base <= 0:
        return verdict("unknown", "Nothing valued in these portfolios, so there is no share to check.")
    x = min(ctx["amount_dkk"], ctx["values"].get(ctx["symbol"], ctx["amount_dkk"]))
    share = (sold + x) / base
    status = _max_status(share, lim, band)
    msg = (f"This sale and the {dkk(sold)} sold in the last {p['days']} days would be {pct(share)} of what "
           f"{ctx.get('selection') or 'your portfolios'} held before them ({dkk(base)}); the limit is {pct(lim)}")
    comply = None
    if status != "complies":
        fits = lim * base - sold
        clears = max(_day(t["date"]) for t in window) + timedelta(days=p["days"]) if window else None
        parts = [f"at most {dkk(fits)} now" if fits > 0 else "nothing more now"]
        if clears:
            parts.append(f"the window clears {clears.isoformat()}")
        comply = "Sell " + parts[0] + (f", or wait: {parts[1]}" if len(parts) > 1 else "")
    return verdict(status, msg, share, lim, "pct", comply)


def max_trades_per_month(p: dict, ctx: dict, band: float) -> Verdict:
    day = _day(ctx["date"])
    n = sum(1 for t in ctx.get("trades") or [] if _day(t["date"]).replace(day=1) == day.replace(day=1)
            and _day(t["date"]) <= day) + 1
    status = "breaks" if n > p["n"] else "near" if n == p["n"] else "complies"
    nxt = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return verdict(status, f"This would be trade number {n} in {day:%B %Y} in {ctx.get('selection') or 'your portfolios'}"
                           f"; the maximum is {p['n']}", n, p["n"], "count",
                   f"Wait until {nxt.isoformat()}" if status == "breaks" else None)


def no_average_down(p: dict, ctx: dict, band: float) -> Verdict:
    sym = ctx["symbol"]
    if ctx.get("avg_cost") is None and sym not in ctx["values"] and sym not in (ctx.get("unvalued") or []):
        return verdict("not_applicable", f"{sym} isn't held: nothing to average down")
    if ctx.get("avg_cost") is None or ctx.get("price") is None:
        return verdict("unknown", f"No {'average cost' if ctx.get('avg_cost') is None else 'price'} for {sym}.")
    loss = ctx["price"] / ctx["avg_cost"] - 1
    lim = p["loss_pct"] / 100
    status = "breaks" if loss < -lim - EPS else "near" if loss <= -lim * (1 - band) + EPS else "complies"
    return verdict(status, f"{sym} is at {ctx['price']:.2f}, {loss:+.1%} from your average cost of "
                           f"{ctx['avg_cost']:.2f}; the limit is -{pct(lim)}", loss, -lim, "pct")


def trend_filter(p: dict, ctx: dict, band: float) -> Verdict:
    ma, sym = int(p["ma"]), ctx["symbol"]
    level, px = (ctx.get("sma") or {}).get(ma), ctx.get("close")
    if level is None or px is None:
        return verdict("unknown", f"Fewer than {ma} days of prices for {sym}, so there is no {ma}-day average.")
    status = "breaks" if px < level - EPS else "near" if px <= level * (1 + band) + EPS else "complies"
    return verdict(status, f"{sym} closed at {px:.2f}, {px / level - 1:+.1%} from its {ma}-day average of {level:.2f}",
                   px / level - 1, 0.0, "pct", f"Wait for a close above {level:.2f}" if status == "breaks" else None)


def no_chase(p: dict, ctx: dict, band: float) -> Verdict:
    r, lim = ctx.get("ret_3m"), p["ret_3m_pct"] / 100
    if r is None:
        return verdict("unknown", f"Fewer than 3 months of prices for {ctx['symbol']}.")
    status = _max_status(r, lim, band)
    return verdict(status, f"{ctx['symbol']} rose {r:+.1%} over 3 months; the limit is +{pct(lim)}", r, lim, "pct")


def min_score_rank(p: dict, ctx: dict, band: float) -> Verdict:
    s = ctx.get("score")
    if s is None:
        return verdict("unknown", f"No momentum score for {ctx['symbol']} (not a tracked stock, or less than a year "
                                  "of prices).")
    status = _min_status(s, p["score"], band)
    return verdict(status, f"{ctx['symbol']} has a momentum score of {s:.0f}; the minimum is {p['score']}",
                   s, p["score"], "score")


def account_placement(p: dict, ctx: dict, band: float) -> Verdict:
    h = ctx.get("horizon_months")
    if h is None:
        return verdict("unknown", "No horizon given for the action (or in its journal entry).")
    if h > p["horizon_max"]:
        return verdict("not_applicable", f"A {h}-month horizon isn't short-term (up to {p['horizon_max']} months)")
    kind = ctx.get("account_kind")
    status = "complies" if kind == p["account_kind"] else "breaks"
    return verdict(status, f"A {h}-month trade in a {kind or 'unknown'} account; short-term trades belong in "
                           f"{p['account_kind']}", h, p["horizon_max"], "months",
                   f"Place it in your {p['account_kind']} account" if status == "breaks" else None)


def exit_rule_first(p: dict, ctx: dict, band: float) -> Verdict:
    j, sym = ctx.get("journal"), ctx["symbol"]
    if j is None:
        return verdict("unknown", "Your journal couldn't be read.")
    if j.get("open") and j.get("exit_rules"):
        return verdict("complies", f"An open journal entry for {sym} has exit rules")
    return verdict("breaks", f"An open journal entry for {sym} {'has no Exit rules section' if j.get('open') else 'is missing'}",
                   comply="Write the journal entry with its exit rules first (/journal)")


def judgment(p: dict, ctx: dict, band: float) -> Verdict:
    return verdict("judgment", "A question only you can answer")


ACTION: dict[str, Callable[[dict, dict, float], Verdict]] = {
    "max_position_weight": max_position_weight, "max_exposure_weight": max_exposure_weight,
    "min_core_weight": min_core_weight, "min_ticket": min_ticket, "max_positions": max_positions,
    "no_rebuy_within": no_rebuy_within, "sell_cooling": sell_cooling, "max_trades_per_month": max_trades_per_month,
    "no_average_down": no_average_down, "trend_filter": trend_filter, "no_chase": no_chase,
    "min_score_rank": min_score_rank, "account_placement": account_placement, "exit_rule_first": exit_rule_first,
    "judgment": judgment,
}


# ---------------- standing: what you hold now ----------------

def _names(ctx: dict) -> list[str]:
    only = ctx.get("only")
    return [s for s in ctx["values"] if only is None or s in only]


def standing_max_position_weight(p: dict, ctx: dict, band: float) -> list[Verdict]:
    total, lim = sum(ctx["values"].values()), p["pct"] / 100
    out = []
    for s in _names(ctx):
        w = ctx["values"][s] / total if total > 0 else None
        if w is None or s in ctx.get("world", ()):
            continue
        status = _max_status(w, lim, band)
        if status != "complies":
            out.append(verdict(status, f"{s} is {pct(w)} {_of(ctx)}; the cap is {pct(lim)}", w, lim, "pct",
                               f"About {dkk(ctx['values'][s] - lim * total)} above the cap" if status == "breaks"
                               else None, symbol=s))
    return out


def standing_max_exposure_weight(p: dict, ctx: dict, band: float) -> list[Verdict]:
    total, lim = sum(ctx["values"].values()), p["pct"] / 100
    held, inside, unsure = _theme(p, ctx, _names(ctx))
    if total <= 0 or not inside:
        return []
    w = held / total
    status = _max_status(w, lim, band)
    if status == "complies":
        return []
    msg = f"{_theme_label(p)} ({', '.join(inside)}) is {pct(w)} {_of(ctx)}; the cap is {pct(lim)}"
    if unsure:
        msg += f". Unknown whether {', '.join(unsure)} count"
    return [verdict(status, msg, w, lim, "pct", symbol=None) | {"symbols": inside}]


def standing_min_core_weight(p: dict, ctx: dict, band: float) -> list[Verdict]:
    total, lim = sum(ctx["values"].values()), p["pct"] / 100
    if total <= 0:
        return []
    w = sum(v for s, v in ctx["values"].items() if s in set(p["core"])) / total
    status = _min_status(w, lim, band)
    if status == "complies":
        return []
    return [verdict(status, f"The core ({', '.join(p['core'])}) is {pct(w)} {_of(ctx)}; the floor is {pct(lim)}",
                    w, lim, "pct")]


def standing_max_positions(p: dict, ctx: dict, band: float) -> list[Verdict]:
    n = _count(ctx)
    status = "breaks" if n > p["n"] else "near" if n == p["n"] else "complies"
    if status == "complies":
        return []
    return [verdict(status, f"{n} names in {ctx.get('selection') or 'your portfolios'}; the maximum is {p['n']}",
                    n, p["n"], "count")]


STANDING: dict[str, Callable[[dict, dict, float], list[Verdict]]] = {
    "max_position_weight": standing_max_position_weight, "max_exposure_weight": standing_max_exposure_weight,
    "min_core_weight": standing_min_core_weight, "max_positions": standing_max_positions,
}

ORDER = {"breaks": 0, "near": 1, "unknown": 2, "judgment": 3, "complies": 4, "not_applicable": 5}
SEVERITY_ORDER = {"hard": 0, "soft": 1, "reminder": 2}


def summary(rows: list[dict]) -> dict:
    """Each status counted per severity, and in total."""
    out: dict = {s: {sev: 0 for sev in SEVERITY_ORDER} for s in ORDER}
    for r in rows:
        out[r["status"]][r["severity"]] += 1
    return {"by_status": out, "total": {s: sum(v.values()) for s, v in out.items()}}
