"""Proposals: a fee-aware basket of new stocks for one of your portfolios, tested against ACWI and the alternatives
(`radar propose`, the /propose-portfolio skill). Analysis, not advice; a number that can't be computed is None with
a note, never 0. The method: guide/laerebog/portefoeljeforslag.md (*Sådan gør radaren*); the steps as you meet
them: guide/brugervejledning/claude-code.md (*/propose-portfolio*).

The package, in the order they build on each other: `rules`, `pricing`, `exposure`, `basket`, `riskmodel`,
`drift`, `draft`, `evaluation`, `store`. Every public name is re-exported here (`__all__`): callers use `propose.<name>`."""
from __future__ import annotations

from .basket import (
    Base,
    budgets,
    corr_to,
    filler,
    gates,
    half_spread,
    n_for,
    pool,
    proposal_score,
    select,
    size_picks,
    terms_for,
)
from .draft import (
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
from .drift import haircut, load_study, long_prior, shrink, study_view
from .evaluation import adv_dkk, alternative_metrics, alternatives, decide, evaluate, factors, picks_sha, randoms
from .exposure import DIMS, annotate, exposures, holdings_book, look_through, ticker_meta
from .pricing import Prices
from .riskmodel import bootstrap, ex_ante_risk, realised_dd, shrunk_cov, stress, weekly_returns
from .rules import (
    MEMOS,
    MODES,
    PROPOSALS,
    RULE_KEYS,
    TILTS,
    WEEKS_PER_MONTH,
    WEIGHTINGS,
    cfg,
    rule_hash,
    rule_settings,
    slug,
)
from .store import check_exits, evaluation_file, keep_evaluation, proposals, review, save_evaluation, save_picks, shadow

__all__ = [
    "DIMS", "MEMOS", "MODES", "PROPOSALS", "RULE_KEYS", "TILTS", "WEEKS_PER_MONTH", "WEIGHTINGS", "adv_dkk",
    "alternative_metrics", "alternatives", "annotate", "ask_account", "ask_flag", "Base", "bootstrap", "budgets",
    "candidates", "cfg", "check_exits", "context", "corr_to", "Ctx", "decide", "default_exit", "evaluate",
    "evaluation_file", "ex_ante_risk", "exposures", "factors", "filler", "gates", "haircut", "half_spread",
    "holdings_base", "holdings_book", "keep_evaluation", "load_study", "long_prior", "look_through", "n_for",
    "picks_sha", "pool", "Prices", "proposal_score", "proposals", "randoms", "ranked_pool", "realised_dd", "review",
    "rule_basket", "rule_hash", "rule_settings", "save_evaluation", "save_picks", "select", "shadow", "shrink",
    "shrunk_cov", "size_picks", "slug", "stress", "study_view", "terms_for", "ticker_meta", "values_of",
    "weekly_returns",
]
