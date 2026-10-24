"""Portfolios: real ones (your accounts) and virtual ones, tags, the A/B test, comparisons, performance, forks and moves."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import (
    errors,
    portfolio,
    trades,
    userstore,
)
from ..api_models import (
    AbStartIn,
    AbTest,
    Comparison,
    FeePreset,
    ForkIn,
    MoveIn,
    MoveResult,
    Performance,
    Portfolio,
    PortfolioIn,
    SimRun,
    TagCount,
    TagsIn,
)
from . import state
from .common import (
    PortfolioQ,
    TagQ,
    found,
    portfolio_or_404,
    sentence,
    ticker_symbol,
)

router = APIRouter()


# ---------------- portfolios: real ones (your accounts) and virtual ones, with tags ----------------




def _save_portfolio(body: PortfolioIn, pid: int | None = None) -> dict:
    import sqlite3

    if pid is not None:
        portfolio_or_404(pid)
    data = body.model_dump()
    if "fee_schedule" not in body.model_fields_set:      # an older client: keep the schedule as it is
        data.pop("fee_schedule")
    try:
        return portfolio_or_404(userstore.save_portfolio(data, pid))
    except errors.RadarError:
        raise
    except (ValueError, sqlite3.IntegrityError) as e:       # the store's rules (kind, mode, a simulation stays virtual)
        raise HTTPException(422, sentence(e)) from e





@router.get("/api/portfolios", response_model=list[Portfolio])
def list_portfolios(archived: bool = True) -> list[dict]:
    """Every portfolio with its tags, number of rows and date range."""
    trades.ensure_migrated()
    return userstore.portfolios(include_archived=archived)


@router.post("/api/portfolios", response_model=Portfolio)
def add_portfolio(body: PortfolioIn) -> dict:
    return _save_portfolio(body)


@router.put("/api/portfolios/{pid}", response_model=Portfolio)
def edit_portfolio(pid: int, body: PortfolioIn) -> dict:
    """Rename or change a portfolio (its rows stay with it)."""
    return _save_portfolio(body, pid)


@router.delete("/api/portfolios/{pid}", response_model=Portfolio)
def delete_portfolio(pid: int) -> dict:
    """Delete a virtual portfolio with its rows (a backup is taken first), or an empty real one. A real one
    with trades is 409: move them, or archive it."""
    portfolio_or_404(pid)
    return found(userstore.delete_portfolio(pid), f"No portfolio {pid}.")


@router.get("/api/portfolios/fee-presets", response_model=list[FeePreset])
def list_fee_presets() -> list[dict]:
    """Broker fee schedules copied from public price lists (dated): a starting point for a portfolio's own."""
    from .. import fees

    return fees.presets()


@router.get("/api/portfolios/{pid}/runs", response_model=list[SimRun])
def list_sim_runs(pid: int) -> list[dict]:
    """The runs that wrote a simulated portfolio's rows (empty for any other portfolio)."""
    portfolio_or_404(pid)
    return userstore.sim_runs(pid)


@router.get("/api/portfolios/tags", response_model=list[TagCount])
def list_tags() -> list[dict]:
    return userstore.all_tags()


@router.put("/api/portfolios/{pid}/tags", response_model=Portfolio)
def set_tags(pid: int, body: TagsIn) -> dict:
    portfolio_or_404(pid)
    try:
        userstore.set_tags(pid, body.tags)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return portfolio_or_404(pid)


@router.post("/api/portfolios/{pid}/default", response_model=list[Portfolio])
def set_default(pid: int) -> list[dict]:
    """Make this real portfolio the one new trades and imports go into unless another is chosen."""
    portfolio_or_404(pid)
    try:
        userstore.set_default_portfolio(pid)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return userstore.portfolios()


@router.get("/api/abtest", response_model=AbTest)
def get_abtest() -> dict:
    """The forward A/B test: kvalitet+værdi, momentum and 50/50 against ACWI from their first purchase."""
    from .. import abtest

    with state.lock:
        return abtest.view(state.market())


@router.post("/api/abtest", response_model=AbTest)
def start_abtest(body: AbStartIn | None = None) -> dict:
    """Start the A/B test with this month's picks (409 when it is already running)."""
    from .. import abtest

    b = body or AbStartIn()
    with state.lock:
        m = state.market()
        if abtest.portfolios():
            raise HTTPException(409, "The A/B test is already running.")
        try:
            abtest.create(m, b.capital, b.n, b.max_per_sector, b.value_score)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        return abtest.view(m)


@router.get("/api/portfolios/compare", response_model=Comparison)
def compare_portfolios(portfolio: list[int] | None = PortfolioQ, tag: list[str] | None = TagQ,
                       start: str | None = None) -> dict:
    """Portfolios and tag groups (each pooled into one line) side by side from a common start, every
    time-weighted index rebased to 100 there, with ACWI. Default: each of your real portfolios with rows."""
    from .. import performance

    ids = portfolio if (portfolio or tag) else userstore.compared_ids()
    with state.lock:
        return performance.compare(state.market(), ids, tag, start)


@router.get("/api/portfolios/{pid}/performance", response_model=Performance)
def portfolio_performance(pid: int, start: str | None = None, end: str | None = None) -> dict:
    """One portfolio's value over time in DKK, its time- and money-weighted returns and ACWI's with the same
    cash flows. Gaps (a price or DKK rate missing) are None, never 0."""
    from .. import performance

    with state.lock:
        out = performance.portfolio_performance(pid, state.market(), start, end)
    if out is None:
        raise HTTPException(404, f"No portfolio {pid}.")
    return out


@router.post("/api/portfolios/{pid}/fork", response_model=Portfolio)
def fork_portfolio(pid: int, body: ForkIn) -> dict:
    """A virtual copy of this portfolio as it stood at a day's close (one deposit, one buy per holding), to
    A/B-test changes against it from there on (compare with start = that day)."""
    from .. import simulate

    portfolio_or_404(pid)
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "The copy needs a name.")
    try:
        with state.lock:
            new = simulate.fork(pid, name, body.date, state.market(), body.extra_cash_dkk, body.tags)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return portfolio_or_404(new)


@router.post("/api/portfolios/{pid}/move", response_model=MoveResult)
def move_rows(pid: int, body: MoveIn) -> dict:
    """Move rows (all, or only these ids / tickers) to another portfolio; refused (422) if a sale would be left
    without its buy in either portfolio. A backup is taken first."""
    portfolio_or_404(pid)
    portfolio_or_404(body.to)
    if body.to == pid:
        raise HTTPException(422, "Choose another portfolio to move to.")
    symbols = [ticker_symbol(s) for s in body.symbols] if body.symbols else None
    problems = portfolio.check_move(pid, body.to, body.ids, symbols)
    if problems:
        raise HTTPException(422, {"message": "Not moved: " + problems[0],
                                  "issues": [{"level": "error", "field": "portfolio", "message": p} for p in problems]})
    return {"moved": userstore.move_transactions(pid, body.to, body.ids, symbols)}
