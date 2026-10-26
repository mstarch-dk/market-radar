"""Tools about your portfolios and tickers: the portfolios, returns vs ACWI, the X-ray, attribution, the calendar,
the evidence, and one or several tickers' profiles. Each is the view the matching `--json` command prints."""
from __future__ import annotations

from .. import agenda, errors, evidence, profile, userstore, xray
from .. import attribution as attr
from ..portfolios import performance as perf
from ..portfolios import trades
from ..reporting import dashboard
from .common import iso_day, market, selection


def portfolios(archived: bool = False) -> dict:
    """Every portfolio: name, mode (real = the user's accounts, virtual = simulations and tests), tax kind, tags,
    number of rows, and which is the default. Other tools take these names."""
    trades.ensure_migrated()
    return {"portfolios": userstore.portfolios(include_archived=archived)}


def performance(portfolios: list[str] | None = None, tags: list[str] | None = None, start: str | None = None) -> dict:
    """Returns in DKK against ACWI from a common start: time-weighted (the investments) and money-weighted (your
    timing), max drawdown, value. Default: each of your real portfolios; a tag group is pooled into one line."""
    trades.ensure_migrated()
    ids = selection(portfolios, None, None) if portfolios else userstore.compared_ids()
    return perf.compare(market(), ids, tags, iso_day(start, "start"))


def portfolio_xray(portfolios: list[str] | None = None, tags: list[str] | None = None,
                   scope: str | None = None) -> dict:
    """The X-ray of the chosen portfolios pooled (default: your real ones; `scope` real | virtual | all): exposure
    by sector, region and currency vs ACWI, ex-ante and realised risk with each position's share, concentration,
    stress windows and factor tilts. Analysis, not advice."""
    return xray.cached(market(), selection(portfolios, tags, scope), scope)


def attribution(portfolios: list[str] | None = None, tags: list[str] | None = None, scope: str | None = None,
                start: str | None = None, end: str | None = None) -> dict:
    """Attribution vs ACWI of the chosen portfolios pooled, from `start` to `end` (YYYY-MM-DD): trading and fees,
    benchmark proxies vs ACWI, allocation / selection / interaction by sector and region, the currency effect, and
    the factor regression's alpha with its t. Analysis, not advice."""
    return attr.cached(market(), selection(portfolios, tags, scope), scope, iso_day(start, "start"),
                       iso_day(end, "end"))


def calendar(portfolios: list[str] | None = None, tags: list[str] | None = None, scope: str | None = None,
             days: int | None = None, symbols: list[str] | None = None) -> dict:
    """The coming `days` (default calendar.days in settings) for what you hold and watch: earnings and
    ex-dividend dates (estimated or a range, with source), your journal reviews and the proposals' time stops, each
    with a level and the reasons it is highlighted; `no_date` lists held or watched stocks with no known date.
    `symbols`: only these tickers' items."""
    if days is not None and not 1 <= days <= 366:
        raise errors.Invalid("days must be from 1 to 366")
    d = dashboard.load()
    if d is None:
        raise errors.NotFound("No dashboard yet: run `uv run radar run` first.")
    v = agenda.cached(market(), d, selection(portfolios, tags, scope), scope, days)
    if not symbols:
        return v
    want = {s.strip().upper() for s in symbols}
    items = [i for i in v["items"] if (i.get("symbol") or "").upper() in want]
    ids = {i["id"] for i in items}
    return v | {"items": items, "soon": [i for i in v["soon"] if i in ids],
                "no_date": [n for n in v["no_date"] if n["symbol"].upper() in want]}


def evidence_view() -> dict:
    """The Evidence page: a card per score study (momentum, kvalitet, værdi, K+V) and the long-run study with
    status, age, IC with t and holdout, the rule studies' headers, and the forward record vs ACWI (A/B test, paper
    trail, frozen proposals). Without prices the forward record is null and the cards still come back."""
    trades.ensure_migrated()
    try:
        m = market()
    except errors.NotFound:
        m = None
    return evidence.cached(m)


def ticker_profile(symbols: list[str], personal: bool = False, portfolios: list[str] | None = None,
                   tags: list[str] | None = None, refresh: bool = False) -> dict:
    """Everything the radar knows about one ticker (Yahoo symbol): price, technicals, levels, analysts,
    fundamentals, ETF data, peers, quality, your views; each section has a `status`. With several symbols: a
    side-by-side comparison with ACWI (profiles, a metrics table, risk, correlations); your positions and
    correlations with your holdings only with `personal` (from `portfolios`/`tags`, default your real ones). An
    untracked ticker's prices are downloaded first (about 10 s). `refresh`: fetch fundamentals and estimates now."""
    if not symbols:
        raise errors.Invalid("Give at least one symbol.")
    if len(symbols) == 1:
        return profile.legacy_info(profile.build(symbols[0].strip().upper(), refresh=refresh))
    sel = selection(portfolios, tags, None) if (portfolios or tags) else None
    return profile.compare(symbols, personal=personal, portfolios=sel)


TOOLS = (portfolios, performance, portfolio_xray, attribution, calendar, evidence_view, ticker_profile)
