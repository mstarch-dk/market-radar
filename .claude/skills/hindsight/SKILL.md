---
name: hindsight
description: Build a basket of stocks as it could have been picked on a past day (1M, 3M, 6M or 1Y ago) from what the radar knew then (by momentum score alone, the score plus the user's market views, or the score plus Claude's judgment), simulate it kept and with the stop/take-profit rule against ACWI, a score-only control, the equal-weight universe and random baskets, and write a memo that puts it next to the rolling score study. Use when the user asks what a momentum or AI-picked portfolio would have done, wants to test the score on past data, or runs /hindsight.
argument-hint: "[1M|3M|6M|1Y …]"
---

# Hindsight baskets

Read `notes/investor.md` first if it exists: the user's accounts, horizon and preferences.

Output goes to `research/hindsight/YYYY-MM-DD_<name>.md`, one memo per basket. Reply with the results table and the
links. This is a simulation for inspiration and for judging the score, not advice. **One basket over one period
is an illustration; the evidence is the rolling study (`radar study score`).** Say so in every memo.

## Hindsight: the rule that matters most
You know what happened in markets up to your training cutoff. A basket you pick for a day **before** that cutoff can
be steered by memory of which names went on to rally, even without meaning to. So:
- Work out your knowledge cutoff as `YYYY-MM` and pass it as `--model-cutoff` every time. The output's
  `after_cutoff` says whether the day is clean.
- **Judgment basis on a day before your cutoff:** always use `--blind` (tickers and names hidden behind C001…),
  never try to work out which company an id is, and say in the memo that recognition from sector and figures can't
  be ruled out. Suggest a day after your cutoff (usually 1M or 3M) as the clean test.
- Pick only from the candidates file. No web searches, no `radar info`, no prices after the day, no news, before
  the picks are frozen.
- **Freeze the picks** in their file before running anything that shows a result. Never change them after a run;
  a new idea is a new basket with a new name.

## Steps

