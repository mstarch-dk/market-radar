# Web app

Python computes every number; the frontend only formats and draws. It is the radar's only UI.

## Running
- First build: `pnpm -C web install`, then `pnpm -C web build` (writes `web/dist`, not committed).
- `uv run radar serve [--open]`: API and app on http://127.0.0.1:8780 (localhost only, no auth). The dashboard pages need a `reports/dashboard.json` from `radar run` (or `radar report`); without it they say so (HTTP 503).
- `uv run radar ticker <TICKER>`: open one ticker's page, starting the server if needed.
- Frontend work: run `pnpm -C web dev` (port 5173, proxies `/api` to 8780) next to `radar serve`.

## Contract
- `src/radar/api_models.py` defines every response with `extra="forbid"`, so `profile.py`, `dashboard.py`, `mine.py` and the models can't drift silently (`test_report_e2e` validates a built dashboard against them).
- After changing the models, run `pnpm -C web gen:api` to regenerate `web/src/api/schema.ts` from `radar openapi`. `pnpm -C web build` then fails on any field the UI uses that no longer exists.
- TypeScript is pinned to 5.9: version 7's native compiler lacks the API `openapi-typescript` needs.

## Endpoints
- `GET /api/ticker/{symbol}` returns the profile; `GET /api/ticker/{symbol}/series?days=` returns the chart series.
- `GET /api/search?q=` is Yahoo symbol search, with tracked names first.
- `GET /api/context` returns the regime plus holdings and watchlist.
- `GET /api/regime`, `/api/rotation`, `/api/momentum`, `/api/positioning`, `/api/coverage`: the sections of `reports/dashboard.json` from the last `radar run`, each with `asof`, `generated`, `age_days` and `stale` (older than `coverage.max_age.prices`; the pages then show a warning).
- `GET /api/tickers`: every tracked symbol in brief (price, 1d/1m/3m, score or quadrant, 6-month weekly sparkline, your status), for hover cards and held/watch markers. Cached until prices or the dashboard change; no Yahoo calls.
- `GET /api/me`: holdings, watchlist and sold positions, computed live from the current prices (quadrants and regime for the stop levels come from the dashboard).
- `GET` / `POST /api/update`: the data refresh run from the app (`updater.JOB`: one at a time, log lines, price-download progress; 409 while running).
- `POST /api/import`: a Yahoo Finance portfolio CSV as the request body (the quick path on the holdings and welcome pages).
- Portfolio editor (`/portfolio` page):
  - `GET/POST /api/portfolio/transactions`, `PUT/DELETE /api/portfolio/transactions/{id}`, `POST /api/portfolio/transactions/restore` (undo a delete). Writes are validated (`portfolio.validate`); errors and unconfirmed warnings return 422 with `detail.issues`.
  - `POST /api/portfolio/validate` (issues, before/after effect and price check while typing), `GET /api/portfolio/positions` (total and per account), `GET /api/portfolio/price-check`, `GET/POST /api/portfolio/accounts`, `GET /api/portfolio/export.csv`.
  - Imports: `GET /api/portfolio/import/presets`, `POST /api/portfolio/import/preview` (file as the body; `preset`, `mapping`, `symbols`, `account` as query parameters; never writes), `POST /api/portfolio/import/commit` (re-runs the same preview server-side, then saves one undoable import), `GET /api/portfolio/imports`, `DELETE /api/portfolio/imports/{id}`.
- Without `reports/dashboard.json` the pages show a welcome page (download data, import a portfolio) instead of an error.
- `PUT` / `DELETE /api/watchlist/{symbol}`: add or remove a watchlist symbol (`userstore`); unknown symbols are 404, removing a holding is 409.
- An untracked ticker is downloaded on its first lookup (~10 s). It is kept in `prices.parquet` but not added to the daily update. A failing Yahoo section returns `status: missing`; an unknown symbol returns 404.

## Pages
`/` (search and overview), `/regime`, `/rotation`, `/themes` (themes and factors), `/momentum`, `/positioning`, `/me`, `/data`, `/ticker/:symbol`. "/" focuses the search from anywhere.

## Building blocks (`web/src/components`, `web/src/lib`)
- `TickerLink`: every ticker links to its profile, shows a hover card (`/api/tickers`) and a small held/watch marker. `WatchStar` / `WatchButton` edit the watchlist.
- `DataTable` + `TableToolbar`: pages only declare columns (`columns.ts`: `sort`, `search`, `filter` enum/bool/range, `help`, `heat`, `hidden`, `csv`). Sort, search and filters live in the URL as `?{tableId}.sort=…&{tableId}.q=…&{tableId}.f.{col}=…` (`lib/tableState.ts`, pure and unit-tested), so views survive reloads and Back undoes a filter. Tables sharing an id (the momentum regions) share one toolbar. A range filter leaves out rows without data and says how many; missing values always sort last. Hidden columns are remembered per browser (`localStorage`).
- `Tip` / `Term` / `lib/glossary.ts`: hover-and-focus explanations for every metric label. Add new metrics to the glossary.
- `LineChart` (ranges, crosshair readout), `RrgChart` (linked to its table: hover highlights, table filters decide which trails show), `PriceChart` (session readout).
- Effects must use a block body when they call something that returns a value (`window.scrollTo` returns a Promise in current Chromium, which React would run as a cleanup and crash).

## Stack
Vite, React 19, React Router, TanStack Query, lightweight-charts (v5 panes), floating-ui (tooltips, popovers, hover cards), plain CSS with light/dark tokens in `web/src/styles.css`.
