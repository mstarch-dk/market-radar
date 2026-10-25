# Web app

Python computes every number; the frontend only formats and draws. It is the radar's only UI.

## Running
- First build: `pnpm -C web install`, then `pnpm -C web build` (writes `web/dist`, not committed).
- `uv run radar serve [--open]`: API and app on http://127.0.0.1:8780 (localhost only, no auth). The dashboard pages
  need a `reports/dashboard.json` from `radar run` (or `radar report`); without it they say so (HTTP 503).
- `uv run radar ticker <TICKER>`: open one ticker's page, starting the server if needed.
- Frontend work: run `pnpm -C web dev` (port 5173, proxies `/api` to 8780) next to `radar serve`.

## Contract
- `src/radar/api_models/` defines every response with `extra="forbid"` (one module per area, every model
  re-exported by the package: `from radar.api_models import X`), so `profile.py`, `reporting/dashboard.py`, `mine.py`
  and the models can't drift silently (`report.build` checks every dashboard section against them before writing,
  `dashboard.check`, and `profile.build` its profile; `test_report_e2e` and `test_profile` hold both to it).
  `api_models` sits in the features layer, below the API, so the producers can import it.
- After changing the models, run `pnpm -C web gen:api` to regenerate `web/src/api/schema.ts` from `radar openapi`.
  `pnpm -C web build` then fails on any field the UI uses that no longer exists. Only the responses are checked:
  `web/src/api/client.ts` writes the URLs and query parameters by hand, so a renamed route or parameter still
  compiles and only fails at runtime.
- Errors have one shape, `{"detail": {"message", "issues"}}` (issues: `{field, level, message}`; empty when there
  is one message), from one set of handlers in `api/app.py`. The domain raises `errors.NotFound` (404), `Conflict` (409)
  or `Invalid` (422, with its issues); an `HTTPException` and a request that doesn't fit its model come out the same
  way. `client.ts` reads only this shape.
- TypeScript is pinned to 5.9: version 7's native compiler lacks the API `openapi-typescript` needs.

## Endpoints
- `GET /api/ticker/{symbol}` returns the profile; `GET /api/ticker/{symbol}/series?days=` returns the chart series.
- `GET /api/search?q=` is Yahoo symbol search, with tracked names first.
- `GET /api/context` returns the regime plus holdings and watchlist.
- `GET /api/regime`, `/api/rotation`, `/api/momentum`, `/api/positioning`, `/api/coverage`: the sections of
  `reports/dashboard.json` from the last `radar run`, each with `asof`, `generated`, `age_days` and `stale` (older
  than `coverage.max_age.prices`; the pages then show a warning). `/api/regime` votes the stored indicators again with
  your current choice of groups and lists the switches (`votes`).
- `GET` / `PUT /api/settings/regime-votes` `{votes: {group: bool}}`: which switchable indicator groups (euro credit,
  valuation) count in the regime vote; unknown groups are 422. The Regime page's switches use it.
- Valuation fields (`pe_fy1`, `pe_vs_sector`, `eps_rev_4w`, … for stocks; `pe`, `pe_vs_acwi`, `pe_pct` for funds;
  their gauges in `val_gauges`, apart from the momentum `gauges`) are on the momentum, rotation and holdings rows
  (joined at `radar report`), and joined live on `/api/me` and `/api/discover` from the latest snapshot. Positioning
  has `valuation`, `revisions`, `sentiment` and `rates`.
- `GET /api/tickers`: every tracked symbol in brief (price, 1d/1m/3m, score or quadrant, 6-month weekly sparkline,
  your status), for hover cards and held/watch markers. Cached until prices or the dashboard change; no Yahoo calls.
- `GET /api/me`: holdings, watchlist and sold positions, computed live from the current prices (quadrants and regime
  for the stop levels come from the dashboard). A stock reporting within `calendar.soon_days` gets an
  `earnings in N d` flag from the same `agenda.build` as the calendar.
- A portfolio selection on `/api/me`, `/api/xray`, `/api/calendar`, `/api/portfolio/transactions`, `/positions` and `/export.csv`:
  `portfolio` (ids, repeatable), `tag` (repeatable) or `scope` (real | virtual | all); none means your real
  portfolios. The web app keeps it in the URL as `?pf=` (`real`, `3,5`, `tag:sim-a`).
