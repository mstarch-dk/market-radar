"""The calendar (agenda.py): earnings and ex-dividend dates of what you hold and watch, your review dates and the
proposals' time stops, each with the reasons it is highlighted. A date that isn't known is listed, never guessed."""
from __future__ import annotations

from typing import Literal

from .common import Num, Strict

AgendaKind = Literal["earnings", "ex_dividend", "review", "time_stop"]
AgendaLevel = Literal["high", "normal", "info"]
ReasonKey = Literal["held", "big_position", "near_level", "momentum_weak", "estimates_cut", "estimates_raised",
                    "unconfirmed", "moved", "stale_date", "ex_dividend", "review_due", "time_stop", "exit_status"]


class AgendaReason(Strict):
    """Why an item stands out: a stated rule (`key`), its text with the number in it, and the number."""
    key: ReasonKey
    text: str
    value: Num = None


class AgendaEarnings(Strict):
    """How sure the date is: `is_range` is Yahoo's expected window (date to date_end), `source` yahoo_detail (the
    ticker's calendar) or yahoo_screener (the weekly snapshot), `read_on` the day it was read. The consensus is
    for the quarter being reported."""
    is_range: bool
    source: Literal["yahoo_detail", "yahoo_screener"]
    read_on: str | None = None
    moved_from: str | None = None
    eps_avg: Num = None
    eps_low: Num = None
    eps_high: Num = None
    rev_avg: Num = None


class AgendaItem(Strict):
    """One dated item. `days` is counted from the as-of date (negative: a window under way, or an overdue review);
    `weight` is a holding's share of the invested value; `id` is stable (kind:symbol:date)."""
    id: str
    kind: AgendaKind
    date: str
    date_end: str | None = None
    days: int
    symbol: str | None = None
    name: str | None = None
    status: Literal["holding", "watch", "own"]
    level: AgendaLevel
    weight: Num = None
    reasons: list[AgendaReason]
    earnings: AgendaEarnings | None = None
    link: str


class AgendaNoDate(Strict):
    """A held or watched stock with no known earnings date, and why."""
    symbol: str
    name: str | None = None
    status: Literal["holding", "watch"]
    reason: str


class AgendaSelection(Strict):
    ids: list[int]
    names: list[str]
    scope: str | None = None


class AgendaView(Strict):
    """`soon`: the ids of the high items within `calendar.soon_days`, in date order."""
    asof: str
    generated: str
    today: str
    days: int
    selection: AgendaSelection
    items: list[AgendaItem]
    soon: list[str]
    no_date: list[AgendaNoDate]
    excluded_funds: int
    notes: list[str]
