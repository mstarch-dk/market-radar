# F2 Evidence page: implementation plan

*Written 2026-10-25, from [the product owner review](analyses/product_owner.md) (feature F2), against
`main` at `eca4df8` (0.2.0 plus the X-ray). Analysis, not advice.*

## 1. Goal and non-goals

**Goal.** The radar's honest testing of its own scores, visible in the app: for each score the latest study's
numbers with their t-statistics, the long-run study next to it, and the forward record that no backtest can fake,
each with its age and the rule it tested. Read-only over the study reports; the app never runs or imports a study.

User stories (MVP):

1. I open *Evidence* and see, for each score (momentum, quality, value, K+V), the latest study's IC with t, the
   quintile spread, the top N vs the universe and vs ACWI, the holdout vs in-sample, and the verdict on each variant.
2. I see the long-run study (decades, recession splits, the survivorship gauge, the factors' base rates) next to the
   recent one.
3. I see the forward evidence as one out-of-sample scoreboard: the A/B test, the `picks-live` paper trail and the
   frozen proposals, each against ACWI over the same days.
4. I see each report's age, rule hash and whether it is stale. A missing report says "not run yet" and gives the
   command; a report of another rule is greyed with "older rule" and never mixed with current numbers.
5. The same data from the CLI: `uv run radar evidence [--json]` (decided in section 9).

**Non-goals for this plan** (the review's *Later*, as backlog tasks TASK-2.8 to 2.10):

- Running a study from the UI as an ops job (TASK-2.8). The card shows the command instead.
- The rolling 36-month IC chart (TASK-2.9).
- Links from the score column headers to their card (TASK-2.10).
- The `picks-live` baskets' percentile among random baskets and the equal-weight universe: those sit in
  `reports/sim-picks/<name>.json`, a backtest output without a contract. The scoreboard reads the portfolios
  instead (section 4.3); giving `sim-picks` a contract is a later step.
- New studies or new statistics beyond the two t-statistics in section 4.2.
- A section in `dashboard.json` or `summary.json`: the page is assembled per request from the reports and the
  portfolios, like `/api/xray`.

## 2. Licence check

No new data source. The page reads reports built from sources already in `DATA_LICENSE.md` (Yahoo prices, SEC
EDGAR, Kenneth R. French, JKP). Only the *Used for* column changes: add "Evidence page" to the French and JKP rows
(and to SEC EDGAR for the quality/value cards), in `DATA_LICENSE.md` and `guide/brugervejledning/datalicenser.md`.

## 3. What the code does today (findings that shape the design)

| # | Finding | Where | Consequence |
|---|---|---|---|
| C1 | `ARTIFACTS` has one `score-study` entry. The fund signals write the same contract (kind `score-study`) under another name via `artifacts.write(..., file=SIGNALS[signal].report)`, but `load` only reads `spec.file`, so `score-study-quality/value/qv.json` can't be loaded at all | `model/artifacts.py`, `backtest/study.py` `SIGNALS` | `load` takes `file=` like `write`; the signal → file map moves down to `model/artifacts.py` (`SCORE_SIGNALS`) and `study.py` reads it from there. New `ARTIFACTS` keys would fail the kind check, so that route is out. |
| C2 | Only the proposal study stamps a `rule_hash`. Score, long-run, exit and redeploy studies write `None` | writers in `backtest/` | "Older rule" needs a fingerprint: a study rule hash for the score and long-run studies (4.1). Exit and redeploy studies get age only (they test the stop rule, which is shown elsewhere). |
| C3 | `load(rule_hash=h)` marks a report whose hash is `None` as stale with "tested another rule (settings None, …)" | `artifacts.load` | Every existing score report would read as stale once a hash is asked for. That is the honest outcome (we don't know its rule), but the reason must say "written before rules were recorded: run again". |
| C4 | The score reports hold `in_sample`, `top_excess_t`, `monotone` and `n_mean` per split, and the long-run report holds `top_vs_market_t` and each panel's `variants` with a `baseline` flag, but the models don't type them (kept as extras) | `model/stats.summarize`, `backtest/longrun.py` | Type them (consumed fields). |
| C5 | No t-statistic exists for the top N in DKK vs ACWI (`top_dkk`, `acwi_dkk` are separate means) | `model/stats.summarize` | Add `top_vs_acwi` and `top_vs_acwi_t` (Newey-West, the same lag) in `model/stats.summarize`. Older reports show "t not in this report". |
| C6 | The per-date IC rows are already kept: `dates[].horizons[h].ic[variant]` | `backtest/study.py` | TASK-2.9 needs no writer change, only the model field and the chart. Its description is corrected. |
| C7 | `picks-live` baskets are virtual portfolios (`origin: sim`, strategy `picks-hold`, tag `picks-live`); the strategy names and `baskets()` live in `backtest/picks.py`, which the app must not import | `backtest/picks.py` `STRATEGIES`, `baskets` | Move `STRATEGIES` and `baskets()` down to `portfolios/simulate.py` (domain), callers updated, no behaviour change. |
| C8 | `abtest.summary` gives per basket TWR, ACWI over the same flows, excess, max drawdown and start; `propose.store.review` gives per frozen proposal return, ACWI over the same days, excess, `count`, `enough` (vs `propose.review_min`) and a summary | `abtest.py`, `propose/store.py` | The scoreboard reuses both as they are. |
| C9 | The app contract lists `updater, reporting, api, abtest, propose, xray` as never importing `backtest` | `pyproject.toml` | `evidence` joins that list and the features layer. |

## 4. Design

### 4.1 Modules, by layer

| Layer | Module | Change |
|---|---|---|
| kernel | `model/artifacts.py` | `SCORE_SIGNALS` (`momentum`, `quality`, `value`, `qv` → label, file); `load(name, *, rule_hash=None, file=None)` with the cache keyed by file; `study_rule_hash(kind, signal=None)`; the clearer reason for a report without a hash (C3); typed fields (C4, C5, `LongrunPanel.variants`); `SCHEMA_VERSION` 2. |
| kernel | `model/stats.py` | `summarize` adds `top_vs_acwi` and `top_vs_acwi_t` (C5). |
| domain | `portfolios/simulate.py` | `PICKS_STRATEGIES` and `picks_baskets(tag)` moved from `backtest/picks.py` (C7). |
| features | `backtest/study.py`, `backtest/longrun.py` | Read the report file from `SCORE_SIGNALS`; stamp `study_rule_hash`. |
| features | `evidence.py` (new top-level module) | Assembles the page: one card per score study and the long-run study, header rows for the rule studies (propose, exits, redeploy), the forward scoreboard, notes. No math of its own; never imports `backtest/`. |
| features | `api_models/evidence.py` | `EvidenceView` and its parts (`extra="forbid"`), re-exported by `api_models`. |
| interfaces | `api/evidence.py` | `GET /api/evidence`, a router included **last** in `api/app.py`. |
| interfaces | `cli/study.py` | `radar evidence [--json]`. |
| web | `web/src/pages/Evidence.tsx` | New page `/evidence` in the *Markets* group after *Quality & value*. |

**The study rule hash.** `study_rule_hash(kind, signal)` is a SHA-256 (12 hex) of the raw settings the study's
numbers depend on, plus a hand-bumped revision per score, so a change to a score's code also retires the old
report:

| Report | Settings hashed | Revision |
|---|---|---|
| `score-study` (momentum) | `backtest.study_holdout_from`, `study_min_names`, `fee_bps`, `fill` | `SCORE_REVISION["momentum"]` |
| `score-study` (quality, value, qv) | the above, `backtest.fundamentals_lag_days`, `fundamentals.quality`, `fundamentals.value` | `SCORE_REVISION[signal]` |
| `longrun-study` | the whole `longrun:` section (it is pre-registered) | `SCORE_REVISION["momentum"]` |
| `propose-study` | `propose.rule_hash()` as today | – |

Taken of `config.settings()` (the raw values, as `propose.rule_hash` is) so a stored hash doesn't move when the model
writes 10 as 10.0. A test fails when a key in the table disappears from `settings.yaml`. The revision is bumped in
the same PR as a change to the score's code (`signals/momentum.py` percentile rule, `signals/fundamentals.py`); the
architecture doc says so.

### 4.2 Report readers (consumed fields)

Added to the models, all optional with `None` defaults so schema-1 and schema-0 reports still load:

- `ScoreSummary`: `top_excess_t`, `monotone`, `n_mean`, `top_vs_acwi`, `top_vs_acwi_t`.
- `ScoreVariant`: `in_sample`.
- `ScoreStudy`: `signal_label`; `VariantInfo.label`, `VariantInfo.note`.
- `LongrunSummary`: `top_vs_market_t`. `LongrunPanel.variants: list[VariantInfo]`.

`SCHEMA_VERSION` goes to 2 because consumed fields changed (architecture rule): a schema-2 report is invalid to an
older Market Radar, as intended.

### 4.3 Method (`evidence.py`)

**Status per report.** `artifacts.load(name, file=…, rule_hash=study_rule_hash(…))`:

| Status | Card shows |
|---|---|
| `missing` | "Not run yet" and the command (`radar study score --signal quality` etc.) |
| `invalid` | The reason and the command; no numbers |
| `stale` | Greyed, labelled "older rule" with the report's hash and today's; numbers shown only inside the greyed card, never in the summary row or next to a current card's numbers |
| `ok` | The numbers; an "old data" badge when `data_asof` is older than `evidence.max_age_days` (the rule is the same, so the numbers are current for that rule, but the market has moved on) |

**Score card** (per signal; baseline variant):

- Header: created, `data_asof`, rule hash, universe (tickers, first and last formation date, dates), US only for the
  fund signals, `variants_tried`.
- Per horizon: IC mean with t and share of positive dates; quintile means Q1–Q5 with `monotone`; spread with t; top
  N excess over the universe with t; top N in DKK vs ACWI with t and the share of dates it beat ACWI.
- In-sample vs holdout: the same rows for both parts, with the holdout start quoted from `backtest.study_holdout_from`
  *and* the report's own `settings.holdout_from`. They agree by construction (the holdout date is in the rule hash);
  if they don't, the card is stale.
- Verdicts: one row per variant and horizon (label, in-sample IC, holdout IC, holdout IC t, holdout difference t),
  with the multiple-testing note "N variants tried".
- Turnover of the top quintile; for the fund signals the rank correlation with momentum; caveats.

Every mean carries its t from the report. A mean the report has no t for (an older report) shows "t: not in this
report", never a blank that reads as fine.

**Long-run card.** Per panel (`french49`, `countries`): members, months, first and last; per horizon the baseline's
all and holdout rows (IC, spread, top excess, top vs market, each with t); by decade; by recession; the verdicts;
then the survivorship gauge (implied vs configured haircut, window) and the factors' base rates (annual return with
t, last 10 years, share of negative 6- and 12-month windows, max drawdown). Panel `errors` are shown as notes.

**Rule studies** (propose, exits, redeploy): one header row each (status, created, `data_asof`, rule hash where
there is one, the command). Their numbers stay on the pages that act on them (proposals, the stop rule).

**Forward scoreboard.** Three groups, each record against ACWI over the same days:

| Group | Source | Record | "Too short" when |
|---|---|---|---|
| A/B test | `abtest.summary(market)` | each basket's TWR, ACWI with the same flows, excess, max drawdown, since `start` | fewer than `evidence.forward_min_months` since the first purchase |
| Paper trail | `portfolios.simulate.picks_baskets("picks-live")` and `performance.compare(market, ids=[…])` | each monthly hold basket's return, ACWI, excess, age | a basket younger than `evidence.cohort_age_months`; the cohort's mean only from `evidence.cohort_min` such baskets |
| Frozen proposals | `propose.store.review(market)` | each proposal's return, ACWI, excess, judgment vs rule | the cohort's mean only when `enough` (`propose.review_min`) |

A record below its minimum is listed with its numbers and the label "too short", outside any ranking or mean. A
cohort mean is shown with its count and the share that beat ACWI, and no t: the windows overlap and the count is
small, so a t would overstate the evidence; the page says so (decided in section 9). Missing values are `None` with
a note, never 0.

### 4.4 Settings

```yaml
evidence:                  # src/radar/evidence.py: the Evidence page (read-only over the study reports)
  max_age_days: {score: 62, longrun: 120, rules: 120}   # data older than this: an "old data" badge (same rule)
  forward_min_months: 12   # a forward line younger than this is "too short", never ranked
  cohort_age_months: 3     # a paper-trail basket counts towards the cohort's mean from this age
  cohort_min: 6            # the paper trail's mean is shown from this many such baskets
```

In `settings.yaml` and `config_schema.py` (`Evidence`). None of these is in a rule hash.

### 4.5 API

`GET /api/evidence` → `EvidenceView`:

```text
EvidenceView
  generated, holdout_from (backtest.study_holdout_from), longrun_holdout_from (longrun.holdout_from)
  scores: [ScoreCard]              # momentum, quality, value, qv, always all four
  longrun: LongrunCard
  rules: [ReportHead]              # propose-study, exit-study, redeploy-study
  forward: {abtest: ForwardGroup, paper_trail: ForwardGroup, proposals: ForwardGroup}
  notes: [str]

ReportHead   {name, signal | null, label, status, reason | null, command, created | null, data_asof | null,
              age_days | null, old_data: bool, rule_hash | null, rule_hash_now | null, legacy: bool}
ScoreCard    {head: ReportHead, universe | null, us_only: bool, variants_tried | null,
              horizons: [{h, all, in_sample, holdout}]          # each a ScoreRow | null (baseline)
              verdicts: [{h, variant, label, in_sample_ic, holdout_ic, holdout_ic_t, holdout_diff_t}],
              turnover | null, momentum_corr | null, caveats}    # every number field null when status != ok/stale
ScoreRow     {dates, ic_mean, ic_t, ic_pos, q: [5], monotone, spread, spread_t, top_excess, top_excess_t,
              top_dkk, acwi_dkk, top_vs_acwi, top_vs_acwi_t, top_beats_acwi}
LongrunCard  {head, panels: [{key, label, members, months, first, last, horizons: [{h, all, holdout}],
              by_decade: [{h, decade, row}], by_recession: [...], verdicts: [...], error | null}],
              survivorship | null, base_rates: [{label, ann_return, t, last_10y_ann, share_neg_6m, share_neg_12m,
              max_dd}], caveats}
ForwardGroup {records: [{label, start, days, ret, acwi, excess, max_dd | null, too_short: bool}],
              cohort: {count, mean_excess | null, beat_acwi | null, enough: bool, note | null} | null,
              running: bool, note | null}
```

- No 503 when the reports are missing: a valid view with every card `missing`. 503 only when the forward
  scoreboard needs prices and there are none; then the study cards still come back, with the scoreboard `null` and
  a note (the study cards don't need prices).
- Cached per (each report's mtime, prices mtime, transactions version), the `performance._cached` pattern.
- Then `pnpm -C web gen:api`; `client.ts` gets `evidence()`.

### 4.6 CLI

`uv run radar evidence [--json]` in `cli/study.py`: one line per report (status, age, rule, command when missing or
stale), the baseline's 6-month IC with t and holdout IC with t per score, and the scoreboard's records; `--json`
prints the `EvidenceView`. It is the input `/market-brief` can read for "the score's paper trail" instead of running
`radar performance --tag picks-live` and parsing it (the skill change is optional, in the release PR).

### 4.7 Web page

`/evidence`, label *Evidence*, blurb "How well the scores have worked: studies, holdout, forward record", in
*Markets* after *Quality & value*. Layout:

1. **Status strip**: one chip per report (score × 4, long-run, propose, exits, redeploy) coloured by status, with
   age; a click scrolls to the card.
2. **Score cards** (tabs `?tab=` momentum | quality | value | qv): the IC bar per horizon with t printed on the bar,
   quintile bars, the in-sample vs holdout table with the holdout start, the verdict table (`DataTable`),
   caveats. Missing: "Not run yet" with the command in a copyable code block. Stale: the whole card greyed with an
   "older rule" badge and both hashes.
3. **Long-run card**: panel tabs, a decade bar chart of the IC with t, the recession split, the survivorship gauge,
   the base-rate table.
4. **Forward scoreboard**: three tables (`DataTable`), "too short" rows muted and unranked, the cohort line under
   each.
5. **Notes** and the link to the guide (`page_links`).

Terms (IC, Newey-West t, holdout, quintile spread, survivorship haircut, overlapping windows) get `Term` tooltips via
`lib/glossary.ts` with `glossary_links` to the textbook. Charts are plain SVG bars (no time axis, so not
`LineChart`).

## 5. Steps as PRs

Each PR is green on `uv run pytest -q`, `uv run ruff check`, `uv run mypy`, `uv run lint-imports` (and
`pnpm -C web test` from step 3 on), and carries its guide changes.

| # | Task | PR | Contents | Behaviour change |
|---|---|---|---|---|
| 1 | TASK-2.2 | **Report readers** | `SCORE_SIGNALS`, `load(file=)`, `study_rule_hash` stamped by the score and long-run writers, the clearer reason for an unrecorded rule, the typed fields (4.2), `top_vs_acwi(_t)` in `stats.summarize`, `SCHEMA_VERSION` 2; `cli/study.py` prints the new t; `docs/architecture.md` *Study reports* (the hash and the revision). | Study reports gain `rule_hash` and two fields; old reports load. |
| 2 | TASK-2.3 | **`evidence.py`** | `picks` strategies moved to `portfolios/simulate.py`; `evidence.py`; `evidence:` settings and schema; `pyproject.toml` (features layer, the app contract); `docs/architecture.md` (Features). | None visible (new module). |
| 3 | TASK-2.4 | **API and CLI** | `api_models/evidence.py`, `api/evidence.py`, `radar evidence`, types regenerated, `client.ts`; `docs/web-app.md`, `docs/commands.md`, `CLAUDE.md` main commands. | New endpoint and command. |
| 4 | TASK-2.5 | **Web page** | `Evidence.tsx`, nav, glossary entries. | New page. |
| 5 | TASK-2.6 | **Guide** | `brugervejledning/scoretest.md` section *Evidens-siden*, `laerebog/test-af-scoren.md` link, `navigation.md`, `indstillinger.md` (`evidence:`), `guide.yaml` `page_links`; `DATA_LICENSE.md` and `datalicenser.md` *Used for*. | – |
| 6 | TASK-2.7 | **Release** | `CHANGELOG.md` and *Nyheder* (incl. "run each study once more: reports from before 0.3 show as older rule"), marketing `features.yaml`, screenshot check in the demo copy; optionally `/market-brief` reads `radar evidence --json`. | – |

Steps 4 and 5 can be one PR if small. Each step needs the one before.

## 6. Tests

| Test | File | Checks |
|---|---|---|
| `test_load_score_signal_files` | `tests/test_artifacts.py` | Each of the four score files loads through `load("score-study", file=…)`; the cache keeps them apart. |
| `test_study_rule_hash_moves_with_its_keys` | `tests/test_artifacts.py` | Changing `backtest.study_holdout_from` changes the score hash, not the long-run hash; changing `fundamentals.quality` changes the fund hashes only; a revision bump changes it. |
| `test_rule_keys_exist` | `tests/test_artifacts.py` | Every settings path in the hash table exists in `settings.yaml`. |
| `test_unrecorded_rule_is_stale_with_reason` | `tests/test_artifacts.py` | A schema-1 report without a hash, asked with a hash: `stale`, reason says "before rules were recorded". |
| `test_older_reports_still_load` | `tests/test_artifacts.py` | Schema-0 and schema-1 fixtures of each kind load; the new fields are `None`. |
| `test_top_vs_acwi_t` | `tests/test_backtest_study.py` | Hand-computed rows: mean and Newey-West t of `top_dkk − acwi_dkk`, dates without either left out. |
| `test_picks_baskets_moved` | `tests/test_backtest_picks.py` | `simulate.picks_baskets("picks-live")` returns what `picks.baskets` returned. |
| `test_evidence_missing_reports` | `tests/test_evidence.py` | No reports: four score cards and the long-run card `missing`, each with its command; numbers `None`. |
| `test_evidence_stale_not_mixed` | `tests/test_evidence.py` | A stale momentum report next to an ok quality report: the stale card has `stale` status and both hashes, and no stale number appears in any summary or `ok` field. |
| `test_evidence_t_next_to_every_mean` | `tests/test_evidence.py` | For every `ScoreRow` and long-run row: each mean field has its `_t` field present (value or `None` with the "not in this report" note). |
| `test_evidence_holdout_from_settings` | `tests/test_evidence.py` | `holdout_from` equals `backtest.study_holdout_from` under `with_settings`. |
| `test_forward_too_short_not_ranked` | `tests/test_evidence.py` | A/B basket younger than `forward_min_months`, picks baskets younger than `cohort_age_months`: `too_short`, left out of the cohort mean; the cohort mean is `None` below `cohort_min`. |
| `test_forward_missing_is_none` | `tests/test_evidence.py` | A basket without prices since its day: `ret`, `excess` `None` with a note, never 0. |
| `test_evidence_api_contract` | `tests/test_api.py` | `GET /api/evidence` validates against `EvidenceView`; no reports and no portfolios returns 200. |
| `test_cli_evidence` | `tests/test_cli_smoke.py` | `radar evidence --json` runs on the test world and prints valid JSON. |
| layers | `tests/test_layers.py`, `lint-imports` | `evidence` in features and in the app contract; nothing reads `STRATEGIES` through `backtest.picks`. |
| web | `pnpm -C web test` | Nav includes `/evidence`; a formatter test for "t: not in this report" and for a stale card's class. |

Study fixtures for the evidence tests are written with the real writers on the synthetic world
(`study.run(..., horizons=(1,))`, kept small) where that is fast; otherwise hand-made JSON in the report's shape under
`tests/fixtures/reports/`, no real data.

## 7. Docs

- **User guide**: `brugervejledning/scoretest.md` gets a section on the page (what each card shows, how to read t and
  the holdout, *older rule* and *old data*, the scoreboard's *too short*), linked from the table at the top;
  `navigation.md` lists the page; `indstillinger.md` the `evidence:` keys. Thresholds quoted with
  `{{settings:evidence.forward_min_months}}`, `{{settings:backtest.study_holdout_from}}` etc.
- **Textbook**: `laerebog/test-af-scoren.md` links to the page from its *Sådan gør radaren* part, and gets one
  paragraph on why overlapping forward windows get no t.
- **Developer docs**: `docs/architecture.md` (*Study reports*: the study rule hash and revision; Features:
  `evidence.py`), `docs/web-app.md` (endpoint, page), `docs/commands.md` (`radar evidence`), `CLAUDE.md` main
  commands (one line).
- **Data licence**: *Used for* (section 2).
- **Release**: `CHANGELOG.md`, *Nyheder*; `uv run pytest -q tests/test_guide.py`.

## 8. Definition of done

The review's cross-cutting checklist ([section 3.3](analyses/product_owner.md#33-cross-cutting-definition-of-done-applies-to-every-feature)),
applied:

- [ ] The rule hash and the statistics in `model/`; the page in `evidence.py`, which never imports `backtest/`;
      `lint-imports` and `tests/test_layers.py` pass.
- [ ] A missing report is "not run yet" with its command, a stale one greyed and never mixed, a missing number
      `None` with a note; nothing is 0 by default.
- [ ] No new files written (reports are read, the view is cached in memory): nothing to add to `paths.REGISTRY`
      (the score files are already under `score-study-*.json`).
- [ ] No new `userstore` table.
- [ ] `evidence:` settings in `settings.yaml` and `config_schema.py`; quoted with `{{settings:…}}` in the guide.
- [ ] `EvidenceView` strict; TypeScript types regenerated; `pnpm -C web build` passes.
- [ ] `DATA_LICENSE.md` and `datalicenser.md` *Used for* updated.
- [ ] Guide and textbook per section 7; `tests/test_guide.py` passes.
- [ ] `summary.json` unchanged (a skill reads `radar evidence --json`).
- [ ] `uv run pytest -q`, `uv run ruff check`, `uv run mypy`, `pnpm -C web test` green.
- [ ] `CHANGELOG.md`, *Nyheder*, marketing `features.yaml`.
- [ ] Screenshot check in the demo copy (`/marketing` workspace, fictional investor), never the user's data folder.
- [ ] No personal data in commits or fixtures; the leak check passes.

## 9. Decisions taken here, and open questions

**Decided**:

- `radar evidence [--json]` is in scope (step 3): one call into `evidence.build`, and it gives `/market-brief` the
  paper trail and the study status in one read, without growing `summary.json`.
- Staleness is the rule, not the calendar: a different (or unrecorded) rule hash greys the card; an old `data_asof`
  only adds an "old data" badge, because the numbers are still that rule's.
- A report written before this plan has no rule hash and shows as *older rule* until the study is run again. That
  is truthful (we don't know what it tested); the release notes say to re-run each study once.
- The forward scoreboard shows cohort means without a t (overlapping windows, small counts), and says why. The
  acceptance criterion "t next to every mean" applies to the study cards, where every mean has one.
- The page lives in *Markets* (it is about the scores shown there), not *System*.
- Running a study from the UI stays a later task (TASK-2.8): minutes of CPU, and the review suggests an ops job
  refused while a report build holds the lock (`locks.py`); the card shows the command until then.

**Open**:

1. Should the exit and redeploy studies get a rule hash too (of `stops:` and the redeploy arms), so their header row
   can say *older rule*? Suggest: yes, but in the plan that next touches the stop rule, not here.
2. The `SCORE_REVISION` integers depend on a person remembering to bump them. A test could hash the source of the
   score functions instead, at the cost of a stale card after every refactor. Suggest: keep the hand-bumped
   revision, with the rule written in `docs/architecture.md` next to the score's code.
