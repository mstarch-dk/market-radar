# F4 Attribution and decision analytics: implementation plan

*Written 2026-10-25, from [the product owner review](analyses/product_owner.md) (feature F4), against `main` at
`eca4df8` (after F1, the portfolio X-ray). Backlog: TASK-3 and its subtasks. Analysis, not advice.*

## 1. Goal and non-goals

**Goal.** Explain *why* a selection of portfolios beat or lagged ACWI over a period, in DKK, and say honestly whether
the difference looks like skill. It uses the same books as *Returns* and the same classification as the X-ray, so
the three pages never disagree about what was held.

User stories (MVP):

1. I see a Brinson–Fachler attribution vs ACWI by sector and by region for a chosen period: allocation, selection
   and interaction per segment, plus a currency effect in DKK, month by month and linked over the period (Carino
   linking, named on the page).
2. I see how the attribution adds up to the return *Returns* shows: the effects, the part the attribution can't
   assign (trading at fills rather than closes, fees) and the part that comes from the benchmark proxies not being
   ACWI itself, each as its own line.
3. I see a factor regression of my portfolio's weekly DKK excess returns on the developed-market factors (market,
   size, value, profitability, investment, momentum), with alpha, its Newey-West t, n, and the months of data needed
   for this alpha to reach t = 2 at this volatility.
4. The same data from the CLI: `uv run radar attribution [NAME…] [--tag T] [--scope …] [--start D] [--json]`.

**Non-goals for this plan** (TASK-3.11 and 3.12, low priority, get their own short plan when they start):

- Trade-level and behavioural review (closed positions vs ACWI, what happened after a sale, PGR − PLR, holding
  periods, turnover and fee drag).
- Journal theses vs outcomes.
- After-tax attribution (waits on F3).
- Stock-level benchmark returns (ACWI's own sector returns aren't free; see 4.3).
- A section in `dashboard.json` or `summary.json`: computed live per request, like the X-ray.

## 2. Licence check

| Source | New use | Terms read | Outcome |
|---|---|---|---|
| **Kenneth R. French Data Library** | Developed 5 factors and momentum, **daily** (`Developed_5_Factors_Daily_CSV.zip`, `Developed_Mom_Factor_Daily_CSV.zip`) | Same library and terms as the monthly files already used | Allowed for personal use; update *Used for* ("factor regression of your portfolios"). |
| **iShares (BlackRock)**, SSAC holdings | Keep a weekly **aggregate** of ACWI's weights (sector, region, country, currency and their cross-tabs; no stock rows) in the history tier, so past months have the weights they had | [Nutzungsbedingungen](https://www.ishares.com/de/privatanleger/de/nutzungsbedingungen), read 2026-10-25: information only; "jegliche Vervielfältigung von Informationen oder Daten … erfordert die vorherige Genehmigung" | Same footing as today's cached file: a personal copy for one's own analysis, never redistributed. Storing only ~40 aggregate numbers per week (not the holdings list) keeps the copy minimal. *Redistribution: No* stays. `DATA_LICENSE.md` row and `datalicenser.md` updated in TASK-3.3, when the file starts being written. |
| **Yahoo** | Prices of the proxy ETFs (Xtrackers MSCI World sector UCITS, SPDR Global Real Estate, iShares country ETFs) | Existing row | *Used for* gets "attribution's benchmark segments". |

No new host. The new tickers go through `net.py`'s Yahoo pacing like every other price.

### Spike: does iShares serve past holdings? No.

Checked 2026-10-25 against the German (SSAC, product 251850) and US (ACWI, product 239600) fund pages:

- Both pages now show one date only (`data-as-of-dates="{"all":20261023}"`) and link to `…/latest-holdings.csv`.
- `latest-holdings.csv?asOfDate=20231229` ignores the parameter and returns the 23 Oct 2026 file (DE and US).
- The legacy endpoint (`…/1478358465952.ajax?fileType=csv&dataType=fund&asOfDate=…` on DE, `1467271812596.ajax` on
  US), which used to serve past month-ends, now returns the product page's HTML. It is gone, not just hidden.
