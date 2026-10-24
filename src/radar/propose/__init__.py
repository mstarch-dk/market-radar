"""Proposals: a fee-aware basket of new stocks for one of your portfolios, tested against ACWI and the alternatives
(`radar propose`, the /propose-portfolio skill). Analysis, not advice; a number that can't be computed is None with
a note, never 0. The method: guide/laerebog/portefoeljeforslag.md (*Sådan gør radaren*); the steps as you meet
them: guide/brugervejledning/claude-code.md (*/propose-portfolio*).

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
from .evaluation import adv_dkk, alternatives, decide, evaluate, factors, metrics, picks_sha, randoms  # noqa: F401
from .exposure import DIMS, annotate, book, exposures, info, look_through  # noqa: F401
from .pricing import Prices  # noqa: F401
from .riskmodel import bootstrap, realised_dd, risk, series, shrunk_cov, stress  # noqa: F401
from .rules import (  # noqa: F401
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
from .store import check, evaluation_file, keep_evaluation, proposals, review, save_evaluation, save_picks, shadow  # noqa: F401
