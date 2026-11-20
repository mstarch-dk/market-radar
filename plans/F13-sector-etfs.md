# F13 Sector ETFs: the go-to UCITS ETF per sector: implementation plan

*Written 2026-11-20, against `main` at `cc24775`. A slice of F11 (UCITS ETF toolkit) in [the product owner review](analyses/product_owner.md): costs, tax status and choosing between candidates for one exposure, here per sector. Analysis, not advice. Backlog: epic TASK-8 (label `f13`).*

## Context
The rotation overview ranks sectors through US-listed SPDRs (XLK…) and STOXX 600 supersectors (EXV3.DE…). A Danish retail investor can't buy the SPDRs (no KID), and the radar doesn't say which UCITS ETF to buy, what it costs, or how it is taxed. Today the only buyable sector funds are the Xtrackers proxies in `universe.yaml attribution.sectors`, which carry no ISIN or TER. The `/research` skill looks up TER and positive-list status by hand, every time.

This feature adds:
- **A manually run skill, `/sector-etfs`.** Every few months it researches the candidates and records one go-to ETF per sector, plus its peers.
- **A page, `/sectoretfs`.** It shows each sector's go-to and peers with live performance in DKK and vs ACWI, costs, and the detected Danish tax status.
- **Links to the page** from the Rotation, X-ray and Ticker pages, so "I want exposure to this sector" leads straight to an ETF.

Everything shown is analysis, not advice.

**Decisions taken with the user:**
- The curated list lives in the data folder as dated, frozen snapshots, never in the repo.
- Coverage is the 11 GICS sectors plus the EU supersectors that have their own UCITS ETFs.
- Each sector gets one go-to plus peers.
- Code ranks the candidates, Claude picks (with a reason when the pick departs from the top rank), and the user confirms before anything is saved.

**Branch.** The working tree holds uncommitted `/scout` work on `feat/scout-cards-optout`. Land or stash it first, then branch `feat/sector-etfs` from `main`.

## Design

### 1. Taxonomy (shipped, committed): `config/sector_etfs.yaml`
- **The sector list.** Each entry has a `key`, a Danish `label`, a `parent` (the GICS key for a supersector, null for a GICS sector), and `rotation:` (the rotation tickers that map to it).
  - The 11 GICS keys match the Yahoo sector names already used in `universe.yaml sector_etfs.us` and `attribution.sectors`: Technology, Healthcare, Financial Services, ….
  - The supersectors are Banks, Insurance, Autos & parts, Chemicals, Construction & materials, Travel & leisure, Food & beverage, Personal & household, Retail and Basic resources. Each has `parent:` set.
  - Example rotation mapping: `Technology: [XLK, EXV3.DE]`, `Banks: [EXV1.DE]`.
- **Optional `seed:` candidates per sector.** These are the known UCITS families (Xtrackers MSCI World 1C, iShares S&P 500 sector, SPDR MSCI World / S&P US Select Sector, iShares STOXX 600), to give the skill a starting point.
- **Validation.** Add a `SectorEtfTaxonomy` model to `config_schema.py` and load it through a new `config.sector_etf_taxonomy()`, following `config.index_funds()`. A test checks that every rotation sector ticker in `etf_groups.us_sectors`/`eu_sectors` maps to exactly one key.

### 2. Recommendation records (personal tier): `src/radar/sector_etfs.py` (domain layer, next to `scout`)
Mirror `scout.py` (`check` / `freeze` / `records` / `symbols`):
- **Where.** `RECORDS = HOME/"exports"/"sector_etfs"`, one file per run: `<date>.json`. A file is never overwritten; a second run on the same day gets a `-2` suffix. Register the folder in `paths.REGISTRY` (home tier; `exports/` is already there, so check whether that covers it).
- **Shape:**
  ```
  {type:"sector_etfs", as_of, frozen_at, sectors:[{key, pick:<isin>, reason, rank_override:bool,
    etfs:[{isin, ticker, name, issuer, index, scope:"world|us|europe|em", ter, distribution:"acc|dist",
           domicile, currency, aum_musd|null, tracking_diff|null, sources:[url], checked:<date>}]}]}
  ```
