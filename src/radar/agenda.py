"""The calendar: what is coming for the names you hold and watch, and which of it to look at first.

Earnings and ex-dividend dates of held and watched stocks, the review dates of your open journal entries and the
time stops of your proposals' picks, in a window of days. Each item carries the reasons it is highlighted, by
stated rules (`calendar.highlight`): how much of the money is at stake, how close the price is to the review level,
whether the momentum is fading, whether the quarter's estimate is being cut, and how sure the date is. The level
(high / normal / info) follows from those reasons; nothing here says what to do.

`build` and the rules are pure: the caller passes in the holdings rows (`mine.table`), the weights, the calendar
history (`external.load_calendar`), the screener's dates, the journal and the exit check, and `today`, which is the
data's as-of date (the benchmark's last close), so the same data gives the same items. `collect` gathers those for
a selection of portfolios; `cached` keeps its result until one of them changes. Analysis, not advice."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pandas as pd

from . import mine, notebook, propose, userstore
from .config import settings, typed
from .config_schema import Calendar
from .portfolios import exposure
from .portfolios.prices import Prices
from .sources import external, tracked, valuation

if TYPE_CHECKING:
    from .market import Market

LEVELS = ("high", "normal", "info")
ESCALATE = ("big_position", "near_level", "momentum_weak", "estimates_cut")   # with `held` and soon: high
WEAK_FLAGS = ("losing momentum", "below 200d")


# ---------------- the next earnings date ----------------

def _day(v) -> date | None:
    if v is None or (not isinstance(v, str) and pd.isna(v)):   # NaT passes for a date: ask pandas
        return None
    return pd.Timestamp(v).date()


def _fmt(d: date) -> str:
    return f"{d.day} {d:%b}"


def resolve_earnings(hist: pd.DataFrame, snapshot: tuple[Any, Any] | None, today: date,
                     stale_days: int) -> dict:
    """One stock's next earnings date, from its calendar reads (`hist`: its rows of the history file) and the
    weekly screener (`snapshot`: its (earnings date, snapshot date)), and how sure it is.

    The latest read wins while it is at most `stale_days` old and its date hasn't passed; else the screener's
    date if it is today or later (the screener keeps a date that has just passed for up to a week); else an older
    read's date that is still to come, marked stale; else none, with the reason. `moved_from` is the previous
    read's date when the new one falls outside the window that read gave (a window narrowing to a day is not a
    move). Returns start, end, is_range, source, read_on, stale, moved_from and the read used (`row`), or
    start None and `reason`."""
    rows = hist.sort_values("fetched") if not hist.empty else hist
    last = rows.iloc[-1] if not rows.empty else None
    snap_day, snap_on = (_day(snapshot[0]), _day(snapshot[1])) if snapshot else (None, None)

    def from_row(r, stale: bool) -> dict:
        start, end = _day(r["earnings_start"]), _day(r["earnings_end"])
        assert start is not None and end is not None
        return {"start": start, "end": end, "is_range": start != end, "source": "yahoo_detail",
                "read_on": _day(r["fetched"]), "stale": stale, "moved_from": _moved(rows, r), "row": r}

    read_on = _day(last["fetched"]) if last is not None else None
    last_end = _day(last["earnings_end"]) if last is not None else None
    upcoming = last_end is not None and last_end >= today
    fresh = read_on is not None and (today - read_on).days <= stale_days
    if upcoming and fresh:
        return from_row(last, stale=False)
    if snap_day is not None and snap_day >= today:
        return {"start": snap_day, "end": snap_day, "is_range": False, "source": "yahoo_screener",
                "read_on": snap_on, "stale": True, "moved_from": None, "row": None}
    if upcoming:
        return from_row(last, stale=True)
    if read_on is None:
        reason = "not read yet"
    elif last_end is None:
        reason = f"Yahoo gave no date (read {_fmt(read_on)})"
    else:
        reason = f"the last known date ({_fmt(last_end)}) has passed and no new one is known yet"
    return {"start": None, "reason": reason}


def _moved(rows: pd.DataFrame, r) -> date | None:
    """The previous read's date, when this read's window lies outside the one that read gave while it was still
    to come (a report that has passed starts a new cycle: not a move)."""
    earlier = rows[(rows["fetched"] < r["fetched"]) & rows["earnings_start"].notna()]
    if earlier.empty:
        return None
    p = earlier.iloc[-1]
    p_start, p_end = _day(p["earnings_start"]), _day(p["earnings_end"])
    start, end, read_on = _day(r["earnings_start"]), _day(r["earnings_end"]), _day(r["fetched"])
    if p_start is None or p_end is None or start is None or end is None or read_on is None or p_end < read_on:
        return None
    return None if p_start <= start and end <= p_end else p_start


# ---------------- reasons ----------------

def _reason(key: str, text: str, value: float | None = None) -> dict:
    return {"key": key, "text": text, "value": value}


def _date_reasons(e: dict) -> list[dict]:
    out = []
    if e["is_range"]:
        out.append(_reason("unconfirmed", f"no set date: Yahoo expects {_fmt(e['start'])}–{_fmt(e['end'])}"))
    if e["moved_from"]:
        out.append(_reason("moved", f"date moved from {_fmt(e['moved_from'])}"))
    if e["stale"]:
        where = "the weekly screener" if e["source"] == "yahoo_screener" else "an older read"
        out.append(_reason("stale_date", f"date from {where} ({_fmt(e['read_on'])})" if e["read_on"]
                           else f"date from {where}"))
    return out


def _estimate_reasons(row, cut: float) -> list[dict]:
    if row is None:
        return []
    chg = row.get("eps_chg_30d")
    chg = None if chg is None or pd.isna(chg) else float(chg)
    up, down = (None if row.get(k) is None or pd.isna(row.get(k)) else int(row.get(k))
                for k in ("eps_up_30d", "eps_down_30d"))
    counts = f" ({down} down, {up} up)" if up is not None and down is not None else ""
    # the text quotes the change only when the change itself passes the threshold; else it was the counts
    if (chg is not None and chg <= cut) or (up is not None and down is not None and down > up):
        text = (f"the quarter's EPS estimate cut {-chg:.1%} in 30 days" if chg is not None and chg <= cut
                else "more estimate cuts than raises in 30 days") + counts
        return [_reason("estimates_cut", text, chg)]
    if (chg is not None and chg >= -cut) or (up is not None and down is not None and up > down):
        text = (f"the quarter's EPS estimate raised {chg:.1%} in 30 days" if chg is not None and chg >= -cut
                else "more estimate raises than cuts in 30 days") + counts
        return [_reason("estimates_raised", text, chg)]
    return []


def _holding_reasons(me: dict, weight: float | None, hl) -> list[dict]:
    out = [_reason("held", "you hold it")]
    if weight is not None and weight >= hl.big_position:
        out.append(_reason("big_position", f"{weight:.1%} of the portfolio", weight))
    gap = (me.get("levels") or {}).get("stop_pct")
    if gap is not None and abs(gap) <= hl.near_level:
        side = "above" if gap <= 0 else "below"
        out.append(_reason("near_level", f"price {abs(gap) / (1 + gap):.1%} {side} its review level", gap))
    weak = [f for f in me.get("flags") or [] if f in WEAK_FLAGS]
    if weak:
        out.append(_reason("momentum_weak", ", ".join(weak)))
    return out


def _level(status: str, reasons: list[dict], days: int, soon_days: int) -> str:
    keys = {r["key"] for r in reasons}
    if status != "holding":
        return "info"
    return "high" if days <= soon_days and keys & set(ESCALATE) else "normal"


# ---------------- the items ----------------

def _item(kind: str, start: date, end: date | None, symbol: str | None, name: str | None, status: str, level: str,
          weight: float | None, reasons: list[dict], today: date, link: str, earnings: dict | None = None) -> dict:
    return {"id": f"{kind}:{symbol or name}:{start.isoformat()}", "kind": kind, "date": start.isoformat(),
            "date_end": end.isoformat() if end and end != start else None, "days": (start - today).days,
            "symbol": symbol, "name": name, "status": status, "level": level, "weight": weight, "reasons": reasons,
            "earnings": earnings, "link": link}


def _ticker_link(symbol: str) -> str:
    return f"/ticker/{symbol}"


def _num(v) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def build(me_rows: list[dict], weights: dict[str, float], calendar: pd.DataFrame,
          snapshot: dict[str, tuple[Any, Any]], journal: list[dict], exits: dict | None, portfolio_names: set[str],
          today: date, cfg: Calendar, days: int | None = None, funds: set[str] | frozenset = frozenset()) -> dict:
    """The calendar for one selection, as plain data: items (oldest first), the ids of the high ones within
    `soon_days`, the held and watched stocks with no known date, and the number of funds left out.

    `me_rows` are `mine.table` rows (status holding / watch / sold), `weights` each held symbol's share of the
    invested value, `calendar` the history file, `snapshot` symbol -> (screener earnings date, snapshot date),
    `journal` the journal entries of `notebook.listing`, `exits` `propose.check_exits` (None: not checked),
    `portfolio_names` the selection's portfolio names (a proposal counts when it is for one of them), `funds`
    symbols known to be funds (besides those the calendar says are)."""
    days = cfg.days if days is None else days
    last_day = today + timedelta(days=days)
    hl, inc = cfg.highlight, cfg.include
    by_symbol = {s: g for s, g in calendar.groupby("ticker")} if not calendar.empty else {}
    items: list[dict] = []
    no_date: list[dict] = []
    excluded_funds = 0
    for me in me_rows:
        sym, status = me["symbol"], me["status"]
        if status not in ("holding", "watch") or (status == "watch" and not inc.watchlist):
            continue
        hist = by_symbol.get(sym, pd.DataFrame(columns=calendar.columns))
        qt = hist.sort_values("fetched").iloc[-1].get("quote_type") if not hist.empty else None
        if sym in funds or qt in external.FUND_TYPES:
            excluded_funds += 1
            continue
        weight = weights.get(sym) if status == "holding" else None
        base = _holding_reasons(me, weight, hl) if status == "holding" else []
        e = resolve_earnings(hist, snapshot.get(sym), today, cfg.stale_days)
        if e["start"] is None:
            no_date.append({"symbol": sym, "name": me.get("name"), "status": status, "reason": e["reason"]})
        elif e["start"] <= last_day:
            row = e["row"]
            reasons = base + _date_reasons(e) + _estimate_reasons(row, hl.revision_cut)
            n = max((e["start"] - today).days, 0)
            earn = {"is_range": e["is_range"], "source": e["source"],
                    "read_on": e["read_on"].isoformat() if e["read_on"] else None,
                    "moved_from": e["moved_from"].isoformat() if e["moved_from"] else None,
                    **{k: _num(row.get(k)) if row is not None else None
                       for k in ("eps_avg", "eps_low", "eps_high", "rev_avg")}}
            items.append(_item("earnings", e["start"], e["end"], sym, me.get("name"), status,
                               _level(status, reasons, n, cfg.soon_days), weight, reasons, today,
                               _ticker_link(sym), earn))
        if inc.ex_dividend and not hist.empty:
            ex = _day(hist.sort_values("fetched").iloc[-1].get("ex_dividend"))
            if ex is not None and today <= ex <= last_day:
                items.append(_item("ex_dividend", ex, None, sym, me.get("name"), status, "info", weight,
                                   base[:1] + [_reason("ex_dividend", f"goes ex-dividend {_fmt(ex)}")], today,
                                   _ticker_link(sym)))
    if inc.reviews:
        items += _review_items(journal, today, last_day)
        items += _time_stop_items(exits, portfolio_names, today, last_day)
    items.sort(key=lambda i: (i["date"], LEVELS.index(i["level"]), -(i["weight"] or 0), i["id"]))
    soon = [i["id"] for i in items if i["level"] == "high" and i["days"] <= cfg.soon_days]
    no_date.sort(key=lambda r: (r["status"] != "holding", r["symbol"]))
    return {"today": today.isoformat(), "days": days, "soon_days": cfg.soon_days, "items": items, "soon": soon,
            "no_date": no_date, "excluded_funds": excluded_funds}


def _review_items(journal: list[dict], today: date, last_day: date) -> list[dict]:
    """Open journal entries whose review date falls before the window ends (overdue ones included)."""
    out = []
    for j in journal:
        meta = j.get("meta") or {}
        rb = _safe_day(meta.get("review_by"))
        if meta.get("status") != "open" or rb is None or rb > last_day:
            continue
        overdue = rb < today
        text = f"review overdue since {_fmt(rb)}" if overdue else f"review your journal entry by {_fmt(rb)}"
        out.append(_item("review", rb, None, meta.get("ticker"), j.get("title"), "own", "normal", None,
                         [_reason("review_due", text)], today, f"/notebook/journal/{j['name']}"))
    return out


def _time_stop_items(exits: dict | None, portfolio_names: set[str], today: date, last_day: date) -> list[dict]:
    """The time stops of proposal picks still held (or not known to be sold) that fall before the window ends,
    with the pick's exit status. A Triggered pick is high."""
    if not exits:
        return []
    asof = _safe_day(exits.get("asof")) or today
    out = []
    for p in exits.get("proposals") or []:
        if p.get("portfolio") not in portfolio_names:
            continue
        for n in p.get("names") or []:
            d = n.get("days_to_time_stop")
            if d is None or n.get("held") is False:
                continue
            ts = asof + timedelta(days=int(d))
            if ts > last_day:
                continue
            status = n.get("status") or "Intact"
            reasons = [_reason("time_stop", f"time stop of the {p['date']} proposal for {p['portfolio']}"),
                       _reason("exit_status", f"exit check: {status}")]
            out.append(_item("time_stop", ts, None, n["ticker"], None, "own",
                             "high" if status == "Triggered" else "normal", None, reasons, today, "/experiments"))
    return out


