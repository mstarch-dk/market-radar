---
name: propose-portfolio
description: Propose a diversified, fee-aware basket of stocks to add an amount in DKK to one of the user's named portfolios (momentum, value/K+V or a mix), from the radar's own proposal score, caps on sector, region, currency and correlation after the addition, and at least 10.000 DKK per name. Ends in a memo with the expected max drawdown, the modelled return and risk vs ACWI, the alternatives (ACWI itself, the rule-only basket, other tilts, fewer or more names, topping up, sector ETFs, random baskets), exit criteria per pick and a decision record. Also `review`: how past proposals did and whether their exit criteria have triggered. Use when the user asks what to buy with an amount, how to invest X DKK in a portfolio, for a basket or portfolio proposal, or runs /propose-portfolio.
argument-hint: <portfolio> <amount-dkk> [momentum|value|mix] | review
---

# Propose a portfolio addition

Read `investor_notes` first: the user's accounts, horizon, max position size, drawdown tolerance, sectors to
avoid (if it has none yet, go on without). Also `market_views` (the user's market views: subjective beliefs, not
evidence).

Work through the `mcp__radar__*` tools; their descriptions carry the units. A proposal is named by the `id` that
`propose_freeze` returns. If the `radar` tools aren't connected, use the CLI instead: `uv run radar paths --json`
for the folders, then `radar propose candidates|freeze|evaluate|shadow|review|check … --json` with picks files in
`exports/proposals/`, and `radar study propose`.

Output goes to `research/proposals/YYYY-MM-DD_<portfolio>.md` (`write_memo(kind="proposals", …)`; a review to
`research/proposals/reviews/YYYY-MM.md`, `kind="proposal_reviews"`).
Reply with the summary and the alternatives table, and a link. Everything here is analysis, not a recommendation to
buy or sell; say so in the memo.

**The method in one paragraph.** The engine (`radar propose`) does the numbers; you add judgment within limits.
The rule picks a basket by the proposal score (the tilt's pre-registered weights on the momentum score and K+V
percentiles, less penalties for volatility, a one-month spike and correlation with the portfolio) under caps on
the portfolio *after* the addition. The **expected excess over ACWI comes from the rule study** (`radar study
propose`: the same rule at every past month-end), cut by the survivorship haircut and **shrunk toward the
long-run prior** (JKP's survivorship-free tercile portfolios of the same characteristics since 2008, in today's
ACWI trend), never from the picks' own past returns, which were chosen for being high. Risk comes from three drawdown lenses. **ACWI is the null**: the decision rule proposes stocks only when
the modelled edge after costs clears `propose.min_edge`, the holdout agrees, and the bad-case drawdown is within
the user's tolerance. Saying "buy ACWI instead" is a valid, often the right, answer.

## Reading the results
- **Missing values** are `null`: write "n/a", never fill one in.
- **`propose_candidates`**: `portfolio`, `n`, `ticket_dkk`, `regime`, `fee_model`, `notes` (read them: no fee schedule, no
  ACWI weights, holdings without a price), `exposure_now` (weights and active weights vs ACWI by sector, region,
  currency), `gates.excluded` (reason → tickers), `shortlist` (score parts: `c_momentum`, `c_qv`, `pen_vol`,
  `pen_stretch`, `pen_corr`, `corr_book`; `in_rule_basket`, `passed_over` with why), `rule_basket` (picks, sizing,
  filler), `study` (the rule study for this tilt and size: `drift_gross`, `basis`, `stale`, `us_only`; see the
  model fields below), `trend` (ACWI vs its 10-month average), `ask` (aktiesparekonto notes) and
  **`draft_picks`**: the rule basket as a picks file with the standard exits.
