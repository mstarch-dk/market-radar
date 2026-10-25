# Product owner review: features for the semi-professional investor

*Review date: 2026-10-25, against `main` at `cac5c6f` (0.2.0). Analysis, not advice.*

This document reviews Market Radar's current feature set from the point of view of a financial analyst acting as
product owner. It names the features that would make the product most appealing to its target user. Every feature
uses **free data sources only**. Each feature is written so it can become an implementation plan without further
discovery: problem, what already exists to build on, scope, method, data and licence, acceptance criteria, the docs
to update, and the open questions.

---

## 1. The target user

**The detail- and theory-oriented hobby investor.** This is not an institution or an industry professional. It is a
private investor who:

- manages their own money across a few account types (here: *frie midler*, *aktiesparekonto*, possibly pension),
  in DKK, against a global benchmark;
- reads the literature (Jegadeesh–Titman, Fama–French, Asness, Novy-Marx, Damodaran) and wants to see the method,
  the statistics and the caveats rather than a verdict;
- distrusts black boxes, backtests without holdouts and "signals" with no evidence behind them;
- has a few hours a week, not a Bloomberg terminal: it must work from free data on one laptop;
- cares about **net, after-tax, in-DKK** results, because that is what they actually keep.

The question they keep asking is: *"Am I actually doing better than just holding ACWI, after costs and tax, and is
that skill or luck?"* Their second question: *"What is my portfolio really exposed to right now?"*

## 2. Review of the current feature set

### 2.1 What exists (0.2.0)

