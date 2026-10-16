"""The canonical items read from financial statements, and where each one is found in each source.

One item can be reported under several names: a company switches XBRL tag (revenue moved from `SalesRevenueNet` to
`RevenueFromContractWithCustomer…` with ASC 606 in 2018), and Yahoo's rows differ between companies. Each source
lists its names in order of preference; the first that has a value for a period is used for that period, and the
name used is stored with the value (`tag`).

An EDGAR recipe is a tuple of tags summed for the same period and filing: ("LongTermDebtCurrent",
"ShortTermBorrowings") adds the two when a company doesn't report total current debt; a tag the company doesn't
use counts as nothing to add. A recipe applies to a period when its first tag has it, and of those the one that
finds the most of its tags wins (on a tie, the earlier one).

`flow` items cover a period (revenue in a quarter or a year); the others are balances on a day (assets). Yahoo
reports cash going out (capex, dividends, buybacks) as negative numbers; they are stored as positive amounts
(`outflow`).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    key: str
    flow: bool                                   # a period's amount (True) or a balance on a day (False)
    edgar: tuple[tuple[str, ...], ...] = ()      # recipes of us-gaap (or dei:) tags, in order of preference
    yahoo: tuple[str, ...] = ()                  # Yahoo statement rows (yfinance, pretty=False), in order
    outflow: bool = False                        # cash paid out: stored as a positive amount
    unit: str = "money"                          # money | shares | per_share


def _r(*tags: str) -> tuple[tuple[str, ...], ...]:
    return tuple((t,) for t in tags)


ITEMS: tuple[Item, ...] = (
    # income statement
    Item("revenue", True,
         _r("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet", "SalesRevenueGoodsNet"),
         ("TotalRevenue", "OperatingRevenue")),
    Item("cost_of_revenue", True,
         _r("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfServices"),
         ("CostOfRevenue", "ReconciledCostOfRevenue")),
    Item("gross_profit", True, _r("GrossProfit"), ("GrossProfit",)),
    Item("operating_income", True, _r("OperatingIncomeLoss"), ("OperatingIncome", "EBIT")),
    Item("pretax", True,
         _r("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"),
         ("PretaxIncome",)),
    Item("income_tax", True, _r("IncomeTaxExpenseBenefit"), ("TaxProvision",)),
    Item("net_income", True, _r("NetIncomeLoss", "ProfitLoss"), ("NetIncomeCommonStockholders", "NetIncome")),
    Item("interest", True, _r("InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"),
         ("InterestExpense", "InterestExpenseNonOperating")),
    Item("dna", True,
         _r("DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
            "DepreciationAmortizationAndAccretionNet"),
         ("ReconciledDepreciation", "DepreciationAndAmortization", "DepreciationAmortizationDepletion")),
    Item("diluted_shares", True, _r("WeightedAverageNumberOfDilutedSharesOutstanding"), ("DilutedAverageShares",),
         unit="shares"),
    Item("dps", True, _r("CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"),
         unit="per_share"),
    # cash flow
    Item("cfo", True,
         _r("NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
         ("OperatingCashFlow", "CashFlowFromContinuingOperatingActivities")),
    Item("capex", True, _r("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"),
         ("CapitalExpenditure", "PurchaseOfPPE"), outflow=True),
    Item("dividends_paid", True, _r("PaymentsOfDividends", "PaymentsOfDividendsCommonStock"),
         ("CashDividendsPaid", "CommonStockDividendPaid"), outflow=True),
    Item("buybacks", True, _r("PaymentsForRepurchaseOfCommonStock"),
         ("RepurchaseOfCapitalStock", "CommonStockPayments"), outflow=True),
    Item("issuance", True, _r("ProceedsFromIssuanceOfCommonStock", "ProceedsFromStockOptionsExercised"),
         ("CommonStockIssuance", "IssuanceOfCapitalStock")),
    # balance sheet
    Item("total_assets", False, _r("Assets"), ("TotalAssets",)),
    Item("current_liabilities", False, _r("LiabilitiesCurrent"), ("CurrentLiabilities",)),
    Item("cash", False,
         (("CashAndCashEquivalentsAtCarryingValue", "ShortTermInvestments"),
          ("CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "ShortTermInvestments"),
          ("CashAndCashEquivalentsAtCarryingValue", "MarketableSecuritiesCurrent")),
         ("CashCashEquivalentsAndShortTermInvestments", "CashAndCashEquivalents")),
    Item("debt_current", False,
         (("DebtCurrent",), ("LongTermDebtCurrent", "ShortTermBorrowings", "CommercialPaper"),
          ("ShortTermBorrowings", "CommercialPaper")),
         ("CurrentDebt", "CurrentDebtAndCapitalLeaseObligation")),
    Item("debt_noncurrent", False, _r("LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"),
         ("LongTermDebt", "LongTermDebtAndCapitalLeaseObligation")),
    Item("equity", False,
         _r("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
         ("StockholdersEquity", "CommonStockEquity")),
    Item("minority", False, _r("MinorityInterest"), ("MinorityInterest",)),
    Item("preferred", False, _r("PreferredStockValue"), ("PreferredStockEquity",)),
    Item("shares", False, _r("dei:EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding"),
         ("OrdinarySharesNumber", "ShareIssued"), unit="shares"),
)

BY_KEY = {i.key: i for i in ITEMS}
FLOWS = frozenset(i.key for i in ITEMS if i.flow)


def edgar_tags() -> set[str]:
    """Every tag the EDGAR parser reads (prefixed `dei:` for the dei taxonomy)."""
    return {t for i in ITEMS for recipe in i.edgar for t in recipe}