- **`propose_evaluate`**: `constraints` (each `ok` with detail), `size` (quantity, value, fee, spread and round-trip cost per
  name; `leftover_dkk`), `filler`, `exposure.before/after/basket`, `factors` (loadings on ACWI and MTUM/VLUE/QUAL/USMV
  tilts, with t), `risk.basket/before/after` (vol, beta, tracking error, diversification ratio, risk contributions),
  `model` (`drift_gross`, `cost_pct`, `drift_net`, `bootstrap` with `excess` p10/median/p90,
  `p_beat`, `max_dd`), `drawdown` (`expected`, `bad_case`, `lenses`), `stress` (per window: coverage, return, max
  DD, ACWI's), `alternatives` (A0–A6, same metrics), `decision` (`verdict`, `why`, `checks`, `unchecked`),
  `untested_kv` (picks outside the US in a K+V tilt: the rule study never tested them).
- **The drift, step by step** (`model.study[H]`): `drift_gross_raw` (the study's mean) → `haircut.used` (the
  configured haircut, or the long-run study's survivorship gauge when larger; `haircut.basis`) → `drift_short` →
  shrunk toward `prior.mean` (`prior.basis`: region, trend, independent periods; `prior.regions`: developed,
  ex-US and US side by side) with weight `w_short` on the study → `drift_gross`. A small `w_short` means the
  study is too noisy to move far from the decades of evidence; say so.
- **Statistics to respect**: the study's `effective_n` (dates ÷ horizon) is the number of roughly independent
  periods; `t` is Newey-West. An excess with |t| < 2 or a holdout of the opposite sign is weak evidence. Value and
  mix tilts are tested on US stocks only (`us_only`).

## Steps

1. **Parse and check.** Arguments: portfolio name, amount (accept `50k`, `50.000`, `50000`), optionally the tilt.
   Check the name against `portfolios` (real portfolios are the user's accounts; a
   virtual one is fine but say so). If the amount is below one ticket (`propose.min_ticket_dkk`), say that one
   ETF (ACWI UCITS) is the sensible answer and stop unless the user insists.

2. **The rule study.** `study_reports`: the `propose-study` entry. If it is missing or stale (or `candidates`'
   `study.stale` is true), `job_start(kind="study", study="propose-study")` (slow: several minutes; it runs in the
   background, so continue with step 3 and check `job_status(kind="study")` before step 6). Without it, the drift
   is n/a and the verdict will be A0: say why.

3. **Ask once** (one AskUserQuestion call), only for what the arguments and the investor notes don't settle:
   - **Tilt**: Momentum / Value (K+V) / Mix. In each option's description quote the rule study's evidence for that
     tilt at the default size and horizon: the mean excess with its t, the holdout's sign, and the figure for
     today's regime when it has enough dates, then the long-run prior and the shrunk drift (e.g. "momentum: study
     +3 % per 6 months, t 1.4, holdout positive; long run +1 % (developed, uptrend); model +1.5 %"). Don't recommend the tilt that looked best in the study: that is snooping; the user chooses.
   - **Mode**: conviction (best scores) or fill-gaps (prefer sectors the portfolio is underweight vs ACWI).
   - **Horizon**: 3 or 6 months (default from the investor notes, else 6).
   - **Number of names**: default amount ÷ min ticket (capped at `max_names`); mention that the frontier (A3)
     will show the trade-off.
   - **ETF filler** for leftover cash: yes / no.
   Skip the question entirely when the amount allows only one name and the tilt was given.

4. **Candidates.** `propose_candidates(portfolio, amount, tilt, mode, n?, horizon?, max_position?, etf?)`.
   `max_position` from the investor notes (a share: 0.10 = 10 %) when they give one, or from the user's own
   trading rules when stricter: `trading_rules()` lists them, and an active `max_position_weight` rule in scope
   for this portfolio sets it (its `pct` / 100). Read the notes and the gates.

5. **Judgment, bounded.** Start from `draft_picks` (the rule basket). You may swap at most `propose.max_swaps`
   picks, each with a written `swap_reason`, and only for reasons the rule can't see:
   - an earnings report within two weeks (`calendar(symbols=[…])` for the names the user already holds or watches,
     the same dates as the app; `ticker_profile([<T>])`'s `analyst` for the others), or news that
     breaks the thesis (search the web for the 2–3 names you have doubts about);
   - a conflict with a market view of conviction 4–5;
   - a sector or name the investor avoids (the investor notes);
   - a one-month spike the rule's stretch penalty didn't catch.
   Replace from the shortlist only (a name that passed the gates). For every pick write `why` (one line: what the
   score says, what the role in the portfolio is) and add 1–2 checkable thesis items under `exit.thesis`: either
   `{"text": …, "metric": "score"|"qv"|"r3m"|"from_high", "op": "<"|">", "value": …}` or a text-only item
   (marked as a suggestion). Leave the standard exits (review level, signal, time stop) as they are.
   Check every pick against the user's trading rules with `rules_check("buy", <T>, amount_dkk=<its amount>,
   portfolio, style=<the tilt's style: momentum for momentum, value for value>)` (not logged). A pick that
   breaks a `max_position_weight`, `max_exposure_weight`, `min_ticket` or `max_positions` rule is replaced from the
   shortlist (a swap with that `swap_reason`, within `propose.max_swaps`); any other break or near verdict stays in
   the memo under *Dine handelsregler*, with the numbers, as something for the user to weigh.
   Then **freeze the picks before seeing any model number**: `propose_freeze(meta=draft_picks.meta, picks=[…],
   filler=draft_picks.filler)` returns the proposal's `id`. A frozen proposal is never changed.

6. **Evaluate.** `propose_evaluate(id, tolerance=T)` (`tolerance` from the investor notes' drawdown tolerance,
   e.g. 0.25). It is saved beside the frozen picks (review and check read its drawdown band). If a constraint
   fails, make one repair pass (swap the offending name for the next one in the shortlist that fits), freeze the
   repaired picks (a new `id`), evaluate again, and say so in the memo. Never re-pick to
   improve the modelled return or drawdown: that is curve-fitting to our own model.

7. **Red team.** Launch a general-purpose subagent with the proposal's `id` (it reads the picks, their `why` and
   the evaluation with `propose_picks(id, with_evaluation=true)`): "Argue the strongest case against this basket
   and for the best alternative in `alternatives` (usually A0, ACWI). Use only the numbers given, the long-run base
   rates in `evidence_view(sections=["longrun"])` (`base_rates`, `survivorship`), plus at most three web
   searches. List the three facts that would most change the verdict."
   Put its answer, condensed, in the memo, with your response to each point.

8. **Write the memo** (template below), then reply with the summary table, the alternatives table and the link.

9. **Offer next steps** (don't do them unasked):
   - `propose_shadow(id, name="<portfolio> proposal <date>")`: virtual copies of the
     portfolio with the proposal, with ACWI and with the rule-only basket, so the Returns page tracks all three.
   - `/journal` for each real buy: pass the pick's `why` as the thesis and its exit criteria (review level, signal
     exit, thesis items, time stop) as the exit rules, and the account.

### `review`
`/propose-portfolio review`: `propose_review()` and `propose_check()`.
Write `research/proposals/reviews/YYYY-MM.md` (`write_memo(kind="proposal_reviews", name="YYYY-MM", …)`):
- per proposal: realised return vs ACWI and vs its rule basket (judgment's value), drawdown vs the modelled band,
  the trend exit vs keeping (did it cut losses or whipsaw);
- per open pick: Intact / Weakening / Triggered with the evidence; flag `older_rule` (criteria set under other
  settings: re-evaluate at the next review date, never move a review level down to avoid a trigger);
- what is due: time stops passed → re-run the scoring and keep a name only if it would be picked again today; cash
  freed by exits is a natural input to the next proposal (the redeploy study, `redeploy-study.json` in
  `data_paths`' `folders.reports`, backs parking in ACWI vs re-picking; `study_reports` says how old it is).
State plainly when there are fewer proposals than `propose.review_min`: too few to judge the method.

## Template

```markdown
# Proposal: <amount> DKK into <portfolio> (<date>)

*Analysis, not advice.* Tilt <tilt>, <mode>, horizon <H> months, <n> names. Regime: <regime>.

## Verdict
<stocks | A0 (ACWI)> — <decision.why>. Checks: edge <…>, holdout <…>, drawdown <…>; unchecked: <…>.

## The basket
| Ticker | Name | Sector | Region | Ccy | DKK | Qty | Cost | Why |
|---|---|---|---|---|---|---|---|---|
(swaps marked "↔ for <ticker>: <reason>"); filler: <ETF, DKK, positive list> or "leftover <x> DKK stays cash"
Total round-trip cost <x DKK, y %>; fee model <schedule or flat bp>.

## What it does to the portfolio
| | Before | After | ACWI |
|---|---|---|---|
| Largest sectors / regions / currencies (active weights) | … | … | … |
| Vol / beta / tracking error / diversification ratio | … | … | – |
Factor loadings of the basket (MTUM/VLUE/QUAL/USMV, with t): …

## Modelled return and risk vs ACWI (<H> months)
- Excess over ACWI after costs: <drift_net>. Rule study: <drift_gross_raw> gross (<basis>, n <n_used>, eff. N <…>,
  t <…>, holdout <…>) → <drift_short> after a <haircut.used> survivorship haircut (<haircut.basis>) → <drift_gross>
  shrunk toward the long-run prior <prior.mean> (<prior.basis>; ex US <…>, US <…>), weight on the study <w_short>.
  Band (bootstrap) <p10> to <p90>; P(beat ACWI) <…>.
- Untested: <untested_kv, or "none">.
- **Expected max drawdown <expected>; bad case <bad_case>.** Lenses: study <median/p10>, bootstrap <median/p10>,
  stress windows: <table: window, coverage, basket, ACWI>. Realised 1y / 3y drawdown of today's weights: <…>.

## Alternatives
| | What it tests | Net excess | Cost | Vol | TE | Exp. DD | P(beat) |
|---|---|---|---|---|---|---|---|
| A0 ACWI | the null | | | | | | |
| A1 rule-only | judgment | | | | | | |
| A2 other tilts | tilt | | | | | | |
| A4 top-up | no new names | | | | | | |
| A5 sector ETFs | picking vs exposure | | | | | | |
A3 frontier: n → cost / vol / TE (knee at n = …). A6: the proposal's vol / TE / diversification percentile among
<draws> random baskets under the same caps.

## Exit plan
| Ticker | Review level | Signal exit | Thesis checks | Time stop |
|---|---|---|---|---|
Basket level: review the model if the drawdown passes <bad_case>. `propose_check` re-evaluates these.

## Red team
<the strongest case against, and the response>

## Account
<ASK: 17 % lager, positive list for the filler, deposit-cap check; frie midler: realisation taxation, so turnover
costs tax too; an after-tax illustration of the modelled median>

## Decision record
- Decision: <the user's, or "pending">  - Proposal: <id> (sha <picks_sha>)  - Review on: <time stop>
```

## Ground rules
- Missing is n/a; never fill in a number the JSON doesn't have.
- The drift comes from the rule study shrunk toward the long-run prior, never from the picks' own past. The
  bootstrap and stress windows describe risk, not a forecast;
  ACWI's drift in the bootstrap is an assumption (`propose.acwi_drift_annual`): say so.
- Freeze before evaluating; at most `max_swaps` swaps, each with a reason; one repair pass for a failed constraint.
- Say plainly when the verdict is A0, and don't argue the user out of it.
- Never present a simulated or shadow portfolio as the user's; never write trades into a real portfolio (that is
  `/journal`, on the user's word).