- **`check(record)` refuses:**
  - an unknown sector key
  - an invalid ISIN (regex from `positive_list.ISIN_RE` plus the Luhn check digit)
  - an invalid ticker (the same regex as scout)
  - a TER outside 0–3 %
  - a `pick` that is not among that sector's `etfs`
  - a duplicate ISIN within one sector
  - more than about 8 ETFs per sector

  A missing optional field stays `null`, never 0.
- **Readers.** `records()` marks an unreadable file with `problem` instead of dropping it, as scout does. `latest()` returns the newest readable record. `symbols()` returns every ticker in the latest record and is fed into `universe.all_price_tickers()`, as `scout.symbols()` is, so `radar run` keeps their prices.

### 3. Ranking and view (features layer): `src/radar/sector_etf_view.py`
- **`rank(etfs, year, years)`** sorts lexicographically:
  1. Tax status: on the positive list, so share income and ASK-eligible.
  2. TER, lowest first.
  3. Fund size, falling under `settings.sector_etfs.min_aum_musd` sinks a fund.
  4. Tracking difference, when known.
  5. Accumulating before distributing.

  It returns the order plus a per-ETF list of reasons. The thresholds go in a new `sector_etfs:` section of `config/settings.yaml` and its `config_schema.py` model: `stale_days: 180`, `min_aum_musd: 100`.
- **`view(market)` builds the page's data:**
  - **Performance.** 1M, 3M, 6M, 1Y and YTD in DKK, and the same vs ACWI in DKK. Reuse `portfolios/prices.Prices.dkk`, `portfolios/performance.bench_dkk` and `performance.period_return`/`PERIODS`. Do not reuse the private `profile._windows`. A missing price gives `null`.
  - **A sparkline:** the weekly DKK closes over one year.
  - **Costs.** The record's TER, with its `checked` date and source. The Yahoo TER from `sources/external.cached_detail(ticker)` (never fetched here) is shown next to it, and a mismatch over 0.05 pp gets a warning badge.
  - **Tax status.** `positive_list.status(isin, current_year, Market.positive_list years)` gives yes, no, no_sheet or no_isin. It is mapped to three fields:
    - `tax_class`: aktiebaseret (lager, share income) / kapitalindkomst (lager) / ukendt
    - `ask_ok`
    - `sheet_year`

    Where a sheet exists for next year, it is checked too, so the page can flag "leaves the list next year".
  - **The sector's rotation context.** The quadrant, rank and `rs_score` of its rotation rows, read from `dashboard.json["rotation"]` through the existing report reader.
  - **Staleness.** The record's age against `stale_days`. An ETF whose current rank departs from the frozen pick gets a "re-check" badge.
- **`candidates(sector)`** gives the skill its starting list:
  - the latest record's ETFs and the `seed:` entries
  - the discovery pool (`CACHE/discovery/isin_map.csv`/`universe.csv`, `kind=etf`, category or name match)

  It returns them with live numbers and the ranking, so the skill starts from data rather than memory.
- Add both modules to their layers in `pyproject.toml [tool.importlinter]`.

### 4. Interfaces
- **API.** `src/radar/api/sector_etfs.py` serves `GET /api/sector-etfs` with response model `SectorEtfsView` (sectors, each with a pick, peers, a rotation block, `as_of`, `stale`). The models go in `api_models/sector_etfs.py`, re-exported from `__init__.py`. Append the router last in `api/app.py`. When there is no record, return 200 with `sectors: []` and `as_of: null` (never 503); the page then shows an empty state that says to run `/sector-etfs`.
- **MCP.** Add to `src/radar/mcp/engine.py` and register in `server.TOOLS`:
  - `sector_etf_candidates(sector)`: read-only.
  - `sector_etf_view()`: read-only.
  - `sector_etfs_save(record, confirm)`: the fourth narrow write. Without confirm it is a dry run that returns the validated record and the ranking diff against the latest record. With `confirm=true` it calls `profile.ensure_prices` for each ticker, then `sector_etfs.freeze`. It goes in `REACHES_OUT`.

  Update `INSTRUCTIONS` and `tests/test_mcp.py`'s tool-name set.
