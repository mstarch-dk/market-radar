# Web app

Python computes every number; the frontend only formats and draws.

## Running
- First build: `pnpm -C web install`, then `pnpm -C web build` (writes `web/dist`, not committed).
- `uv run radar serve [--open]`: API and app on http://127.0.0.1:8780 (localhost only, no auth). Port 8765 is used by the static report preview.
- `uv run radar ticker <TICKER>`: open one ticker's page, starting the server if needed.
- Frontend work: run `pnpm -C web dev` (port 5173, proxies `/api` to 8780) next to `radar serve`.

## Contract
- `src/radar/api_models.py` defines every response with `extra="forbid"`, so `profile.py` and the models can't drift silently.
- After changing the models, run `pnpm -C web gen:api` to regenerate `web/src/api/schema.ts` from `radar openapi`. `pnpm -C web build` then fails on any field the UI uses that no longer exists.
- TypeScript is pinned to 5.9: version 7's native compiler lacks the API `openapi-typescript` needs.

## Endpoints
- `GET /api/ticker/{symbol}` returns the profile; `GET /api/ticker/{symbol}/series?days=` returns the chart series.
- `GET /api/search?q=` is Yahoo symbol search, with tracked names first.
- `GET /api/context` returns the regime plus holdings and watchlist.
- An untracked ticker is downloaded on its first lookup (~10 s). It is kept in `prices.parquet` but not added to the daily update. A failing Yahoo section returns `status: missing`; an unknown symbol returns 404.

## Stack
Vite, React 19, React Router, TanStack Query, lightweight-charts (v5 panes), plain CSS with light/dark tokens in `web/src/styles.css`.
