# F3 Danish tax engine: implementation plan

*Written 2026-10-25, from [the product owner review](analyses/product_owner.md) (feature F3), against `main` at
`86bd937` (after F1, F2, F4 and F5 part 2). Backlog: TASK-5 and its subtasks. Analysis, not advice, and not tax
advice: the user's *årsopgørelse* wins.*

## 1. Goal and non-goals

**Goal.** For each real account and tax year, estimate what Danish tax the radar's own records imply: realised gains
and losses with the average-cost method in DKK, dividends, lager gains on lager-taxed holdings, the aktiesparekonto's
and the pension account's yearly tax base with losses carried forward, and an estimated tax with the progression
limit. Every number is labelled an estimate, says which year's rules it used, and names what it left out.

User stories (MVP):

1. For each account and tax year I see realised gains and losses (average-cost method, in DKK at each trade day's
   rate), dividends, lager gains on lager-taxed securities, the ASK's and the pension account's tax base with the
   loss carried forward, and an estimated tax.
2. For each tax person I see the year's share income (*aktieindkomst*) across their *frie midler* accounts, how much
   of the progression limit (*progressionsgrænse*) it uses, the capital income (*kapitalindkomst*) from funds off the
   positive list, the loss pools and what is carried forward.
3. A holding the radar can't classify (a fund without an ISIN, a year without a positive-list sheet) is listed as
   "unknown classification" with its value, left out of the estimate, and can be fixed from the page.
4. The same data from the CLI: `uv run radar tax year 2026 [--portfolio P] [--person N] [--json]`.

**Non-goals for this plan** (TASK-5.13 to 5.16, low priority, each gets a short plan when it starts):

- After-tax TWR and the after-tax ACWI twin on *Returns* (TASK-5.13).
- The year-end planner: unrealised gains and losses, progression-limit headroom, candidate losses to realise, the
  ASK's deposit headroom (TASK-5.14).
- An after-tax mode for `sim`, `propose evaluate` and `study redeploy` (TASK-5.15).
- A foreign withholding-tax estimate on dividends by domicile (TASK-5.16).
- After-tax attribution (F4 follow-up, after 5.13).
- Not modelled at all, and listed as such in the guide: the spouse transfer of unused progression limit, unlisted
  shares, bonds and other capital income outside the radar, the negative share income's tax value against other
  income (shown as carried forward only), *kildeartsbegrænsning* beyond the pools in 4.3, the ASK's closing rules,
  pension payout tax, *virksomhedsskat*, and anything before the radar's first transaction (except the opening
  balances in 4.2).

## 2. Licence check

| Source | New use | Terms | Outcome |
|---|---|---|---|
| **skat.dk** (Skattestyrelsen), rates and limits | Typed by hand into `config/tax_dk.yaml`: share-income rates, progression limit, ASK rate and deposit cap, PAL rate, each with its URL and the date read | Public-sector information (*lov om videreanvendelse af den offentlige sektors informationer*); the numbers are facts of law | Allowed. New row in `DATA_LICENSE.md` and `datalicenser.md` (TASK-5.2): "typed in by hand, not downloaded". |
| **SKAT positive list** | Every year's sheet, not only the newest (TASK-5.3) | Existing row | *Used for* gets "the tax engine's classification per year". |

No new host, no new download.

## 3. What the code does today (findings that shape the design)