- Rejected alternatives: the Wayback Machine's captures (sporadic, and a copy of someone else's copy), MSCI's index
  factsheets (MSCI's terms, PDF only).

**Decision.** From TASK-3.3 on, `radar run` appends ACWI's aggregate weights to a history file once per ISO week
(4.2). Months before the first snapshot get **back-drifted** weights (4.3): the first snapshot's weights rolled back
month by month with the segment proxies' returns. That ignores index changes (IPOs, deletions, country upgrades) and
GICS reclassifications: the 2018 move of Alphabet, Meta and Netflix into Communication Services and the 2023 move of
Visa, Mastercard and PayPal from Technology to Financials. So every month carries its basis (`snapshot` or
`back-drifted`), the page says which months are back-drifted, and sector attribution before 2023-03 carries a note
about the GICS change. As snapshots accumulate, the back-drifted share of any recent period shrinks.

## 3. What the code does today (findings that shape the design)

| # | Finding | Where | Consequence |
|---|---|---|---|
| C1 | `Book` keeps only the total holdings value per day; the per-symbol DKK values (`val`) are computed in the loop and dropped | `portfolios/performance.book` | Attribution needs per-symbol daily values. Keep them on `Book` (a `positions` frame) and pool them in `pool()`: a refactor with no behaviour change, its own PR (step 2). |
| C2 | `acwi_holdings.csv` is a cache file, overwritten on every refresh; the parser drops the file's date (`Fondsposition per`) | `sources/constituents.py` | Past weights need a history file of their own, and the snapshot needs its as-of date. Parse it and keep it. |
| C3 | `factors.french` has only monthly `ff3_dev` / `mom_dev`. `french_blocks` reads YYYYMM rows and skips everything else, and `load()` promises month-end dates | `config/settings.yaml`, `sources/factors.py` | Daily files need a daily row pattern and their own file (`factors/daily.parquet`), so the monthly contract stays true. `factors/` is already in the cache tier. |
| C4 | The French daily files end about two months back (the October 2026 files run to 2026-08-31) | spike | The regression window ends at the last factor date, and the page says so ("factors to 2026-08-31"). |
| C5 | `model/stats.nw_t` gives the Newey-West t of a *mean* only; `signals/risk.ols` gives classical standard errors | `model/stats.py`, `signals/risk.py` | Add `ols_nw` in `model/stats.py` (coefficients from `ols`, HAC standard errors with the same Bartlett kernel), so alpha and the loadings get NW t-stats. `nw_t` stays as it is. |
| C6 | `daily_rf` is the ECB deposit rate as a daily return; French's `Mkt-RF` is USD over the US T-bill | `model/stats.daily_rf`, French files | Convert the market factor to a DKK excess return (4.4); long-short factors stay as they are (documented assumption). |
| C7 | ACWI weights use Yahoo-style sector names and the radar's region keys (`us`, `nordic`, `europe`, `asia`, `other`), and F1 aligned them with the X-ray's classification | `sources/constituents.acwi_region`, `portfolios/exposure.ticker_meta` | Portfolio and benchmark segments share one key set. A test holds it (TASK-3.3 AC 3). |
| C8 | `universe.yaml` `sector_etfs.us` (XLK … XLRE) has long US history; the region ETFs list has country ETFs for the US, Japan, China, India, Korea, Taiwan, Germany, UK and the Nordics | `config/universe.yaml` | The fallback sector proxies and most region proxies are already downloaded. Region proxies need a few more country ETFs (4.3). |
| C9 | `ticker_meta` classifies a world fund with ACWI's weights and a fund it can't look through as `fund: not looked through` | `portfolios/exposure.py` | The attribution spreads world funds over segments and keeps unclassified value as its own segment, never dropped and never given a 0 % return (4.3). |

## 4. Design

### 4.1 Modules, by layer

| Layer | Module | Change |
|---|---|---|
| sources | `sources/factors.py` | Daily French blocks (`YYYYMMDD`), `DAILY_FILE = CACHE / "factors" / "daily.parquet"`, `daily_panel(key)`. Same guard and refresh rules. |
| sources | `sources/constituents.py` | `parse_acwi_holdings` keeps the file's as-of date; `acwi_segments(df)` (the aggregates); `record_acwi_segments()` appends a week's snapshot to `HISTORY / "acwi_segments.csv"`; `acwi_segment_history()` reads it. |
| domain | `portfolios/performance.py` | `Book.positions`: per-symbol daily DKK values (NaN where unknown), pooled by `pool()` (step 2). |
| domain | `portfolios/segments.py` (new) | Benchmark segments: monthly ACWI weights per dimension (snapshot or back-drifted, with the basis), daily DKK returns of each segment from its proxies, the currency split of each segment. Reads prices through `portfolios/prices.py`. |
| kernel | `model/attribution.py` (new) | Pure math: single-period Brinson–Fachler by segment, the currency effect, Carino linking. Arrays and frames in, frames out. |
| kernel | `model/stats.py` | `ols_nw(y, X, lag)` (coefficients via `signals.risk.ols`, Newey-West standard errors), `nw_lag(n)` (the usual rule ⌊4 (n/100)^(2/9)⌋), `months_to_t(alpha, lrv_sd, t=2)`. |
| features | `attribution.py` (new top-level module) | For a selection: books → daily segment weights and returns by sector and region (via `portfolios/exposure.ticker_meta`) → benchmark segments → attribution per day, linked to months and the period → reconciliation → factor regression → notes. No math of its own. Added to the features layer and to the "app never imports backtest" contract in `pyproject.toml`. |
| features | `api_models/attribution.py` | `AttributionView` and its parts (`extra="forbid"`), re-exported by `api_models`. |
| interfaces | `api/attribution.py` | `GET /api/attribution`, a router included last in `api/app.py`. |
| interfaces | `cli/portfolios.py` | `radar attribution` next to `radar performance` and `radar xray`. |
| web | `web/src/pages/Performance.tsx` | An *Attribution* tab on *Returns*. |

Why `model/` for the math: Brinson and the regression are what a later study (an attribution of the A/B portfolios
or of proposals, run point in time) must compute the same way, and `model/` may import `signals/` (for `ols`).
`portfolios/segments.py` sits in the domain because it reads prices, `universe.yaml` and the history file.

### 4.2 Data

**ACWI segment history** (`HISTORY / "acwi_segments.csv"`, history tier, append-only). Long format, one row per
(snapshot, dimension, key):

```text
asof        (the holdings file's "Fondsposition per" date)
recorded    (when radar run wrote it)
dim         sector | region | country | currency | sector_currency | region_currency | region_country
key         e.g. "Technology", "us", "Japan", "USD", "Technology|USD", "europe|EUR", "asia|Japan"
weight      fraction of ACWI's stock weight (each of sector, region, country, currency sums to 1)
```

- Written by `radar run` after the ACWI holdings refresh, when no row with the same ISO week of `asof` exists. A
  re-run in the same week adds nothing; a file whose `asof` is older than the newest stored one is not written. Never
  rewritten or trimmed; a schema change adds columns.
- ~150 rows a week, about 8,000 a year. Only aggregates; the stock list itself stays in the cache file.
- Country names are stored in English (a small German → English map next to `acwi_region`, tested to cover every
  country in a real sample file).

**French daily factors** (`CACHE / "factors" / "daily.parquet"`, cache tier through `factors/`). Same long columns
as `returns.parquet` (key, series, date, ret, fetched) with trading-day dates. Settings:

```yaml
factors:
  french:
    …                                          # unchanged
  french_daily:                                # new: the attribution's factor regression
    ff5_dev: Developed_5_Factors_Daily_CSV     # Mkt-RF, SMB, HML, RMW, CMA, RF (USD, daily, 1990-07-)
    mom_dev: Developed_Mom_Factor_Daily_CSV    # WML (daily, 1990-11-)
```

A file that parses to nothing raises and keeps the stored rows (`guard.check`, as the monthly files). Weekly
returns are compounded from the daily rows to W-FRI weeks; a week with a missing day is missing.

**Proxies** (`config/universe.yaml`, new `attribution:` section):

```yaml
attribution:
  sectors:                 # benchmark sector segments: MSCI World sector UCITS (Xtrackers 1C, accumulating, EUR)
    Technology: XDWT.DE              # from 2016-04
    Healthcare: XDWH.DE
    Financial Services: XDWF.DE      # from 2017-04
    Industrials: XDWI.DE
    Consumer Cyclical: XDWC.DE
    Consumer Defensive: XDWS.DE
    Energy: XDW0.DE
    Basic Materials: XDWM.DE
    Utilities: XDWU.DE
    Communication Services: XWTS.DE  # the sector only exists in this form since 2018-09
    Real Estate: SPYJ.DE             # SPDR Dow Jones Global Real Estate: no MSCI World real estate UCITS on Yahoo
  sector_fallback: us      # before a proxy's first price: universe.yaml sector_etfs.us (XLK …), with a note
  regions:                 # region segments: country ETFs, weighted by ACWI's country weights inside the region
    us: {United States: SPY}
    nordic: {Denmark: EDEN, Sweden: EWD, Norway: ENOR, Finland: EFNL}
    europe: {United Kingdom: EWU, Germany: EWG, France: EWQ, Switzerland: EWL, Netherlands: EWN, Spain: EWP,
             Italy: EWI}
    asia: {Japan: EWJ, China: MCHI, India: INDA, Korea: EWY, Taiwan: EWT, Hong Kong: EWH, Singapore: EWS}
    other: {Canada: EWC, Australia: EWA, Brazil: EWZ}
```

New tickers (EWQ, EWL, EWN, EWP, EWI, EWH, EWS, EWC, EWA, EWZ, the ten Xtrackers and SPYJ.DE) are added to the price
universe through `universe.py`, so `radar run` downloads them. Every proxy ticker was checked on Yahoo in the spike.

### 4.3 Method

**Periods.** Days are the single periods: the attribution runs on each session of the benchmark calendar, with
weights at the previous close and returns over the day, and is linked to calendar months and to the whole period.
Monthly weights with returns from mid-month trades would not add up; daily periods with prices (not values) keep
trades out of the returns.

**Portfolio segments.** For each held symbol on day *t*: its DKK value at *t−1* (`Book.positions`) and its DKK
return from closes and rates (adjusted closes under `reinvested`). Classification from `ticker_meta` (today's, for
every past day; a note says so):

| Class | Segments | Return given to each slice |
|---|---|---|
| stock | its sector / its region | its own return |
| sector_fund | its sector; region `fund: not looked through` unless `sector_etfs` gives one | its own return |
| world | spread with that month's ACWI weights | the segment's proxy return plus the fund's own difference to the proxy benchmark, so the slices add up to the fund's own return |
| fund_sectors | spread by its Yahoo sector weights (remainder `fund: other`) | as world |
| fund, unknown | one segment, `unclassified` | its own return |
| cash (ledger portfolios) | segment `cash` | 0 (the book's cash earns nothing) |

A segment the benchmark doesn't have (`cash`, `unclassified`, `fund: …`) has benchmark weight 0 and benchmark
return := the benchmark's total return, so its effect lands in selection (`unclassified`) or allocation (`cash`,
whose return is 0: the cash drag). These rows are always listed, with their value. A day with an unknown position
value (a gap in the book) has no attribution; the month's linked figures then cover fewer days, and the count is
shown.

**Benchmark segments.** Weights per month: the last snapshot on or before the month's first day; before the first
snapshot, back-drifted: w_s(m−1) ∝ w_s(m) / (1 + R_s(m)) with R_s the segment's proxy return in month m (local
currency for sectors and regions alike), renormalised to 1. Within a month the weights drift with the proxies' daily
returns (buy-and-hold), so a day's benchmark is what ACWI would have held. Segment returns in DKK:

- *Sector*: the proxy's DKK return (EUR close × EURDKK). Before the UCITS proxy's first price, the `sector_etfs.us`
  ETF (USD × USDDKK), with a note. A segment with neither is missing for that day, and that day's sector attribution
  is missing (never a 0 % segment).
- *Region*: the country ETFs' DKK returns, weighted by ACWI's country weights inside the region (from
  `region_country`). Needs `attribution.min_proxy_coverage` of the region's weight in countries with a proxy, else
  the region's return is missing for that day.

The proxy benchmark's return Σ w_b,s R_b,s is not ACWI's own return. The difference is shown as its own line,
*benchmark proxies vs ACWI*, never folded into the effects.

**Brinson–Fachler** per day and dimension, with portfolio weights w_p,s, benchmark weights w_b,s, returns r_p,s and
R_b,s, and R_b = Σ w_b,s R_b,s:

- allocation A_s = (w_p,s − w_b,s)(R_b,s − R_b)
- selection S_s = w_b,s (r_p,s − R_b,s)
- interaction I_s = (w_p,s − w_b,s)(r_p,s − R_b,s)
- Σ_s (A_s + S_s + I_s) = r_p − R_b, with r_p = Σ w_p,s r_p,s (exact; the identity TASK-3.4 tests).

**Currency effect in DKK.** Each DKK return splits as 1 + r = (1 + r_local)(1 + f), with f the segment's currency
return against DKK:

- Stocks: the quote currency's DKK return (pence → GBP). World funds and benchmark segments: the currency mix from
  ACWI's `sector_currency` / `region_currency` cross-tabs applied to the FX returns. Sector funds on the US map: USD.
  A fund that isn't looked through has no known currency: its whole DKK return is treated as local, and the note gives
  its share of value.
- Brinson runs on local returns. The currency effect is C = Σ_c (w_p,c − w_b,c)(f_c − F_b), with F_b = Σ w_b,c f_c
  (a currency's return is the same on both sides, so it has no selection). The cross term (r_local · f, both sides)
  is shown as *currency cross*, so allocation + selection + interaction + currency + cross = r_p − R_b exactly in
  DKK. Daily, the cross term is tiny; it is still shown, not dropped.

**Linking: Carino (1999), chosen over Menchero (2000).** Both are exact. Carino's factor k_t = ln(1+r_p,t) −
ln(1+R_b,t) over (r_p,t − R_b,t) (and 1/(1+r) when the two are equal), scaled by K = (ln(1+r_p) − ln(1+R_b)) / (r_p −
R_b) over the period, has a closed form, depends on no optimisation and doesn't depend on the order of the days, so a
golden test can be checked by hand. Menchero's optimised factors spread the residual more evenly, which matters when
a period has extreme single days, not at daily granularity. A month's figures are linked over its days; the period's
figures are linked over all its days in one go (so the months don't sum to the period exactly, and the page says so).
Linking error: |Σ linked effects − (r_p − R_b)| ≤ `attribution.tolerance` (1e-8, return units), asserted in the
code and tested.

**Reconciliation**, shown for every period, from the top down:

1. Portfolio return (TWR, as on *Returns*) − ACWI's return (DKK) = **active return vs ACWI**
2. − *trading and fees* = TWR − r_p (fills vs closes, fees, flows inside a day: not attributed)
3. − *benchmark proxies vs ACWI* = R_b − ACWI (the proxies aren't ACWI)
4. = **attributed active return** = allocation + selection + interaction + currency + cross

**Minimum data.** No attribution under `attribution.min_months` (12) of book history in the period, with a note
that says how many months there are.

### 4.4 Factor regression and skill-or-luck

- y: the selection's weekly (W-FRI) DKK return from the TWR index, minus the weekly compounded `daily_rf` (ECB
  deposit rate). The week in progress is left out.
- Market factor in DKK: (1 + Mkt-RF + RF_us)(1 + USDDKK return) − 1 − rf_DKK, weekly. SMB, HML, RMW, CMA, WML are
  long-short in USD and treated as currency-neutral: a self-financing position's currency exposure is second order.
  Documented on the page and in the textbook.
- Window: the overlap of the book and the factor files, ending at the last factor date (C4). Under
  `attribution.min_weeks` (52) observations: no regression, a note says why and how many weeks there are.
- `model/stats.ols_nw` with lag `nw_lag(n)` unless `attribution.nw_lag` is set: alpha (annualised ×52) with its NW
  t and n, loadings with NW t, R².
- Months needed for t = 2: n* = (2 σ_LR / |α|)² weeks, with σ_LR the long-run (NW) standard deviation of α + ε, shown
  in months (×12/52), and as "already reached" when |t| ≥ 2. It assumes the alpha and the volatility stay as
  measured, and says so; it is not a forecast. Alpha is never shown without t and n.

### 4.5 Settings

```yaml
attribution:                # src/radar/attribution.py
  min_months: 12            # less book history in the period: no attribution, a note
  min_weeks: 52             # fewer weekly observations: no factor regression, a note
  nw_lag: null              # Newey-West lag in weeks; null = the rule floor(4 (n/100)^(2/9))
  min_proxy_coverage: 0.8   # share of a region's ACWI weight its country proxies must cover
  tolerance: 1.0e-8         # linked effects vs the active return they explain (return units)
  factors: {five: ff5_dev, momentum: mom_dev}   # keys under factors.french_daily
```

In `config/settings.yaml` and `config_schema.Attribution`; the guide quotes them with `{{settings:attribution.…}}`.
None is in `RULE_KEYS`.

### 4.6 API

`GET /api/attribution?portfolio=&tag=&scope=&start=&end=` → `AttributionView`:

```text
AttributionView
  asof, generated, selection: {ids, names, scope}, period: {start, end, months, days, days_missing}
  reconciliation: {twr, acwi, active, trading_fees, proxy_vs_acwi, attributed, linking_error} | null
  dims: for sector and region:
      rows: [{key, w_p, w_b, r_p, r_b, allocation, selection, interaction, total}]   (period, linked; average weights)
      months: [{month, allocation, selection, interaction, currency, cross, active, days, basis}]
      coverage, proxy_notes: [str]
  currency: {effect, cross, rows: [{currency, w_p, w_b, fx_return, effect}]}
  benchmark: {basis: [{month, basis: snapshot | back-drifted}], first_snapshot | null}
  regression: {n_weeks, start, end, factors_to, r2, nw_lag, alpha_ann, alpha_t, months_to_t2 | null,
               reached: bool, loadings: [{factor, beta, t}]} | null
  notes: [str]
```

- 503 without prices, like the other live endpoints; an empty selection or too short a history returns a valid view
  with nulls and notes, not an error.
- Cached per (selection, period, market mtime, transactions version) with the `performance._cached` pattern.
- Then `pnpm -C web gen:api`; `client.ts` gets `attribution(sel, start?)`.

### 4.7 CLI

`uv run radar attribution [NAME…] [--tag T] [--scope real|virtual|all] [--start D] [--end D] [--json]` in
`cli/portfolios.py`: the reconciliation, the linked sector and region tables (largest |total| first), the currency
line, the regression box; `--json` prints the `AttributionView` dict (TASK-3.7 AC 1: same view as the API).

### 4.8 Web

An *Attribution* tab on *Returns* (`Performance.tsx`), using the page's portfolio picker and period:

1. **Reconciliation**: a waterfall from active return vs ACWI to the attributed effects (trading and fees, proxies vs
   ACWI as their own bars).
2. **By sector / by region** (tabs): the linked table, and a monthly stacked bar of the effects.
3. **Currency**: the effect per currency.
4. **Skill or luck**: alpha, t, n, months needed for t = 2, the loadings with t, the window and "factors to …".
5. **Notes**: the proxy statement ("benchmark segments are ETFs that track MSCI World sectors and country indices,
   not ACWI's own segments"), back-drifted months, today's classification used for past days, unclassified value.

Missing values show as "–" with a reason, never 0. Terms (allocation, selection, interaction, Carino, Newey-West) get
`Term` tooltips via `lib/glossary.ts`, linked to the textbook.

## 5. Steps as PRs

Each PR is green on `uv run pytest -q`, `uv run ruff check`, `uv run mypy`, `uv run lint-imports` (and `pnpm -C web
test` when the web changes), and carries its guide changes.

| # | PR | Task | Contents | Behaviour change |
|---|---|---|---|---|
| 1 | **Plan** | 3.1 | This file; the task files updated. | – |
| 2 | **Per-symbol values on `Book`** | 3.13 | `Book.positions`, pooled by `pool()`. | None: a test holds `analyze` and `compare` output equal on the test world before and after. |
| 3 | **French daily factors** | 3.2 | `factors.french_daily`, daily parser, `daily.parquet`, weekly compounding helper; `DATA_LICENSE.md` and `datalicenser.md` *Used for*. | New download in `radar run`. |
| 4 | **Benchmark segments** | 3.3 | As-of date in the ACWI parser; `acwi_segments.csv` (history tier, `REGISTRY`); `record_acwi_segments` in `radar run`; `universe.yaml` `attribution:` and the new tickers; `portfolios/segments.py` (weights with basis, back-drift, DKK segment returns, currency split); `DATA_LICENSE.md` and `datalicenser.md` (iShares aggregate history, proxy tickers). | New history file; more tickers downloaded. |
| 5 | **Attribution math** | 3.4 | `model/attribution.py`: Brinson–Fachler, currency effect and cross, Carino. Golden tests. | None (new functions). |
| 6 | **Regression** | 3.5 | `model/stats.ols_nw`, `nw_lag`, `months_to_t`; the factor-regression function (DKK market factor, weekly excess returns). | None (new functions). |
| 7 | **`attribution.py`** | 3.6 | The feature module; `pyproject.toml` layers and contracts; `docs/architecture.md`. | None visible yet. |
| 8 | **API and CLI** | 3.7 | `api_models/attribution.py`, `api/attribution.py`, `radar attribution`, `attribution:` settings and schema, TS types, `docs/commands.md`, `docs/web-app.md`, `CLAUDE.md` main commands. | New endpoint and command. |
| 9 | **Web tab** | 3.8 | The *Attribution* tab, client, glossary, `page_links`. | New tab. |
| 10 | **Docs** | 3.9 | `laerebog/attribution.md`, a section in `brugervejledning/afkast.md`, `formler.md`, `indstillinger.md`, `glossary_links`. | – |
| 11 | **Release** | 3.10 | `CHANGELOG.md`, *Nyheder*, marketing `features.yaml`, screenshot check in the demo copy. | – |

Steps 2–6 are independent of each other; 7 needs all of them; 8–11 follow in order. Step 4 should merge early, since
every week it waits is a snapshot the history doesn't get.

## 6. Tests

| Test | File | Checks |
|---|---|---|
| `test_book_positions_sum_to_holdings` | `tests/test_performance.py` | Step 2: Σ positions = holdings each day, NaN on the same days; pooled books likewise; `analyze` unchanged. |
| `test_french_daily_parse` | `tests/test_factors.py` | A real (trimmed) daily sample: YYYYMMDD dates, percent → decimals, −99.99 → missing; an empty file raises and keeps the stored rows. |
| `test_weekly_from_daily` | `tests/test_factors.py` | Compounding to W-FRI; a week with a missing day is missing. |
| `test_acwi_asof_parsed` | `tests/test_sources.py` | `Fondsposition per` → the as-of date, from the real sample. |
| `test_acwi_segments_append_only` | `tests/test_sources.py` | Same ISO week twice adds nothing; an older file adds nothing; earlier rows are never changed. |
| `test_acwi_keys_match_classification` | `tests/test_sources.py` | Every sector and region key in the history is one `ticker_meta` can produce (TASK-3.3 AC 3); every country in the sample maps to English. |
| `test_backdrift` | `tests/test_segments.py` | Hand example: two segments, known returns, weights rolled back and renormalised; basis flagged. |
| `test_missing_proxy_is_missing` | `tests/test_segments.py` | A sector without proxy prices on a day gives a missing segment return, never 0; region coverage below the setting gives missing. |
| `test_brinson_sums_to_active` | `tests/test_attribution_math.py` | Hand-computed three-segment day: A + S + I = r_p − R_b; with currency and cross, the DKK identity is exact. |
| `test_benchmark_weights_zero_allocation` | `tests/test_attribution_math.py` | Portfolio weights = benchmark weights → allocation 0 in every segment (TASK-3 AC 3). |
| `test_carino_links_exactly` | `tests/test_attribution_math.py` | A hand-checked multi-day example; linked total = period active return within `tolerance`; the r_p = R_b day uses the limit. |
| `test_ols_nw` | `tests/test_stats.py` | With lag 0 the standard errors equal White's; on AR(1) residuals the NW t is smaller than the classical one; `nw_lag` rule values. |
| `test_regression_known_loading` | `tests/test_attribution.py` | Synthetic world: a portfolio built as 1.2 × market + 0.5 × HML + noise recovers the loadings within tolerance (TASK-3.5 AC 3). |
| `test_regression_minimum` | `tests/test_attribution.py` | Under `min_weeks`: `regression` null with a note; alpha never without t and n. |
| `test_world_fund_only` | `tests/test_attribution.py` | A portfolio of one world fund: zero allocation; selection equals the fund's difference to the proxy benchmark. |
| `test_unclassified_listed` | `tests/test_attribution.py` | A fund that isn't looked through is its own row with its real return; an unvalued holding blocks those days and is named (TASK-3.6 AC 2). |
| `test_min_months` | `tests/test_attribution.py` | Under 12 months: no attribution, a note (TASK-3.6 AC 1). |
| `test_reconciliation_adds_up` | `tests/test_attribution.py` | TWR − ACWI = trading/fees + proxies vs ACWI + attributed effects, exactly. |
| `test_attribution_api_contract` | `tests/test_api.py` | Validates against `AttributionView`; empty selection 200 with notes; no prices 503. |
| `test_cli_attribution_same_as_api` | `tests/test_cli_smoke.py` | `--json` equals the API's view for the same selection (TASK-3.7 AC 1). |
| settings | `tests/test_config.py` | `attribution:` validated; a misspelt key fails with its path. |
| layers | `tests/test_layers.py`, `lint-imports` | `attribution` in features; `model/attribution.py` imports no app or study module. |
| web | `pnpm -C web test` | The tab renders a view with nulls as "–"; the proxy statement is present. |

The synthetic world (`docs/testing.md`) gets the proxy tickers and a small `acwi_segments.csv`; no real holdings or
personal data in any fixture.

## 7. Docs

- **Textbook**: new chapter `laerebog/attribution.md` (*Attribution: hvorfor du slog eller tabte til ACWI*):
  Brinson–Fachler with a worked example, the currency effect, why linking is needed and how Carino does it, the proxy
  benchmark and the back-drifted weights, factor regression on the developed factors, alpha's t and the months to
  t = 2, skill vs luck. In `guide.yaml`, linked from `beta-og-alfa.md`. The disposition effect is added when TASK-3.11
  lands.
- **User guide**: a section in `brugervejledning/afkast.md` on the *Attribution* tab (how to read the reconciliation,
  the tables and the skill box, what the notes mean); thresholds via `{{settings:attribution.min_months}}` etc.;
  `indstillinger.md` for the new keys; `datalicenser.md` for the sources (steps 3 and 4).
- **Formulas**: `formler.md` gets the Brinson, currency, Carino and months-to-t formulas.
- **Developer docs**: `docs/architecture.md` (features: `attribution.py`; domain: `portfolios/segments.py`; kernel:
  `model/attribution.py`), `docs/data-conventions.md` (a *Attribution* section: daily periods, proxies, back-drift,
  DKK market factor), `docs/commands.md`, `docs/web-app.md`, `CLAUDE.md` main commands.
- **Release**: `CHANGELOG.md`, *Nyheder*; `uv run pytest -q tests/test_guide.py`.

## 8. Definition of done

The review's cross-cutting checklist ([section 3.3](analyses/product_owner.md#33-cross-cutting-definition-of-done-applies-to-every-feature)),
applied:

- [ ] Pure math in `model/attribution.py` and `model/stats.py`, I/O in `sources/`, segments in `portfolios/`, the
      feature in `attribution.py`; `lint-imports` and `tests/test_layers.py` pass.
- [ ] Missing prices, proxies, weights, factors and book days show as missing with notes, never 0; a source that
      parses to nothing fails loudly and keeps its cache.
- [ ] `acwi_segments.csv` in the history tier of `paths.REGISTRY`, append-only; `factors/daily.parquet` in the cache
      tier (under `factors/`).
- [ ] No new `userstore` table (nothing stateful from the user).
- [ ] `attribution:` and `factors.french_daily` in `settings.yaml` and `config_schema.py`; quoted in the guide with
      `{{settings:…}}`.
- [ ] `AttributionView` strict; TypeScript types regenerated; `pnpm -C web build` passes.
- [ ] `DATA_LICENSE.md` and `datalicenser.md` updated (French daily, iShares aggregate history, proxy tickers);
      the new downloads paced through `net.py`, logged in the source log, listed on *Data & coverage*.
- [ ] Textbook chapter and user-guide section per section 7; `tests/test_guide.py` passes.
- [ ] `summary.json` unchanged (a skill can read `radar attribution --json`).
- [ ] `uv run pytest -q`, `uv run ruff check`, `uv run mypy`, `pnpm -C web test` green.
- [ ] `CHANGELOG.md`, *Nyheder*, marketing `features.yaml`.
- [ ] Screenshot check in the demo copy (fictional investor), never the user's data folder; the leak check passes.

## 9. Decisions taken here, and open questions

**Decided** (TASK-3.1's three decisions and the review's open question):

1. **Sector proxies**: the Xtrackers MSCI World sector UCITS ETFs (accumulating, Xetra, from 2016-04; Financials
   from 2017-04), Real Estate from SPDR Dow Jones Global Real Estate (no MSCI World real estate UCITS on Yahoo);
   before a proxy's first price, the US sector ETFs in `sector_etfs.us`, with a note. MSCI World has no emerging
   markets (about a tenth of ACWI), and the page says so.
2. **Linking**: Carino (logarithmic), for its closed form and order independence; daily periods linked to months and
   to the period; tolerance 1e-8.
3. **ACWI weights for past months**: iShares serves no past holdings (spike, section 2). A weekly aggregate snapshot
   in the history tier from TASK-3.3 on; before the first snapshot, back-drifted weights, flagged per month, with the
   GICS-change note for sectors before 2023-03.
4. **Region segments**: country ETFs weighted by ACWI's own country weights inside each region, with a coverage
   threshold, rather than broad regional ETFs whose boundaries don't match the radar's regions (VGK includes the
   Nordics, which the radar keeps apart).
5. **Factor data**: French *daily* developed 5 factors and momentum, compounded to weeks (French has no weekly
   developed files); a separate cache file, so the monthly file's contract doesn't change.

**Open**:

1. Should the back-drift reach back before 2016 (the US fallback proxies would allow it), or should attribution start
   no earlier than the UCITS proxies? Suggest: allow it, with the fallback and back-drift notes. The user's books
   decide in practice.
2. Should *Returns*' period picker drive the tab, or should the tab have its own (attribution needs ≥ 12 months)?
   Suggest: the page's picker, with the minimum note when it's shorter.
3. A later study could run the same attribution on the A/B test's virtual portfolios point in time. Out of scope
   here; the math in `model/` keeps it possible.