def _safe_day(v) -> date | None:
    try:
        return _day(str(v)[:10]) if v else None
    except ValueError:
        return None


def next_earnings_map(view: dict) -> dict[str, dict]:
    """symbol -> the earnings item of a built calendar, for flags elsewhere (the holdings table), so they never
    disagree with the calendar."""
    return {i["symbol"]: i for i in view["items"] if i["kind"] == "earnings"}


# ---------------- gathering the inputs (I/O) ----------------

def screener_dates(vctx, symbols) -> dict[str, tuple[Any, Any]]:
    """symbol -> (the weekly screener's earnings date, the snapshot's date), for those that have one."""
    out = {}
    for s in symbols:
        d = vctx.stock(s).get("earnings_date")
        if d:
            out[s] = (d, vctx.asof)
    return out


def _funds() -> set[str]:
    return {i.ticker for i in tracked.etfs()} | {tracked.benchmark()}


def with_earnings_flags(rows: list[dict], vctx, today: date, cfg: Calendar) -> list[dict]:
    """The holdings rows with an "earnings in N d" flag where a held or watched stock reports within `soon_days`,
    from the same `build` as the calendar (so the two never disagree)."""
    v = build(rows, {}, external.load_calendar(), screener_dates(vctx, [r["symbol"] for r in rows]), [], None,
              set(), today, cfg, days=cfg.soon_days, funds=_funds())
    nxt = next_earnings_map(v)
    out = []
    for r in rows:
        i = nxt.get(r["symbol"])
        if i is not None and r["status"] in ("holding", "watch"):
            n = max(i["days"], 0)
            r = r | {"flags": [*r["flags"], "earnings today" if n == 0 else f"earnings in {n} d"]}
        out.append(r)
    return out


