"""The portfolio editor: transactions in the local store, positions, the price check, the CSV export."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from .. import rulecheck, userstore
from ..api_models import (
    PositionsView,
    PriceCheck,
    TxCheck,
    TxIn,
    TxResult,
    TxRow,
)
from ..portfolios import checks, trades
from . import state
from .common import (
    PortfolioQ,
    ScopeQ,
    TagQ,
    found,
    selection,
    ticker_symbol,
)

router = APIRouter()


# ---------------- portfolio editor: transactions in the local store ----------------

def _tx_row(body: TxIn) -> dict:
    trade = body.type in userstore.TRADE_TYPES
    return {"symbol": ticker_symbol(body.symbol) or None, "date": body.date[:10], "type": body.type,
            "quantity": body.quantity if trade else None, "price": body.price if trade else None,
            "fee": (body.fee or 0.0) if trade else 0.0, "amount": None if trade else body.amount,
            "currency": None if trade else (body.currency or "DKK").upper(), "fx_rate": body.fx_rate if trade else None,
            "portfolio_id": body.portfolio_id, "note": body.note or None}


def _validated(row: dict, exclude_id: int | None) -> list[dict]:
    with state.lock:
        if row["symbol"]:
            state.ensure(row["symbol"], missing="ignore")                # validate() reports the unknown symbol
        return checks.validate(row, state.market(), exclude_id=exclude_id)


def _checked(body: TxIn, exclude_id: int | None = None) -> tuple[dict, list[dict], dict | None]:
    """The row, its issues and (a new trade) its rule check; 422 with the issues when it can't be saved
    (checks.checked). Your trading rules add warnings to confirm, never errors."""
    row = _tx_row(body)
    with state.lock:
        if row["symbol"]:
            state.ensure(row["symbol"], missing="ignore")                # validate() reports the unknown symbol
        rc: dict = {}

        def rules(r: dict) -> list[dict]:
            rc["check"] = rulecheck.trade_check(state.market(), r)
            return rulecheck.trade_issues(rc["check"])

        issues = checks.checked(row, state.market(), body.confirm, exclude_id, None if exclude_id else rules)
        return row, issues, rc.get("check")


@router.get("/api/portfolio/transactions", response_model=list[TxRow])
def list_transactions(symbol: str | None = None, portfolio: list[int] | None = PortfolioQ,
                      tag: list[str] | None = TagQ, scope: str | None = ScopeQ) -> list[dict]:
    trades.ensure_migrated()
    sel = selection(portfolio, tag, scope)
    return userstore.transactions(ticker_symbol(symbol) if symbol else None, userstore.portfolio_ids() if sel is None else sel)


@router.post("/api/portfolio/validate", response_model=TxCheck)
def check_transaction(body: TxIn, id: int | None = None) -> dict:
    """Issues, the effect on the position and the price check for a row being typed, without saving it."""
    trades.ensure_migrated()
    row = _tx_row(body)
    issues = _validated(row, id)
    with state.lock:
        pc = checks.price_check(state.market(), row["symbol"], row["date"], row["price"]) \
            if row["symbol"] in state.market().closes.columns else None
        rules = (rulecheck.trade_check(state.market(), row) if id is None
                 and not any(i["level"] == "error" for i in issues) else None)
    issues += rulecheck.trade_issues(rules)
    blocking = {i["field"] for i in issues if i["level"] == "error"} & {"symbol", "type", "date"}
    trade = row["type"] in userstore.TRADE_TYPES
    return {"issues": issues, "effect": checks.effect(row, exclude_id=id) if trade and not blocking else None,
            "price": pc, "fee_estimate": _fee_estimate(row, pc) if trade and pc else None, "rules": rules}


def _fee_estimate(row: dict, pc: dict) -> dict | None:
    """The commission the trade's portfolio schedule gives (fees.for_trade): your fx rate, else Yahoo's that day."""
    from ..portfolios import fees

    def closes():
        return state.market().closes

    return fees.for_trade(row, pc.get("currency"), row["fx_rate"] or pc.get("fx"), closes)


@router.post("/api/portfolio/transactions", response_model=TxResult)
def add_transaction(body: TxIn) -> dict:
    """Save a row. A new trade that breaks or comes close to one of your trading rules is saved only once
    confirmed, and the check is logged with what you did and `rule_reason`."""
    trades.ensure_migrated()
    row, issues, rules = _checked(body)
    tx_id = userstore.add_tx(row)
    rulecheck.log_trade(rules, tx_id, body.rule_reason)
    return {"tx": userstore.get_tx(tx_id), "issues": issues}


@router.put("/api/portfolio/transactions/{tx_id}", response_model=TxResult)
def edit_transaction(tx_id: int, body: TxIn) -> dict:
    if not userstore.get_tx(tx_id):
        raise HTTPException(404, f"No transaction {tx_id}.")
    row, issues, _ = _checked(body, exclude_id=tx_id)
    userstore.update_tx(tx_id, row)
    return {"tx": userstore.get_tx(tx_id), "issues": issues}


@router.delete("/api/portfolio/transactions/{tx_id}", response_model=TxRow)
def delete_transaction(tx_id: int) -> dict:
    """Delete one transaction; the response is the deleted row, which /restore puts back (undo)."""
    row = userstore.delete_tx(tx_id)
    if not row:
        raise HTTPException(404, f"No transaction {tx_id}.")
    return row


@router.post("/api/portfolio/transactions/restore", response_model=TxRow)
def restore_transaction(row: TxRow) -> dict:
    if userstore.get_tx(row.id):
        raise HTTPException(409, "That transaction is already there.")
    return found(userstore.get_tx(userstore.restore_tx(row.model_dump())), "The restored transaction is gone.")


@router.get("/api/portfolio/positions", response_model=PositionsView)
def get_positions(portfolio: list[int] | None = PortfolioQ, tag: list[str] | None = TagQ,
                  scope: str | None = ScopeQ) -> dict:
    from ..portfolios import checks as pf

    sel = selection(portfolio, tag, scope)
    with state.lock:
        return pf.positions_view(state.market(), sel)


@router.get("/api/portfolio/price-check", response_model=PriceCheck)
def get_price_check(symbol: str, date: str, price: float | None = None) -> dict:
    sym = ticker_symbol(symbol)
    with state.lock:
        state.ensure(sym)
        return checks.price_check(state.market(), sym, date, price)


@router.get("/api/portfolio/export.csv", response_class=Response)
def export_transactions(portfolio: list[int] | None = PortfolioQ, tag: list[str] | None = TagQ,
                        scope: str | None = ScopeQ) -> Response:
    """The chosen portfolios' transactions as CSV (default: your real ones; a backup you can keep, or open in a
    spreadsheet)."""
    trades.ensure_migrated()
    return Response(userstore.export_transactions_csv(selection(portfolio, tag, scope)), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="transactions-{dt.date.today()}.csv"'})
