"""Your trading rules checked: a proposed action against every active rule (check), what you hold now against the
rules that are about holdings (standing), and your own past trades against today's rules (replay).

The readings are signals/rules.py's pure functions; this module builds their input (`ctx`) from the store and the
prices as of a day: the book of the rule's portfolios valued in DKK, your past trades, the average cost, the
moving averages, the 3-month return, the momentum score and your journal. Everything is as of the action's day,
so a check of a past day (and the replay) never sees a later price. Nothing is written unless a check is logged.
A mirror, never a gate. Analysis, not advice."""
from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING, Any

import pandas as pd

from . import market_views, notebook, trading_rules, universe, userstore
from .config import typed
from .errors import Invalid
from .portfolios import exposure, trades
from .portfolios.prices import Prices
from .signals import momentum
from .signals import rules as sr
from .signals import score as scoring
from .signals import views as sv
from .sources import fxrates, tracked
from .userstore import rulestore
from .values import num

if TYPE_CHECKING:
    from .market import Market

BARS_3M = 63
EXIT_HEADING = re.compile(r"^#+\s*(exit|exit[- ]?regler|udgangs)", re.I | re.M)
SIDES = ("buy", "sell")


def _frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=trades.TX_COLS + ["id"])
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


class Data:
    """The store and the prices as of one day, computed once per check: portfolios, stored trades, each
    selection's book, the journal."""

    def __init__(self, market: Market, asof: pd.Timestamp, before: tuple[str, int] | None = None) -> None:
        """`asof`: the day (trades and journal entries up to it, prices up to it); `before`: the replay's trade
        (date, id), whose own row and later ones are left out."""
        self.market, self.asof = market, asof
        self.price_asof = min(asof, market.closes.index[-1])
        self.prices = Prices(market)
        trades.ensure_migrated()
        self.ports = {p["id"]: p for p in userstore.portfolios()}
        rows = userstore.transactions(types=userstore.TRADE_TYPES)
        day = asof.date().isoformat()
        if before:          # the replay: the trades before this one (same day: stored earlier)
            d, tid = before
            rows = [r for r in rows if r["date"] < d or (r["date"] == d and r["id"] < tid)]
        else:
            rows = [r for r in rows if r["date"][:10] <= day]
        self.rows = rows
        self._books: dict[tuple, tuple[dict, list]] = {}
        self._journal: list[dict] | None = None
        self._leaders: pd.DataFrame | None = None
        self._meta: dict[tuple, dict] = {}

    # ---- prices as of the day ----

    def close(self, sym: str, raw: bool = True) -> float | None:
        """The traded close (raw=True) or the adjusted close on the day, or the last session before it."""
        frame = self.market.raw_closes() if raw else None
        if frame is None or sym not in frame:
            frame = self.market.closes
        if sym not in frame:
            return None
        s = frame[sym].loc[:self.asof].dropna()
        return num(s.iloc[-1]) if len(s) else None

    def rate(self, sym: str, day=None) -> float | None:
        return self.prices.rate(sym, day if day is not None else self.asof)

    def adjusted(self, sym: str) -> pd.Series:
        c = self.market.closes
        return c[sym].loc[:self.asof].dropna() if sym in c else pd.Series(dtype=float)

    # ---- the book ----

    def book(self, ids: list[int]) -> tuple[dict[str, float], list[str]]:
        """DKK value per held name in these portfolios, and the held names without one."""
        key = tuple(sorted(ids))
        if key not in self._books:
            pos, _ = trades.positions(_frame([r for r in self.rows if r["portfolio_id"] in ids]))
            values: dict[str, float] = {}
            unvalued: list[str] = []
            for _, r in (pos[pos["status"] == "holding"] if not pos.empty else pos).iterrows():
                px, rate = self.close(r["symbol"]), self.rate(r["symbol"])
                if px is None or rate is None:
                    unvalued.append(r["symbol"])
                else:
                    values[r["symbol"]] = float(r["quantity"]) * px * rate
            self._books[key] = (values, unvalued)
        return self._books[key]

    def position(self, sym: str, ids: list[int]) -> dict | None:
        """The name's position over these portfolios (quantity, average cost in the quote currency)."""
        pos, _ = trades.positions(_frame([r for r in self.rows if r["portfolio_id"] in ids and r["symbol"] == sym]))
        if pos.empty or pos.iloc[0]["status"] != "holding":
            return None
        return {"quantity": float(pos.iloc[0]["quantity"]), "avg_price": float(pos.iloc[0]["avg_price"])}

    def past_trades(self, ids: list[int]) -> list[dict]:
        out = []
        for r in self.rows:
            if r["portfolio_id"] not in ids:
                continue
            rate = r.get("fx_rate") or self.rate(r["symbol"], r["date"][:10])
            value = r["quantity"] * r["price"] * rate if rate else None
            out.append({"symbol": r["symbol"], "date": r["date"][:10], "type": r["type"], "value_dkk": value})
        return out

    # ---- what the readings need ----

    def journal(self) -> list[dict]:
        """Journal entries dated up to the day (open ones with their style and whether they have exit rules)."""
        if self._journal is None:
            day = self.asof.date().isoformat()
            out = []
            for e in notebook.listing().get("journal", []):
                if e["date"][:10] > day or not e.get("meta"):
                    continue
                try:
                    body = notebook.document("journal", e["name"])["markdown"]
                except notebook.NotFound:
                    body = ""
                out.append({"ticker": (e["meta"].get("ticker") or "").upper(), "status": e["meta"].get("status"),
                            "style": e["meta"].get("style"), "horizon": e["meta"].get("horizon"),
                            "date": e["date"], "exit_rules": bool(EXIT_HEADING.search(body))})
            self._journal = sorted(out, key=lambda x: x["date"], reverse=True)
        return self._journal

    def entry(self, sym: str) -> dict | None:
        return next((e for e in self.journal() if e["ticker"] == sym.upper() and e["status"] == "open"), None)

    def score(self, sym: str) -> float | None:
        """The momentum score as of the day, against the tracked stocks (as on the dashboard)."""
        mc = typed().momentum.min_history_days
        if self._leaders is None:
            last = self.market.closes.index[-1]
            self._leaders = (self.market.leaders() if self.asof >= last else momentum.leaders(
                self.market.closes.loc[:self.asof], self.market.volumes.loc[:self.asof],
                tracked.stock_groups(offline=True), mc))
        lead = self._leaders
        hit = lead[lead["ticker"] == sym]
        if len(hit):
            return num(hit["score"].iloc[0])
        m = momentum.metrics(self.market.closes.loc[:self.asof], self.market.volumes.loc[:self.asof], [sym], mc)
        return scoring.score_vs(lead, m.iloc[0]) if len(m) else None

    def meta(self, names: list[str], etfs: list[str]) -> dict[str, dict]:
        """Sector, industry, region and correlation with `etfs` per name (the views' matcher input)."""
        key = (tuple(sorted(names)), tuple(sorted(etfs)))
        if key not in self._meta:
            tm = exposure.ticker_meta(names, self.prices)
            sec = universe.sectors(names)
            unknown = {exposure.NOT_LOOKED_THROUGH, exposure.UNKNOWN, exposure.FUND_OTHER}
            clean = lambda v: v if isinstance(v, str) and v and v not in unknown else None  # noqa: E731
            meta = pd.DataFrame({
                "sector": [clean(tm.at[t, "sector"]) if t in tm.index else None for t in names],
                "industry": [clean(sec["industry"].get(t)) if t in sec.index else None for t in names],
                "region": [clean(tm.at[t, "region"]) if t in tm.index else None for t in names],
                "country": None}, index=names)
            bench = tracked.benchmark()
            closes = self.market.closes.loc[:self.asof]
            cfg = market_views.config()
            self._meta[key] = (sv.contexts(names, meta, closes, bench, etfs, market_views.ucits_map(), cfg)
                               if bench in closes else {t: {"ticker": t, **meta.loc[t].to_dict()} for t in names})
        return self._meta[key]