1. **Ask once** with a single AskUserQuestion call (the user's arguments preselect the lookbacks):
   - **Lookback** (multi-select): 1M, 3M, 6M, 1Y back from the latest prices.
   - **Basis:**
     - *Score only*: mechanical, the score's own top N. The clean test.
     - *Score + your views*: your market views created by that day tilt the choice.
     - *Score + Claude's judgment*: Claude chooses from the candidates (blind before your cutoff).
   - **Number of stocks:** 5, 10, 15 (default) or 20.
   - **Diversification and weighting:** "max 3 per sector, equal" (default); "max 3 per sector and 6 per
     region, equal"; "no caps, equal"; "max 3 per sector, weighted by score".

   Capital is 100.000 DKK unless the user says otherwise. Name each basket
   `hs-<lookback>-<basis>-<today>`, e.g. `hs-6m-judgment-2026-10-15`.

2. **Candidates** per lookback:
   ```
   uv run radar sim picks-candidates --asof <1M|3M|6M|1Y> --model-cutoff <YYYY-MM> [--blind] [--views] --json --out exports/picks/<name>-candidates.json
   ```
   - Read `asof` (the day D) and `fill` (the buy session) from the file. **Use that date, not the lookback, from
     here on**, so a later run doesn't drift with new prices.
   - Values are fractions; `null` is missing. Sectors are today's (the file says so).
   - `dkk: false` names can't be bought in a simulation (no DKK rate): leave them out.

3. **Pick** (skip for *Score only*):
   - *Score + your views* (`--views`):
     - Start from the top 60 by score.
     - Prefer names whose `views.label` is aligned. Leave out names that conflict with a view of conviction 4–5.
     - Otherwise go by score, within the caps.
     - List each view used, with its `created` date. Flag `edited_after: true`: its text may not be what you
       believed on D.
   - *Score + Claude's judgment*: from the top 60–80 by score, judge from the figures only:
     - momentum persistence (12-1 against 3m)
     - trend
     - volatility
     - extension (`from_high`)
     - sector concentration

     One line of reasoning per pick, citing the fields.

   Write `exports/picks/<name>.json`:
   ```json
   {"meta": {"basis": "judgment", "n": 15, "max_per_sector": 3, "max_per_group": null, "weighting": "equal",
             "lookback": "6M", "blind": true},
    "picks": [{"id": "C004", "why": "12-1 +85%, 3m +20%, in trend, vol 38%"}]}
   ```
   Use `ticker` instead of `id` when not blind. Leave weights out for equal weights. The caps in `meta` also shape
   the score-only control.

4. **Run** each basket:
   - *Score only*:
     ```
     uv run radar sim picks --asof <D> --rule top-n --n <N> [--max-per-sector 3] [--max-per-group 6] [--weighting score] --name <name> --model-cutoff <YYYY-MM> --json
     ```
   - Otherwise:
     ```
     uv run radar sim picks --asof <D> --picks exports/picks/<name>.json --name <name> --model-cutoff <YYYY-MM> --json
     ```

   The report is also in `reports/sim-picks/<slug>.json`. It holds:
   - `portfolios`: hold / exits / control, each with `return_dkk` (every fee included) and `excess_dkk` against
     ACWI
   - `yardsticks`: ACWI, the equal-weight universe, and `random` (the percentile among random baskets of the same
     size and caps)
   - `score_check` for that day
   - `picks` with each one's return and contribution
   - `exits` (`summary`, and each exit with `saved_dkk`)
   - `returns_link`

5. **The study.**
   - If `reports/score-study.json` is under 35 days old, read it.
   - Otherwise run `uv run radar study score --no-regime` (a few minutes) and read the file.
   - Take, for 3 and 6 months: the score's `ic_mean` with `ic_t`, `ic_pos`, `spread` with `spread_t`,
     `top_excess`, `top_dkk` against `acwi_dkk`, and the holdout IC.
   - Add any variant whose verdict is a candidate improvement.

6. **Write the memo** (template below) for each basket. If there are several lookbacks, add one short comparison
   table at the end of the last memo.

7. **Reply** with a table: basket, D, return (DKK), vs ACWI, vs the equal-weight universe, the control, random
   percentile. Give the links to the memos and the Returns page. End with one line on what the study says about
   the score.

## Template

```markdown
# Hindsight basket: <name>
*Picked on <D> (bought <fill>) to <end>, <sessions> sessions. Basis: <basis>. Simulation, not advice.*

> One basket over one period is an illustration, not evidence. <If the day is before the picker's knowledge cutoff:
> "Picked before Claude's knowledge cutoff (<YYYY-MM>): hindsight can't be ruled out, even blind.">

## Setup
The questions and answers, capital, fee per trade, the caps, blind or not, views used (with created dates and any
edited after D).

## Picks
| Pick | Weight | Score (rank) on D | Sector | Why (as of D) | Return DKK | Contribution |

## Results
| | Return DKK | vs ACWI | Max drawdown |
|---|---|---|---|
| Kept | | | |
| With the stop/take-profit rule | | | |
| Score-only control | | | |
| Equal-weight universe | | | n/a |
| ACWI | | – | n/a |

How concentrated was it? Name the picks behind most of the gain or loss. A result carried by one or two names says
little about the method.

## Against chance
Percentile among <draws> random baskets of the same size and caps; their median and 10–90 % range.

## The exit rule
Stops and take-profits, each with what it saved or cost to the end (`saved_dkk`). Which half of the rule helped,
and whether the money parked in ACWI did better than holding on would have.

## The score on that day
IC, the quintiles' excess returns and the top-N hit rate over the same period, for every ranked stock.

## The score across every month
From the study: IC and t at 3 and 6 months, Q5−Q1, the holdout, the top N in DKK against ACWI, and any candidate
improvement. Is this basket typical of the score, or an outlier?

## What this does and doesn't show
- Survivorship: today's universe flatters momentum.
- One period, one market phase.
- Hindsight, for the judgment basis.
- Sectors are today's.
- Costs: fees are included; taxes aren't.

## Links
Returns page: <returns_link> · Report: reports/sim-picks/<slug>.json · Candidates: exports/picks/<name>-candidates.json
```

## Ground rules
- Every number comes from the radar's output. Write "n/a" for a `null`, never 0, never an estimate.
- Keep facts (the simulation) apart from interpretation, and label the interpretation.
- Never present a basket as something to buy now. If the user wants to act on an idea, offer `/research` or
  `/compare` on the names, which look at them as of today.
- Simulated portfolios are virtual. Never move them into a real portfolio.
