"""agenda.py: the next earnings date and how sure it is, the calendar's items, the highlight rules and levels, on
hand-made inputs (the history file's rows, holdings rows, journal entries, an exit check)."""
from datetime import date

import pandas as pd
import pytest

from radar import agenda
from radar.config import typed

TODAY = date(2026, 10, 25)


def cal(*rows) -> pd.DataFrame:
    """History rows: (ticker, fetched, start[, end[, extra fields]]); no end is a one-day date."""
    out = []
    for r in rows:
        t, fetched, start, *rest = r
        end = rest[0] if rest else None
        extra = rest[1:]
        out.append({"ticker": t, "fetched": pd.Timestamp(fetched),
                    "earnings_start": pd.Timestamp(start) if start else pd.NaT,
                    "earnings_end": pd.Timestamp(end or start) if start else pd.NaT,
                    "eps_avg": 1.2, "eps_low": 1.0, "eps_high": 1.5, "rev_avg": 1e9, "ex_dividend": pd.NaT,
                    "eps_chg_30d": None, "eps_up_30d": None, "eps_down_30d": None, "quote_type": "EQUITY",
                    **(extra[0] if extra else {})})
    return pd.DataFrame(out)


def me(symbol, status="holding", stop_pct=None, flags=()):
    return {"symbol": symbol, "name": f"{symbol} Inc", "status": status, "flags": list(flags),
            "levels": {"stop_pct": stop_pct} if stop_pct is not None else None}


def build(rows, calendar, weights=None, snapshot=None, journal=(), exits=None, names=frozenset({"Main"}), **kw):
    return agenda.build(rows, weights or {}, calendar, snapshot or {}, list(journal), exits, set(names), TODAY,
                        typed().calendar, **kw)


def item(view, kind, symbol):
    return next(i for i in view["items"] if i["kind"] == kind and i["symbol"] == symbol)


def keys(i):
    return [r["key"] for r in i["reasons"]]


# ---------------- resolve_earnings ----------------

def test_resolve_earnings_order():
    fresh = cal(("A", "2026-10-24", "2026-10-30"))
    e = agenda.resolve_earnings(fresh, ("2026-11-02", "2026-10-20"), TODAY, stale_days=10)
    assert (e["start"], e["source"], e["stale"]) == (date(2026, 10, 30), "yahoo_detail", False)   # the read wins
    old = cal(("A", "2026-10-01", "2026-10-30"))
    e = agenda.resolve_earnings(old, ("2026-11-02", "2026-10-20"), TODAY, stale_days=10)
    assert (e["start"], e["source"], e["stale"]) == (date(2026, 11, 2), "yahoo_screener", True)   # too old: screener
    e = agenda.resolve_earnings(old, None, TODAY, stale_days=10)
    assert (e["start"], e["source"], e["stale"]) == (date(2026, 10, 30), "yahoo_detail", True)    # nothing newer
    assert agenda.resolve_earnings(cal(), None, TODAY, 10) == {"start": None, "reason": "not read yet"}
    e = agenda.resolve_earnings(cal(("A", "2026-10-24", None)), None, TODAY, 10)
    assert e["start"] is None and e["reason"] == "Yahoo gave no date (read 24 Oct)"
    e = agenda.resolve_earnings(cal(("A", "2026-10-24", "2026-10-22")), None, TODAY, 10)
    assert e["start"] is None and "has passed" in e["reason"]


def test_snapshot_past_date_ignored():
    e = agenda.resolve_earnings(cal(), ("2026-10-23", "2026-10-20"), TODAY, 10)   # the screener keeps a passed date
    assert e["start"] is None


def test_moved_and_narrowed_dates():
    moved = cal(("A", "2026-10-15", "2026-10-28"), ("A", "2026-10-24", "2026-11-04"))
    assert agenda.resolve_earnings(moved, None, TODAY, 10)["moved_from"] == date(2026, 10, 28)
    narrowed = cal(("A", "2026-10-15", "2026-10-28", "2026-11-05"), ("A", "2026-10-24", "2026-10-30"))
    e = agenda.resolve_earnings(narrowed, None, TODAY, 10)
    assert e["moved_from"] is None and e["is_range"] is False                     # inside the old window: not a move
    new_cycle = cal(("A", "2026-07-01", "2026-07-20"), ("A", "2026-10-24", "2026-10-29"))
    assert agenda.resolve_earnings(new_cycle, None, TODAY, 10)["moved_from"] is None   # the old report passed


