"""Proposals: a fee-aware basket of new stocks for one of your portfolios, tested against ACWI and the alternatives
(`radar propose`, the /propose-portfolio skill). Analysis, not advice; a number that can't be computed is None with
a note, never 0. The method: guide/laerebog/portefoeljeforslag.md (*Sådan gør radaren*); the steps as you meet
them: guide/brugervejledning/claude-code.md (*/propose-portfolio*).

The package, in the order they build on each other: `rules`, `basket`, `resample`, `drift`, `draft`,
`evaluation`, `store`. Every public name is re-exported here (`__all__`): callers use `propose.<name>`. The holdings,
exposure and risk model a proposal is measured with are shared with the portfolio views: `portfolios.prices`,
`portfolios.exposure`, `portfolios.riskmodel`."""
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
from .evaluation import (
    adv_dkk,
    alternative_metrics,
    alternatives,
    cost_share,
    decide,
    evaluate,
    net_drift,
    picks_sha,
    randoms,
)
from .resample import bootstrap
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
    "MEMOS", "MODES", "PROPOSALS", "RULE_KEYS", "TILTS", "WEEKS_PER_MONTH", "WEIGHTINGS", "adv_dkk",
    "alternative_metrics", "alternatives", "ask_account", "ask_flag", "Base", "bootstrap", "budgets", "candidates",
    "cfg", "check_exits", "context", "corr_to", "cost_share", "Ctx", "decide", "default_exit", "evaluate",
    "evaluation_file", "filler", "gates", "haircut", "half_spread", "holdings_base", "keep_evaluation", "load_study",
    "long_prior", "n_for", "net_drift", "picks_sha", "pool", "proposal_score", "proposals", "randoms", "ranked_pool",
    "review", "rule_basket", "rule_hash", "rule_settings", "save_evaluation", "save_picks", "select", "shadow",
    "shrink", "size_picks", "slug", "study_view", "terms_for", "values_of",
]