- **CLI.** `src/radar/cli/sector_etfs.py`, registered in `cli/__init__.py`:
  - `radar sector-etfs [--json]`: the view.
  - `radar sector-etfs candidates SECTOR [--json]`
  - `radar sector-etfs history`: what each record picked, by date.

### 5. Skill: `.claude/skills/sector-etfs/SKILL.md`
Follow the `/scout` structure: frontmatter with `name`, `description` ("… Use when the user asks which ETF to buy for a sector … or runs /sector-etfs.") and `argument-hint: [sector …]`. Use MCP first, with one line of CLI fallback per tool. Write in Danish, following `guide/STIL.md`.

Steps:
1. **Context.** Read `investor_notes` (accounts: ASK vs frie midler), `sector_etf_view`, and `summary(["rotation"])`.
2. **Candidates.** For each sector (or only the sectors named in the arguments), call `sector_etf_candidates`.
3. **Web research.** Use issuer factsheets and justETF to confirm or fill in ISIN, TER, fund size, distribution policy, domicile and tracking difference. Look for new launches and closures. Record every figure with its source URL and date. Never invent a number; an unknown is `null`.
4. **Ranking and pick.** Show the code's ranking. Pick the go-to; when the pick departs from rank 1, write `reason` and set `rank_override`.
5. **Dry run.** Call `sector_etfs_save` without confirm and show a per-sector card with the changes vs the last record (a new pick, a TER change, a fund leaving the positive list).
6. **Confirm.** Ask the user with AskUserQuestion, then save with `confirm=true`.
7. **Memo.** `write_memo(kind="research", name="sector-etfs/<date>")`: the method, changes, caveats, and "analysis, not advice".

Add `research/sector-etfs/` to `notebook.FOLDERS` (or reuse the `research` kind with a subfolder, whichever `write_memo` allows) and to `paths.REGISTRY`.

### 6. Web page and links
- **Page.** `web/src/lib/nav.ts`: add `{path: "/sectoretfs", label: "Sektor-ETF'er", group: markets}`. `web/src/main.tsx`: add it to `ELEMENTS`. Add `api.sectorEtfs` to `web/src/api/client.ts`, then run `pnpm -C web gen:api`.
- **`web/src/pages/SectorEtfs.tsx`:**
  - `PageHead` showing the "updated <as_of> by /sector-etfs" date, with a stale warning badge.
  - One `Card` per sector, GICS first, each followed by its supersectors. Each card has:
    - a header with the rotation quadrant and rank
    - the go-to row highlighted, with its reason
    - a `DataTable` of peers with columns: name/ticker, scope, ISIN, TER (record vs Yahoo), size, acc/dist, domicile, a tax badge (aktiebaseret / kapitalindkomst / ukendt, plus ASK ✓/✗ and the sheet year), 1M/3M/6M/1Y DKK, vs ACWI (heat), and a sparkline
  - Anchors `#<sector-key>` and a filter by scope.
  - Reuse `DataTable`, `Pct`, `Badge`, `Sparkline`, `TickerLink`, `Quadrant` and `Term`. Add glossary entries for TER, tracking difference, aktiebaseret and lagerbeskatning in `lib/glossary.ts`.
- **Links:**
  - **Rotation.** `Rotation.tsx` gets a "UCITS go-to" column for `us_sectors`/`eu_sectors`, filled from `/api/sector-etfs` and linking to `/sectoretfs#key`. This happens in the frontend; the dashboard build is not touched.
  - **X-ray.** `Xray.tsx` sector exposure rows link to the sector's anchor.
  - **Ticker.** The "vs <sector_etf>" row in `components/sections.tsx` gets a "buy as UCITS → go-to" link.