# ---------------- the items ----------------

def test_agenda_items_kinds():
    calendar = cal(("HLD", "2026-10-24", "2026-10-29", None, {"ex_dividend": pd.Timestamp("2026-11-10")}),
                   ("WAT", "2026-10-24", "2026-11-12"),
                   ("FND", "2026-10-01", None, None, {"quote_type": "ETF"}),
                   ("OLD", "2026-10-24", "2026-10-29"))
    journal = [{"name": "2026-09-01-hld", "title": "Bought HLD", "meta": {"status": "open", "review_by": "2026-11-01",
                                                                          "ticker": "HLD"}},
               {"name": "2026-08-01-x", "title": "Closed", "meta": {"status": "closed", "review_by": "2026-11-01"}}]
    exits = {"asof": "2026-10-25", "proposals": [
        {"date": "2026-05-01", "portfolio": "Main", "names": [
            {"ticker": "HLD", "held": True, "status": "Intact", "days_to_time_stop": 6},
            {"ticker": "GONE", "held": False, "status": "Intact", "days_to_time_stop": 6}]},
        {"date": "2026-05-01", "portfolio": "Other", "names": [
            {"ticker": "ZZZ", "held": True, "status": "Triggered", "days_to_time_stop": 2}]}]}
    rows = [me("HLD"), me("WAT", "watch"), me("FND"), me("OLD", "sold")]
    v = build(rows, calendar, weights={"HLD": 0.02}, journal=journal, exits=exits)
    assert [(i["kind"], i["symbol"]) for i in v["items"]] == [
        ("earnings", "HLD"), ("time_stop", "HLD"), ("review", "HLD"), ("ex_dividend", "HLD"), ("earnings", "WAT")]
    h = item(v, "earnings", "HLD")
    assert (h["status"], h["date"], h["days"], h["link"], h["id"]) == (
        "holding", "2026-10-29", 4, "/ticker/HLD", "earnings:HLD:2026-10-29")
    assert h["earnings"]["read_on"] == "2026-10-24" and h["earnings"]["eps_low"] == 1.0
    assert item(v, "earnings", "WAT")["status"] == "watch"
    assert item(v, "review", "HLD")["link"] == "/notebook/journal/2026-09-01-hld"
    assert item(v, "time_stop", "HLD")["date"] == "2026-10-31"
    assert v["excluded_funds"] == 1                                                 # counted, not listed


def test_window_and_include_switches():
    calendar = cal(("FAR", "2026-10-24", "2026-12-15"), ("RNG", "2026-10-24", "2026-10-22", "2026-10-28"),
                   ("WAT", "2026-10-24", "2026-10-30"))
    rows = [me("FAR"), me("RNG"), me("WAT", "watch")]
    v = build(rows, calendar)
    assert [i["symbol"] for i in v["items"]] == ["RNG", "WAT"]                   # FAR is after the window
    r = item(v, "earnings", "RNG")
    assert (r["date"], r["date_end"], r["earnings"]["is_range"]) == ("2026-10-22", "2026-10-28", True)
    assert "unconfirmed" in keys(r)                                             # a window under way is still shown
    assert [i["symbol"] for i in build(rows, calendar, days=60)["items"]] == ["RNG", "WAT", "FAR"]
    cfg = typed().calendar.model_copy(update={"include": typed().calendar.include.model_copy(update={"watchlist": False})})
    v = agenda.build(rows, {}, calendar, {}, [], None, set(), TODAY, cfg)
    assert "WAT" not in {i["symbol"] for i in v["items"]}


def test_no_date_listed_never_dropped():
    calendar = cal(("NOD", "2026-10-24", None), ("PAS", "2026-10-24", "2026-10-20"))
    v = build([me("NOD"), me("PAS"), me("NEW", "watch")], calendar)
    assert v["items"] == []
    assert [(r["symbol"], r["status"]) for r in v["no_date"]] == [("NOD", "holding"), ("PAS", "holding"),
                                                                  ("NEW", "watch")]
    assert v["no_date"][2]["reason"] == "not read yet"


