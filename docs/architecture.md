# Architecture

This page says what each part is responsible for and which rules it keeps. It does not list functions: the code
and its docstrings do. The method behind each reading is explained for users in the guide's *lærebog*.

## Layers
```
interfaces       api, cli
features         abtest, agenda, api_models/, backtest/, health, mine, profile, propose/, reporting/, updater, xray
kernel           model/
domain           datahome/, guide, importers/, market, market_views, notebook, portfolios/, snapshot, universe,
                 userstore/
data sources     discovery/, fundamentals/, sources/, updates
pure readings    signals/
infrastructure   config, config_schema, guard, jsonsafe, locks, manifest, money, net, ops, paths, sourcelog, values
```
A module imports its own layer and the ones below. The `layers` contract in `pyproject.toml` holds every module to
it (`uv run lint-imports`, `tests/test_layers.py`, CI; indirect imports and imports inside functions count). It
has no exceptions (`ignore_imports`): a module that needs something from above gets it passed in, or the shared
piece moves down.

Three `forbidden` contracts keep the app and the studies apart, so an experiment can't change what the app shows
and the app never runs a study: the kernel (`model/`) imports neither; the studies (`backtest/`) never import the
report builder or the app (`dashboard`, `mine`, `profile`, `api`, `cli`); the app (`updater`, `report`, `api`,
`abtest`, `agenda`, `propose/`, `xray`) never imports `backtest/` and reads the studies' reports through `model/artifacts.py`.

A helper both sides need goes down a layer (e.g. `Market` in `market.py`; the regime votes and level universe in
`model/inputs.py`), and its callers move with it: a name is read from the module that defines it, never through one
that only imported it (`tests/test_layers.py` holds this; the package facades `propose`, `api`, `api_models` and
`cli` are the exceptions). So there is one place to patch a name: the module the callers read it from.

## Config
- `config/universe.yaml`: everything tracked (ETF groups, stock lists, macro series, CFTC/OECD sources, the
  watchlist, the sector ETF each stock is compared with). Theme ETFs carry a UCITS `isin`, checked against SKAT's
  positive list (only the latest year's sheet counts).
- `config/settings.yaml`: thresholds and rules (regime, momentum, rotation, stops, coverage, backtest, propose,
  `network:` host limits, `ops:` retention). Checked on load against `config_schema.py`, which models every
  section: an unknown key, a missing key or a wrong type fails with the key's path; `radar doctor` reports it. A
  new key goes in the file and the model together; a key read with a default is optional in the model, with that
  default. Code reads values through `config.typed()` (the model; `propose.cfg()` is its `propose` section);
  `config.settings()` is the file as written, for what hashes it (`propose.rule_hash`, of the raw values, so a
  stored hash doesn't move when the model writes 10000 as 10000.0) and the pure readings that take a section as a
  dict (`fundamentals/context.py`, `signals/gauges.py`). Not yet everywhere: the profile's sections read the file
  as written (`ProfileInputs.cfg`), so a misspelt key there fails at runtime, not in mypy. Tests change settings
  with `conftest.with_settings(monkeypatch, backtest={...})`, which both views read; never by editing the dict
  `settings()` returns, which `typed()` doesn't see.

- `config/views.yaml`: market-view templates and the indicator catalogue the evidence check can read.
- `config/fee_presets.yaml`: broker fee schedules, each with the date and source of its price list.
- `config/discovery.yaml`: the discovery scan's markets, size and liquidity floors, flags and ETF categories.

## Where data lives
Nothing the user owns lives in the install folder (`config.ROOT` holds app files only: code, `config/` defaults,
`guide/`, `web/dist`, the positive list). Four tiers, each with one root (`paths.py`):

| Tier | What | Default |
|---|---|---|
| home / userdata / imports | `radar.db` and `backups/`, `notes/`, `briefs/`, `research/`, `journal/`, `exports/`, broker files in `imports/` | `~/Market Radar` |
| history | what builds up run by run and can't be downloaded again: rank and discovery snapshots, valuation snapshots, analyst, FactSet and put/call history, Yahoo statements, FRED series that roll out of FRED's window (ICE BofA spreads) | `~/Market Radar/history` |
| cache | everything `radar run` downloads or rebuilds (prices, macro, profiles, `sources.json`, `ops.db`) | `platformdirs.user_cache_dir("MarketRadar")` |
| reports | built from the cache | `<cache>/reports` |

- Paths resolve on every use, so a module-level constant follows `paths.configure()` (tests, `--home`) without
  patching. `paths.REGISTRY` places every file the code writes in a tier, which decides whether it is backed up
  and moved; `tests/test_paths.py` fails for a path not in it and for a data path built from `ROOT`.
- Where the home is: `--home`, then `MARKET_RADAR_HOME` (+ `MARKET_RADAR_CACHE`), then `portable.json` in the
  install folder (portable mode, used by the marketing demo), then the pointer file in
  `platformdirs.user_config_dir("MarketRadar")`. The pointer lives outside install folder and home, so every
  unzipped version finds the data; it is never written under an env var or in portable mode.
- Moving in: `datahome/home.py` finds an older install's data only in this install folder and its siblings (never wider:
  macOS privacy prompts), copies it with checks (SQLite backup API, row counts, integrity check, SHA-256 per file),
  stages it beside the new home and renames it into place. The old folder only gets `MOVED.txt`.
- **Downgrade guard**: a home or a `radar.db` newer than this code knows is read-only: the API answers 409 to every
  write, the CLI refuses.
- **Migrations**: the schema's (`userstore/`) and the layout's (`datahome/home.py`) are append-only and forward-only; a
  step never deletes user data (it copies or renames) and a released step is never edited. Both run after a
  backup. Cache formats may change freely: the cache is rebuilt, never migrated.
- Without a home the API serves only setup, the guide and the doctor, the web app shows the setup screen, and the
  CLI allows `setup`, `paths`, `serve`, `doctor`, `openapi` and `ticker`.

## Writing files
- Every cache, history and report file is written through `config.py`'s atomic writers: a temp file of the
  writer's own process and thread, swapped in, retried while a Windows reader holds the file. A running server
  never reads a half-written file. `tests/test_guard.py` fails on a direct write outside the few files that write
  a user-named file.
- `guard.py` decides whether a fresh download may replace a stored dataset (not empty, no series missing, no
  shorter span, not markedly fewer rows); otherwise the step fails and keeps its cache.
- `locks.py` gives one writer at a time across threads and processes: a second update, scan or report build is
  refused with `locks.Busy`, not queued.
- JSON files are written with `jsonsafe.dumps` only, which can't write NaN (`tests/test_guard.py` fails on a
  `json.dumps` passed to a writer). Plain `json.dumps` is left for hashes and database values.