| # | Finding | Where | Consequence |
|---|---|---|---|
| C1 | `replay` keeps the average cost in the security's quote currency, and a sale's fee is ignored | `portfolios/trades.replay` | Tax needs the average in DKK at each trade day's rate, and sale fees deducted from the proceeds. A new DKK replay in `model/tax.py` (4.3); `replay` stays as it is, since positions, *Returns* and the X-ray rely on it. |
| C2 | The DKK rate of a trade: its own `fx_rate`, else Yahoo's rate that day | `portfolios/performance.trade_fx`, `trade_cash_dkk` | The tax engine uses the same rule, so pre-tax and tax numbers agree on a trade's DKK value. A trade with no rate makes its security's gains missing, named. |
| C3 | `positions()` replays per symbol over every portfolio given, or per (symbol, portfolio) | `portfolios/trades.positions` | SKAT's average is per person over their *frie midler* accounts; ASK and pension stand apart. The engine groups trades by (tax person, security) for *frie midler* and by (portfolio, security) otherwise. |
| C4 | Portfolios have a `kind` (`ask`, `frie_midler`, `pension`, `other`) but no owner | `userstore` migration, `portfolios.kind` | New `tax_persons` table and `portfolios.tax_person_id` (4.2). `other` accounts are listed, with no estimate. |
| C5 | Transactions store no ISIN. ISINs exist in `universe.yaml` (ETFs), as keys in `symbol_map` (from broker imports) and in discovery's `isin_map.csv` | `userstore.symbol_map`, `importers.commit`, `discovery/scan.py` | New `instruments` table (symbol → ISIN, class override), filled from those three and editable (4.2). Stocks are classified by Yahoo's `quoteType` and need no ISIN; funds need one. |
| C6 | `positive_list.load()` reads only the newest year's sheet; the file path comes from `config.ROOT` | `sources/positive_list.py`, `config.POSITIVE_LIST_FILE` | `load_years()` returns every year's ISIN set; `status(isin, year)` gives yes / no / no sheet. `load()`/`isins()` keep their meaning. The path moves to `paths` with a tier while the module is open. |
| C7 | The ASK deposit cap is a `propose` setting (`ask_deposit_cap`, `ask_cap_year`), null by default | `config/settings.yaml`, `propose/draft.ask_account` | The cap moves to `tax_dk.yaml` per year; `ask_account` reads it there; the two settings keys are removed with a note in `CHANGELOG.md`. |
| C8 | `Book.positions` has each symbol's DKK value per session (0 = not held, NaN = unknown) | `portfolios/performance.book` (from F4) | Year-start and year-end values for lager come from here, at the last session on or before 31 Dec; a NaN makes that holding's lager missing, never 0. |
| C9 | Dividends are imported as DKK amounts with their instrument. Whether a broker books them before or after foreign withholding tax isn't recorded | `importers` (`DIVIDEND` aliases, `_cash_row`) | MVP: dividends "as booked", with a note on the page. Gross vs net and the withholding estimate are TASK-5.16. |
| C10 | `DIVIDEND` rows exist under both dividend policies; under `reinvested` they don't move the book's cash | `performance.cash_moves` | Tax counts every `DIVIDEND` row regardless of the policy: the policy is about the return index, not about income. |
| C11 | The guide's textbook chapter says "Radaren beregner ingen skat" and lists the pooled-average caveat | `guide/laerebog/skat.md` | Rewritten in TASK-5.11; its worked examples become golden tests (4.7). |

## 4. Design

### 4.1 Modules, by layer

| Layer | Module | Change |
|---|---|---|
| infrastructure | `paths.py` | `POSITIVE_LIST_FILE` moves here (personal tier: the user downloads it; older years' sheets can't always be fetched again). |
| sources | `sources/positive_list.py` | `load_years() -> dict[int, set[str]]`, `status(isin, year, years)` → `yes`, `no`, `no_sheet`, `no_isin`. A sheet that parses to no ISINs raises (as today). |
| domain | `portfolios/taxrules.py` (new) | Loads and validates `config/tax_dk.yaml` (`config_schema.TaxRules`); `rules(year)` returns the year's rules or raises `NoRules(year)`. |
| domain | `portfolios/taxinputs.py` (new) | Per account and year, the engine's inputs: trades with DKK rates (C2), dividends, deposits and withdrawals, year-start and year-end DKK values per holding (C8), each holding's class for the year (4.3), the openings. Reads `userstore`, `positive_list`, prices. |
| domain | `userstore` | Migrations for `tax_persons`, `portfolios.tax_person_id`, `instruments`, `tax_openings` (4.2); CRUD functions. |
| kernel | `model/tax.py` (new) | Pure math: the DKK average-cost replay with gains per sale, lager per holding and year, the ASK/PAL pool with carry-forward, share-income netting and progression, the loss pools. Dataclasses in, dataclasses out; no I/O, no dates beyond the inputs. |
| features | `tax.py` (new top-level) | For a year and a selection: inputs → engine → per-account and per-person reports, unknowns, notes. No math of its own. Added to the features layer and the "app never runs a study" contract in `pyproject.toml`. |
| features | `api_models/tax.py` | `TaxYearView` and its parts (`extra="forbid"`), and the edit models for instruments, persons and openings. |
| interfaces | `api/tax.py` | `GET /api/tax`, the edit endpoints (4.5). |
| interfaces | `cli/tax.py` | `radar tax year|classify|isin|person|opening` (4.6). |
| web | `web/src/pages/Portfolio.tsx`, `web/src/components/TaxTab.tsx` | A *Tax* tab on *Portfolio* (4.7). |