- Market views: `GET /api/views` (views with evidence, templates, vocabulary), `POST /api/views`, `PUT` / `DELETE
  /api/views/{id}` (a delete returns the view; `POST /api/views/restore` undoes it), `POST /api/views/align`
  `{tickers, store: main|discovery}` (compact alignment for table columns, cached by the views' version). The ticker
  profile has a `views` section.
- `GET /api/discover`: the last discovery scan (`reports/discovery.json`), stale after
  `coverage.max_age.discovery_prices`; 503 until the first scan. `GET` / `POST /api/discover/scan`: run the scan from
  the app (`updater.DISCOVER_JOB`, same status shape as `/api/update`).
- Operations (`ops.py`, the Operations page): `GET /api/ops/summary?days=` (tiles, rows per host and source with
  errors, 429s, p50/p95, today vs budget, requests per day, cooldowns), `GET
  /api/ops/events?level=&kind=&source=&limit=&before=`, `GET /api/ops/requests?host=&source=&status=&limit=&before=`,
  `GET /api/ops/jobs`, `GET /api/ops/jobs/{id}` (with its log and request counts), `GET /api/ops/doctor?probe=`
  (`radar doctor`; with `probe` every source is contacted once), `DELETE /api/ops/cooldown/{host}` (resume a paused
  host; 404 if it isn't paused). A middleware records every 5xx except 503 ("no data yet") as an `api` event with its
  traceback, and attributes the app's own Yahoo calls to `app:<area>`. At startup the server marks its own jobs left
  `running` by an earlier server as `interrupted` and prunes the log.
- `GET /api/coverage` overlays the live `sources.json` (last attempt, success, error, `failing`) on the built section,
  so a failure after the last report shows at once.
- Notebook (`notebook.py`, read-only): `GET /api/notebook` (briefs, research memos, comparisons, journal entries with
  their front matter and *review due*, monthly reviews; newest first) and `GET /api/notebook/{kind}/{name}` (the
  Markdown without front matter, headings; 404 for anything not listed).
- Guide (`guide.py`): `GET /api/guide` (books, parts, chapters, `page_links`, `glossary_links`), `GET
  /api/guide/{book}/{slug}` (Markdown with settings filled in, `headings` with ids, part, prev/next, last change; 404
  for anything not in `guide/guide.yaml`), `GET /api/guide/search?q=` (sections holding every word, with a snippet).
- `GET` / `POST /api/update`: the data refresh run from the app (`updater.JOB`: one at a time, log lines,
  price-download progress; 409 while running).
- `GET` / `POST /api/report`: rebuild the readings from the data already downloaded (`updater.REPORT_JOB`, same status
  shape; 409 while an update or another rebuild runs). The dashboard sections carry `outdated` (`{reason: format |
  inputs, changed, rebuilding}`, `dashboard.outdated`; null while the update job runs), shown as a *Rebuild the
  readings* banner by `PageHead`. A dashboard of an older `dashboard.FORMAT` is rebuilt at server start.
- `POST /api/import`: a Yahoo Finance portfolio CSV as the request body (the quick path on the holdings and welcome
  pages).
- Portfolio editor (`/portfolio` page):
  - `GET/POST /api/portfolio/transactions`, `PUT/DELETE /api/portfolio/transactions/{id}`, `POST
    /api/portfolio/transactions/restore` (undo a delete). Writes are validated (`portfolio.validate`); errors and
    unconfirmed warnings return 422 with `detail.issues`.
  - `POST /api/portfolio/validate` (issues, before/after effect, price check and `fee_estimate` from the portfolio's
    fee schedule while typing), `GET /api/portfolio/positions` (total, per portfolio, and cash), `GET
    /api/portfolio/price-check` (with that day's DKK rate), `GET /api/portfolio/export.csv`.
  - Imports: `GET /api/portfolio/import/presets`, `POST /api/portfolio/import/preview` (file as the body; `preset`,
    `mapping`, `symbols`, `portfolio` as query parameters; never writes), `POST /api/portfolio/import/commit` (re-runs
    the same preview server-side, then saves one undoable import), `GET /api/portfolio/imports`, `DELETE
    /api/portfolio/imports/{id}`.
- Portfolios: `GET/POST /api/portfolios`, `PUT/DELETE /api/portfolios/{id}` (a real one with trades is 409: move or
  archive), `PUT /api/portfolios/{id}/tags`, `GET /api/portfolios/tags`, `POST /api/portfolios/{id}/default`, `POST
  /api/portfolios/{id}/move` (refused if a sale would lose its buy), `POST /api/portfolios/{id}/fork`, `GET
  /api/portfolios/{id}/runs` (a simulated portfolio's runs), `GET /api/portfolios/fee-presets` (broker fee schedules
  from `config/fee_presets.yaml`). `PortfolioIn.fee_schedule` left out of a PUT keeps the schedule; `null` removes it.
- Returns: `GET /api/portfolios/{id}/performance?start=&end=` (series with null gaps, TWR/MWR stats vs ACWI, notes),
  `GET /api/portfolios/compare?portfolio=&tag=&start=` (lines rebased at a common start; default: each of your real
  portfolios).
- X-ray: `GET /api/xray?portfolio=&tag=&scope=` → `XrayView` (`xray.py`): exposure by sector, region and currency
  against ACWI with coverage (`warn` below `warn_coverage`), each name's class (`class` on the wire), ex-ante risk with
  each position's share of total and active risk and its MCTR (null below `risk.xray.min_coverage`, `warn` below
  `warn_coverage`), realised 1-year vol and drawdown, concentration with correlated pairs, the stress windows, the
  factor tilts, the score tilts (value-weighted momentum score and K+V vs the universe's median; names without a score
  left out and listed) and notes. Computed live under the price lock; cached per (selection, prices mtime, transactions
  version, fund-detail cache). An empty selection is a view with empty tables and a note; no prices at all is 503. Its
  router is included last in `api/app.py`, so the OpenAPI order of the others stays put.
- Calendar: `GET /api/calendar?portfolio=&tag=&scope=&days=` → `AgendaView` (`agenda.py`): earnings and ex-dividend
  items of held and watched stocks, open journal reviews and proposal time stops in `days` (default `calendar.days`),
  each with `reasons` (`key`, an English `text` with the number, `value`) and a `level` (high | normal | info); `soon`
  lists the high ids within `soon_days` (also in the view); `no_date` the stocks with no known date and why; `excluded_funds` the funds
  left out. Item ids are stable (`kind:symbol:date`). Days count from the benchmark's last close, not the clock.
  Computed live under the price lock, cached per (selection, days, prices mtime, transactions version, calendar file,
  dashboard build, journal and proposals folders). Needs the dashboard (503 without one) and prices (503); included
  after the X-ray's router.
- Attribution: `GET /api/attribution?portfolio=&tag=&scope=&start=&end=` → `AttributionView` (`attribution.py`): the
  period, the reconciliation with Returns, per dimension (`dims.sector`, `dims.region`) the segments' average weights,
  returns and linked allocation / selection / interaction, the months (with `basis` snapshot | back-drifted), the
  totals incl. currency and cross, days used and left out and the linking error; the currency effect by currency;
  ACWI's first weekly snapshot and the back-drifted months; unclassified holdings (`class` on the wire); the factor
  regression (null under `attribution.min_weeks` or without factors) and notes. Under `attribution.min_months` or
  without ACWI's weekly weights: a valid view with empty `dims`, nulls and notes. `start`/`end` must be YYYY-MM-DD
  (422 otherwise). Computed live under the price lock; cached per (selection, period, prices mtime, transactions
  version, ACWI segment file, daily factor file); no prices is 503. Its router is included last.
- Evidence: `GET /api/evidence` → `EvidenceView` (`evidence.py`): a card per score study (momentum, quality, value,
  K+V) and the long-run study, each with its header (`status` ok | stale | missing | invalid, the reason and the
  command, `data_asof`, `age_days`, `old_data` past `evidence.max_age_days`, the rule tested and today's), the baseline
  per horizon with a t next to every mean, the verdicts and notes; the rule studies' headers; and `forward` (A/B test,
  paper trail, frozen proposals vs ACWI; `too_short` records are never averaged; null without prices, the cards still
  come back). Never 503. Cached until a report, the prices, a trade, a frozen proposal, the settings or the day
  change. Its router is included last, after the calendar's.
- Data folder (`datahome/`, `updates.py`): `GET /api/setup` (state ok | unset | missing |
  newer, locations, old folders found), `GET /api/setup/scan?path=` (what an old folder holds; 404 if nothing), `POST
  /api/setup` `{action: migrate|create|use, source, home, copy_cache}` (409 once a folder is in use). Until then every
  other `/api/*` route except the guide and the doctor answers 409 `{detail: {setup}}` and the app shows the setup
  screen (`components/Setup.tsx`, `SetupGate` around the shell). Data from a newer version: writes answer 409
  `{detail: {read_only}}` and a banner says why. `GET /api/data-home` (folders by tier with sizes, backups here and in
  the mirror), `POST /api/data-home/backup`, `PUT /api/data-home/mirror` `{path}`, `POST /api/data-home/restore`
  `{name}` (only a listed backup), `POST /api/data-home/open` `{key}` (Explorer / Finder / xdg-open), `GET
  /api/data-home/export` (zip download), `GET` / `PUT /api/updates` `{enabled}`. The Data page shows them under *Your
  data* (`components/DataHome.tsx`), also before the first download.
- Without `reports/dashboard.json` the pages show a welcome page (download data, import a portfolio) instead of an
  error.
- `PUT` / `DELETE /api/watchlist/{symbol}`: add or remove a watchlist symbol (`userstore`); unknown symbols are 404,
  removing a holding is 409.
- An untracked ticker is downloaded on its first lookup (~10 s). It is kept in `prices.parquet` but not added to the
  daily update. A failing Yahoo section returns `status: missing`; an unknown symbol returns 404.

## Pages
The navigation has two rows (`lib/nav.ts`, the one place that lists pages, groups, labels and blurbs; the Home tiles
use it too): the groups *Markets*, *Mine* and *System*, and the active group's pages. A group's tab returns to the
page last opened in it (remembered per browser). Ticker pages count as *Markets*; Home and the guide show the group
row only.

`/` (search, overview and the *Soon* strip: the calendar's `soon` items for your real portfolios, the same
request as `/calendar`'s default view, hidden when empty), `/regime`, `/rotation`, `/themes` (themes and factors), `/momentum`, `/discover` (heat map
+ screener over the discovery scan; market, colour, size and grouping in the URL as `mkt`, `color`, `size`, `by`;
presets set the `d.*` table filters), `/positioning` (FactSet and regional revisions, valuation, OECD CLI, rates,
CFTC, sentiment), `/me`, `/xray` (the portfolio X-ray: `?pf=` selection, header tiles, exposure tabs `?tab=` sector |
region | currency with active-weight bars, risk shares, concentration, stress, factor tilts), `/calendar` (the
calendar: `?pf=` selection, the next `soon_days` high items as cards, tabs `?tab=` agenda | month (ISO-week tables, a
CSS month grid with ranges drawn across their days; layout in `lib/agenda.ts`), filters `?who=` holding | watch and
`?kinds=`, no date known, notes), `/views` (market views:
templates, editor, evidence), `/notebook` (briefs, research, journal; `?tab=`) and `/notebook/:kind/:name` (one document), `/portfolio` (your accounts only: account strip `?pf=<id>`, tabs
`?tab=` positions | transactions | imports | accounts; a virtual selection redirects to /experiments), `/experiments`
(virtual portfolios: list with the A/B test card, or one experiment `?pf=<id>` with tabs holdings | trades |
rebalances | returns), `/returns` (returns over time vs ACWI; `?pf=` lines, `?from=` start), `/data`, `/ops`
(operations: tiles, sites and sources with a `?days=` window, events, jobs with their logs, recent requests, health
checks, resuming a paused site), `/evidence` (the study cards per score with tabs `?tab=` momentum | quality | value |
qv, the long-run card, the forward scoreboard and the rule studies; a stale report greyed with both rule hashes, a
missing one with the command to run it, a t next to every mean), `/ticker/:symbol`, `/guide` and `/guide/:book/:slug` (the Danish books: sidebar with
both books and their parts, search, "På denne side" with the current section, prev/next; below 900 px the sidebars
fold into disclosures). The topbar's *Guide* link opens it, the group row ends with "? Om denne side" (from
`page_links`), and a glossary tooltip links to its textbook section when `glossary_links` has one. "/" focuses the
search from anywhere.

## Building blocks (`web/src/components`, `web/src/lib`)
- `TickerLink`: every ticker links to its profile, shows a hover card (`/api/tickers`) and a small held/watch marker.
  `WatchStar` / `WatchButton` edit the watchlist.
- `DataTable` + `TableToolbar`: pages only declare columns (`columns.ts`: `sort`, `search`, `filter` enum/bool/range,
  `help`, `heat`, `hidden`, `csv`). Sort, search and filters live in the URL as
  `?{tableId}.sort=…&{tableId}.q=…&{tableId}.f.{col}=…` (`lib/tableState.ts`, pure and unit-tested), so views survive
  reloads and Back undoes a filter. Tables sharing an id (the momentum regions) share one toolbar. A range filter
  leaves out rows without data and says how many; missing values always sort last. Hidden columns are remembered per
  browser (`localStorage`).
- `Tip` / `Term` / `lib/glossary.ts`: hover-and-focus explanations for every metric label. Add new metrics to the
  glossary.
- `LineChart` (ranges, crosshair readout), `RrgChart` (linked to its table: hover highlights, table filters decide
  which trails show), `PriceChart` (session readout).
- `Treemap` (`lib/treemap.ts`: squarified layout, pure and unit-tested): grouped tiles sized by a measure and coloured
  on the graded palette; unknown sizes are drawn at the smallest known size and counted above the map. Hidden below
  640 px.
- Effects must use a block body when they call something that returns a value (`window.scrollTo` returns a Promise in
  current Chromium, which React would run as a cleanup and crash).

- `pages/Guide.tsx` is loaded lazily (`React.lazy`), so react-markdown, remark-gfm, remark-math, rehype-katex and
  KaTeX's CSS and fonts are only fetched on the guide. Heading ids come from the server (a rehype step applies them in
  order). `lib/guide.ts` (pure, unit-tested) sorts links into chapter, app page, in-page anchor and external, and
  finds callouts (`> **Bemærk:**`, `**Eksempel:**`, `**Tip:**`).

## Stack
Vite, React 19, React Router, TanStack Query, lightweight-charts (v5 panes), floating-ui (tooltips, popovers, hover
cards), plain CSS with light/dark tokens in `web/src/styles.css`.