# ---------------- scope ----------------

def selection(rule: dict, data: Data) -> tuple[list[int], str]:
    """The portfolio ids a rule covers, and what they are in words."""
    s = rule.get("scope") or {}
    p = s.get("portfolios", "real")
    ports = list(data.ports.values())
    if isinstance(p, list):
        ids = [i for i in p if i in data.ports]
        label = ", ".join(data.ports[i]["name"] for i in ids) or "no portfolio"
    else:
        ids = [x["id"] for x in ports if not x["archived"] and (p == "all" or x["mode"] == "real")]
        label = "your real portfolios" if p == "real" else "all your portfolios"
    if s.get("kind"):
        ids = [i for i in ids if data.ports[i]["kind"] == s["kind"]]
        label += f" of kind {s['kind']}"
    if s.get("tag"):
        ids = [i for i in ids if s["tag"] in data.ports[i]["tags"]]
        label += f" tagged {s['tag']}"
    return ids, label


# ---------------- the action ----------------

def _portfolio(action: dict) -> dict:
    ref = action.get("portfolio")
    if ref is None or ref == "":
        pid = userstore.default_portfolio()
        p = userstore.get_portfolio(pid) if pid else None
    elif isinstance(ref, int) or str(ref).isdigit():
        p = userstore.get_portfolio(int(ref))
    else:
        p = userstore.portfolio_by_name(str(ref))
    if not p:
        raise Invalid(f"No portfolio {ref!r}." if ref else "Choose a portfolio.")
    return p


