"""Danish tax arithmetic, pure: the average-cost replay in DKK, lager per holding and year, the aktiesparekonto's
and the pension account's pool with negative tax carried forward, share income with the loss rules and the
progression limit, and the ASK's deposit headroom. Numbers in, numbers out; the rules come from config/tax_dk.yaml
(`portfolios/taxrules.py`) and the inputs from `portfolios/taxinputs.py`. An estimate, not tax advice.

A missing input gives a missing result (None), never 0: a trade without a DKK rate, a holding without a year-end
value. The caller leaves such items out of a total and says so."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

EPS = 1e-9


@dataclass(frozen=True)
class Trade:
    """A buy or sale in the security's quote currency, with the DKK rate it was booked at (None: unknown)."""
    day: date
    kind: str                     # BUY | SELL
    quantity: float
    price: float
    fee: float
    rate: float | None
    ref: object = None            # the caller's own key (its row), carried to the sale

    @property
    def dkk(self) -> float | None:
        """What the trade cost (a buy: price × quantity + fee) or brought in (a sale: less the fee), in DKK."""
        if self.rate is None:
            return None
        gross = self.quantity * self.price
        return (gross + self.fee if self.kind == "BUY" else gross - self.fee) * self.rate


@dataclass(frozen=True)
class Sale:
    day: date
    quantity: float
    proceeds: float | None        # DKK, after the sale's fee
    basis: float | None           # the average cost of what was sold, DKK
    gain: float | None
    ref: object = None


@dataclass
class Replay:
    quantity: float = 0.0
    cost: float | None = 0.0      # DKK; None once a trade's rate is unknown
    sales: list[Sale] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def replay_dkk(trades: Iterable[Trade]) -> Replay:
    """The average-cost method (gennemsnitsmetoden) in DKK, in date order: a buy adds its cost with the fee, a sale
    takes out cost in proportion (the average doesn't change) and its gain is proceeds less fee minus that cost. A
    sale larger than the position is capped and reported. A trade without a rate makes the cost unknown from then on,
    so later gains are None, never a guess."""
    r = Replay()
    for t in sorted(trades, key=lambda x: x.day):
        if t.kind == "BUY":
            r.quantity += t.quantity
            r.cost = None if r.cost is None or t.dkk is None else r.cost + t.dkk
            continue
        q = t.quantity
        if q > r.quantity + EPS:
            r.warnings.append(f"sold {q:g} on {t.day:%Y-%m-%d} but held {r.quantity:g} (split or missing buy?)")
            q = r.quantity
        if q <= EPS:
            continue
        basis = None if r.cost is None else r.cost / r.quantity * q
        proceeds = None if t.rate is None else (q * t.price - t.fee * q / t.quantity) * t.rate
        gain = None if basis is None or proceeds is None else proceeds - basis
        r.sales.append(Sale(t.day, q, proceeds, basis, gain, t.ref))
        r.cost = None if r.cost is None or basis is None else r.cost - basis
        r.quantity -= q
        if r.quantity <= EPS:
            r.quantity, r.cost = 0.0, (0.0 if r.cost is not None else None)
    return r


def lager(v_start: float | None, v_end: float | None, buys: Iterable[float | None],
          sales: Iterable[float | None]) -> float | None:
    """The year's lager gain of one holding: value at year end plus what sales brought in, less the value at the
    year's start and what buys cost (all DKK). SKAT's "end value minus start value, or cost when bought in the year",
    written for any sequence of trades. None when any part is unknown."""
    b, s = list(buys), list(sales)
    if v_start is None or v_end is None or any(x is None for x in b + s):
        return None
    return v_end + sum(x for x in s if x is not None) - v_start - sum(x for x in b if x is not None)