Why `model/` for the math: TASK-5.15 runs the same rules inside simulations and studies, and anything the app shows
and a study tests lives once in `model/`.

### 4.2 Data

**Rules** (`config/tax_dk.yaml`, committed, no personal data). One block per income year, every number with its
source; a year is only used when `verified` is set:

```yaml
# Danish tax rules per income year, typed in by hand from skat.dk (model/tax.py; analysis, not tax advice).
# Each number has its source and the day it was read. A year without a block, or without `verified`, gives
# "no rules for <year>": the engine never reuses another year's numbers silently.
years:
  2026:
    verified: "2026-10-25"            # the day every number below was checked against its source
    share_income:
      low_rate: 0.27
      high_rate: 0.42
      progression_limit: …            # DKK per person (spouse transfer: not modelled)
      source: https://skat.dk/…
    ask:
      rate: 0.17
      deposit_cap: …                  # DKK, the year's ceiling on net deposits
      source: https://skat.dk/…
    pension:
      pal_rate: 0.153
      source: https://skat.dk/…
    loss_pools:                       # which income a pool's loss may offset (4.3); checked against Den juridiske vejledning
      listed_shares: [listed_shares, dividends_listed, pl_funds]
      source: https://info.skat.dk/…
```

The `…` are filled in TASK-5.2 from skat.dk, never from memory. 2025 and 2026 are entered; earlier years only if the
user's history needs them (the report says "no rules for 2024" otherwise).

**Tax persons** (`userstore`, append-only migration):

```text
tax_persons      id, name (unique), capital_income_rate (REAL NULL: the person's marginal rate on capital income,
                 typed by the user; null = the base is shown, no tax on it), note, created_at, updated_at
portfolios       + tax_person_id INTEGER NULL REFERENCES tax_persons(id) ON DELETE SET NULL
```

The migration creates one person, "Me", and links every real `frie_midler`, `ask` and `pension` portfolio to it.
Virtual portfolios keep null (TASK-5.15 decides their default).

**Instruments** (`userstore`):

```text
instruments      symbol (PK), isin (NULL), tax_class (NULL = automatic; else stock | pl_fund | fund |
                 dk_distributing), source (manual | import | universe | discovery), note, updated_at
```

Filled on first use, in this order, never overwriting a `manual` row: the import's ISIN for the symbol
(`symbol_map`), `universe.yaml`'s `isin:`, discovery's `isin_map.csv`. Each fill records its source.

**Openings** (`userstore`): what the radar can't see, entered once by hand.

```text
tax_openings     id, year (the first year it applies to), pool (ask_loss | pension_loss | listed_share_loss |
                 share_income_loss), portfolio_id (ASK/pension) or tax_person_id (frie midler pools), amount (DKK,
                 > 0, a loss carried into that year), note, created_at
```

Losses carried forward from before the history, e.g. an ASK's negative return from before the first import. No new
files: everything personal is in `radar.db`; `paths.REGISTRY` gets only the positive-list file (C6).

### 4.3 Method