## The report's build
`radar report` (also the last step of `radar run`) builds `dashboard.json` and `summary.json` in one pass over
the whole price store (about 30 s), saves the rank snapshots and the weekly score history, and refreshes the A/B
test. It is a separate pass on purpose, not computed per request; what depends on the user's own edits is applied
live by the API instead (the holdings table, the regime re-vote, coverage).

- Before anything is written, each section is checked against the `api_models` view the API serves it with
  (extra fields are an error), so a shape the app can't show fails the build, not a page. Ticker profiles are
  checked the same way.
- `dashboard.json` carries `build: {format, inputs}`: a format number (bump it when a section is added or changed)
  and the mtime of each file the build read. The server rebuilds an older format at start; a changed input only
  shows a *Rebuild* banner, since a build saves snapshots.
- `summary.json` is a contract with the skills: its keys don't change without them.

## Study reports
The study reports production code reads have a pydantic model for the parts it consumes (`model/artifacts.py`):
the proposals read the rule study's drift, the long-run study's survivorship gauge and the exit studies' run time;
the long-run study reads the score study; `radar study …` prints each report from the model its writer returns, so
a renamed field fails mypy in the printer too.

Each starts with a header (`schema_version`, `kind`, `created`, `data_asof`, `rule_hash`); writers stamp and check
it, readers get `ok`, `stale` (another rule: shown, never acted on), `missing` or `invalid` with a reason. A report
from before the header is read as schema 0; one from a newer version is invalid. A change to a consumed field is a
change to the model and to its schema version.

## `src/radar/`

### Interfaces
- `api/` + `api_models/`: FastAPI with strict Pydantic response models; see [web-app.md](web-app.md). `api/app.py`
  builds the app (lifespan, error handlers, the data-home gate and error-recording middlewares, the web app) from
  one `APIRouter` per page area (`setup`, `ticker`, `readings`, `operations`, `views`, `discover`, `holdings`,
  `refresh`, `transactions`, `portfolios`, `docs`, `imports`), included in a fixed order so the OpenAPI schema
  doesn't move; `api/state.py` holds the price store, its re-entrant lock (`ensure`, `has_prices`) and the data
  home's gate; `api/common.py` what several routers share. `api_models/` has one module per area of the app
  (common, profile, dashboard, positioning, portfolios, tx, views, ops, home, docs), all re-exported by the package.