@dataclass(frozen=True)
class Pool:
    """An aktiesparekonto's or a pension account's year: the return, the tax and the negative tax carried."""
    ret: float
    rate: float
    gross_tax: float              # ret × rate; negative in a losing year
    carried_in: float             # negative tax from earlier years (≥ 0)
    used: float                   # of carried_in, used this year
    tax: float                    # payable (≥ 0)
    carried_out: float            # negative tax carried into next year


def account_pool(v_start: float, v_end: float, deposits: float, withdrawals: float, carried_in: float,
                 rate: float) -> Pool:
    """Lager on the whole account: return = end value − start value − deposits + withdrawals (dividends are in
    the values). A losing year's negative tax is carried forward and set against the next positive years' tax
    (aktiesparekontoloven, PAL § 17); it isn't paid out."""
    ret = v_end - v_start - deposits + withdrawals
    gross = ret * rate
    if gross < 0:
        return Pool(ret, rate, gross, carried_in, 0.0, 0.0, carried_in - gross)
    used = min(carried_in, gross)
    return Pool(ret, rate, gross, carried_in, used, gross - used, carried_in - used)


@dataclass(frozen=True)
class ShareIncome:
    """A person's share income (aktieindkomst) for the year, from their frie midler accounts."""
    realised_gains: float
    realised_losses: float        # this year's, ≥ 0
    dividends: float
    pl_gains: float               # lager gains on positive-list funds
    pl_losses: float              # lager losses on positive-list funds, ≥ 0
    listed_loss_in: float         # listed-share losses carried in
    listed_loss_used: float
    listed_loss_out: float
    negative_in: float            # negative share income carried in
    negative_out: float
    net: float                    # the year's share income after losses (≥ 0)
    limit: float
    tax_low: float
    tax_high: float
    tax: float


def share_income(realised: Iterable[float], dividends: float, pl_lager: Iterable[float], *, listed_loss_in: float,
                 negative_in: float, low_rate: float, high_rate: float, limit: float,
                 listed_offsets: Iterable[str]) -> ShareIncome:
    """Share income with the loss rules: a realised loss on listed shares (with what is carried in) offsets only the
    income kinds in `listed_offsets` (realised gains, dividends, positive-list lager gains) and the rest is carried
    forward; a lager loss on a positive-list fund is deducted as it stands. A negative total is carried forward as
    negative share income (its tax value against other income isn't modelled). Tax: `low_rate` up to `limit`,
    `high_rate` above."""
    rs, pl = list(realised), list(pl_lager)
    gains = sum(x for x in rs if x > 0)
    losses = -sum(x for x in rs if x < 0)
    pl_gains = sum(x for x in pl if x > 0)
    pl_losses = -sum(x for x in pl if x < 0)
    kinds = set(listed_offsets)
    offsetable = (gains if "realised" in kinds else 0.0) + (dividends if "dividends" in kinds else 0.0) \
        + (pl_gains if "pl_lager" in kinds else 0.0)
    pool = losses + listed_loss_in
    used = min(pool, offsetable)
    before = gains + dividends + pl_gains - used - pl_losses
    if before >= negative_in:
        net, neg_out = before - negative_in, 0.0
    else:
        net, neg_out = 0.0, negative_in - before
    low = low_rate * min(net, limit)
    high = high_rate * max(0.0, net - limit)
    return ShareIncome(gains, losses, dividends, pl_gains, pl_losses, listed_loss_in, used, pool - used,
                       negative_in, neg_out, net, limit, low, high, low + high)


def capital_tax(base: float, rate: float | None) -> float | None:
    """Tax on capital income at the person's own marginal rate; None when the rate isn't given (it depends on the
    rest of their income). A negative base gives no tax here: its deduction depends on that income too."""
    if rate is None:
        return None
    return max(0.0, base) * rate


def ask_headroom(cap: float, value_prev_end: float, deposits: float) -> float:
    """What may still be deposited on an aktiesparekonto this year: the cap less the account's value on 31 December
    the year before and this year's deposits so far (skat.dk). Negative: over the cap by that much."""
    return cap - value_prev_end - deposits
