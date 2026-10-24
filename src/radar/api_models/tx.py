"""The portfolio editor: transactions, their validation, positions, and the holdings and broker imports."""
from __future__ import annotations

from typing import Literal

from .common import Num, Strict
from .portfolios import FeeEstimate


class ImportResult(Strict):
    holdings: int
    sold: int
    watch: int
    warnings: dict[str, list[str]]


TxType = Literal["BUY", "SELL", "DEPOSIT", "WITHDRAW", "DIVIDEND", "FEE", "INTEREST"]


class TxIn(Strict):
    """A trade (symbol, quantity, price in the quote currency, fee) or a cash row (amount in DKK; a dividend
    also names its symbol)."""
    symbol: str = ""
    date: str
    type: TxType
    quantity: float | None = None
    price: float | None = None
    fee: float = 0.0
    amount: float | None = None
    currency: str | None = None
    fx_rate: float | None = None           # trades: DKK per unit of price as booked (default: Yahoo's rate)
    portfolio_id: int | None = None        # default: the default portfolio
    note: str | None = None
    confirm: bool = False                  # save despite warnings (errors always block)


class TxRow(Strict):
    id: int
    portfolio_id: int
    portfolio: str
    symbol: str | None = None
    date: str
    type: TxType
    quantity: Num = None
    price: Num = None
    fee: float
    amount: Num = None                     # cash rows, in `currency`
    currency: str | None = None
    fx_rate: Num = None                    # DKK per unit of price, as booked (optional)
    note: str | None = None
    source: str
    import_id: int | None = None
    run_id: int | None = None
    ext_ref: str | None = None
    created_at: str
    updated_at: str


class Issue(Strict):
    level: Literal["error", "warning"]
    field: str
    message: str


class PositionState(Strict):
    quantity: float
    avg_price: Num = None


class Effect(Strict):
    symbol: str
    before: PositionState
    after: PositionState


class PriceCheck(Strict):
    symbol: str
    currency: str | None = None
    close: Num = None
    close_date: str | None = None
    verdict: Literal["ok", "x100", "div100", "far", "no_data"]
    message: str | None = None
    fx: Num = None                         # DKK per unit of price that day (Yahoo), to prefill a trade's rate


class TxCheck(Strict):
    issues: list[Issue]
    effect: Effect | None = None
    price: PriceCheck | None = None
    fee_estimate: FeeEstimate | None = None


class TxResult(Strict):
    tx: TxRow
    issues: list[Issue]


class PositionRow(Strict):
    symbol: str
    name: str | None = None
    currency: str | None = None
    portfolio_id: int | None = None
    portfolio: str | None = None
    portfolios: str | None = None
    quantity: float
    avg_price: float
    first_trade: str | None = None
    last: Num = None
    value: Num = None
    unrealized: Num = None


class CashRow(Strict):
    portfolio_id: int
    portfolio: str
    funding: Literal["ledger", "implicit"]
    cash_dkk: Num = None                   # None without a cash ledger, or when a DKK rate is missing
    problems: list[str] = []


class PositionsView(Strict):
    total: list[PositionRow]
    by_portfolio: list[PositionRow]
    cash: list[CashRow] = []
    warnings: dict[str, list[str]]
    transactions: int


class ImportRow(Strict):
    row: int
    ident: str
    symbol_in: str | None = None
    isin: str | None = None
    name: str | None = None
    date: str | None = None
    type: TxType | None = None
    quantity: Num = None
    price: Num = None
    fee: float = 0.0
    amount: Num = None                     # cash rows, in DKK
    currency: str | None = None
    portfolio: str | None = None           # named in the file (its account column)
    ext_ref: str | None = None
    skip: str | None = None
    symbol: str | None = None
    issues: list[Issue] = []
    duplicate: bool = False


class SymbolCandidate(Strict):
    symbol: str
    how: str
    name: str | None = None
    exchange: str | None = None


class SymbolMatch(Strict):
    ident: str
    isin: str | None = None
    name: str | None = None
    candidates: list[SymbolCandidate]
    chosen: str | None = None
    certain: bool
    search_failed: bool = False


class ImportCounts(Strict):
    rows: int
    new: int
    duplicates: int
    skipped: int
    errors: int
    warnings: int


class ImportPreview(Strict):
    preset: str | None = None
    preset_label: str | None = None
    verified: bool | None = None
    snapshot: bool
    columns: list[str]
    mapping: dict[str, str]
    rows: list[ImportRow]
    symbols: list[SymbolMatch]
    watch: list[str]
    counts: ImportCounts
    portfolio_id: int | None = None        # where rows without their own portfolio go (None: "Main", created)
    new_portfolios: list[str] = []         # named in the file, created as real portfolios on import


class ImportCommitResult(Strict):
    id: int
    added: int
    skipped: int
    replaced: int
    source: str


class ImportRecord(Strict):
    id: int
    source: str
    file_name: str | None = None
    rows_added: int
    rows_skipped: int
    at: str
    portfolio_id: int | None = None
    portfolio: str | None = None
    rows_now: int
    rows_replaced: int = 0           # a snapshot import's replaced rows: it can't be undone, only restored
    backup: str | None = None        # the database copy taken before it


class Preset(Strict):
    key: str
    label: str
    verified: bool
