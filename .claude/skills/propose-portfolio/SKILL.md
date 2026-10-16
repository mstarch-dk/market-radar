---
name: propose-portfolio
description: Propose a diversified, fee-aware basket of stocks to add an amount in DKK to one of the user's named portfolios (momentum, value/K+V or a mix), from the radar's own proposal score, caps on sector, region, currency and correlation after the addition, and at least 10.000 DKK per name. Ends in a memo with the expected max drawdown, the modelled return and risk vs ACWI, the alternatives (ACWI itself, the rule-only basket, other tilts, fewer or more names, topping up, sector ETFs, random baskets), exit criteria per pick and a decision record. Also `review`: how past proposals did and whether their exit criteria have triggered. Use when the user asks what to buy with an amount, how to invest X DKK in a portfolio, for a basket or portfolio proposal, or runs /propose-portfolio.
argument-hint: <portfolio> <amount-dkk> [momentum|value|mix] | review
---

# Propose a portfolio addition

Read `notes/investor.md` first if it exists: the user's accounts, horizon, max position size, drawdown tolerance,
sectors to avoid. Also read `uv run radar views --json` (the user's market views: subjective beliefs, not evidence).

**Where files are.** The user's data lives in their data folder, outside this project. Run `uv run radar paths --json` once and use its `folders`: in this skill `notes/…`, `briefs/…`, `research/…`, `journal/…` and `exports/…` are those folders inside `folders.data`, `reports/…` is `folders.reports` and `data/…` is `folders.cache`. Read and write them by their full path (pass full paths to `--out` too). If `state` is `unset` or `missing`, ask the user to start the app or run `uv run radar setup` first.

Output goes to `research/proposals/YYYY-MM-DD_<portfolio>.md` (a review to `research/proposals/reviews/YYYY-MM.md`).
Reply with the summary and the alternatives table, and a link. Everything here is analysis, not a recommendation to
buy or sell; say so in the memo.

**The method in one paragraph.** The engine (`radar propose`) does the numbers; you add judgment within limits.
The rule picks a basket by the proposal score (the tilt's pre-registered weights on the momentum score and K+V
percentiles, less penalties for volatility, a one-month spike and correlation with the portfolio) under caps on
the portfolio *after* the addition. The **expected excess over ACWI comes only from the rule study** (`radar study
propose`: the same rule at every past month-end), never from the picks' own past returns, which were chosen for
being high. Risk comes from three drawdown lenses. **ACWI is the null**: the decision rule proposes stocks only when
the modelled edge after costs clears `propose.min_edge`, the holdout agrees, and the bad-case drawdown is within
the user's tolerance. Saying "buy ACWI instead" is a valid, often the right, answer.

## The JSON you'll read
- **Units**: returns and weights are fractions (0.12 = 12 %); money is DKK. A missing value is `null`: write "n/a",
  never fill it in.
- **`candidates`**: `portfolio`, `n`, `ticket_dkk`, `regime`, `fee_model`, `notes` (read them: no fee schedule, no
  ACWI weights, holdings without a price), `exposure_now` (weights and active weights vs ACWI by sector, region,
  currency), `gates.excluded` (reason → tickers), `shortlist` (score parts: `c_momentum`, `c_qv`, `pen_vol`,
  `pen_stretch`, `pen_corr`, `corr_book`; `in_rule_basket`, `passed_over` with why), `rule_basket` (picks, sizing,
  filler), `study` (the rule study for this tilt and size: `drift_gross`, `basis`, `stale`, `us_only`), `ask`
  (aktiesparekonto notes) and **`draft_picks`**: the rule basket as a picks file with the standard exits.
- **`evaluate`**: `constraints` (each `ok` with detail), `size` (quantity, value, fee, spread and round-trip cost per
  name; `leftover_dkk`), `filler`, `exposure.before/after/basket`, `factors` (loadings on ACWI and MTUM/VLUE/QUAL/USMV
  tilts, with t), `risk.basket/before/after` (vol, beta, tracking error, diversification ratio, risk contributions),
  `model` (`drift_gross` from the study, `cost_pct`, `drift_net`, `bootstrap` with `excess` p10/median/p90,
  `p_beat`, `max_dd`), `drawdown` (`expected`, `bad_case`, `lenses`), `stress` (per window: coverage, return, max
  DD, ACWI's), `alternatives` (A0–A6, same metrics), `decision` (`verdict`, `why`, `checks`, `unchecked`).
- **Statistics to respect**: the study's `effective_n` (dates ÷ horizon) is the number of roughly independent
  periods; `t` is Newey-West. An excess with |t| < 2 or a holdout of the opposite sign is weak evidence. Value and
  mix tilts are tested on US stocks only (`us_only`).

## Steps

1. **Parse and check.** Arguments: portfolio name, amount (accept `50k`, `50.000`, `50000`), optionally the tilt.
   Check the name against `uv run radar portfolios list --json` (real portfolios are the user's accounts; a
   virtual one is fine but say so). If the amount is below one ticket (`propose.min_ticket_dkk`), say that one
   ETF (ACWI UCITS) is the sensible answer and stop unless the user insists.

2. **The rule study.** Read `reports/propose-study.json`. If it is missing or `candidates`' `study.stale` is true,
   run `uv run radar study propose` (slow: several minutes; run it in the background and continue with step 3
   meanwhile). Without it, the drift is n/a and the verdict will be A0: say why.

3. **Ask once** (one AskUserQuestion call), only for what the arguments and `notes/investor.md` don't settle:
   - **Tilt**: Momentum / Value (K+V) / Mix. In each option's description quote the rule study's evidence for that
     tilt at the default size and horizon: the mean excess with its t, the holdout's sign, and the figure for
     today's regime when it has enough dates (e.g. "momentum: +3 % per 6 months, t 1.4, holdout positive; weaker
     in Risk-off"). Don't recommend the tilt that looked best in the study: that is snooping; the user chooses.
   - **Mode**: conviction (best scores) or fill-gaps (prefer sectors the portfolio is underweight vs ACWI).
   - **Horizon**: 3 or 6 months (default from `investor.md`, else 6).
   - **Number of names**: default amount ÷ min ticket (capped at `max_names`); mention that the frontier (A3)
     will show the trade-off.
   - **ETF filler** for leftover cash: yes / no.
   Skip the question entirely when the amount allows only one name and the tilt was given.

4. **Candidates.** `uv run radar propose candidates --portfolio <name> --amount <A> --tilt <t> --mode <m>
   [--n N] [--horizon H] [--max-position P] --json --out exports/proposals/<date>_<portfolio>-candidates.json`.
   `--max-position` from `investor.md` (a share: 0.10 = 10 %) when it gives one. Read the notes and the gates.

5. **Judgment, bounded.** Start from `draft_picks` (the rule basket). You may swap at most `propose.max_swaps`
   picks, each with a written `swap_reason`, and only for reasons the rule can't see:
   - an earnings report within two weeks (check the ticker's calendar via `uv run radar info <T>`), or news that
     breaks the thesis (search the web for the 2–3 names you have doubts about);
   - a conflict with a market view of conviction 4–5;
   - a sector or name the investor avoids (`investor.md`);
   - a one-month spike the rule's stretch penalty didn't catch.
   Replace from the shortlist only (a name that passed the gates). For every pick write `why` (one line: what the
   score says, what the role in the portfolio is) and add 1–2 checkable thesis items under `exit.thesis`: either
   `{"text": …, "metric": "score"|"qv"|"r3m"|"from_high", "op": "<"|">", "value": …}` or a text-only item
   (marked as a suggestion). Leave the standard exits (review level, signal, time stop) as they are.
   Write the file to the scratchpad or `exports/proposals/draft.json`, then **freeze it before seeing any model
   number**: `uv run radar propose freeze <file>` (prints the stored path). Never edit a frozen file.

6. **Evaluate.** `uv run radar propose evaluate <frozen file> [--tolerance T] --json` (`--tolerance` from
   `investor.md`'s drawdown tolerance, e.g. 0.25). The full result is saved next to the frozen file as
   `<name>-evaluation.json` (`review` and `check` read its drawdown band); read it from there. If a constraint fails, make one repair pass (swap the offending name for the next one
   in the shortlist that fits), freeze the repaired file, evaluate again, and say so in the memo. Never re-pick to
   improve the modelled return or drawdown: that is curve-fitting to our own model.

7. **Red team.** Launch a general-purpose subagent with the evaluation JSON and the picks' `why`: "Argue the
   strongest case against this basket and for the best alternative in `alternatives` (usually A0, ACWI). Use only
   the numbers given plus at most three web searches. List the three facts that would most change the verdict."
   Put its answer, condensed, in the memo, with your response to each point.

8. **Write the memo** (template below), then reply with the summary table, the alternatives table and the link.

9. **Offer next steps** (don't do them unasked):
   - `uv run radar propose shadow <frozen file> --name "<portfolio> proposal <date>"`: virtual copies of the
     portfolio with the proposal, with ACWI and with the rule-only basket, so the Returns page tracks all three.
   - `/journal` for each real buy: pass the pick's `why` as the thesis and its exit criteria (review level, signal
     exit, thesis items, time stop) as the exit rules, and the account.

### `review`
`/propose-portfolio review`: run `uv run radar propose review --json` and `uv run radar propose check --json`.
Write `research/proposals/reviews/YYYY-MM.md`:
- per proposal: realised return vs ACWI and vs its rule basket (judgment's value), drawdown vs the modelled band,
  the trend exit vs keeping (did it cut losses or whipsaw);
- per open pick: Intact / Weakening / Triggered with the evidence; flag `older_rule` (criteria set under other
  settings: re-evaluate at the next review date, never move a review level down to avoid a trigger);
- what is due: time stops passed → re-run the scoring and keep a name only if it would be picked again today; cash
  freed by exits is a natural input to the next proposal (the redeploy study in `reports/redeploy-study.json`
  backs parking in ACWI vs re-picking).
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
- Excess over ACWI after costs: <drift_net> (from the rule study: <basis>, n <n_used>, eff. N <…>, t <…>, holdout
  <…>; survivorship haircut <…>; gross <drift_gross_raw>). Band (bootstrap) <p10> to <p90>; P(beat ACWI) <…>.
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
Basket level: review the model if the drawdown passes <bad_case>. `radar propose check` re-evaluates these.

## Red team
<the strongest case against, and the response>

## Account
<ASK: 17 % lager, positive list for the filler, deposit-cap check; frie midler: realisation taxation, so turnover
costs tax too; an after-tax illustration of the modelled median>

## Decision record
- Decision: <the user's, or "pending">  - Picks file: <frozen path> (sha <picks_sha>)  - Review on: <time stop>
```

## Ground rules
- Missing is n/a; never fill in a number the JSON doesn't have.
- The drift comes only from the rule study. The bootstrap and stress windows describe risk, not a forecast;
  ACWI's drift in the bootstrap is an assumption (`propose.acwi_drift_annual`): say so.
- Freeze before evaluating; at most `max_swaps` swaps, each with a reason; one repair pass for a failed constraint.
- Say plainly when the verdict is A0, and don't argue the user out of it.
- Never present a simulated or shadow portfolio as the user's; never write trades into a real portfolio (that is
  `/journal`, on the user's word).
