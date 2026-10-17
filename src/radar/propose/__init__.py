"""Proposals: a fee-aware basket of new stocks for one of your portfolios, tested against the alternatives
(`radar propose`, the /propose-portfolio skill). Analysis, not advice.

- **Context**: the portfolio, its fee schedule (fees.SimFees), its holdings valued in DKK today, and your whole real
  book (every real portfolio) for overlap and the position limit. ACWI's own sector, region and currency weights
  come from the iShares MSCI ACWI UCITS holdings file (constituents.acwi_holdings); without it the active weights are
  unknown and said so.
- **Gates**: a name is left out, and listed with why, when it has no score the tilt needs, no DKK rate, a stale
  price, a short history, thin trading, a share price above the ticket, or (tilts led by momentum) no uptrend.
- **Score** (`score`): the proposal score is a weighted mean of percentiles in the gated pool (the momentum score
  and K+V, by the tilt's pre-registered weights in settings.yaml `propose.tilts`) less penalties for volatility,
  a one-month spike and correlation with the portfolio. The weights are part of the rule the rule study tests
  (backtest/propose_study.py); changing them makes the study stale.
- **Selection** (`select`): greedy by score under caps on the portfolio *after* the addition: active weight vs
  ACWI by sector, region and currency (a bucket's first name is always allowed: one ticket is not a pile-up),
  new names per sector, a correlation cap against the picks and the holdings, and a position limit against your
  whole real book.
- **Sizing** (`size`): at least `min_ticket_dkk` per name, equal or inverse-volatility weights, whole shares, the
  portfolio's broker schedule with its FX surcharge, and an estimated half-spread by liquidity. Leftover cash
  goes to the ETF filler (ACWI UCITS; on an aktiesparekonto only if it is on the positive list) or stays cash.
- **Evaluation** (`evaluate`): exposures before → after, risk from a shrunk covariance of weekly DKK returns,
  the drawdown three ways (the rule study's realised drawdowns, a vol-scaled block bootstrap, historical stress
  windows), the expected excess over ACWI from the rule study only, the alternatives A0-A6 on the same metrics,
  and the pre-committed decision rule.
- **Follow-up**: `shadow` (virtual copies: the proposal, ACWI and the rule-only basket), `review` (how past
  proposals did against their model) and `check` (each pick's exit criteria today).

Missing is missing: a number that can't be computed is None with a note, never 0.

The package, in the order they build on each other: `rules`, `pricing`, `exposure`, `basket`, `riskmodel`,
`drift`, `draft`, `evaluation`, `store`. Every public name is re-exported here: callers use `propose.<name>`."""
from __future__ import annotations

from .basket import Base, budgets, corr_to, filler, gates, half_spread, n_for, pool, score, select, size, terms_for  # noqa: F401
from .draft import (  # noqa: F401
    Ctx,
    ask_account,
    ask_flag,
    candidates,
    context,
    default_exit,
    holdings_base,
    ranked_pool,
    rule_basket,
    values_of,
)
from .drift import haircut, load_study, long_prior, shrink, study_view  # noqa: F401
from .evaluation import adv_dkk, alternatives, decide, evaluate, factors, metrics, picks_doc, picks_sha, randoms  # noqa: F401
from .exposure import DIMS, annotate, book, exposures, info, look_through  # noqa: F401
from .pricing import Prices  # noqa: F401
from .riskmodel import bootstrap, realised_dd, risk, series, shrunk_cov, stress  # noqa: F401
from .rules import MEMOS, MODES, PROPOSALS, RULE_KEYS, TILTS, WEEKS_PER_MONTH, WEIGHTINGS, cfg, rule_hash, slug  # noqa: F401
from .store import check, evaluation_file, proposals, review, save_evaluation, save_picks, shadow  # noqa: F401