def resolve(action: dict, data: Data) -> dict:
    """The action as checked: side, symbol, portfolio, day, the price and DKK rate, quantity and DKK value
    (one of amount_dkk, quantity or fraction (a sell) is given; the others follow when the price is known)."""
    side = (action.get("side") or "").lower()
    if side not in SIDES:
        raise Invalid("The side is buy or sell.")
    sym = (action.get("ticker") or action.get("symbol") or "").strip().upper()
    if not sym:
        raise Invalid("Choose a ticker.")
    given = [k for k in ("amount_dkk", "quantity", "fraction") if action.get(k) is not None]
    if len(given) != 1:
        raise Invalid("Give one of an amount in DKK, a quantity, or (for a sale) a fraction of the position.")
    if "fraction" in given and (side != "sell" or not 0 < float(action["fraction"]) <= 1):
        raise Invalid("A fraction (0-1 of the position) is for a sale.")
    for k in ("amount_dkk", "quantity"):
        if k in given and float(action[k]) <= 0:
            raise Invalid("The amount must be more than 0.")
    if action.get("style") is not None and action["style"] not in trading_rules.config()["styles"]:
        raise Invalid(f"Style is one of {', '.join(trading_rules.config()['styles'])}.")
    p = _portfolio(action)
    price = num(action.get("price")) or data.close(sym)
    rate = data.rate(sym) if sym in data.market.closes else None
    q = num(action.get("quantity"))
    held = data.position(sym, [p["id"]])
    if "fraction" in given:
        if not held:
            raise Invalid(f"{sym} isn't held in {p['name']}.")
        q = held["quantity"] * float(action["fraction"])
    amount = num(action.get("amount_dkk"))
    if amount is None and q is not None and price is not None and rate is not None:
        amount = q * price * rate
    if q is None and amount is not None and price and rate:
        q = amount / (price * rate)
    entry = data.entry(sym)
    horizon = action.get("horizon") or (entry or {}).get("horizon")
    return {"side": side, "symbol": sym, "name": universe.names([sym]).get(sym),
            "portfolio": p["name"], "portfolio_id": p["id"], "portfolio_kind": p["kind"], "portfolio_mode": p["mode"],
            "date": data.asof.date().isoformat(), "price": price, "currency": fxrates.currencies([sym]).get(sym)
            if sym in data.market.closes else None, "rate": rate, "quantity": q, "amount_dkk": amount,
            "fraction": num(action.get("fraction")), "style": action.get("style") or (entry or {}).get("style"),
            "style_from": "action" if action.get("style") else "journal" if (entry or {}).get("style") else None,
            "horizon": horizon, "note": action.get("note")}