### 7. Docs and licences
- **New guide chapter** `guide/brugervejledning/sektor-etfer.md`, under "Markedet" in `guide/guide.yaml`, plus `page_links: /sectoretfs`. It covers the method, the ranking rule (with `{{settings:sector_etfs.min_aum_musd}}` and `stale_days`), what the tax status means, and its limits: the positive list only proves aktiebaseret status, and a fund off the list counts as capital income.
- **Skill docs.** A `## /sector-etfs` section and an overview entry in `guide/brugervejledning/claude-code.md`. Also update `nyheder.md` and `CHANGELOG.md`.
- **Data licences.** Update `DATA_LICENSE.md` and `guide/brugervejledning/datalicenser.md` with a row for issuer factsheets and justETF, read by Claude during the skill: figures recorded by hand with source and date, for personal use, never redistributed. The Yahoo fund data and SKAT positive-list rows gain "used by sector ETFs".
- **Project docs.**
  - `CLAUDE.md`: a skill line (`/sector-etfs` → `exports/sector_etfs/`, memo in `research/sector-etfs/`) and a command line.
  - `docs/commands.md`: the CLI and MCP tools.
  - `docs/architecture.md`: the config file and the two modules.
  - `docs/web-app.md`: the endpoint.

## Critical files
- **New:**
  - `config/sector_etfs.yaml`
  - `src/radar/sector_etfs.py`
  - `src/radar/sector_etf_view.py`
  - `src/radar/api/sector_etfs.py`
  - `src/radar/api_models/sector_etfs.py`
  - `src/radar/cli/sector_etfs.py`
  - `.claude/skills/sector-etfs/SKILL.md`
  - `web/src/pages/SectorEtfs.tsx`
  - `guide/brugervejledning/sektor-etfer.md`
  - `tests/test_sector_etfs.py`
- **Modified:**
  - `config/settings.yaml`, `config_schema.py`, `config.py`
  - `paths.py`, `universe.py` (`all_price_tickers`), `notebook.py`
  - `mcp/engine.py`, `mcp/server.py`
  - `api/app.py`, `cli/__init__.py`, `pyproject.toml`
  - `web/src/lib/nav.ts`, `main.tsx`, `api/client.ts`, `api/schema.ts`, `lib/glossary.ts`, `pages/Rotation.tsx`, `pages/Xray.tsx`, `components/sections.tsx`
  - `guide/guide.yaml`, `DATA_LICENSE.md`, and the docs listed in §7
- **Reused:**
  - `sources/positive_list.status/load_years`
  - `portfolios/taxinputs.classify`
  - `portfolios/performance.period_return/bench_dkk`
  - `portfolios/prices.Prices.dkk`
  - `sources/external.cached_detail`
  - `profile.ensure_prices`
  - the `scout.py` freeze pattern
  - the `Rotation.tsx` `ucitsCols`
  - `DataTable` and `Sparkline`

## Verification
- **`tests/test_sector_etfs.py`:**
  - The taxonomy covers every rotation sector ticker.
  - `check` refuses each bad input.
  - A freeze never overwrites.
  - `latest()` skips an unreadable file and flags it.
  - `rank` orders ASK-eligible first, then TER and the AUM floor.
  - On the synthetic world (`tests/world.py`), the view gives DKK returns and vs ACWI, and a missing price gives `null`, not 0.
  - The tax badge follows the fixture positive list (yes / no / no_sheet).
  - The page is marked stale after `stale_days`.
- **Other tests:**
  - An API contract test, `SectorEtfsView.model_validate`, including the empty-state 200.
  - The path order in `tests/test_api.py`.
  - The MCP tool set and the save's dry run and confirm (`tests/test_mcp_engine.py`).
  - `tests/test_paths.py`, `tests/test_layers.py`, `tests/test_guide.py`.
- **Checks to run:**
  ```
  uv run pytest -q
  uv run ruff check
  uv run mypy
  uv run lint-imports
  pnpm -C web gen:api
  pnpm -C web build
  ```
