# F1 Portfolio X-ray: implementation plan

*Written 2026-10-25, from [the product owner review](analyses/product_owner.md) (feature F1), against
`main` at `cac5c6f` (0.2.0, after the `radar.datahome` / `radar.reporting` grouping). Analysis, not advice.*

## 1. Goal and non-goals

**Goal.** A live view of what the real portfolio is exposed to and where its risk comes from, against ACWI, in DKK.
It works for one account, several accounts or a tag, using the same exposure and risk code that `propose evaluate`
uses, so a proposal and the X-ray never disagree about the same holdings.

User stories (MVP):

1. I see my sector, region and currency weights and the active weights vs ACWI. World funds are looked through,
   and the page says how much of my value it could look through for each dimension.
2. I see ex-ante volatility, beta and tracking error vs ACWI, and each position's share of total risk and of
   active risk (tracking error).
3. I see concentration as numbers: effective N, top-5 share, the largest position and the largest risk
   contributor, and the pairs of holdings that move together (correlation above a threshold).
4. I see how today's holdings would have done in the configured stress windows, next to ACWI.
5. I see the factor tilts of today's holdings (the regression the ticker profile already runs, on the portfolio's
   backcast weekly returns).
6. The same data from the CLI: `uv run radar xray [NAME…] [--tag T] [--json]`.

**Non-goals for this plan** (later plans or later features):