def _ctx(rule: dict, act: dict | None, data: Data, ids: list[int], label: str) -> dict[str, Any]:
    values, unvalued = data.book(ids)
    ctx: dict[str, Any] = {"values": values, "unvalued": unvalued, "selection": label,
                           "theme_corr": market_views.config()["theme_corr"]}
    kind = rule["kind"]
    if kind == "max_position_weight":
        ctx["world"] = exposure.diversified()
    if kind == "max_exposure_weight":
        names = list(dict.fromkeys([*values, *([act["symbol"]] if act else [])]))
        etfs = [e["key"] for e in rule["params"]["exposures"] if e["kind"] == "etf"]
        ctx["meta"] = data.meta(names, etfs)
    if act is None:
        return ctx
    sym = act["symbol"]
    ctx |= {"side": act["side"], "symbol": sym, "date": act["date"], "amount_dkk": act["amount_dkk"]}
    if kind in ("no_rebuy_within", "sell_cooling", "max_trades_per_month"):
        ctx["trades"] = data.past_trades(ids)
    if kind == "no_average_down":
        pos = data.position(sym, ids)
        ctx["avg_cost"] = pos["avg_price"] if pos else None
        ctx["price"] = act["price"]
    if kind in ("trend_filter", "no_chase"):
        c = data.adjusted(sym)
        ctx["close"] = num(c.iloc[-1]) if len(c) else None
        ctx["sma"] = {n: num(c.iloc[-n:].mean()) if len(c) >= n else None for n in (50, 200)}
        ctx["ret_3m"] = num(c.iloc[-1] / c.iloc[-1 - BARS_3M] - 1) if len(c) > BARS_3M else None
    if kind == "min_score_rank":
        ctx["score"] = data.score(sym)
    if kind == "account_placement":
        ctx["horizon_months"] = trading_rules.horizon_months(act.get("horizon"))
        ctx["account_kind"] = act["portfolio_kind"]
    if kind == "exit_rule_first":
        e = data.entry(sym)
        ctx["journal"] = {"open": e is not None, "exit_rules": bool(e and e["exit_rules"])}
    return ctx


def _row(rule: dict, v: dict) -> dict:
    return {"rule_id": rule["id"], "statement": rule["statement"], "kind": rule["kind"],
            "kind_label": trading_rules.kinds()[rule["kind"]]["label"], "severity": rule["severity"],
            "rationale": rule.get("rationale"), **v}


def evaluate(rule: dict, act: dict, data: Data) -> dict:
    """One rule against one resolved action."""
    k = trading_rules.kinds()[rule["kind"]]
    ids, label = selection(rule, data)
    na = lambda msg: _row(rule, sr.verdict("not_applicable", msg))  # noqa: E731
    if act["portfolio_id"] not in ids:
        return na(f"{act['portfolio']} is outside the rule's scope ({label})")
    if act["side"] not in k["sides"]:
        return na(f"Applies to {' and '.join(s + 's' for s in k['sides'])} only")
    style = (rule.get("scope") or {}).get("style")
    if style:
        if not act.get("style"):
            return _row(rule, sr.verdict("unknown", f"The rule is for {style} positions, and this one has no style: "
                                                    "give one, or add style: to its journal entry"))
        if act["style"] != style:
            return na(f"For {style} positions; this is {act['style']}")
    v = sr.ACTION[rule["kind"]](rule["params"], _ctx(rule, act, data, ids, label), trading_rules.near_band(rule["kind"]))
    if rule["kind"] == "judgment":
        v["message"] = f"Ask yourself: {rule['statement']}"
    return _row(rule, v)


def _sort(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (sr.ORDER[r["status"]], sr.SEVERITY_ORDER[r["severity"]], r["rule_id"]))


def as_of(day) -> pd.Timestamp:
    d = pd.Timestamp(day or date.today()).normalize()
    if d.date() > date.today():
        raise Invalid("The date is in the future.")
    return d


def check(market: Market, action: dict, rules: list[dict] | None = None, log: bool = False) -> dict:
    """Every active rule against a proposed action, breaks first. `log` stores the check (rule_checks)."""
    data = Data(market, as_of(action.get("date")))
    act = resolve(action, data)
    rules = rulestore.rules("active") if rules is None else rules
    rows = _sort([evaluate(r, act, data) for r in rules])
    notes = []
    if act["amount_dkk"] is None:
        notes.append(f"No DKK value for the trade: no price or exchange rate for {act['symbol']}")
    if act["portfolio_mode"] == "virtual":
        notes.append(f"{act['portfolio']} is a virtual portfolio: rules about your real portfolios don't apply")
    out = {"disclaimer": trading_rules.DISCLAIMER, "asof": data.price_asof.date().isoformat(), "action": act,
           "verdicts": rows, "summary": sr.summary(rows), "notes": notes, "check_id": None}
    if log:
        out["check_id"] = rulestore.log_check(dict(action, **{k: act[k] for k in ("symbol", "portfolio", "date")}),
                                              rows)
    return out