# ---------------- highlight rules and levels ----------------

def test_highlight_rules():
    hl = typed().calendar.highlight
    soon = "2026-10-28"

    def one(row, extra=None, weight=None):
        v = build([row], cal((row["symbol"], "2026-10-24", soon, None, extra or {})),
                  weights={row["symbol"]: weight} if weight is not None else {})
        return item(v, "earnings", row["symbol"])

    assert "big_position" in keys(one(me("A"), weight=hl.big_position))
    assert "big_position" not in keys(one(me("A"), weight=hl.big_position - 0.001))
    near = one(me("A", stop_pct=-hl.near_level))
    assert "near_level" in keys(near) and "above its review level" in near["reasons"][-1]["text"]
    assert "near_level" not in keys(one(me("A", stop_pct=-hl.near_level - 0.01)))
    assert "below its review level" in one(me("A", stop_pct=0.01))["reasons"][-1]["text"]
    assert "momentum_weak" in keys(one(me("A", flags=["losing momentum", "trend intact"])))
    assert "momentum_weak" not in keys(one(me("A", flags=["trend intact"])))
    cut = one(me("A"), {"eps_chg_30d": hl.revision_cut})
    assert "estimates_cut" in keys(cut) and cut["reasons"][-1]["value"] == pytest.approx(hl.revision_cut)
    assert "estimates_cut" not in keys(one(me("A"), {"eps_chg_30d": hl.revision_cut + 0.001}))
    assert "estimates_cut" in keys(one(me("A"), {"eps_up_30d": 0, "eps_down_30d": 2}))
    tiny = one(me("A"), {"eps_chg_30d": -0.0004, "eps_up_30d": 0, "eps_down_30d": 1})   # the counts, not the change
    assert tiny["reasons"][-1]["text"] == "more estimate cuts than raises in 30 days (1 down, 0 up)"
    assert "estimates_raised" in keys(one(me("A"), {"eps_chg_30d": -hl.revision_cut}))
    rng = build([me("A")], cal(("A", "2026-10-24", "2026-10-28", "2026-11-03")))["items"][0]
    assert "unconfirmed" in keys(rng) and "28 Oct–3 Nov" in rng["reasons"][-1]["text"]
    stale = build([me("A")], cal(), snapshot={"A": ("2026-10-28", "2026-10-19")})["items"][0]
    assert "stale_date" in keys(stale) and stale["earnings"]["source"] == "yahoo_screener"
    moved = build([me("A")], cal(("A", "2026-10-15", "2026-10-26"), ("A", "2026-10-24", soon)))["items"][0]
    assert "moved" in keys(moved)


def test_levels():
    soon_days = typed().calendar.soon_days
    calendar = cal(("BIG", "2026-10-24", "2026-10-28"), ("SML", "2026-10-24", "2026-10-28"),
                   ("LATE", "2026-10-24", f"2026-11-{1 + soon_days + 5:02d}"),
                   ("WAT", "2026-10-24", "2026-10-28", None, {"eps_chg_30d": -0.2}))
    v = build([me("BIG"), me("SML"), me("LATE"), me("WAT", "watch")], calendar,
              weights={"BIG": 0.2, "SML": 0.01, "LATE": 0.2})
    assert item(v, "earnings", "BIG")["level"] == "high"                        # held, soon, a large position
    assert item(v, "earnings", "SML")["level"] == "normal"                      # held, soon, nothing to escalate
    assert item(v, "earnings", "LATE")["level"] == "normal"                     # large, but not within soon_days
    w = item(v, "earnings", "WAT")
    assert w["level"] == "info" and "estimates_cut" in keys(w)                  # watched: info, reasons still shown
    assert v["soon"] == ["earnings:BIG:2026-10-28"]
    exits = {"asof": "2026-10-25", "proposals": [{"date": "2026-05-01", "portfolio": "Main", "names": [
        {"ticker": "BIG", "held": True, "status": "Triggered", "days_to_time_stop": 0}]}]}
    assert item(build([], cal(), exits=exits), "time_stop", "BIG")["level"] == "high"


def test_next_earnings_map_is_the_calendar():
    v = build([me("A")], cal(("A", "2026-10-24", "2026-10-28")))
    assert agenda.next_earnings_map(v)["A"] is v["items"][0]
