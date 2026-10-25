"""The tax estimate (tax.py): per account and tax person for an income year, and the inputs you edit (tax
persons, instruments, openings). An estimate, not tax advice. Missing figures are None, never 0."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Num, Strict
from .portfolios import PortfolioKind

TaxClass = Literal["stock", "pl_fund", "fund", "dk_distributing", "unknown"]     # taxinputs.classify
ManualTaxClass = Literal["stock", "pl_fund", "fund", "dk_distributing"]          # userstore.TAX_CLASSES
OpeningPool = Literal["ask_negative_tax", "pension_negative_tax", "listed_loss", "negative_share_income"]


class TaxRulesRef(Strict):
    """The year's rules in config/tax_dk.yaml: the day they were checked and their sources."""
    year: int
    verified: str | None = None
    sources: list[str]


class ShareIncomeView(Strict):
    """A person's share income (aktieindkomst) after the loss rules, and its tax with the progression limit."""
    realised_gains: float
    realised_losses: float
    dividends: float
    pl_gains: float
    pl_losses: float
    listed_loss_in: float
    listed_loss_used: float
    listed_loss_out: float
    negative_in: float
    negative_out: float
    net: float
    limit: float
    tax_low: float
    tax_high: float
    tax: float


class TaxBases(Strict):
    """The year's amounts before any netting, also when there are no rules for the year."""
    realised_gains: float
    realised_losses: float
    dividends: float
    pl_gains: float
    pl_losses: float
    capital_base: float


class CapitalIncome(Strict):
    base: float
    rate: Num = None              # the person's own marginal rate; none: no tax shown
    tax: Num = None


class TaxPerson(Strict):
    id: int
    name: str
    accounts: list[str]
    share_income: ShareIncomeView | None = None
    bases: TaxBases | None = None
    capital_income: CapitalIncome | None = None
    complete: bool
    notes: list[str]


class TaxPool(Strict):
    """An aktiesparekonto's or a pension account's year: return = v_end − v_start − deposits + withdrawals."""
    v_start: Num = None
    v_end: Num = None
    deposits: float
    withdrawals: float
    ret: Num = None
    carried_in: Num = None        # negative tax carried in
    rate: Num = None
    gross_tax: Num = None
    used: Num = None
    tax: Num = None
    carried_out: Num = None


class TaxSale(Strict):
    symbol: str
    date: str
    portfolio_id: int | None = None
    portfolio: str | None = None
    quantity: float
    proceeds: Num = None
    basis: Num = None
    gain: Num = None
    tax_class: TaxClass
    reason: str | None = None


class TaxLager(Strict):
    symbol: str
    tax_class: TaxClass
    v_start: Num = None
    v_end: Num = None
    buys: Num = None
    sales: Num = None
    gain: Num = None
    portfolio_id: int
    portfolio: str


class TaxDividend(Strict):
    symbol: str
    date: str
    portfolio_id: int
    portfolio: str
    amount: float
    tax_class: TaxClass
    reason: str | None = None


class TaxAccount(Strict):
    id: int
    name: str
    kind: PortfolioKind
    person_id: int | None = None
    pool: TaxPool | None = None
    realised: list[TaxSale]
    lager: list[TaxLager]
    dividends: list[TaxDividend]
    complete: bool
    warnings: list[str]
    notes: list[str]


class TaxUnknown(Strict):
    symbol: str
    portfolio_id: int
    portfolio: str
    value_dkk: Num = None
    reason: str | None = None


class TaxYearView(Strict):
    year: int
    asof: str
    complete_year: bool
    rules: TaxRulesRef | None = None
    disclaimer: str
    persons: list[TaxPerson]
    accounts: list[TaxAccount]
    unknown: list[TaxUnknown]
    notes: list[str]


class TaxPersonView(Strict):
    id: int
    name: str
    capital_income_rate: Num = None
    note: str | None = None
    portfolio_ids: list[int]
    created_at: str
    updated_at: str


class TaxPersonIn(Strict):
    name: str
    capital_income_rate: float | None = Field(None, ge=0, le=1)
    note: str | None = None


class InstrumentView(Strict):
    symbol: str
    isin: str | None = None
    tax_class: ManualTaxClass | None = None
    source: Literal["manual", "import", "universe", "discovery"]
    note: str | None = None
    updated_at: str


class InstrumentIn(Strict):
    isin: str | None = None
    tax_class: ManualTaxClass | None = None      # none: decided automatically
    note: str | None = None


class TaxOpeningView(Strict):
    id: int
    year: int
    pool: OpeningPool
    portfolio_id: int | None = None
    tax_person_id: int | None = None
    amount: float
    note: str | None = None
    created_at: str


class TaxOpeningIn(Strict):
    year: int = Field(ge=1990, le=2100)
    pool: OpeningPool
    portfolio_id: int | None = None
    tax_person_id: int | None = None
    amount: float = Field(gt=0)
    note: str | None = None