**Classification per holding and year** (`taxinputs`, from `instruments` and the year's positive-list sheet):

| Class | When | Frie midler | ASK / pension |
|---|---|---|---|
| `stock` | `quoteType` EQUITY, or set by hand | realisation, share income | in the account's pool |
| `pl_fund` | a fund whose ISIN is on that year's sheet | lager, share income | in the pool |
| `fund` | a fund whose ISIN is not on that year's sheet, not Danish | lager, capital income | ASK: a warning (not allowed there), still in the pool; pension: in the pool |
| `dk_distributing` | set by hand (a DK ISIN off the list is asked about, not guessed) | realisation, share income; its dividends as share income | in the pool |
| `unknown` | a fund without an ISIN, a year without a sheet, a DK fund not yet classified | left out, with its year-end value and the reason | left out of the pool, the pool marked incomplete |

A manual `tax_class` wins over the automatic one. The class is decided per year, so an ETF that leaves the list moves
from `pl_fund` to `fund` in the year it leaves (and gets the ASK warning).

**DKK average cost** (`model/tax.replay_dkk`), per group (C3), trades in date order:

- Buy: quantity += q; cost += (q · price + fee) · rate.
- Sell: proceeds = (q · price − fee) · rate; basis = cost / quantity · q; gain = proceeds − basis; cost −= basis.
- A sale larger than the position is capped and reported (as `replay`); a trade without a rate makes the group's
  gains from that day on missing.
- Returns the gains per sale (date, quantity, proceeds, basis, gain) and the remaining quantity and cost.

**Lager** (`model/tax.lager`), per holding and year: gain = V_end + Σ sale proceeds in the year − V_start − Σ buy cost
in the year, with V_start the DKK value at the last session of the year before (0 if not held) and V_end at the last
session of the year (C8). Sale proceeds and buy costs in DKK as above. This is SKAT's "value at year end minus value
at year start (or cost if bought in the year)" written for any sequence of trades; partial sales need no average,
because the year's basis is the whole position's start value plus its buys. A missing V_start or V_end makes the
holding's lager missing, named.

**ASK and pension pool** (`model/tax.account_pool`), per account and year: return = V_end − V_start − deposits +
withdrawals, with V the whole account in DKK (holdings plus cash where the account keeps a ledger; holdings only
otherwise, with dividends added as income). Taxable = max(0, return − carried loss); carried loss next year =
max(0, carried loss − return) when the return is positive, carried loss − return when negative. Tax = taxable × rate.
The tax itself, debited from the account, is a withdrawal if the ledger records it, and the page says how it should
be booked (a `FEE` row would wrongly count as a loss). A year with an incomplete value is incomplete, not 0.

**Frie midler, per person and year** (`model/tax.share_income`):

1. Share income = realised gains on `stock` and `dk_distributing` + dividends on `stock`/`dk_distributing`/`pl_fund`
   + lager on `pl_fund`, across the person's *frie midler* accounts.
2. Loss pools, as `loss_pools` in the rules: realised losses on listed shares offset only the income kinds the rules
   list for that pool, then carry forward per person; what's left of share income is netted. A negative net share
   income carries forward (its tax value against other income: not modelled, C11 list).
3. Tax = low_rate × min(S, limit) + high_rate × max(0, S − limit), with S the net positive share income.
4. Capital income = lager on `fund`; tax = base × the person's `capital_income_rate`, or none when it's null.

The `loss_pools` default above is a simplification. TASK-5.2 checks it against *Den juridiske vejledning* (the
sections on listed shares and investment companies) and records what it found in the rules file and in the guide's
"modelled / not modelled" list.

**Pre-tax numbers unchanged.** Nothing in `performance`, `trades` or the X-ray changes behaviour; a regression test
holds `analyze` and `compare` output on the test world before and after (TASK-5.8).

### 4.4 Settings

The rules are data, not settings: `config/tax_dk.yaml` with `config_schema.TaxRules`. One settings key:

```yaml
tax:                         # src/radar/tax.py
  years_back: 3              # tax years shown in the picker before the current one
```

`propose.ask_deposit_cap` and `propose.ask_cap_year` go (C7). The guide quotes rates with a new
`{{tax:2026.ask.rate}}` placeholder, so the chapter can't drift from the file; `tests/test_guide.py` checks it.

### 4.5 API

`GET /api/tax?year=&person=&portfolio=` → `TaxYearView`:

```text
TaxYearView
  year, rules: {year, verified, sources: [url]} | null, generated, asof
  persons: [{id, name, share_income: {realised, dividends, pl_lager, losses_used, net, limit, used_of_limit,
             tax_low, tax_high, tax, carried_forward}, capital_income: {base, rate | null, tax | null},
             complete: bool}]
  accounts: [{id, name, kind, person, pool: {v_start, v_end, deposits, withdrawals, return, carried_in, taxable,
              rate, tax, carried_out} | null, realised: [{symbol, date, quantity, proceeds, basis, gain}],
              lager: [{symbol, class, v_start, v_end, buys, sales, gain | null}],
              dividends: [{symbol, date, amount}], complete: bool, warnings: [str]}]
  unknown: [{symbol, portfolio, value_dkk | null, reason}]
  notes: [str]
```

- No rules for the year: a valid view with `rules: null`, every tax null, the bases still computed, and the note "no
  rules for <year>". Nothing is reused from another year.
- 503 without prices, like the other live endpoints. Cached per (year, selection, market mtime, transactions version,
  tax tables version).
- Edits: `PUT /api/tax/instruments/{symbol}` (isin, tax_class), `GET/POST/PATCH /api/tax/persons`,
  `GET/POST/DELETE /api/tax/openings`, `PATCH /api/portfolios/{id}` accepts `tax_person_id`.
- Then `pnpm -C web gen:api`; `client.ts` gets `tax(year, sel)` and the edit calls.

### 4.6 CLI

In `cli/tax.py`, registered as `radar tax`:

- `radar tax year 2026 [--portfolio P] [--person N] [--json]`: per person, then per account, then unknowns; `--json`
  prints the `TaxYearView` (same as the API).
- `radar tax classify [--unknown]`: the instruments with ISIN, class and source; `radar tax isin SYMBOL ISIN`,
  `radar tax classify SYMBOL CLASS`.
- `radar tax person list|add|set`, `radar tax opening list|add|remove`.

### 4.7 Web

A *Tax* tab on *Portfolio* (the accounts live there), with a year picker:

1. **Banner**: "Estimate, not tax advice. Your årsopgørelse wins." The rules year, its verified date and sources.
2. **Per person**: share income as a stacked bar against the progression limit, the tax at each rate, capital income,
   carried forward.
3. **Per account**: the pool (ASK, pension) or the realised and lager tables (*frie midler*), dividends, warnings.
4. **Unknown classification**: each holding with its value and reason, and an inline fix (enter the ISIN or choose
   the class).
5. **Settings** (collapsed): persons and their capital-income rate, which account belongs to whom, openings.

Missing values show as "–" with a reason, never 0. Terms (*lagerbeskatning*, *realisationsbeskatning*,
*gennemsnitsmetoden*, *progressionsgrænse*, *positivlisten*) get `Term` tooltips linked to the textbook.

## 5. Steps as PRs

Each PR is green on `uv run pytest -q`, `uv run ruff check`, `uv run mypy`, `uv run lint-imports` (and
`pnpm -C web test` when the web changes), and carries its guide changes.

| # | PR | Task | Contents | Behaviour change |
|---|---|---|---|---|
| 1 | **Plan** | 5.1 | This file; the task files. | – |
| 2 | **Rules file** | 5.2 | `config/tax_dk.yaml` (2025, 2026), `config_schema.TaxRules`, `portfolios/taxrules.py`, `{{tax:…}}` in the guide renderer; `propose.ask_deposit_cap` moved; loss pools checked; `DATA_LICENSE.md`, `datalicenser.md`. | `propose` reads the cap from the rules file. |
| 3 | **Positive list per year** | 5.3 | `load_years`, `status`; path into `paths` with its tier; `datalicenser.md` *Used for*. | None visible. |
| 4 | **Instruments** | 5.4 | `instruments` migration, the fill order, class per year in `taxinputs`; `radar tax classify/isin`. | New table. |
| 5 | **Tax persons** | 5.5 | `tax_persons`, `portfolios.tax_person_id`, the "Me" default; `radar tax person`. | New table and column. |
| 6 | **Realisation engine** | 5.6 | `model/tax.replay_dkk`, golden tests. | None (new functions). |
| 7 | **Lager and pools** | 5.7 | `model/tax.lager`, `account_pool`, `share_income`, golden tests. | None (new functions). |
| 8 | **Year report** | 5.8 | `taxinputs`, `tax.py`, `tax_openings`, the pre-tax regression test; `pyproject.toml` layers; `docs/architecture.md`. | None visible yet. |
| 9 | **API and CLI** | 5.9 | `api_models/tax.py`, `api/tax.py`, `radar tax year/opening`, `tax:` setting, TS types, `docs/commands.md`, `docs/web-app.md`, `CLAUDE.md`. | New endpoints and commands. |
| 10 | **Web tab** | 5.10 | The *Tax* tab, client, glossary, `page_links`. | New tab. |
| 11 | **Docs** | 5.11 | `brugervejledning/skat.md`, `laerebog/skat.md`, `formler.md`, `indstillinger.md`, `portefoljer-og-tags.md`. | – |
| 12 | **Release** | 5.12 | `CHANGELOG.md`, *Nyheder*, `features.yaml`, demo-copy screenshots. | – |

Steps 2–7 are independent of each other (6 and 7 need only the plan); 8 needs all of them; 9–12 follow in order.

## 6. Tests

| Test | File | Checks |
|---|---|---|
| `test_rules_verified_only` | `tests/test_taxrules.py` | A year without `verified` or without a block raises `NoRules`; a misspelt key fails with its path. |
| `test_guide_tax_placeholders` | `tests/test_guide.py` | `{{tax:2026.ask.rate}}` renders from the file; an unknown path fails. |
| `test_positive_list_years` | `tests/test_sources.py` | A sample with two year sheets: `status` per year; a year without a sheet is `no_sheet`; `load()` unchanged. |
| `test_instruments_fill_order` | `tests/test_userstore.py` | Import ISIN before `universe.yaml` before discovery; a manual row is never overwritten; the migration keeps existing data. |
| `test_tax_person_default` | `tests/test_userstore.py` | The migration links real ask/frie_midler/pension portfolios to "Me" and leaves virtual ones null. |
| `test_replay_dkk_partial_sales` | `tests/test_tax_math.py` | The textbook's example (buy 10 @ 100, buy 10 @ 130, sell 5 @ 150, fees 20): gain 145; with rates ≠ 1 the DKK figures by hand; an oversized sale is capped and reported. |
| `test_average_across_accounts` | `tests/test_tax_math.py` | Buys in two *frie midler* accounts of one person, a sale in one: one average; a buy on the ASK doesn't move it. |
| `test_ask_loss_year` | `tests/test_tax_math.py` | The textbook's three-year ASK table: taxes 2,040 / 0 / 510, carried loss 5,000 used in year 3. |
| `test_pl_lager_mid_year_buy` | `tests/test_tax_math.py` | The textbook's example (bought 50,000 during the year, worth 56,000 at 31 Dec): lager 6,000 as share income; a partial sale in the year by hand. |
| `test_leaves_positive_list` | `tests/test_tax.py` | An ETF on the 2025 sheet, off the 2026 sheet: share income in 2025, capital income in 2026, an ASK warning in 2026. |
| `test_progression` | `tests/test_tax_math.py` | Share income below, at and above the limit; the split between the rates. |
| `test_pension_pal` | `tests/test_tax_math.py` | A pension account's positive and negative year with carry-forward at the PAL rate. |
| `test_unknown_excluded` | `tests/test_tax.py` | A fund without an ISIN: listed with its value and reason, not in any estimate, the account marked incomplete. |
| `test_missing_value_is_missing` | `tests/test_tax.py` | A NaN year-end value: that holding's lager null, never 0; a trade with no rate makes its gains null. |
| `test_no_rules_year` | `tests/test_tax.py` | Year 2027 without rules: bases computed, taxes null, the note; nothing from 2026 used. |
| `test_pretax_unchanged` | `tests/test_performance.py` | `analyze` and `compare` on the test world equal before and after the feature's migrations and tables. |
| `test_tax_api_contract` | `tests/test_api.py` | Validates against `TaxYearView`; no prices 503; edits round-trip. |
| `test_cli_tax_same_as_api` | `tests/test_cli_smoke.py` | `--json` equals the API's view. |
| layers | `tests/test_layers.py`, `lint-imports` | `tax` in features; `model/tax.py` imports nothing above the kernel. |
| web | `pnpm -C web test` | The tab renders nulls as "–"; the banner is present; the unknown fix calls the API. |

The textbook's three worked examples are the golden tests: if the textbook and the engine disagree, one of them is
wrong. The synthetic world gets a two-sheet positive-list sample, one fund without an ISIN and one person with an ASK
and two *frie midler* portfolios; no real holdings or personal data in any fixture.

## 7. Docs

- **User guide**: new chapter `brugervejledning/skat.md` (*Skat: radarens skatteestimat*): what the tab shows, how to
  classify a holding, persons and openings, how to book the ASK tax, the "modelled / not modelled" list, and the
  disclaimer. In `guide.yaml`; linked from `portefolje.md` and `portefoljer-og-tags.md` (accounts and persons).
- **Textbook**: `laerebog/skat.md`: "Radaren beregner ingen skat" goes; *Sådan gør radaren* describes the engine
  (DKK average across a person's accounts, lager per year, pools, classification per year); the pooled-average
  caveat becomes "the Tax tab does it per person". Rates quoted with `{{tax:…}}`.
- **Formulas**: `formler.md` gets the DKK average, lager, the pool and progression.
- **Settings**: `indstillinger.md` for `tax.years_back` and the removed `propose` keys; a section on `tax_dk.yaml`.
- **Licences**: `DATA_LICENSE.md` and `datalicenser.md` (TASK-5.2, 5.3).
- **Developer docs**: `docs/architecture.md` (kernel `model/tax.py`, domain `taxrules`/`taxinputs`, feature
  `tax.py`, the tables), `docs/data-conventions.md` (*Tax*: DKK rates per trade, year-end values, missing is
  missing), `docs/commands.md`, `docs/web-app.md`, `CLAUDE.md` main commands.
- **Skills**: `/journal` and `/propose-portfolio` mention `radar tax year --json` for placement questions; no
  `summary.json` key (computed live).
- **Release**: `CHANGELOG.md`, *Nyheder*; `uv run pytest -q tests/test_guide.py`.

## 8. Definition of done

The review's cross-cutting checklist ([section 3.3](analyses/product_owner.md#33-cross-cutting-definition-of-done-applies-to-every-feature)),
applied:

- [ ] Pure math in `model/tax.py`, rules and inputs in `portfolios/`, I/O in `sources/`, the feature in `tax.py`;
      `lint-imports` and `tests/test_layers.py` pass.
- [ ] Missing values, rates, sheets and rules show as missing with notes, never 0; unknown holdings are named with
      their value; a positive-list sheet that parses to nothing fails loudly.
- [ ] The positive-list file in `paths.REGISTRY`; no other new file (personal data in `radar.db`).
- [ ] `tax_persons`, `portfolios.tax_person_id`, `instruments`, `tax_openings` through append-only migrations; the
      pre-migration backup is taken as for every schema change.
- [ ] `tax:` in `settings.yaml` and `config_schema.py`; `tax_dk.yaml` validated; the guide quotes rules with
      `{{tax:…}}` and settings with `{{settings:…}}`.
- [ ] `TaxYearView` and the edit models strict; TypeScript types regenerated; `pnpm -C web build` passes.
- [ ] `DATA_LICENSE.md` and `datalicenser.md` updated (rules typed from skat.dk; positive list per year).
- [ ] User-guide chapter and textbook section per section 7; `tests/test_guide.py` passes.
- [ ] `summary.json` unchanged; skills' docs mention `radar tax year --json`.
- [ ] `uv run pytest -q`, `uv run ruff check`, `uv run mypy`, `pnpm -C web test` green.
- [ ] `CHANGELOG.md`, *Nyheder*, marketing `features.yaml`.
- [ ] Screenshot check in the demo copy (fictional investor), never the user's data folder; the leak check passes.

## 9. Decisions taken here, and open questions

**Decided** (the review's open questions, approved 2026-10-25):

1. **Pension in the MVP**: yes. PAL is the same pool as the ASK with its own rate and carry-forward; payout tax is
   out of scope.
2. **Losses from before the history**: one manual opening row per pool (`tax_openings`), with the year it is carried
   into.
3. **Spouse transfer of the progression limit**: out of scope, on the "not modelled" list.
4. **Dividends**: "as booked" in the MVP, with a note; gross vs net and withholding are TASK-5.16 (C9).
5. **Where the math lives**: `model/tax.py`, so simulations and studies can use it later (TASK-5.15).
6. **Classification**: by `quoteType` for stocks and by ISIN and that year's sheet for funds; a Danish fund off the
   list is asked about, never guessed.

**Open** (settled inside their tasks, recorded here when they are):

1. Which positive-list sheet applies to an income year (the sheet named for the year, or the one published before
   it)? Suggest: the sheet named for the year; TASK-5.3 checks SKAT's own wording.
2. The exact loss-pool rules (`loss_pools`) for listed shares and positive-list funds; TASK-5.2 checks *Den juridiske
   vejledning* and records the result.
3. How the ASK's own tax debit is booked in an import (some brokers show it as a fee row). Suggest: a `WITHDRAW` with
   a note; the guide says so, and TASK-5.8 warns when a `FEE` row in an ASK in January looks like the tax.

## 10. Changes during implementation

Recorded as the work landed; where this section and the sections above disagree, this one is what the code does.

1. **The positive list stays where it is (C6).** `imports/positivliste.xlsx` is an app file shipped in the install
   folder (`docs/architecture.md`, *Where data lives*), so it isn't moved to `paths`. Open question 1 is settled by
   SKAT's own cover sheet: the sheet named for a year ("Kalenderåret 2026") is that income year's list.
2. **The ASK deposit cap follows skat.dk.** The cap is tested against the account's value on 31 December the year
   before plus this year's deposits (`model/tax.ask_headroom`), not against net deposits as `propose` did.
3. **Values at traded closes.** The tax book is `performance.book(rows, market, "cash")`: holdings at traded closes,
   dividends as cash or outflow. Adjusted closes would count a distributing fund's dividend in its lager and again in
   its dividend row.
4. **Negative tax, not negative return, is carried** for the ASK and pension (skat.dk, PAL § 17); the opening pools
   are `ask_negative_tax`, `pension_negative_tax`, `listed_loss` and `negative_share_income`.
5. **Every real portfolio gets the first person** on creation and in the migration (not only the tax kinds), so a
   change of kind needs no second step; `other` still gets no estimate.
6. **ASK and pension pools ignore the class.** The pool taxes the whole account; a holding of class `fund` (off the
   list) or `unknown` on an ASK is a warning, not a gap in the pool. *Not in the estimate* lists frie midler
   holdings only.
7. **No `tax.years_back` setting.** The tab's year picker runs from the first transaction's year to this year.
8. **Loss pools (open question 2):** `losses.listed_offsets: [realised, dividends, pl_lager]` and
   `pl_lager: share_income`, from the general table in *Den juridiske vejledning* C.B.2.1.2 and skat.dk's page on
   listed-share losses. The detailed passage on offsetting lager losses on investment companies wasn't found; the
   guide's "not modelled" list names the conditions for deducting losses.
9. **Wire keys** `ret` and `tax_class` instead of `return` and `class`; `DELETE /api/tax/openings/{oid}` returns the
   id. The tax inputs travel in the export and the holdings bundle as `tax.json`.
10. **Marketing:** `features.yaml` needs a brochure section and a screenshot; that is left to the `/marketing` run
    for the release, as for attribution.
