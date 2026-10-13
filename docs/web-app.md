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
- `GET /api/regime`, `/api/rotation`, `/api/momentum`, `/api/positioning`, `/api/coverage`: the sections of `reports/dashboard.json` from the last `radar run`, each with `asof` and `generated`.
- `GET /api/me`: holdings, watchlist and sold positions, computed live from the current prices (quadrants and regime for the stop levels come from the dashboard).
- `PUT` / `DELETE /api/watchlist/{symbol}`: add or remove a watchlist symbol (`userstore`); unknown symbols are 404, removing a holding is 409.
- An untracked ticker is downloaded on its first lookup (~10 s). It is kept in `prices.parquet` but not added to the daily update. A failing Yahoo section returns `status: missing`; an unknown symbol returns 404.

## Pages
`/` (search and overview), `/regime`, `/rotation`, `/themes` (themes and factors), `/momentum`, `/positioning`, `/me`, `/data`, `/ticker/:symbol`. Every ticker or ETF shown anywhere links to its profile through `components/TickerLink.tsx` (rotation-graph dots navigate too). Tables use `components/DataTable.tsx` (sortable, missing values always last); line charts `LineChart.tsx`, rotation graphs `RrgChart.tsx` (SVG).

## Stack
Vite, React 19, React Router, TanStack Query, lightweight-charts (v5 panes), plain CSS with light/dark tokens in `web/src/styles.css`.