def trade_check(market: Market, row: dict) -> dict | None:
    """A new BUY/SELL row (the portfolio editor's, `radar portfolio add`'s, the add_trade tool's) against your
    active rules; None without rules, for other rows, or when the rules can't read it (the row's own checks say
    why in their words)."""
    from .portfolios import checks

    if row.get("type") not in userstore.TRADE_TYPES or not row.get("symbol") or not rulestore.rules("active"):
        return None
    pid, _ = checks.target_portfolio(row)
    if pid is None or pid < 0:
        return None
    action = {"side": row["type"].lower(), "ticker": row["symbol"], "portfolio": pid, "quantity": row.get("quantity"),
              "price": row.get("price"), "date": str(row.get("date") or "")[:10] or None}
    try:
        return check(market, action)
    except Invalid:
        return None


def trade_issues(result: dict | None) -> list[dict]:
    """A check's breaks and near ones as the editor's warnings to confirm: never errors, nothing is blocked."""
    words = {"breaks": "breaks", "near": "comes close to"}
    return [{"level": "warning", "field": "rules",
             "message": f"This {words[v['status']]} your {v['severity']} rule \"{v['statement']}\": {v['message']}."
             + (f" {v['comply']}." if v.get("comply") else "")}
            for v in (result or {}).get("verdicts", []) if v["status"] in words]


def log_trade(result: dict | None, tx_id: int, reason: str | None) -> int | None:
    """Log a saved trade's check when it broke or came close to a rule: you went ahead, and why."""
    if not result or not any(v["status"] in ("breaks", "near") for v in result["verdicts"]):
        return None
    cid = rulestore.log_check(result["action"], result["verdicts"])
    rulestore.set_decision(cid, "went_ahead", reason, tx_id)
    return cid


def standing(market: Market, rules: list[dict] | None = None) -> dict:
    """What you hold now against the rules about holdings (name, theme and core weights, the number of names):
    the breaks and the near ones, and a flag list per name."""
    data = Data(market, as_of(None))
    rules = rulestore.rules("active") if rules is None else rules
    rows, notes = [], []
    for r in rules:
        fn = sr.STANDING.get(r["kind"])
        if fn is None:
            continue
        ids, label = selection(r, data)
        ctx = _ctx(r, None, data, ids, label)
        style = (r.get("scope") or {}).get("style")
        if style:
            labelled = {e["ticker"]: e["style"] for e in data.journal() if e["status"] == "open" and e["style"]}
            ctx["only"] = {s for s in ctx["values"] if labelled.get(s.upper()) == style}
            unlabelled = [s for s in ctx["values"] if s.upper() not in labelled]
            if unlabelled:
                notes.append(f"Rule #{r['id']} is for {style} positions; {', '.join(unlabelled)} have no style in "
                             "an open journal entry and are left out")
        rows += [_row(r, v) for v in fn(r["params"], ctx, trading_rules.near_band(r["kind"]))]
    rows = _sort(rows)
    flags: dict[str, list[dict]] = {}
    for x in rows:
        for s in x.get("symbols") or ([x["symbol"]] if x.get("symbol") else []):
            flags.setdefault(s, []).append({"rule_id": x["rule_id"], "statement": x["statement"],
                                            "severity": x["severity"], "status": x["status"]})
    return {"disclaimer": trading_rules.DISCLAIMER, "asof": data.price_asof.date().isoformat(), "rows": rows,
            "summary": sr.summary(rows), "flags": flags, "notes": notes}


def digest(market: Market) -> dict | None:
    """The short form for summary.json (the monthly brief): the standing breaks and near ones. None without rules."""
    rules = rulestore.rules("active")
    if not rules:
        return None
    s = standing(market, rules)
    return {"asof": s["asof"], "rules": len(rules), "disclaimer": s["disclaimer"],
            "standing": [{k: x.get(k) for k in ("rule_id", "statement", "severity", "status", "message", "symbol")}
                         for x in s["rows"]]}


# ---------------- replay: would your rules have helped? ----------------

