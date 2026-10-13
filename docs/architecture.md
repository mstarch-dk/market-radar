# Architecture

## Config
- `config/universe.yaml`: everything tracked: ETF groups, stock lists, macro tickers, CFTC/OECD sources, the watchlist, and `sector_etfs` (the sector ETF a stock is compared with on its profile, by Yahoo sector, with industry overrides). Theme ETFs carry a UCITS `isin`, checked against `imports/positivliste.xlsx` (SKAT list; only the latest year's sheet counts).
- `config/settings.yaml`: thresholds (regime, momentum, rotation, stops, coverage limits).

## `src/radar/`
- `ingest.py`: yfinance prices and FRED series → `data/*.parquet`. `config.write_parquet` writes atomically, so a running server never reads a half-written file.
- `external.py`: CFTC positioning, OECD leading indicators, the FactSet Earnings Insight PDF, Yahoo analyst consensus for holdings and watchlist, and Yahoo ticker detail (`fetch_detail` / `detail`, cached in `data/profiles/`).
- `universe.py`: config access, S&P 500 constituents (SSGA SPY holdings), names, currencies, sectors, Yahoo import, positive list.
- `signals/`: `rotation.py` (RRG), `momentum.py`, `regime.py`, `levels.py` (rule-based trailing ATR stop / take-profit with reasons, for held stocks, theme ETFs and ticker profiles), `technicals.py` (RSI, MACD, Bollinger, volatility, drawdown, beta).
- `report.py` + `templates/radar.html.j2`: the static dashboard and `summary.json`.
- `snapshot.py`: rank history for "new" and "Δ rank".
- `coverage.py`: per-source freshness and coverage, the update log `data/sources.json`, and blind spots. These feed the "Data & coverage" tab and `coverage` in summary.json. Stale sources and missing inputs are shown but don't vote; limits are in `settings.yaml` `coverage:`.
- `profile.py`: one ticker's full profile (used by `radar info` and the API).
- `api.py` + `api_models.py`: FastAPI with strict Pydantic response models. See [web-app.md](web-app.md).

## `web/`
Vite + React + TypeScript app served by `radar serve`. The static `radar.html` and the CI brief don't depend on it.

## Local vs committed
- `data/`, `reports/`, `imports/*` and `notes/` are gitignored. They hold local data, personal holdings, and the user's own reading notes (`notes/bloomberg.md`, read by `/market-brief`).
- Exception: `data/snapshots/` is committed, because the CI brief needs the rank history for "new" and "Δ rank". The CI brief commits its own snapshots too.
- CI: `.github/workflows/monthly-brief.yml` runs the tests, restores holdings from the HOLDINGS_BUNDLE secret, runs `radar run` and writes the brief. There is no CI on pull requests.