- `cli/`: the `radar` command, one module per command group. A command parses its options, calls one function of
  the module that owns the work and prints the result; rules and lookups live in those modules, for the CLI and
  the API alike. A command run as an ops job writes its progress to stderr, so `--json` stays valid on stdout.

### Features
- `updater.py`: the update steps behind `radar update` / `run` and the app's *Update data* job. Each source is
  logged; a failure keeps its cache.
- `reporting/`: the report build (see *The report's build*) and what it serves.
  - `report.py`: builds `dashboard.json` and `summary.json`, saves the snapshots, refreshes the A/B test.
  - `dashboard.py`: computes every market-wide reading as data, without side effects.
  - `coverage.py`: per-source freshness, coverage and blind spots, from the source log. Stale sources are shown
    but don't vote.
  - `tickers.py`: a compact summary of every tracked ticker for the web app's hover cards.
- `mine.py`: the holdings, watchlist and sold table (DKK return vs a shadow ACWI position, flags, stop levels).
- `profile.py`: one ticker's full profile and several side by side with ACWI (`radar info`, `/compare`).
  `load_inputs` reads everything a profile needs from outside (prices, the Yahoo detail, your holdings, config,
  the regime and leaders, analyst history, valuation, the quality card) into a `ProfileInputs`; each section
  (`section_identity`, `section_price`, … `section_peers`, `context_notes`) is a pure function of it, testable
  from hand-made inputs, and `build` only loads, calls them in order and checks the result. A new section reads
  what it needs through a new `ProfileInputs` field, not inside the section. (The risk section still goes
  through `risk_section`, which reads the risk settings, the benchmark's currency and FRED itself.)
- `health.py`: `radar doctor`, each check with what it found and what to do.
- `abtest.py`: the forward A/B test of three score strategies as virtual portfolios. Its monthly picks are
  appended and never changed; a failed refresh is logged and never stops the report.
- `propose/`: portfolio proposals (`radar propose`, `/propose-portfolio`). The modules build on each other in the
  order rules → basket → resample → drift → draft → evaluation → store; the package re-exports every public name.
  The holdings, exposure and risk model it measures a proposal with live in `portfolios/` (shared with the
  portfolio views). The frozen picks file's shape is `propose/picks_file.py`, checked on freeze and
  read-back. It reads the rule study only through `model/artifacts.py`, stale when the rule's hash has changed.
- `xray.py`: the portfolio X-ray of a selection of portfolios: the book and its cash, classes, exposures with
  coverage, ex-ante risk with per-position shares (hidden below `risk.xray.min_coverage`), realised figures,
  concentration, stress and factor tilts. It only assembles `portfolios/exposure.py` and `riskmodel.py`, the code
  proposals use, and computes live: nothing written.
- `agenda.py`: the calendar of a selection: earnings and ex-dividend dates of held and watched stocks, open
  journal reviews and proposal time stops in a window, each with the reasons it is highlighted and a level
  (`calendar.highlight`). `resolve_earnings` is the one place a next earnings date is decided (the latest read of
  `history/calendar.parquet`, else the weekly screener, else none with the reason). Pure functions of what the
  caller passes in (holdings rows, weights, the history, the journal, the exit check) and the data's as-of date,
  so a rebuild gives the same items.
- `backtest/`: the studies, point in time: nothing after the day D is read. `pit.py` is what the radar knew on D;
  `exits.py` and `exit_rules.py` the stop / take-profit rule replayed and tested; `redeploy.py` re-investing an
  exit's proceeds; `study.py` the momentum score at every month-end; `longrun.py` its rule on decades of factor
  returns; `fund.py` the quality and value scores on EDGAR facts as known then; `picks.py` hindsight baskets;
  `propose_study.py` the proposal rule at every month-end. Simulated trades pay the portfolio's own fee schedule.

### Kernel
- `model/`: what the app and the studies must compute the same way, defined once, so what is tested is what is
  shown: point-in-time panels and the month-end calendar, selection under caps, the trend exit, the shared
  statistics (Newey-West t, IC, quintiles, path and risk-adjusted stats), the long-run prior, the inputs both sides read (level universe, regime votes) and the study reports' contracts.

### Domain
- `universe.py`: everything the radar downloads prices for (incl. holdings), names, sectors, region, how far
  back prices go.
- `market.py`: the price store as wide frames, loaded once and shared by the API, CLI and studies.
- `userstore/`: the user's own edits in `radar.db` (SQLite, versioned by `PRAGMA user_version` and an append-only
  migration list): portfolios, transactions (the source of truth), simulated runs, watchlist edits, imports,
  symbol map, meta; market views in `viewstore.py`, backup copies in `backups.py`. It is the one place that decides which
  portfolios count, and holds the one list of row types. New stateful data gets a table here.
- `portfolios/`: your portfolios, from the transactions in `userstore/`.
  - `trades.py`: positions from the store: ledgers and holdings for a portfolio selection, average-cost replay.
  - `checks.py`: checks a row before it is saved (unknown symbol, future date, oversold, price vs the close,
    negative cash) and moves between portfolios.
  - `performance.py`: a portfolio's value over time (in total and per symbol), time-weighted and money-weighted
    returns, ACWI with the same flows, comparisons and cash.
  - `simulate.py`: virtual portfolios: forks and the one interface simulations write through (checked, idempotent
    runs).
  - `fees.py`: broker fee schedules and estimates; an estimate is None, never 0, when something is missing.
  - `prices.py`: DKK closes, exchange rates and weekly DKK returns per ticker, computed once.
  - `exposure.py`: the holdings book in DKK, each name's class (world fund, sector fund, other fund, stock,
    unknown) with sector / region / currency (a fund looked through where its cached data allows, else *fund: not
    looked through*, never filed under its listing), and exposures against ACWI with coverage per dimension.
  - `segments.py`: attribution's benchmark segments: ACWI's weights by sector and region on each day (the weekly
    snapshots drifted with the segments' returns, back-drifted before the first) and each segment's daily DKK return
    from its proxy ETFs (universe.yaml `attribution:`); a segment without a return is missing that day.
  - `riskmodel.py`: shrunk covariance (`book_cov`: each set of holdings on its own names and ACWI, so its risk is
    the same wherever it is computed), ex-ante volatility, beta and tracking error with each name's share of total
    and active risk and its marginal contribution, concentration and correlated pairs, the weekly path of fixed
    weights, stress windows, realised drawdown and factor tilts.
- `importers/`: broker exports into trades; a preview never writes, a commit can be undone as a whole.
- `market_views.py`: the user's market views with their evidence and alignment.
- `snapshot.py`: rank history for "new" and "Δ rank", one file per data date (`asof`), never replaced.
- `datahome/`: the data folder (see *Where data lives*).
  - `home.py`: its status, setup, moving in and layout migrations.
  - `backup.py`: zips of the data folder with a manifest and checksums, kept on a schedule, optionally mirrored;
    a restore verifies, backs up first and swaps part by part.
  - `export.py`: the open-format export and the holdings bundle.
- `guide.py`: the Danish books in `guide/`, reached only through `guide/guide.yaml`, with settings placeholders.
- `notebook.py`: a read-only view of what the skills write (briefs, research, journal), with review dates.

### Data sources
Each downloads, checks what it got, caches it and logs it in the source log; a source that parses to nothing
fails loudly and keeps its cache. Their terms are in `DATA_LICENSE.md`.
- `sources/`: one module per source or source family.
  - `ingest.py`: Yahoo prices and FRED series.
  - `external.py`: CFTC positioning, OECD leading indicators, FactSet Earnings Insight, analyst consensus, ECB
    yields and Yahoo ticker detail.
  - `valuation.py`: weekly valuation snapshots of stocks and ETFs, and the market's (CAPE, ERP).
  - `sentiment.py`: CBOE put/call and the AAII survey.
  - `factors.py`: long monthly return histories (Kenneth R. French, JKP) for testing rules over decades.
  - `constituents.py`: the S&P 500 and MSCI ACWI holdings, and a weekly record of ACWI's aggregate weights in the
    history tier (`acwi_segments.csv`, append-only: iShares serves no past holdings).
  - `tracked.py`: what `universe.yaml` lists (benchmark, ETFs, stock groups, macro series), readable by the data
    sources.
  - `fxrates.py`: each ticker's quote currency and the FX tickers that turn it into DKK.
  - `positive_list.py`: SKAT's positive list.
- `fundamentals/`: financial statements from SEC EDGAR (US, with filing dates) and Yahoo (every stock,
  append-only) in one long fact format (its period arithmetic is pure, in `signals/periods.py`); which tickers
  are due.
- `discovery/`: the separate wide scan for names the radar doesn't track. Nothing here feeds the regime, breadth
  or the momentum page.
- `updates.py`: the opt-in daily check of the public repo's latest release.

### Pure readings
- `signals/`: pure functions from data to readings: risk and the series math everything shares, gauges, rotation,
  momentum and its score's percentile rule, regime, stop levels, technicals, valuation, quality and value scores,
  the statement periods (TTM, latest instant, fiscal years as known on a day), views, discovery scores. No I/O.

### Infrastructure
- `config.py`, `config_schema.py`: the config files, checked settings, the atomic writers.
- `paths.py`: the tiers and the registry of every file written (see *Where data lives*).
- `net.py`: the one network layer: per-host pacing and concurrency, retries with backoff, every request recorded,
  a host paused after repeated 429s (shared by the CLI and the server). One honest User-Agent; no proxies or
  identity rotation.
- `ops.py`: the operations log in `ops.db` (requests, events, jobs, host state). A failed write never breaks the
  work; nothing here feeds a market reading. Timestamps are UTC with their offset (`ops.timestamp`), so they
  compare as text across a change of the clocks; `ops.local` turns one into local time for showing and daily
  grouping, and a day's budget runs from `ops.local_midnight()`.
- `sourcelog.py`: the update log `sources.json`; a failure keeps the last success.
- `guard.py`, `locks.py`, `jsonsafe.py`: see *Writing files*.
- `manifest.py`: the data folder's `market-radar.json` (format, the versions that opened it, its log) and the
  app's version.
- `values.py`, `money.py`: the one rule for reading a number (finite or None) and for money (pence quotes, basis
  points, fees, an exchange rate on a day).

## `guide/`
The user-facing documentation in Danish: `brugervejledning/` (the user guide, page by page) and `laerebog/` (the
textbook: the theory behind every reading, with *Sådan gør radaren* sections on the code as it is). Served on the
app's Guide page; conventions in `guide/STIL.md`. A user-facing change updates its chapter in the same change;
`tests/test_guide.py` checks titles, placeholders, links and anchors.

## `web/`
Vite + React + TypeScript, served by `radar serve`: the only UI. The skills don't depend on it; they read
`summary.json`.

## Sharing and releases
- The repo is public. Nothing personal is committed: the user's data lives in the data folder, and
  `scripts/leak_check.py` (installed as a pre-push hook with `--install-hook`) refuses a push whose files or
  commit messages hold a pattern from the local `notes/leak-patterns.txt` (holdings, account names) or the
  private git email. `--history` checks every file version ever committed. The history before 0.2 was
  rewritten once (git filter-repo) to drop an early brief and rank snapshots before the repo went public.
- `marketing/` holds the Danish brochure; the PDF and its sources are committed, the screenshots are rebuilt.
  `scripts/marketing.py` builds a portable demo copy seeded with a fictional investor, so screenshots never see
  the user's data folder.
- Releases: `CHANGELOG.md` and the guide's *Nyheder* each get a `## X.Y.Z` section; `scripts/release.py prepare`
  refuses without them, then sets the version. `scripts/release.py fixture` writes a small data folder made by
  that version into `tests/fixtures/homes/` (never changed afterwards), which `tests/test_upgrade.py` opens with
  the current code.
- A `v*` tag builds the release zip (`scripts/build_release_zip.py`) with start scripts for
  each OS. The smoke workflow sets up a data folder (a path with a space and "ø"), backs up, restores,
  exports and moves the legacy fixture on all three OSes.

## Local vs committed
- Personal data and the cache live outside the repo. A checkout from before the data folder keeps the old root
  folders until `radar setup` copies them out; `.gitignore` leaves them out, anchored with `/` so the fixture
  data folders are committed.
- The monthly brief runs on this machine: a Claude desktop scheduled task runs `/market-brief` on the 1st.
- CI (`.github/workflows/ci.yml`) runs the tests and web checks on every pull
  request and push to main. Its `emails` job fails when any commit's author or committer email isn't a noreply
  address (GitHub's email privacy must stay on, or a merge on github.com would publish the account's email).
- Line endings are LF (`.gitattributes`), except the `.cmd` start script. The one-off renormalisation commit is in
  `.git-blame-ignore-revs`; run `git config blame.ignoreRevsFile .git-blame-ignore-revs` once per clone.