def _after(prices: Prices, sym: str, day: pd.Timestamp, bench: str) -> dict:
    """The name's DKK return from the trade day's close to the last close, and ACWI's over the same days."""
    out: dict[str, Any] = {"ret": None, "acwi": None, "rel": None, "days": None}
    s, b = prices.dkk(sym), prices.dkk(bench)
    if s is None or b is None:
        return out
    s0, b0 = s.loc[:day], b.loc[:day]
    if s0.empty or b0.empty or s.index[-1] <= s0.index[-1]:
        return out
    r, a = float(s.iloc[-1] / s0.iloc[-1] - 1), float(b.iloc[-1] / b0.iloc[-1] - 1)
    return {"ret": r, "acwi": a, "rel": (1 + r) / (1 + a) - 1, "days": int((s.index[-1] - s0.index[-1]).days)}


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def replay(market: Market, start: str | None = None, end: str | None = None,
           rules: list[dict] | None = None) -> dict:
    """Your real BUY/SELL trades from `start` to `end`, each checked against today's active rules as of its day
    (the holdings and trades before it, prices up to that day), with what the name did afterwards in DKK against
    ACWI over the same days. Per rule and side: the trades it would have flagged and those it let through, their
    number and mean return relative to ACWI. Descriptive and small-n: no significance is claimed."""
    rules = [r for r in (rulestore.rules("active") if rules is None else rules) if r["kind"] != "judgment"]
    trades.ensure_migrated()
    real = set(userstore.portfolio_ids("real", include_archived=True))
    rows = [r for r in userstore.transactions(types=userstore.TRADE_TYPES) if r["portfolio_id"] in real
            and (start is None or r["date"][:10] >= start) and (end is None or r["date"][:10] <= end)]
    prices, bench = Prices(market), tracked.benchmark()
    out_trades = []
    for t in rows:
        day = pd.Timestamp(t["date"][:10])
        data = Data(market, day, before=(t["date"], t["id"]))
        action = {"side": t["type"].lower(), "ticker": t["symbol"], "portfolio": t["portfolio_id"],
                  "quantity": t["quantity"], "price": t["price"], "date": t["date"][:10]}
        try:
            act = resolve(action, data)
        except Invalid as e:
            out_trades.append({"id": t["id"], "date": t["date"][:10], "side": action["side"], "symbol": t["symbol"],
                               "portfolio": t["portfolio"], "error": str(e), "verdicts": [], "after": None})
            continue
        verdicts = _sort([evaluate(r, act, data) for r in rules])
        out_trades.append({"id": t["id"], "date": act["date"], "side": act["side"], "symbol": act["symbol"],
                           "portfolio": act["portfolio"], "amount_dkk": act["amount_dkk"], "error": None,
                           "verdicts": [{k: v[k] for k in ("rule_id", "status", "message", "severity")}
                                        for v in verdicts if v["status"] != "not_applicable"],
                           "after": _after(prices, act["symbol"], day, bench)})
    per_rule = []
    for r in rules:
        for side in trading_rules.kinds()[r["kind"]]["sides"]:
            flagged, passed, unknown = [], [], 0
            for t in out_trades:
                if t["side"] != side:
                    continue
                v = next((x for x in t["verdicts"] if x["rule_id"] == r["id"]), None)
                if v is None:
                    continue
                rel = (t["after"] or {}).get("rel")
                if v["status"] in ("breaks", "near"):
                    flagged.append({"id": t["id"], "date": t["date"], "symbol": t["symbol"], "status": v["status"],
                                    "rel": rel})
                elif v["status"] == "complies":
                    passed.append(rel)
                else:
                    unknown += 1
            per_rule.append({"rule_id": r["id"], "statement": r["statement"], "severity": r["severity"], "side": side,
                             "n_flagged": len(flagged), "n_passed": len(passed), "n_unknown": unknown,
                             "flagged_rel": _mean([f["rel"] for f in flagged if f["rel"] is not None]),
                             "passed_rel": _mean([x for x in passed if x is not None]), "flagged": flagged})
    return {"disclaimer": trading_rules.DISCLAIMER, "asof": market.closes.index[-1].date().isoformat(),
            "start": start, "end": end, "n_trades": len(out_trades), "rules": per_rule, "trades": out_trades,
            "note": ("Today's rules on your past trades, each as of its own day; afterwards = the name's DKK return "
                     "from that day's close to the last close, relative to ACWI over the same days. Descriptive and "
                     "a small sample: it shows what happened, not that a rule works.")}
