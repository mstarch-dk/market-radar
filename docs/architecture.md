# Architecture

## Config
- `config/universe.yaml`: everything tracked: ETF groups, stock lists, macro tickers, CFTC/OECD sources, the watchlist, and `sector_etfs` (the sector ETF a stock is compared with on its profile, by Yahoo sector, with industry overrides). Theme ETFs carry a UCITS `isin`, checked against `imports/positivliste.xlsx` (SKAT list; only the latest year's sheet counts).
- `config/settings.yaml`: thresholds (regime, momentum, rotation, stops, coverage limits).

## `src/radar/`
- `updater.py`: the update steps behind `radar update`/`run` (each source logged, failures keep the cache) and the background job the app's *Update data* button runs. `health.py`: `radar doctor`.
- `ingest.py`: yfinance prices and FRED series → `data/*.parquet`. `config.write_parquet` writes atomically, so a running server never reads a half-written file.
- `external.py`: CFTC positioning, OECD leading indicators, the FactSet Earnings Insight PDF, Yahoo analyst consensus for holdings and watchlist, and Yahoo ticker detail (`fetch_detail` / `detail`, cached in `data/profiles/`).
- `universe.py`: config access, S&P 500 constituents (SSGA SPY holdings), names, currencies, sectors, Yahoo import, positive list.
- `signals/`: `risk.py` (weekly DKK beta ± se, alpha, downside beta, Sharpe/Sortino, drawdowns, factor tilts, correlations, risk budget), `gauges.py` (graded readings), `rotation.py` (RRG), `momentum.py`, `regime.py`, `levels.py` (rule-based trailing ATR stop / take-profit with reasons, for held stocks, theme ETFs and ticker profiles), `technicals.py` (RSI, MACD, Bollinger, volatility, drawdown, beta).
- `dashboard.py`: every market-wide reading as data (regime with chart series, rotation with RRG tails, momentum leaders, positioning, coverage). `compute()` has no side effects; `load()` reads `reports/dashboard.json` for the API.
- `report.py`: `radar report` writes `dashboard.json` and the compact `summary.json` (a contract with the skills: its keys don't change without them), then the rank snapshots.
- `mine.py`: the holdings/watchlist/sold table (DKK return vs a shadow ACWI position, flags, stop levels). `radar run` uses it for summary.json; the API recomputes it live.
- `userstore.py`: the user's own edits in `userdata/radar.db` (SQLite, versioned with `PRAGMA user_version` + `MIGRATIONS`). Today: watchlist adds/removes, an overlay on the Yahoo import that `universe.holdings()` applies and that survives `import-yahoo`. New stateful data (notes, targets, alarms) gets a new table here.
- `snapshot.py`: rank history for "new" and "Δ rank".
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
