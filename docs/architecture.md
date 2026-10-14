# Architecture

## Config
- `config/universe.yaml`: everything tracked: ETF groups, stock lists, macro tickers, CFTC/OECD sources, the watchlist, and `sector_etfs` (the sector ETF a stock is compared with on its profile, by Yahoo sector, with industry overrides). Theme ETFs carry a UCITS `isin`, checked against `imports/positivliste.xlsx` (SKAT list; only the latest year's sheet counts).
- `config/settings.yaml`: thresholds (regime, momentum, rotation, stops, coverage limits).
- `config/discovery.yaml`: the discovery scan: markets (exchanges, size floors, minimum counts), size and liquidity thresholds, flag settings, ETF listing preference and the name → category table.

## `src/radar/`
- `updater.py`: the update steps behind `radar update`/`run` (each source logged, failures keep the cache) and the background job the app's *Update data* button runs. `health.py`: `radar doctor`.
- `ingest.py`: yfinance prices and FRED series → `data/*.parquet`. `config.write_parquet` writes atomically, so a running server never reads a half-written file.
- `external.py`: CFTC positioning, OECD leading indicators, the FactSet Earnings Insight PDF, Yahoo analyst consensus for holdings and watchlist, and Yahoo ticker detail (`fetch_detail` / `detail`, cached in `data/profiles/`).
- `universe.py`: config access, S&P 500 constituents (SSGA SPY holdings), names, currencies, sectors, positive list; `transactions()`/`holdings()` from the store (average-cost `replay`, `positions` per account), the Yahoo import, and the one-time move of the old `imports/*.csv` into the store (`ensure_migrated`).
- `signals/`: `risk.py` (weekly DKK beta ± se, alpha, downside beta, Sharpe/Sortino, drawdowns, factor tilts, correlations, risk budget), `gauges.py` (graded readings), `rotation.py` (RRG), `momentum.py`, `regime.py`, `levels.py` (rule-based trailing ATR stop / take-profit with reasons, for held stocks, theme ETFs and ticker profiles), `technicals.py` (RSI, MACD, Bollinger, volatility, drawdown, beta).
- `dashboard.py`: every market-wide reading as data (regime with chart series, rotation with RRG tails, momentum leaders, positioning, coverage). `compute()` has no side effects; `load()` reads `reports/dashboard.json` for the API.
- `report.py`: `radar report` writes `dashboard.json` and the compact `summary.json` (a contract with the skills: its keys don't change without them), then the rank snapshots.
- `mine.py`: the holdings/watchlist/sold table (DKK return vs a shadow ACWI position, flags, stop levels). `radar run` uses it for summary.json; the API recomputes it live.
- `userstore.py`: the user's own edits in `userdata/radar.db` (SQLite, versioned with `PRAGMA user_version` + `MIGRATIONS`). Tables: watchlist adds/removes (an overlay `universe.holdings()` applies), transactions (the source of truth for positions), accounts, imports (undoable as a whole), symbol_map (remembered broker identifier → Yahoo symbol), meta. A backup goes to `userdata/backups/` before imports and undos. New stateful data (notes, targets, alarms) gets a new table here.
- `portfolio.py`: checks a trade before it is saved (unknown symbol, future date, oversold, price vs that day's close) and its effect on the position; the Portfolio page's positions view.
- `importers/`: broker exports → trades: reading CSV/XLSX in any encoding, presets in `presets.yaml`, generic column names, symbol matching, `preview` (never writes) and `commit`.
- `snapshot.py`: rank history for "new" and "Δ rank".
- `discovery/`: the separate wide scan. `sources.py` (Yahoo screener per exchange and per sector, cross-listing removal, iShares STOXX 600 holdings, positive-list ISIN → Yahoo ETF mapping, share-class choice, ETF categories; every source checks its counts and raises), `scan.py` (universe cache `data/discovery/universe.csv`, its own price store `data/discovery/prices.parquet` re-downloaded each scan with retries for Yahoo's rate limit, `reports/discovery.json`, snapshots in `data/discovery/snapshots/`). `signals/discovery.py` scores each market with the momentum formula and adds Δscore, size, liquidity and flags. Nothing here feeds the regime, breadth or the momentum page; `coverage.py` shows its age on the Data page without counting it in "oldest input" or stale sources.
- `coverage.py`: per-source freshness and coverage, the update log `data/sources.json`, and blind spots. These feed the "Data & coverage" page and `coverage` in summary.json. Stale sources and missing inputs are shown but don't vote; limits are in `settings.yaml` `coverage:`.
- `profile.py`: one ticker's full profile (used by `radar info` and the API), including the risk section; `compare()` puts several side by side with ACWI (`radar info A B`, the `/compare` skill).
- `api.py` + `api_models.py`: FastAPI with strict Pydantic response models. See [web-app.md](web-app.md).

## `web/`
Vite + React + TypeScript app served by `radar serve`: the only UI (the old static `radar.html` is gone). The CI brief doesn't depend on it; it reads `summary.json`.

## Sharing and releases
- This repo is private (its history holds personal briefs). `scripts/publish_public.py` exports HEAD without the paths in `publish/exclude.txt`, adds `publish/overlay/` (the public repo's release and smoke workflows), runs a leak check against `notes/leak-patterns.txt` and the git author, and commits into a clone of the public repo as "Market Radar". Pushing and tagging are manual.
- A `v*` tag in the public repo builds the release zip (`scripts/build_release_zip.py`: tracked files + prebuilt `web/dist`) that non-technical users download and start with `Start Market Radar.cmd` / `.command` (they install uv if needed, `uv sync`, `radar serve --open`).

## Local vs committed
- `data/`, `reports/`, `imports/*`, `notes/` and `userdata/` are gitignored. They hold local data, personal holdings, the user's own reading notes (`notes/bloomberg.md`, read by `/market-brief`) and the user's edits from the web app. Unlike `data/`, `userdata/` can't be re-downloaded.
- Exception: `data/snapshots/` is committed, because the CI brief needs the rank history for "new" and "Δ rank". The CI brief commits its own snapshots too.
- CI: `.github/workflows/monthly-brief.yml` runs the tests, restores holdings (and the web app's watchlist edits) from the HOLDINGS_BUNDLE secret, runs `radar run` and writes the brief. There is no CI on pull requests.