| Area | Features | Assessment |
|---|---|---|
| **Market state** | Regime (voting model with switchable groups, stale sources don't vote), sector rotation (RRG, home-market sectors), themes and factors (UCITS alternative, positive list), positioning (FactSet revisions, OECD CLI, rates US/EA, CFTC COT, AAII, put/call, CAPE, ERP) | Strong and unusually transparent. Macro is mostly US. |
| **Stock selection** | Momentum score (pooled percentile rule), quality and value scores (EDGAR + Yahoo statements), K+V, Discover scan (Nordic/European/STOXX 600/positive-list ETFs), clusters, Δ rank, flags | Strong. The tracked universe is US-heavy (S&P 500 vs ~115 non-US names). Q+V is only point-in-time testable in the US. |
| **Ticker research** | Full profile (price, technicals, review/stop levels, risk vs ACWI in DKK, factor loadings, analysts, valuation, Q+V card, ETF look-through, peers), side-by-side compare with ACWI | Excellent. The best single page in the product. |
| **Portfolios** | Real and virtual portfolios, transactions as source of truth, average-cost method, cash ledger, broker import wizard, fee schedules, forks, tags, TWR/MWR vs ACWI with the same flows, gaps never zeros | Accounting is solid. **Analytics stop at returns**: there's no portfolio-level exposure, risk or attribution view. |
| **Evidence** | `study score` (IC, NW t, quintiles, holdout, variants, exits), `study longrun` (French 49, JKP countries), `study exits`, `study redeploy`, `study propose`, Q+V study, hindsight baskets, forward A/B test, `picks-live` paper trail | World-class for a hobby tool: point-in-time, pre-registered, holdouts, ACWI as the null. **Only visible on the CLI and through skills**: the web app has no page for it. |
| **Proposals** | Fee-aware basket proposals with caps after the addition, frozen picks before the model's numbers, ex-ante risk, bootstrap and stress drawdowns, alternatives A0–A6, shadow portfolios, exit-criteria check | Very strong. Its exposure and risk engine is the best piece of portfolio analytics in the codebase, but it runs only for a hypothetical basket. |
| **Workflow** | Market views with evidence, notebook (briefs, research, journal), Claude skills (brief, research, compare, journal, propose, hindsight), Danish guide + textbook | Distinctive. The textbook is a real selling point for this user. |
| **Operations** | Data folder, backups, export, doctor, ops log, coverage and blind spots, downgrade guard | Mature. |

### 2.2 Strengths to protect

1. **Research integrity**: point-in-time studies, holdouts, Newey-West t, pre-registration, ACWI as the null
   hypothesis. No free competitor (Portfolio Visualizer, Koyfin free, Stockopedia, Morningstar) does all of these.
2. **Truthfulness**: missing is missing, stale sources don't vote, blind spots are listed.
3. **Danish fit**: DKK returns, positive list, account kinds, average-cost method, Danish textbook.
4. **Explainability**: every reading has a guide chapter and a textbook chapter.

New features must keep all four. A feature that can't say how sure it is doesn't ship.

### 2.3 Gaps, as the target user would see them

| # | Gap | Evidence in the code |
|---|---|---|
| G1 | No live view of the real portfolio's exposures and risk (sector, region, currency, factor, concentration, look-through, ex-ante volatility and tracking error) | `propose/exposure.py` and `propose/riskmodel.py` compute exactly this, but only inside `propose evaluate` |
| G2 | No tax: returns are pre-tax, though the user's account mix (ASK lager at a flat rate vs realisation vs lager on positive-list ETFs) changes the ranking of strategies | `guide/laerebog/skat.md`: "Radaren beregner ingen skat" |
| G3 | No attribution: the user sees *that* they beat or lagged ACWI, not *why* (allocation, selection, currency, factors, timing) or whether it's significant | `portfolios/performance.py` stops at TWR/MWR/drawdown; `signals/risk.factor_loadings` exists per ticker only |
| G4 | The evidence is invisible in the app | No web page reads `score-study.json`, `longrun-study.json` etc. |
| G5 | No calendar or "what changed" feed: earnings dates exist in the data but aren't surfaced as events; exit criteria and stop hits need a visit to several pages | `earnings_date` in `api_models/common.py`; `propose check` is CLI only |
| G6 | Universe and fundamentals are US-centric while the benchmark is global (US ~64 % of ACWI) | `config/universe.yaml` stock groups; value/mix proposals "US stocks only" |
| G7 | Listed blind spots: insider transactions, short interest, fund flows | `coverage.blind_spots`, `guide/brugervejledning/data-og-daekning.md` |
| G8 | The user can't test their own idea (a screen, a composite score) with the study machinery without writing Python | `backtest/study.py` variants are code-defined |
| G9 | No rebalancing or cash-deployment help for the existing portfolio across accounts (only new baskets via proposals) | `propose candidates --mode fill-gaps` is closest |
| G10 | ETF choice (UCITS share class, TER, tracking difference, domicile, overlap) is left to the user | Positive-list flag and look-through exist; no tracking-difference measure |

## 3. Prioritisation

### 3.1 Scoring

Each candidate is scored 1–5 on:

- **Value**: how much the target user gains;
- **Differentiation**: how rare it is in free tools;
- **Leverage**: how much existing code it reuses;
- **Data safety**: free, stable and licensed for personal use;
- **Effort** (S ≈ 1 PR, M ≈ 2–4 PRs, L ≈ 5+ PRs).

| ID | Feature | Value | Diff. | Leverage | Data safety | Effort | Priority |
|---|---|---|---|---|---|---|---|
| F1 | Portfolio X-ray | 5 | 4 | 5 | 5 | M | **P1** |
| F2 | Evidence page | 4 | 5 | 5 | 5 | S–M | **P1** (quick win) |
| F3 | Danish tax engine and after-tax returns | 5 | 5 | 3 | 5 | L | **P1** |
| F4 | Attribution and decision analytics | 5 | 4 | 4 | 5 | M–L | **P1** |
| F5 | Change feed, calendar and local alerts | 4 | 3 | 4 | 4 | M | **P2** |
| F6 | Universe parity with ACWI | 4 | 3 | 4 | 4 | M | **P2** |
| F7 | European point-in-time fundamentals (ESEF) | 4 | 5 | 3 | 3 | L | **P2** |
| F8 | Insider transactions and short positions | 3 | 4 | 3 | 4 | M–L | **P2** |
| F9 | Research lab: your own screens and scores, tested honestly | 4 | 5 | 4 | 5 | L | **P3** |
| F10 | Rebalancing and cash-deployment planner (with asset location) | 4 | 4 | 4 | 5 | M | **P3** (needs F1, F3) |
| F11 | UCITS ETF toolkit | 3 | 4 | 3 | 4 | M | **P3** |

### 3.2 Dependencies and sequencing

```
F2 Evidence page ─────────────────────────────────────────────┐
F1 Portfolio X-ray ──┬──> F4 Attribution ──┐                  │
                     └──> F10 Rebalancing <┤                  ├──> F9 Research lab
F3 Tax engine ───────────> F10, F4 (after-tax attribution)    │
F6 Universe parity ──> F7 ESEF fundamentals ──> (Q+V tests outside US)
F5 Change feed <── F8 Insider/short (events), F1 (exposure breaches), F3 (tax deadlines)
F11 ETF toolkit ──> F10 (which share class to buy)
```

Suggested releases:

| Release | Theme | Features |
|---|---|---|
| 0.3 | "Know what you own" | F2, F1, F5 (core: change feed and calendar) |
| 0.4 | "What you keep, and why" | F3, F4 |
| 0.5 | "A global evidence base" | F6, F7, F8 |
| 0.6 | "Your own rules" | F9, F10, F11 |

### 3.3 Cross-cutting definition of done (applies to every feature)

Taken from `CLAUDE.md` and `docs/architecture.md`; each implementation plan should copy this list:

- [ ] Computation in the right layer: pure math in `signals/` or `model/`, I/O in `sources/`, features above;
      `uv run lint-imports` and `tests/test_layers.py` pass. Anything the app shows *and* a study tests lives once
      in `model/`.
- [ ] Missing data shows as missing (None/`null`, a note), never 0. A source that parses to nothing fails loudly
      and keeps its cache (`guard.py`).
- [ ] Every new file has a tier in `paths.REGISTRY` (personal / history / cache); history files are append-only.
- [ ] New stateful user data gets a `userstore/` table through an append-only migration.
- [ ] New settings go in `config/settings.yaml` *and* `config_schema.py`; thresholds quoted in the guide with
      `{{settings:…}}`.
- [ ] API responses have strict `api_models/` views; TypeScript types regenerated (`docs/web-app.md`).
- [ ] New data source: `DATA_LICENSE.md` + `guide/brugervejledning/datalicenser.md`, paced through `net.py`, logged
      in the source log, listed on *Data & coverage*; `coverage.blind_spots` updated when a blind spot closes.
- [ ] Guide: the user-guide chapter for the page and a textbook chapter for the method (follow `guide/STIL.md`);
      `uv run pytest -q tests/test_guide.py`.
- [ ] `summary.json` keys added for the skills if a skill should use the feature; the skills' docs updated.
- [ ] Tests with the synthetic world (`docs/testing.md`), `uv run pytest -q`, `uv run ruff check`, `uv run mypy`.
- [ ] `CHANGELOG.md` + *Nyheder*; marketing `features.yaml` when user-visible.
- [ ] No personal data in commits or fixtures; the leak check passes.

---

## 4. Feature specifications

Each spec uses the same headings so it can be converted straight into an implementation plan.

### F1. Portfolio X-ray: what the real portfolio is exposed to, right now

**Problem.** The user holds 15–40 positions across two or three accounts, some of them ETFs. They can't see their
combined active bets against ACWI: how overweight they are in US tech once the ETFs are looked through, how much of
their risk sits in one cluster of correlated names, or what their ex-ante tracking error is. That is the first thing
a semi-pro checks, and today it exists only for a *hypothetical* basket in `propose evaluate`.

**User stories.**
- As an investor, I see my sector, region, currency and factor weights against ACWI, with ETFs looked through, for
  one account or all of them.
- I see where my risk comes from: each position's contribution to total volatility and to tracking error.
- I see concentration as a number (effective N, top-5 share, the largest correlated cluster).
- I see how my current holdings would have done in past stress windows (2020 Covid, 2022 rates, 2008 where data
  allows), against ACWI.

**Builds on.**
- `propose/exposure.py` (`holdings_book`, `ticker_meta`, `exposures`, `look_through`): sector, region and currency
  vs ACWI weights from `sources/constituents.acwi_weights`.
- `propose/riskmodel.py` (`shrunk_cov`, `ex_ante_risk`, `stress`, `bootstrap`).
- `signals/risk.py` (`factor_loadings`, `correlation`), `profile.py` (ETF look-through).
- `portfolios/trades.py` (holdings per portfolio selection), `mine.py` (clusters, flags).

**Scope.**
- *MVP:* new page *X-ray* (or a tab on *Portfolio*) with a portfolio picker (`PortfolioPicker.tsx`); active-weight
  tables for sector, region and currency with look-through; ex-ante volatility, beta, tracking error vs ACWI (DKK,
  weekly, shrunk covariance); per-position risk contribution (MCTR and %CTR); effective N (1/Σw²) and top-5
  share; the stress replay table. `radar xray [--portfolio P] [--json]`.
- *Later:* factor exposure of the whole portfolio (the regression from `factor_loadings` on the portfolio's own
  return series, plus holdings-based factor tilts from momentum/Q+V percentiles); correlation-cluster view
  (hierarchical clustering of the correlation matrix); "what-if" by editing weights in the browser.

**Method.**
- Move the exposure and risk functions that both proposals and the X-ray need from `propose/` down into `model/`
  (or a new domain module), so the proposal shows exactly what the X-ray shows. This is the *proper fix*, not a
  copy.
- Risk contribution: with weights *w* and covariance Σ, σ_p = √(wᵀΣw), MCTR_i = (Σw)_i / σ_p,
  CTR_i = w_i · MCTR_i. Tracking error the same on active weights *w − w_b* (ACWI as one asset, so the active
  vector is the holdings minus a short ACWI position).
- Look-through only for ETFs with holdings data; others are shown as "not looked through" with their weight,
  never spread out by guess.
- Every number carries its window (weeks) and the shrinkage used. Positions with too little history are listed as
  excluded from the risk model, with their weight.

**Data.** No new sources (Yahoo prices, iShares/SSGA holdings already used).

**Acceptance criteria.**
- Exposures of a proposal shown by `propose evaluate` and by the X-ray for the same holdings are identical (one
  code path, tested).
- CTRs sum to 100 % of σ_p (within rounding); a test with a hand-computed 3-asset covariance.
- A portfolio with an ETF without holdings shows it as "not looked through", and the look-through totals say how
  much of the portfolio they cover.
- Missing prices for a position remove it from the risk model with a note; they never become 0 % return.

**Docs.** New user-guide chapter `brugervejledning/xray.md`; textbook: extend `diversifikation.md` (effective N,
risk contribution) and `beta-og-alfa.md` (tracking error, active share).

**Open questions.** Page or tab? Include virtual portfolios (useful for experiments: yes, by picker)? Active share
needs ACWI's constituent weights at stock level; iShares SSAC holdings give it, so add it in the MVP?

---

### F2. Evidence page: the studies in the app

**Problem.** The product's strongest asset, the honest testing of its own scores, is only visible on the command
line and inside skill memos. A theory-oriented user wants to *see* the IC over time, the quintile spread, the
holdout and the decade split before trusting the momentum column. Today they must know which command to run.

**User stories.**
- As an investor, I open *Evidence* and see, for each score (momentum, quality, value, K+V), the latest study's IC
  with t, quintile spread, top-N vs universe and ACWI, holdout vs in-sample, and the verdict on each variant.
- I see the long-run study (decades, recession splits, survivorship gauge) next to the recent one.
- I see the forward evidence: A/B test, `picks-live`, frozen proposals vs ACWI, as one "out-of-sample scoreboard".
- I see each report's age, rule hash and whether it's stale, and can start a re-run as an ops job.

**Builds on.** `model/artifacts.py` (typed readers with `ok`/`stale`/`missing`/`invalid`), the study JSON files in
`reports/`, `abtest.status`, `propose review`, `api/operations.py` jobs, `LineChart.tsx`, `DataTable.tsx`.

**Scope.**
- *MVP:* `GET /api/evidence` returning the parsed study headers and the summary blocks; page with one card per
  study (IC bar per horizon with t, quintile bars, holdout comparison, verdict table); a staleness badge; the forward
  scoreboard from existing data.
- *Later:* rolling 36-month IC chart (needs the per-date IC rows to be kept in the report, check the schema);
  "run study" buttons as ops jobs with progress; a link from each score column header to its evidence card.

**Method.** Read-only. Extend the `model/artifacts.py` models only for the fields the page shows, bumping
`schema_version` where a consumed field changes. The app still never imports `backtest/` (forbidden contract).

**Data.** None new.

**Acceptance criteria.** A missing study shows "not run yet" with the command to run it; a stale one is shown
greyed with "older rule", never mixed with current numbers; t-stats shown next to every mean; the holdout start is
quoted from settings.

**Docs.** `brugervejledning/scoretest.md` gets a section on the page; `test-af-scoren.md` links to it.

**Open questions.** Should running a study from the UI be allowed (minutes of CPU)? Suggest: yes, as an ops job,
refused while a report build runs (`locks.py`).

---

### F3. Danish tax engine and after-tax returns

**Problem.** For a Danish investor, tax is the single largest controllable cost and changes the ranking of
strategies. A high-turnover momentum strategy in *frie midler* (realisation, 27/42 % with progression) is a very
different proposition from the same strategy on an ASK (17 % lager, losses carried forward on the account), and a
positive-list ETF in *frie midler* is taxed on lager. The radar knows the account kind, the security type, the
positive-list status and every trade, so it has everything it needs, yet it shows only pre-tax returns.

**User stories.**
- As an investor, for each account and tax year I see realised gains and losses (average-cost method), dividends,
  lager gains on lager-taxed securities, the ASK's annual tax base with loss carry-forward, and an estimated tax.
- I see an after-tax TWR next to an *after-tax* ACWI twin (an ACWI UCITS ETF on the positive list, lager-taxed in
  the same account kind), so the comparison stays fair.
- Before year end, I see a planner: unrealised gains and losses per position, how much of this year's progression
  limit (*progressionsgrænse*) is used, candidate losses to realise, and the ASK's remaining deposit headroom.
- Virtual portfolios and simulations can be run after tax too, so an experiment's verdict includes tax drag.

**Builds on.** `portfolios/trades.py` (average-cost replay), `portfolios/performance.py` (books, flows, TWR),
`userstore` (portfolio `kind`: `ask|frie_midler|pension|other`), `sources/positive_list.py` (ISIN status per year),
`importers/` (dividend rows), `guide/laerebog/skat.md` (rules already written up).

**Scope.**
- *MVP:* `src/radar/tax/` (domain): a rules table per tax year in `config/tax_dk.yaml` (rates, progression limit,
  ASK rate and deposit cap, each with source and date, like `fee_presets.yaml`), classification per holding
  (stock / positive-list fund / non-positive-list fund / Danish distributing fund) with the year it was decided;
  per-account, per-year tax report; `radar tax year 2026 [--portfolio P] [--json]`; a *Tax* tab on *Portfolio*.
- *Later:* after-tax TWR and the after-tax ACWI twin on *Returns*; the year-end planner; after-tax mode for
  `sim`/`propose evaluate`/`study redeploy` (a `tax_model` argument, default off so studies stay comparable);
  foreign withholding-tax estimate on dividends (by domicile).

**Method.**
- Lager: value at year end minus value at year start (or cost if bought in the year); realised in-year sales use
  the sale price. ASK: one pool per account, negative years carried forward on that account.
- Realisation on stocks in *frie midler*: gain = proceeds − average cost × quantity sold, per security, across all
  *frie midler* accounts of the same person (SKAT's average method is per person, not per account). This is the
  hard rule to get right and must be a setting: which portfolios belong to one tax person.
- Loss pools: listed-share losses vs gains and dividends (simplified, with an explicit "not modelled" list: spouse
  transfer, unlisted shares, carried-forward losses from before the radar's data).
- Everything labelled "estimate". The rules file says which year each rule is verified for; a year without
  verified rules shows "no rules for 2027" rather than reusing 2026 silently.

**Data.** Rates and limits from skat.dk (public-sector information, typed in by hand with source and date). The
positive list is already a source.

**Acceptance criteria.**
- Golden tests: hand-worked examples for ASK lager with a loss year, *frie midler* average-cost realisation over
  partial sales, a positive-list ETF on lager with a mid-year purchase, and an ETF that leaves the positive list.
- An unclassifiable holding (no ISIN, no positive-list year) is shown as "unknown classification", excluded from
  the estimate with its value named, never assumed.
- Pre-tax numbers are unchanged by the feature (regression test on `performance.analyze`).

**Docs.** New user-guide chapter `brugervejledning/skat.md`; textbook `skat.md`: replace "Radaren beregner ingen
skat" with a *Sådan gør radaren* section. Strong disclaimer: not tax advice; the user's *årsopgørelse* wins.

**Open questions.** Pension accounts (PAL tax 15.3 % lager): include in the MVP (simple) or later? How to enter
losses carried forward from before the user's history (one manual opening-balance row per pool)? Spouse
progression-limit transfer: out of scope?

---

### F4. Attribution and decision analytics: why you beat or lagged ACWI, and whether it's skill

**Problem.** *Returns* says "+3.1 pp vs ACWI". The theory-oriented user wants to decompose that into allocation
vs selection vs currency, see their factor exposures over time, know whether the alpha is statistically
distinguishable from zero, and learn from their own behaviour (do they sell winners too early and ride losers?).
These diagnostics come straight out of the literature (Brinson–Fachler, Fama–French regressions, Odean's
disposition effect) and no free tool runs them on a Danish investor's own trades.

**User stories.**
- I see a Brinson–Fachler attribution vs ACWI by sector and by region for a chosen period: allocation, selection,
  interaction, plus a currency effect in DKK.
- I see a returns-based factor regression of my portfolio (market, size, value, profitability, investment,
  momentum; developed-market factors) with alpha, its Newey-West t and "months of data needed for this alpha to
  reach t = 2 at this volatility".
- I see a trade-level review: each closed position's return vs ACWI over the same days, what happened after I sold
  (1/3/6 months later), the proportion of gains realised vs losses realised (PGR − PLR), holding period of winners
  vs losers, turnover and the fee drag per year.
- I see my journal theses next to outcomes: hit rate by thesis type, and whether the exit rules I wrote were
  followed.

**Builds on.** `portfolios/performance.py` (daily books in DKK), F1's exposure functions (sector/region weights per
day), `signals/risk.factor_loadings` and `ols`, `model/stats.nw_t`, `mine.vs_shadow` (shadow ACWI per position),
`backtest/exits.py` (counterfactual hold), `notebook.py` (journal entries), `sources/factors.py` (French data,
already downloaded monthly).

**Scope.**
- *MVP:* *Attribution* tab on *Returns*: monthly Brinson–Fachler by sector (ACWI sector weights and sector returns
  from the sector ETFs as the benchmark segments, stated as such), linked over the period (Carino or
  Menchero smoothing, named); factor regression on French developed daily or weekly factors converted to DKK
  (documented); the "skill or luck" box. `radar attribution [NAME…] [--start D] [--json]`.
- *Later:* the trade-level and behavioural review; journal link (needs a light schema for theses: the `/journal`
  skill already writes structured fields; read them through `notebook.py`); after-tax attribution with F3.

**Method notes.**
- Benchmark segment returns: ACWI's own sector returns aren't free; the sector proxies (MSCI World sector UCITS ETFs
  or the US sector ETFs already tracked) are an approximation and the page says so. Region segments from regional
  ETFs.
- French developed factors are USD; convert the market factor to DKK and treat long-short factors as
  currency-neutral (documented assumption). Use the risk-free rate the radar already uses (ECB deposit rate for DKK
  investors) consistently with `model/stats.risk_adjusted`.
- Minimum data: no attribution for under 12 months; no factor regression under 52 weekly observations (settings).
- Disposition effect: Odean (1998) PGR/PLR computed on days the user sold anything.

**Data.** Kenneth R. French Data Library: add the *daily or weekly developed* factor files to `sources/factors.py`
(same licence, already in `DATA_LICENSE.md`; update the "Used for" column).

**Acceptance criteria.** Allocation + selection + interaction sum to the active return each month; the linked
total equals the period's active return within a stated tolerance; a synthetic portfolio equal to ACWI's sector
weights shows zero allocation; alpha always shown with t and n.

**Docs.** New textbook chapter `laerebog/attribution.md` (Brinson, linking, factor regression, skill vs luck,
disposition effect); user-guide section in `afkast.md`.

**Open questions.** Sector proxies: US sector ETFs (deep history, US-only) or MSCI World sector UCITS (global,
shorter history)? Recommend: World UCITS where history allows, falling back with a note.

---

### F5. Change feed, calendar and local alerts

**Problem.** The radar holds dozens of state changes per week (a regime vote flips, a holding loses its trend, a
stop is breached, a proposal's exit criterion triggers, a watchlist name turns up, an earnings date approaches),
but the user must visit six pages to find them. A semi-pro wants a morning list of *what changed and what's
coming*, without a paid alert service.

**User stories.**
- On *Home*, I see "Since your last visit": an ordered feed of changes relevant to my holdings and watchlist, each
  linking to the page that explains it.
- I see a calendar for the next four weeks: earnings dates and ex-dividend dates of my holdings and watchlist,
  central-bank meetings (Fed, ECB, Nationalbanken), key releases (US CPI, payrolls, OECD CLI), tax deadlines (F3),
  my proposals' review dates and my journal's review dates.
- Optionally, I get a desktop notification after the daily update when something on a list I choose happens (stop
  breached, exit criterion triggered, regime flip).

**Builds on.** `snapshot.py` (rank history), `sources.json` and the report's `build.inputs`, `mine.py` flags,
`propose check`, `notebook.py` review dates, `earnings_date` in the ticker summaries, the Yahoo detail (ex-dividend
date), `updater.py` (end of daily update), `ops.py` jobs.

**Scope.**
- *MVP:* an `events` model: each report build diffs the new readings against the previous build and appends events
  (`kind`, `symbol`, `severity`, `asof`, `link`) to a history-tier file (append-only, can't be rebuilt); `GET
  /api/events?since=`; the feed on *Home*; a calendar of earnings and ex-div dates for holdings and watchlist plus
  review dates.
- *Later:* the macro calendar (FRED release dates API, ECB's published meeting calendar, Nationalbanken's), desktop
  notifications (OS-native from the local server or the start script; **nothing sent to any external service**),
  per-event-kind settings.

**Method.** Events are derived, never edited, and dated by the data's `asof`, not by clock time, so a rebuild
yields the same events. An event from a stale source is marked stale.

**Data.** Yahoo calendar fields (already fetched in ticker detail); FRED release calendar (`fred/releases/dates`,
free API key; FRED terms already in `DATA_LICENSE.md`, add the use); ECB and Danmarks Nationalbank meeting
calendars (public pages, check their reuse terms; hand-maintained yearly YAML is an acceptable fallback, as with fee
presets).

**Acceptance criteria.** Re-running `radar report` on unchanged data creates no new events; an earnings date that
Yahoo doesn't have is absent, never guessed; notifications are off by default.

**Docs.** `brugervejledning/navigation.md` (Home), new section on the calendar; `indstillinger.md` for the
notification settings.

**Open questions.** Should the monthly `/market-brief` read the feed (yes, through `summary.json`)? Email digests
would mean sending data out: keep them out of scope unless the user asks.

---

### F6. Universe parity with ACWI

**Problem.** The benchmark is global, but the tracked stock universe is the S&P 500 plus about 115 hand-picked
European, Nordic and Asian names. That has three costs: the momentum score's cross-section is mostly US (a
European name competes against a thin peer group), Japan and emerging markets (≈ 15 % of ACWI) are nearly absent,
and the hand-picked lists bring survivorship and selection bias into the score study. Discover already scans the
STOXX 600 but never feeds the readings.

**User stories.**
- The momentum and Q+V pages cover the developed world's large and mid caps (S&P 500, STOXX 600, Nordic mid caps,
  MSCI Japan, optionally EM large caps), from index-fund holdings files, not hand-picked lists.
- The score study reports results per region with each region's own N, and says how much of ACWI's weight the
  universe covers.
- Membership is stored point-in-time from the day the radar first saw it, so future studies can use "members on
  date D".

**Builds on.** `sources/constituents.py` (SPY, ACWI/SSAC parsing), Discover's EXSA/CSPX holdings
(`discovery/sources.py`), `universe.py`, `snapshot.py`, `net.py` pacing.

**Scope.**
- *MVP:* universe groups defined by source (`source: ishares:EXSA`, `ishares:IJPA`…) instead of lists; a
  liquidity and size floor from `discovery.yaml`; membership snapshots in the history tier; a coverage line
  ("universe covers N % of ACWI by weight"). Measure the update-time cost first (Yahoo request budget in
  `network:`).
- *Later:* emerging-markets group; point-in-time S&P 500 membership from a free historical source to shrink the
  survivorship haircut (only if the licence allows; otherwise rely on the radar's own snapshots going forward).

**Data.** iShares holdings files (already in `DATA_LICENSE.md`; extend "Used for"). Yahoo prices for more tickers:
check the request budget and the run time; this may push towards incremental updates per group.

**Acceptance criteria.** Update time and Yahoo request count stay within budgets set in `settings.yaml` before the
change ships; a ticker that fails to map to Yahoo is listed, not silently dropped; the regime and breadth readings
state which universe they used (breadth must not silently change meaning: version it).

**Docs.** `momentum.md`, `data-og-daekning.md`, `momentumscore.md` (the cross-section), `test-af-scoren.md`
(survivorship).

**Open questions.** Does breadth (part of the regime vote) stay on the S&P 500 for continuity? Recommend: yes, and
add a separate global breadth reading.

---

### F7. European point-in-time fundamentals (ESEF)

**Problem.** Quality and value are only point-in-time testable in the US (SEC EDGAR with filing dates). Outside the
US, statements come from Yahoo: unofficial, about four years deep, often half-yearly, no filing dates. So the value
and mix proposals carry an "untested outside the US" flag, and a Danish investor's home market is the least
evidenced part of the product. Since 2021 EU-listed companies file annual reports in ESEF (inline XBRL, IFRS
taxonomy), with publication dates, and XBRL International runs a free public index of them.

**User stories.**
- For EU/EEA-listed stocks (including Nasdaq Copenhagen), the quality and value scores use the company's own
  filed annual report, with the date it became public.
- `radar study score --signal qv` can run on European stocks as known on each date (from 2021 onwards, with the
  shorter sample stated).
- `radar fundamentals check` compares ESEF with Yahoo, as it does EDGAR with Yahoo.

**Builds on.** `fundamentals/` (long fact format, `items.py` mapping, `store.py`, `schedule.py`), `signals/periods.py`
(fiscal years as known on a day), `backtest/fund.py`, the EDGAR pattern (contact, pacing).

**Scope.**
- *MVP:* `fundamentals/esef.py`: discover filings per LEI via filings.xbrl.org's API, fetch the xBRL-JSON, map
  IFRS concepts to the radar's items (revenue, operating profit, operating cash flow, capex, equity, debt, shares,
  dividends); LEI mapping per ticker (GLEIF's free API, CC0); annual only.
- *Later:* half-year reports where filed in ESEF (few are); a European Q+V study; drop the "untested outside US"
  flag where evidence now exists.

**Method.** IFRS vs US GAAP differences documented in the item mapping (e.g. leases under IFRS 16, presentation of
operating profit); company-specific extensions ignored with a coverage count. Publication date = the filing's
date in the index; if missing, the item is not used point-in-time.

**Data.** filings.xbrl.org (XBRL International; free, **verify terms of use and rate limits before building**),
GLEIF LEI API (CC0). Both new in `DATA_LICENSE.md`.

**Acceptance criteria.** A company with no ESEF filing falls back to Yahoo and says so per item; a concept that maps
to nothing is missing, not zero; `fundamentals check` lists ESEF–Yahoo disagreements above tolerance.

**Docs.** `kvalitetsscore.md`, `data-og-daekning.md` (Regnskaber), `datalicenser.md`.

**Open questions.** UK companies (not ESEF since Brexit; Companies House has free iXBRL accounts, but mostly for
non-listed filers): out of scope for the MVP.

---

### F8. Insider transactions and short positions

**Problem.** `coverage.blind_spots` says the radar sees no insider trading and no short interest. Both are free,
official and widely studied (opportunistic insider purchases: Cohen, Malloy & Pomorski 2012; short interest as a
negative predictor: Rapach, Ringgenberg & Zhou 2016). A semi-pro wants them on the ticker profile and wants to know
whether they add anything to the radar's own scores.

**User stories.**
- The ticker profile shows the last 12 months of insider transactions (US: SEC Form 4; Denmark/EU: managers'
  transactions under MAR art. 19), net buying in value, and "opportunistic vs routine" classification for US names.
- It shows the latest public net short positions (EU regulators publish positions ≥ 0.5 %; FINRA publishes US short
  interest twice a month) with the trend.
- The momentum and holdings tables can show an insider/short flag.
- `radar study score --signal insider` tests whether net insider buying adds information beyond momentum (US,
  point-in-time from filing dates) before any of it votes anywhere.

**Builds on.** `fundamentals/edgar.py` (SEC client, User-Agent contact, pacing), `profile.py` sections, `mine.py`
flags, `backtest/study.py` variants.

**Scope.**
- *MVP:* US Form 4 from SEC's quarterly *Insider Transactions Data Sets* (bulk, structured, public domain) plus
  daily EDGAR filings for holdings; EU net short positions from the Danish FSA and the larger registers (FCA, AMF,
  BaFin, CONSOB) as published files; a profile card.
- *Later:* Danish managers' transactions via Finanstilsynet's OAM (check structure and terms; announcements may be
  PDF-only, so this may not parse reliably and should only ship if it does); FINRA short interest (check that the
  public file terms allow personal automated download); the study.

**Method.** Classification as in Cohen–Malloy–Pomorski (an insider who trades in the same month each year is
routine). Show amounts in DKK. Nothing votes in the regime; flags are descriptive until a study passes.

**Data.** SEC EDGAR (public domain, already listed); national competent authorities' short-position registers
(public-sector data, verify each register's reuse terms); FINRA (verify terms).

**Acceptance criteria.** Each register parsed with its own guard (non-empty, expected columns); a ticker with no
filings shows "none filed in 12 months" only when the source covered that market, otherwise "not covered".

**Docs.** New textbook chapter on insider trading and short interest; `tickerprofil.md`; `data-og-daekning.md`
(remove the blind spot only for the markets covered).

---

### F9. Research lab: your own screens and scores, tested honestly

**Problem.** The theory-oriented user has ideas: "momentum, but only names with positive FCF and rising
estimates", "12-1 momentum, low volatility, in Europe". The study machinery can test any score at every month-end
with holdouts and NW t, but variants are defined in code. The danger of opening this up is data mining: the selling
point must be that the lab *defends the user from overfitting*, which no free screener does.

**User stories.**
- I define a screen (filters) and/or a composite score (weighted percentiles of available metrics) in a small form
  or YAML, and save it.
- I run it through the score study: IC, quintiles, top N vs universe and ACWI, holdout, turnover, fees.
- The lab counts every variant I have tried and reports a multiple-testing-adjusted verdict (deflated Sharpe ratio
  or a Bonferroni/Holm-adjusted t), and it requires me to *register* the rule before seeing the holdout.
- A rule that passes can become a forward paper portfolio (like the A/B test), frozen monthly.

**Builds on.** `backtest/study.py` (variants, verdicts), `model/stats.py`, `model/panels.py` (point-in-time
panels), `backtest/fund.py`, `abtest.py` (frozen monthly picks), `propose.rule_hash` (hashing a rule), F2's page.

**Scope.**
- *MVP:* a rule spec (`userstore` table: name, spec JSON, hash, created, registered_at), a limited metric
  vocabulary (returns over windows, volatility, distance to highs, momentum/Q+V percentiles and pillars, size), a
  CLI `radar lab run RULE` writing a study report, and a trial counter per user.
- *Later:* the form in the app; the holdout lock (the holdout result is only revealed once per registered hash);
  forward paper portfolios; deflated Sharpe (Bailey & López de Prado 2014).

**Method.** Point-in-time only (reuse `pit.py`); the metric vocabulary only contains things the panel can compute
as of a date. Every result shows the number of trials so far.

**Data.** None new.

**Acceptance criteria.** A rule that reads a future value fails a test that shifts the panel; trial counts can't be
reset without a visible note in the report; the holdout stays hidden until registration.

**Docs.** New user-guide chapter `laboratoriet.md`; textbook `statistik.md` gets multiple testing and the deflated
Sharpe ratio.

---

### F10. Rebalancing and cash-deployment planner (with asset location)

**Problem.** The proposals answer "what new basket for X DKK". The everyday questions are different: "I have
20,000 DKK of new savings: which existing positions and which account?", "my momentum sleeve has drifted: what's the
minimum set of trades back to target, after fees?", and the Danish one: "what belongs on the ASK, given its
deposit cap and flat lager tax, and what belongs in *frie midler*?".

**User stories.**
- I set target weights (or target exposures: e.g. "within ±5 pp of ACWI by region") per account or across accounts.
- I see drift vs target and a fee-aware trade list to get back within bands (honouring the minimum ticket and each
  account's fee schedule), with the turnover, fees and (with F3) the tax it triggers.
- For new cash, I get an allocation across accounts and positions that minimises drift and cost, respecting the
  ASK deposit headroom and the ASK-eligible list (positive list / listed shares).
- Asset location: a comparison of the expected after-tax outcome of putting high-turnover momentum on the ASK vs in
  *frie midler*, under stated return assumptions.

**Builds on.** F1 (exposures), F3 (tax), `portfolios/fees.py`, `propose/basket.py` and `model/select.py` (selection
under caps), `propose/pricing.py`.

**Scope.** *MVP:* targets table, drift view, a greedy fee-aware rebalance within bands, new-cash allocation.
*Later:* asset-location comparison, tax-aware lot choice, export of the order list as CSV (never sent to a broker).

**Acceptance criteria.** No trade below the minimum ticket; no ASK purchase of an ineligible security; fees from
the account's schedule with None (not 0) when unknown; the plan is analysis, labelled as such.

**Docs.** New user-guide chapter; textbook `stop-og-storrelse.md` / `diversifikation.md` on rebalancing bands.

---

### F11. UCITS ETF toolkit

**Problem.** For a Danish investor, the ETF decision is usually "which UCITS share class on the positive list,
accumulating or distributing, which domicile, and how good is it at tracking?". The radar knows the positive list
and looks through iShares/SSGA holdings, but not tracking quality, cost or overlap.

**User stories.**
- For any tracked ETF, I see TER (from the issuer page), tracking difference vs its index proxy over 1/3/5 years,
  distribution policy, domicile (Irish vs Luxembourg: US dividend withholding drag) and positive-list status per
  share class.
- I compare candidate ETFs for one exposure side by side.
- I see overlap between two ETFs and between an ETF and my direct holdings (by look-through weights).

**Builds on.** `sources/positive_list.py`, `profile.py` look-through, `profile` compare, `sources/constituents.py`,
F1's look-through aggregation.

**Scope.** *MVP:* overlap (holdings-weighted) and the compare table for issuers already parsed; tracking difference
computed from Yahoo total-return-adjusted prices vs a reference ETF/index proxy, labelled as an estimate. *Later:*
TER and fund facts from more issuers' fact sheets (Xtrackers, Amundi, Vanguard, SPDR), only where their terms allow
personal automated download.

**Acceptance criteria.** Tracking difference shown only with a named reference and window; an issuer we can't parse
shows "not available" for TER.

**Docs.** `temaer-og-faktorer.md`, textbook `justerede-kurser.md` (tracking difference vs tracking error),
`skat.md` (withholding tax drag).

---

## 5. Considered and deferred

| Idea | Why not now |
|---|---|
| Options-implied data (IV rank, skew, per-stock put/call) via Yahoo option chains | Noisy and patchy for EU names, and the user's horizon is 1–6 months; revisit after F8 |
| News sentiment / NLP on headlines | Free news feeds rarely allow automated reuse; `/market-brief` already covers narrative via web research |
| Real-time or intraday prices | No free legitimate source; the method is end-of-day by design |
| Retirement / goal Monte Carlo | Off the product's focus (momentum and rotation); could follow F3 as a small add-on |
| Danish macro (Danmarks Statistik, CC BY 4.0) | Low marginal value for a global equity book; consider one or two series (DKK rates, housing) in the regime's "home" group later |
| ALFRED real-time macro vintages for the regime study | Valuable for integrity (regime tests without revised data), but only matters once the regime model is tested historically; park as a study task |
| Hosting, sharing, mobile app | Forbidden by the data licences (`DATA_LICENSE.md`) and raises MAR/GDPR issues |
| Broker API order routing | Out of character for an analysis tool and outside free data; the planner exports a CSV at most |

## 6. Risks across the roadmap

- **Scope creep in tax (F3)**: Danish tax has many edge cases. Mitigation: a written "modelled / not modelled"
  list in the guide, golden tests per rule, and estimates labelled as such.
- **Update time and request budgets (F6, F7, F8)**: more tickers and sources lengthen `radar run` and raise the
  risk of throttling. Mitigation: measure first; per-host budgets in `network:`; incremental and staggered
  schedules like `fundamentals.max_per_run`.
- **Source fragility**: issuer pages and regulator files change format. Mitigation: guards, fixtures from real
  samples, loud failure with the cache kept, the ops log.
- **Overfitting by the user (F9)**: mitigated by design (trial counter, registration, holdout lock); this is the
  feature's selling point, not an afterthought.
- **Licence drift**: each new source gets a "verify terms" task in its plan *before* code is written, and the
  outcome is recorded in `DATA_LICENSE.md`.

## 7. Turning a feature into an implementation plan

For each feature, the plan (`plans/<id>-<slug>.md`) should contain:

1. **Goal and non-goals**: copy the user stories and *Scope → MVP*; move *Later* to non-goals for this plan.
2. **Licence check** (new sources only): terms read, outcome, the `DATA_LICENSE.md` row drafted.
3. **Design**: modules per layer (name the files), data model (tables, files and their `paths.REGISTRY` tier),
   settings keys, API endpoints and `api_models` views, CLI commands.
4. **Refactors first**: e.g. F1 moves the exposure and risk functions from `propose/` to `model/` in its own PR,
   with no behaviour change.
5. **Steps as PRs**, each green on `pytest`, `ruff`, `mypy`, `lint-imports`, and each with its guide changes.
6. **Tests**: the acceptance criteria above as named tests; golden examples where a hand calculation exists.
7. **Docs**: the chapters listed under *Docs*; `CHANGELOG.md` and *Nyheder* in the release PR.
8. **Definition of done**: the checklist in section 3.3.