def collect(market: Market, dash: dict, ids: list[int], scope: str | None = None, days: int | None = None) -> dict:
    """The calendar of these portfolios now: the holdings rows, their weights, the history file, the screener,
    the journal and the proposals' exit check, built as of the benchmark's last close. The view adds the
    selection, the as-of date and notes."""
    cfg = typed().calendar
    ports = [p for p in (userstore.get_portfolio(i) for i in ids) if p]
    notes: list[str] = []
    today = market.closes[tracked.benchmark()].dropna().index[-1].date()
    rows = mine.live(market, dash, ids, settings())
    book = exposure.holdings_book(market, Prices(market), ids)
    valued = book.dropna(subset=["value_dkk"]).groupby("symbol")["value_dkk"].sum() if not book.empty else pd.Series(dtype=float)
    total = float(valued.sum())
    weights = {s: float(v) / total for s, v in valued.items()} if total > 0 else {}
    if not book.empty and len(valued) < book["symbol"].nunique():
        notes.append("Holdings without a DKK value have no weight here")
    vctx = valuation.context()
    journal = notebook.listing(today)["journal"] if cfg.include.reviews else []
    exits = None
    if cfg.include.reviews and propose.proposals():
        try:
            exits = propose.check_exits(market)
        except Exception as e:   # the exit check needs the panels; the rest of the calendar stands without it
            notes.append(f"Proposal time stops left out: the exit check failed ({type(e).__name__})")
    v = build(rows, weights, external.load_calendar(), screener_dates(vctx, [r["symbol"] for r in rows]), journal,
              exits, {p["name"] for p in ports}, today, cfg, days=days, funds=_funds())
    if not rows:
        notes.append("Nothing held or watched in this selection")
    if v["no_date"]:
        notes.append(f"{len(v['no_date'])} stock(s) without a known earnings date: listed below, not guessed")
    notes.append("Dates are Yahoo's (a date or the window it expects), not confirmed by the companies; days are "
                 f"counted from the last close ({today.isoformat()})")
    return {"asof": today.isoformat(), "generated": datetime.now().isoformat(timespec="seconds"),
            "selection": {"ids": [p["id"] for p in ports], "names": [p["name"] for p in ports], "scope": scope},
            **v, "notes": notes}


_cache: dict[tuple, dict] = {}


def _mtime(p) -> float:
    try:
        return p.stat().st_mtime
    except (FileNotFoundError, OSError):
        return 0.0


def cached(market: Market, dash: dict, ids: list[int] | None = None, scope: str | None = None,
           days: int | None = None) -> dict:
    """`collect`, kept until a trade or portfolio edit, a price update, a calendar read, a new build, a journal
    entry or a proposal changes it."""
    ids = userstore.portfolio_ids() if ids is None else ids
    key = (tuple(ids), scope, days, market.mtime, userstore.transactions_version(), _mtime(external.CALENDAR_FILE),
           dash.get("generated"), _mtime(notebook.FOLDERS["journal"]), _mtime(propose.rules.PROPOSALS))
    if key not in _cache:
        if len(_cache) > 32:
            _cache.clear()
        _cache[key] = collect(market, dash, ids, scope, days)
    return _cache[key]