- Active share (needs ACWI's stock-level weights mapped to Yahoo symbols).
- Look-through of non-world funds by region and currency from issuer holdings files.
- Hierarchical clustering view, what-if weight editing in the browser.
- Holdings-weighted momentum and Q+V tilts (an optional step 7 below, can be dropped).
- Attribution (F4), tax (F3), rebalancing (F10).
- A section in `dashboard.json` or `summary.json`. The X-ray is computed live per request, like `/api/me`, because
  it depends on the user's own edits.

## 2. Licence check

No new data source. It uses Yahoo prices and the cached Yahoo fund detail, iShares SSAC holdings (ACWI weights) and
`universe.yaml`, all already listed in `DATA_LICENSE.md`. Only the *Used for* column changes: add "portfolio X-ray"
to the Yahoo and iShares rows, in `DATA_LICENSE.md` and `guide/brugervejledning/datalicenser.md`.

## 3. What the code does today (findings that shape the design)

| # | Finding | Where | Consequence |
|---|---|---|---|
| C1 | The exposure and risk engine exists but lives in the `propose` feature package: `holdings_book`, `ticker_meta`, `exposures`, `look_through` (exposure); `shrunk_cov`, `ex_ante_risk` (incl. per-name variance contributions, TE, beta, diversification ratio), `weekly_returns`, `stress`, `realised_dd` (riskmodel); `Prices` (pricing); `factors` (evaluation) | `src/radar/propose/{exposure,riskmodel,pricing,evaluation}.py` | A second feature can't import from `propose` without coupling the two features. Move the shared pieces down a layer (step 1). |
| C2 | Their settings live under `propose:` (`history_weeks`, `min_weeks`, `shrink`, `stress`, `look_through`). None of them is in `RULE_KEYS` | `config/settings.yaml`, `config_schema.Propose`, `propose/rules.py` | They can move to `risk:` without changing any stored rule hash. |
| C3 | A fund that isn't a world fund or a `sector_etfs` entry gets sector `(fund)`, the **listing** region (`universe.region_for`: by suffix, default `us`) and the **quote** currency. CSPX.L (S&P 500 in USD, listed in London) counts as region `europe`, currency `USD` (quoted in USD); a EUR-quoted Nasdaq-100 fund would count as EUR | `propose/exposure.ticker_meta`, `universe.region_for` | This is misleading for a portfolio of UCITS ETFs, which is the user's typical portfolio. Fix it for both features (step 3): a fund is looked through, or shown as *fund, not looked through*. It is never filed under its listing. |
| C4 | `region_for` sends unknown suffixes to `us` (e.g. `.TO`), while ACWI's file sends Canada to `other`; `.AX` is `asia` in the radar and `other` in ACWI | `universe.py`, `sources/constituents.acwi_region` | Small active-weight errors. Align the two maps in step 3 and test that every key of ACWI's weights is a key the radar can produce. |
| C5 | `external.detail()` fetches from Yahoo when the cache is older than `max_age_hours` | `sources/external.py:427` | The X-ray request must not reach the network: it needs a cache-only read of the fund detail (step 3). |
| C6 | `holdings_book` values holdings only; cash isn't included | `propose/exposure.py` | The X-ray shows cash as its own line (from `performance.cash_balance` for portfolios with a ledger) and computes risk on the invested value, saying so. |
| C7 | `ex_ante_risk` already returns variance contributions per name (`contributions`) and models a world fund without its own prices as ACWI | `propose/riskmodel.py` | Add only the active-risk contributions and MCTR; don't reimplement anything. |

## 4. Design

### 4.1 Modules, by layer

| Layer | Module | Change |
|---|---|---|
| domain | `portfolios/prices.py` | **Moved** from `propose/pricing.py` (`Prices`), unchanged. |
| domain | `portfolios/exposure.py` | **Moved** from `propose/exposure.py`: `holdings_book`, `ticker_meta`, `annotate`, `exposures`, `DIMS`, `look_through`. In step 3: fund classification and coverage. |
| domain | `portfolios/riskmodel.py` | **Moved** from `propose/riskmodel.py`: `shrunk_cov`, `ex_ante_risk`, `weekly_returns`, `stress`, `realised_dd`, plus `factors` from `propose/evaluation.py` (renamed `factor_tilts`). `bootstrap` stays in `propose/` (proposal-only, reads `propose.bootstrap`). In step 2: `active_contributions`, `mctr`, `concentration`, `correlated_pairs`. |
| features | `xray.py` (new top-level module) | Builds the X-ray for a portfolio selection: book → meta → exposures → covariance → risk → concentration → stress → factor tilts, with notes. No math of its own. |
| features | `api_models/xray.py` | `XrayView` and its parts (`extra="forbid"`), re-exported by `api_models`. |
| interfaces | `api/xray.py` | `GET /api/xray`, a new router included **last** in `api/app.py`, so the OpenAPI order of the others doesn't move. |
| interfaces | `cli/portfolios.py` | `radar xray` command next to `radar performance`. |
| web | `web/src/pages/Xray.tsx` | New page `/xray` in the *Mine* group (`web/src/lib/nav.ts`), using `PortfolioPicker`, `DataTable`, `Tabs`. |

Why `portfolios/` and not `model/`: `model/` is for what the app and the *studies* must compute the same way, and no
study uses the risk model (of the moved names, `backtest/propose_study.py` uses only `propose.annotate` and
`propose.DIMS`; they move with exposure, and propose_study imports them from `portfolios.exposure`).
`portfolios/` already means "your portfolios, from the transactions", and the domain layer may import `sources/`,
`signals/`, `universe` and `market`, which is everything the moved code needs. No change to the layer contract
apart from adding `xray` to the features layer in `pyproject.toml`.

The `propose` facade does **not** keep re-exporting the moved names: the architecture rule is that a name is read
from the module that defines it (`tests/test_layers.py`). The facade and every caller (`propose/*`, `backtest/propose_study.py`, `tests/test_propose.py`) switch to `portfolios.exposure`,
`portfolios.riskmodel` and `portfolios.prices` in the same PR.

### 4.2 Settings

Move from `propose:` to `risk:` (and the schema from `Propose` to `Risk`), values unchanged:

```yaml
risk:
  windows: {1y: 52, 3y: 156}
  min_weeks: 26
  factors: [MTUM, VLUE, QUAL, USMV]
  budget: 0.01
  covariance: {history_weeks: 156, min_weeks: 26, shrink: 0.3}   # was propose.history_weeks / min_weeks / shrink
  world_funds: [...]       # was propose.look_through: the same list of broad world funds, unchanged
  stress:                                                          # was propose.stress
    - {key: covid, label: "Covid crash", start: 2020-02-19, end: 2020-03-23}
    - …
  xray:                                                            # new
    min_coverage: 0.5      # below this share of invested value in the risk model: no risk figures, only the note
    warn_coverage: 0.8     # below this: the figures are shown with a coverage warning
    pair_corr: 0.7         # pairs of holdings above this weekly correlation are listed as moving together
```

- `propose` reads `typed().risk.covariance` etc. where it read its own keys. `look_through()` returns the benchmark,
  `benchmark.ucits`, `risk.world_funds` and (proposal side) the ETF filler's tickers. The filler (SSAC.L / ACWI) is
  already the benchmark and its UCITS class, so the shared function needs nothing from `propose`.
- `propose.min_weeks` is also read by `bootstrap` and `propose_study`: check every reader with
  `grep -rn "\.min_weeks\|history_weeks\|\.shrink\b"` and keep `propose.min_weeks` if a proposal-only reader needs it.
  The move must not change a proposal's numbers.
- `rule_hash` is unaffected (none of these keys is in `RULE_KEYS`); a test asserts the hash of the shipped settings is
  unchanged by the move.
- *Nyheder*: "if you changed `propose.stress` or `propose.look_through`, the keys have moved to `risk:`". An old key
  fails loudly on load, naming the key (the schema already does this).

### 4.3 Method

**Book.** `holdings_book(market, prices, ids)` for the selection (`api/common.selection`; None = your real
portfolios). Positions without a DKK value (no price or no rate) are listed under *unvalued* with their quantity and
left out of every weight. They are never valued at 0.

**Cash.** For portfolios with a ledger (`performance.has_ledger`), the last value of `performance.cash_balance`, per
portfolio, summed. Implicit-cash portfolios contribute no cash line, and a note says which ones. Weights are shown two
ways: of *invested value* (the default; the basis of the risk model) and of *total value* (cash included, so the cash
share is visible).

**Fund classification** (step 3; shared with proposals). Each held ticker gets one class:

| Class | Rule | Sector | Region | Currency |
|---|---|---|---|---|
| `world` | `look_through()` | ACWI weights | ACWI weights | ACWI weights |
| `sector_fund` | in `universe.yaml` `sector_etfs`, or the cached Yahoo fund detail has one sector ≥ 50 % (the rule `profile.py` uses) | that sector, or the Yahoo sector weights (remainder `fund: other`) | the `sector_etfs` region key if listed there, else `fund: not looked through` | `USD` for the `us` sector map, else `fund: not looked through` |
| `fund_sectors` | other fund with cached Yahoo `sector_weights` | Yahoo's weights (remainder `fund: other`) | `fund: not looked through` | `fund: not looked through` |
| `fund` | other fund, no usable detail | `fund: not looked through` | same | same |
| `stock` | everything else | `universe.sectors` | `region_for` (aligned with ACWI's map, C4) | quote currency (pence → GBP) |

Each dimension carries **coverage**: the share of invested value that is looked through or classified. The page
shows "sector: 92 % of value looked through". The `fund: …` keys are never spread out by guesswork. The fund detail
is read **from the cache only** (C5): add `external.cached_detail(ticker) -> (raw, status, fetched)`, which never
fetches. A detail older than `profile.max_age_hours` is still used, with its date shown.

*Effect on proposals.* Proposal exposure tables for held funds change from listing-based to looked-through or *not
looked through*. Caps on region and currency then treat `fund: not looked through` as its own bucket, never as
active weight in a real region. That's a behaviour change, so it goes in its own PR with a CHANGELOG line. The
proposal study only scores stocks, so it is unaffected; a test holds `propose_study` output equal on the test world
before and after.

**Covariance.** `shrunk_cov` on weekly (W-FRI) DKK returns of the holdings plus ACWI over `risk.covariance.history_weeks`,
columns with fewer than `min_weeks` dropped, shrunk `shrink` towards constant correlation (as proposals do).

**Risk figures** (all annualised with 52 weeks; on invested value; *w* = weights over the names in the model,
Σ = the covariance, *b* = ACWI):

- σ_p = √(wᵀΣw · 52), β = wᵀΣ_b / σ_b², TE = √((wᵀΣw − 2wᵀΣ_b + σ_b²) · 52), diversification ratio
  (already in `ex_ante_risk`).
- Share of total risk: CTR_i / σ_p = w_i (Σw)_i / wᵀΣw (already `contributions`); sums to 1.
- Marginal contribution: MCTR_i = (Σw)_i / √(wᵀΣw) · √52: how σ_p moves per unit of weight.
- Share of active risk: with active vector *a* = (w, −1 on ACWI), share_i = a_i (Σa)_i / aᵀΣa over the holdings
  and the ACWI leg; sums to 1. A share below 0 is a position that *reduces* tracking error, and is shown as such.
- **Coverage**: the share of invested value inside the model. Names left out (too little history) are listed with
  their weight. Below `xray.min_coverage` no figure is shown; below `xray.warn_coverage` figures carry a warning.

**Realised next to ex-ante.** For the same selection: realised volatility and max drawdown of the time-weighted index
over the last year from `performance.compare(ids)`. The difference is explained on the page: *ex-ante* uses today's
weights on past returns; *realised* is what you actually held.

**Concentration.** On position weights (invested value): effective N = 1/Σw², top-5 share, largest position, largest
CTR. A world fund counts as one position here, which understates diversification; the page says so and shows the
count of world-fund value. Pairs of holdings with weekly correlation above `xray.pair_corr` over the covariance
window (from `signals/risk.correlation`), largest first, with their combined weight.

**Stress.** `riskmodel.stress(values, prices, bench)` over `risk.stress`: today's DKK weights replayed through each
window, next to ACWI, with coverage. A window where less than half the value has prices is "not replayed" (the
existing rule). The history only reaches back `history_years`, so a window before it shows as not covered.

**Factor tilts.** `factor_tilts(values, R, market)` (the old `propose.evaluation.factors`): a regression of the
backcast weekly portfolio return on ACWI and the `risk.factors` ETFs' spreads over ACWI, with t-stats, R² and
`alpha_basis`. These are US factor ETFs and the result is descriptive; the page says both.

### 4.4 API

`GET /api/xray?portfolio=&tag=&scope=` → `XrayView`:

```text
XrayView
  asof, generated, selection: {ids, names, scope}
  totals: {invested_dkk, cash_dkk | null, unvalued: [{symbol, quantity}], cash_note | null}
  exposure: for each dim (sector, region, currency):
      rows: [{key, weight, acwi | null, active | null}]  (sorted by |active|, then weight)
      coverage, note | null
  classes: [{symbol, class, value_dkk, weight, detail_asof | null}]
  risk: {vol_ann, beta, te_ann, div_ratio, coverage, warn: bool,
         realised_vol_1y | null, realised_max_dd_1y | null,
         positions: [{symbol, weight, share_total, share_active, mctr_ann}],
         acwi_leg_share_active, excluded: [{symbol, weight, reason}], window_weeks, shrink} | null
  concentration: {effective_n, top5_share, largest: {symbol, weight}, largest_ctr: {symbol, share},
                  world_fund_weight, pairs: [{a, b, corr, weight}]}
  stress: [{key, label, start, end, coverage, ret, max_dd, acwi_ret, acwi_max_dd, missing, note}]
  factors: {n_weeks, r2, alpha_ann, alpha_t, alpha_basis, loadings: [{factor, beta, t}]} | null
  notes: [str]
```

- 503 without prices (like the other live endpoints); an empty selection returns a valid view with empty tables and
  a note, not an error.
- Cached per (selection ids, market mtime, transactions version) with the `performance._cached` pattern; a new
  trade or a price update invalidates it.
- Then `pnpm -C web gen:api`; `client.ts` gets `xray(sel)`.

### 4.5 CLI

`uv run radar xray [NAME…] [--tag T] [--scope real|virtual|all] [--json]` in `cli/portfolios.py`: tables for
exposure (top active weights per dimension), risk (vol, beta, TE, coverage, the top five risk contributors),
concentration, stress; `--json` prints the `XrayView` dict. Names resolve as `radar performance` resolves them.

### 4.6 Web page

`/xray`, label *X-ray*, blurb "What you're exposed to and where the risk sits, vs ACWI", in the *Mine* group after
*Holdings & watchlist*. Selection in the URL as `?pf=` (same as `/me` and `/returns`). Layout:

1. **Header tiles**: invested value, cash share, σ_p, β, TE, effective N, coverage (amber below `warn_coverage`).
2. **Exposure** (tabs: sector / region / currency): a diverging bar per key for active weight, a table with weight,
   ACWI and active, and the coverage line under it.
3. **Risk**: a table of positions with weight, share of total risk, share of active risk and MCTR; excluded names
   below it; the realised-vs-ex-ante line.
4. **Concentration**: the numbers and the list of correlated pairs.
5. **Stress**: a table of windows with portfolio vs ACWI.
6. **Factor tilts**: loadings with t, R², the descriptive caveat.
7. **Notes**: everything in `notes`, plus a link to the guide chapter (`page_links`).

Every ticker cell uses `TickerLink`. Terms (TE, MCTR, effective N) get `Term` tooltips via `lib/glossary.ts`, with
`glossary_links` to the textbook.

## 5. Steps as PRs

Each PR is green on `uv run pytest -q`, `uv run ruff check`, `uv run mypy`, `uv run lint-imports`, and carries its
guide changes.

| # | PR | Contents | Behaviour change |
|---|---|---|---|
| 1 | **Move the engine down** | `propose/pricing.py` → `portfolios/prices.py`; `propose/exposure.py` → `portfolios/exposure.py`; `propose/riskmodel.py` (minus `bootstrap`) and `evaluation.factors` → `portfolios/riskmodel.py`. Callers, the `propose` facade, `backtest/propose_study.py` and the tests updated; `docs/architecture.md` (Domain: `portfolios/`, Features: `propose/`) updated. | None: a test runs `propose candidates` and `propose evaluate` on the test world and compares to a stored JSON snapshot taken before the move. |
| 2 | **Settings to `risk:`** | Keys moved per 4.2, schema, readers, `guide/brugervejledning/indstillinger.md`; new `risk.xray` block. | None (same values); a test asserts the rule hash is unchanged. |
| 3 | **Honest fund classification** | Fund classes (4.3), `external.cached_detail`, `region_for` aligned with ACWI's regions (C4), coverage per dimension in `exposures()`. Proposals use it too. `laerebog/portefoeljeforslag.md` and CHANGELOG note the change for held funds. | Yes, for proposals' exposure of held funds (intended). `propose_study` output unchanged (test). |
| 4 | **Risk additions** | `active_contributions`, `mctr`, `concentration`, `correlated_pairs` in `portfolios/riskmodel.py` (pure functions of arrays and frames), with unit tests. | None (new functions). |
| 5 | **`xray.py`, API, CLI** | `src/radar/xray.py`, `api_models/xray.py`, `api/xray.py`, `radar xray`, `pyproject.toml` layers (`xray` in features), `docs/web-app.md`, `docs/commands.md`, `CLAUDE.md` main commands. | New endpoint and command. |
| 6 | **Web page and guide** | `Xray.tsx`, nav, client, glossary, `page_links`; new chapter `guide/brugervejledning/xray.md` in `guide.yaml` (*Dig og dine penge*, after *Mine beholdninger og watchlist*); textbook additions (section 7); `DATA_LICENSE.md` *Used for*; marketing `features.yaml` entry. | New page. |
| 7 | *(optional)* **Score tilts** | Value-weighted momentum score and K+V percentile of the holdings vs the universe's median, from the live `/api/me` rows; a tile on the page. | New tile. |
| 8 | **Release** | `CHANGELOG.md` and *Nyheder* (incl. the moved settings keys), `/market-brief` skill: read `radar xray --json` for the "your holdings" section (optional). | – |

Steps 1–2 can merge before anything is visible; 3 and 4 are independent of each other; 5 needs 1, 2 and 4; 6 needs 5.

## 6. Tests

Named after the acceptance criteria in the review, plus the ones the findings call for:

| Test | File | Checks |
|---|---|---|
| `test_move_keeps_proposals_identical` | `tests/test_propose.py` | Step 1: `candidates` and `evaluate` on the test world equal the pre-move snapshot. |
| `test_rule_hash_unchanged_by_settings_move` | `tests/test_propose.py` | Step 2. |
| `test_fund_classes` | `tests/test_portfolios.py` (or a new `tests/test_exposure.py`) | Each class from hand-made fund details: world fund, `sector_etfs` fund, Yahoo sector fund ≥ 50 %, diversified fund with sector weights, fund without detail, stock. CSPX-like fund is *not* filed under `europe`. |
| `test_exposure_coverage` | same | Coverage per dimension equals the classified share of value; `fund: not looked through` never appears in `active` as a real region. |
| `test_acwi_region_keys_match` | `tests/test_sources.py` | Every region key `acwi_region` can produce is a key `region_for` can produce, and vice versa (C4). |
| `test_cached_detail_never_fetches` | `tests/test_external.py` | With the network layer patched to fail, `cached_detail` returns the cache or `missing`. |
| `test_risk_contributions_sum_to_one` | `tests/test_risk.py` | Hand-computed 3-asset Σ: shares of total risk and of active risk (incl. the ACWI leg) each sum to 1; MCTR matches the finite-difference derivative of σ_p. |
| `test_effective_n` | `tests/test_risk.py` | Equal weights over n give n; one position gives 1. |
| `test_xray_same_as_proposal` | `tests/test_xray.py` | For the same holdings, `xray` exposure and `ex_ante_risk` before-figures equal `propose evaluate`'s `exposure.before` and `risk.before`. |
| `test_xray_missing_price_is_unvalued` | `tests/test_xray.py` | A holding without a price is in `unvalued`, absent from weights, never a 0 % return; risk coverage reflects it. |
| `test_xray_low_coverage_hides_risk` | `tests/test_xray.py` | Below `min_coverage`: `risk` is null with a note; between min and warn: `warn` is true. |
| `test_xray_cash_lines` | `tests/test_xray.py` | Ledger portfolio: cash shown; implicit portfolio: no cash, note names it. |
| `test_xray_api_contract` | `tests/test_api.py` | `GET /api/xray` validates against `XrayView`; empty selection returns 200 with notes; no prices returns 503. |
| `test_cli_xray` | `tests/test_cli_smoke.py` | `radar xray --json` runs on the test world and prints valid JSON. |
| layers | `tests/test_layers.py`, `lint-imports` | `xray` in features; no caller reads a moved name through `propose`. |
| web | `pnpm -C web test` | Nav includes `/xray`; a formatting test for negative risk shares. |

## 7. Docs

- **User guide**: new chapter `brugervejledning/xray.md` (*Røntgen af porteføljen*): what the page shows, how to read
  active weights and risk shares, coverage and *not looked through*, ex-ante vs realised, the CLI. Thresholds
  quoted with `{{settings:risk.xray.min_coverage|pct}}` etc. Linked from `navigation.md`, `beholdninger.md` and
  `afkast.md`; `indstillinger.md` for the moved and new keys.
- **Textbook**:
  - `diversifikation.md`: effective N, risk contribution and MCTR, why a 5 % position can carry 15 % of the risk.
  - `beta-og-alfa.md`: tracking error, ex-ante vs realised, active risk contributions.
  - `volatilitet-og-drawdown.md`: shrunk covariance in one paragraph (a link from the existing proposals text).
  - `portefoeljeforslag.md`: the *Sådan gør radaren* part now points to the shared engine and the fund classes.
  - `formler.md`: the formulas in 4.3.
- **Developer docs**: `docs/architecture.md` (portfolios/ gets the engine; features gets `xray.py`),
  `docs/commands.md` (`radar xray`), `docs/web-app.md` (endpoint), `CLAUDE.md` main commands (one line).
- **Data licence**: the *Used for* column (section 2).
- **Release**: `CHANGELOG.md`, *Nyheder*; `uv run pytest -q tests/test_guide.py`.

## 8. Definition of done

The review's cross-cutting checklist ([section 3.3](analyses/product_owner.md#33-cross-cutting-definition-of-done-applies-to-every-feature)),
applied:

- [ ] Shared engine in `portfolios/`, the feature in `xray.py`; `lint-imports` and `tests/test_layers.py` pass;
      proposals and the X-ray share one code path (test).
- [ ] Missing prices, rates, fund details and history show as missing with notes; nothing is 0 by default; no
      network call from the request path.
- [ ] No new files written (live computation, in-memory cache): nothing to add to `paths.REGISTRY`. If a cache
      file is added later, it goes in the cache tier.
- [ ] No new `userstore` table.
- [ ] Settings in `settings.yaml` and `config_schema.py`; guide quotes them with `{{settings:…}}`.
- [ ] `XrayView` strict; TypeScript types regenerated; `pnpm -C web build` passes.
- [ ] `DATA_LICENSE.md` and `datalicenser.md` *Used for* updated.
- [ ] Guide and textbook chapters per section 7; `tests/test_guide.py` passes.
- [ ] `summary.json` unchanged (the skills read `radar xray --json` instead).
- [ ] `uv run pytest -q`, `uv run ruff check`, `uv run mypy`, `pnpm -C web test` green.
- [ ] `CHANGELOG.md`, *Nyheder*, marketing `features.yaml`.
- [ ] Screenshot check in the demo copy (`/marketing` workspace, fictional investor), never the user's data folder.

## 9. Decisions taken here, and open questions

**Decided** (the review's open questions):

- A page of its own (`/xray`), not a fifth tab on *Portfolio*: it reads a portfolio selection like `/me` and
  `/returns`, and *Portfolio* is about entering data.
- Virtual portfolios: yes, through the picker (`scope=virtual`, tags), so an experiment can be X-rayed.
- Active share: not in this plan (needs stock-level ACWI weights mapped to Yahoo symbols); a later plan.

**Open**:

1. Should held non-world iShares funds be looked through by region and currency from their own holdings files (the
   SSAC parser generalises)? It would raise coverage a lot for a UCITS-heavy portfolio, at the cost of one download
   per held fund per week. Suggest: a follow-up plan right after this one.
2. `world_funds` holds MSCI World funds counted with ACWI's weights (no emerging markets). Keep the approximation
   with its note, or give MSCI World its own weights from an iShares MSCI World holdings file? Suggest: the latter, in the
   same follow-up as 1.
3. Should the X-ray's coverage and TE feed the monthly brief automatically (via `radar xray --json` in
   `/market-brief`), or stay on demand? Suggest: in step 8, as one short paragraph.