- **End to end.**
  1. Run `/sector-etfs Technology Banks` against the real data folder.
  2. Confirm the save, and check that `exports/sector_etfs/<date>.json` was written.
  3. Run `uv run radar sector-etfs --json`.
  4. Start `radar serve` in the preview, open `/sectoretfs`, and check the cards, tax badges and DKK returns.
  5. Click the Rotation page's "UCITS go-to" link for XLK and check that it lands on `#Technology`.
  6. Check the empty state against a fresh `--home`.
- Run `uv run python scripts/leak_check.py` before pushing. No record or memo may enter the repo.

## Tasks (backlog epic `f13`)

| Task | Title | Plan § | Depends on | Acceptance criteria (short) |
|---|---|---|---|---|
| TASK-8.1 | Sector taxonomy and settings | 1, 3 (settings) | none | `config/sector_etfs.yaml` (11 GICS + 10 EU supersectors, rotation mapping, seeds) validated by `config_schema`; settings `sector_etfs.stale_days/min_aum_musd`; a test that every rotation sector ticker maps to exactly one key |
| TASK-8.2 | Recommendation records (`sector_etfs.py`) | 2 | 1 | check/freeze/records/latest/symbols; never overwrites; refuses a bad ISIN checksum, unknown sector or a pick outside its etfs; in `paths.REGISTRY`; tickers in `all_price_tickers`; layer contract green |
| TASK-8.3 | Ranking and view (`sector_etf_view.py`) | 3 | 2 | lexicographic rank with reasons; DKK returns and vs ACWI with null for missing data; tax status yes/no/no_sheet/no_isin → class + ASK + sheet year; record TER vs Yahoo TER; staleness; candidates from record + seeds + discovery pool |
| TASK-8.4 | API `GET /api/sector-etfs` and TS types | 4 | 3 | `SectorEtfsView` contract test; empty state is 200 (never 503); router appended last; `pnpm -C web gen:api` |
| TASK-8.5 | MCP tools and CLI | 4 | 3 | `sector_etf_candidates`, `sector_etf_view`, `sector_etfs_save` (dry run, confirm, REACHES_OUT); `radar sector-etfs [candidates\|history] [--json]`; test_mcp tool set updated |
| TASK-8.6 | Skill `/sector-etfs` | 5 | 5 | SKILL.md (MCP first, CLI fallback, Danish, sources and dates per figure, a confirm card per sector, memo); `notebook.FOLDERS` path; CLAUDE.md skill line |
| TASK-8.7 | Web page `/sectoretfs` | 6 | 4 | cards per sector with the go-to highlighted, a peers table (TER, size, acc/dist, domicile, tax badge, 1M–1Y DKK, vs ACWI, sparkline), anchors, empty and stale states; glossary terms |
| TASK-8.8 | Links from Rotation, X-ray and Ticker | 6 (links) | 7 | a "UCITS go-to" column on the sector groups; links from X-ray sector rows and from the profile's "vs sector" row to `/sectoretfs#key` |
| TASK-8.9 | Docs and data licences | 7 | 6, 7 | guide chapter `sektor-etfer.md` + `page_links` + the claude-code section; `DATA_LICENSE.md` + `datalicenser.md` (issuer factsheets/justETF recorded by hand); commands/architecture/web-app docs; `test_guide` green |
| TASK-8.10 | Release F13 | Verification | 8, 9 | CHANGELOG + Nyheder; a first real `/sector-etfs` run; page checked in the preview; the full test/lint/type/build suite green; leak check clean |
| TASK-8.11 | Later: propose A5 uses the go-to UCITS | Follow-up | 10 | `propose/evaluation.py` A5 reads the latest record instead of XLK/EXV* |

## Follow-up (not in this change)
Let `/propose-portfolio`'s alternative A5 (`propose/evaluation.py` around line 293) use the go-to UCITS from the latest record instead of XLK/EXV*.
