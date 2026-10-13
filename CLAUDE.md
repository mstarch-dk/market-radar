# Market Radar

A personal investing toolkit for a Danish investor (frie midler + aktiesparekonto). It focuses on proactively spotting trends, sector and theme rotation, and 1–6-month momentum. Portfolio tracking itself stays in Yahoo Finance. Benchmark: MSCI ACWI. Everything produced here is analysis, not advice.

## Commands (always run through uv)
- `uv run radar run`: incremental update of prices, FRED and non-price data (CFTC, OECD CLI, FactSet), then build `reports/radar.html` and `reports/summary.json`. A failing non-price source logs a warning and keeps its cached data.
- `uv run pytest -q`: tests for the parsers, signals, holdings import, config and an end-to-end `report.build()` on a synthetic market (also run in CI). `tests/fixtures/` holds trimmed copies of real FRED/OECD/CFTC/FactSet payloads; when a source changes format, fix the parser and refresh its fixture. A parse that finds nothing should raise (so the update is logged as failed and the cache kept), not store an empty result.
- `uv run radar update` / `uv run radar report`: the two halves of `run`
- `uv run radar import-yahoo imports/yahoo_portfolio.csv`: replays BUY/SELL transactions into `imports/holdings.csv` and `imports/transactions.csv`
- `uv run radar info <TICKER>`: the full ticker profile as JSON (price development, momentum, technicals, stop levels, analyst estimates, valuation, ETF look-through, peers). The old flat keys stay at the top for `/research`.
- `uv run radar serve [--open]` / `uv run radar ticker <TICKER>`: the local web app on http://127.0.0.1:8780 (search plus a ticker page). Build the frontend once with `pnpm -C web install` and `pnpm -C web build`; during frontend work run `pnpm -C web dev` (port 5173, proxies `/api` to 8780).
- `pnpm -C web gen:api`: regenerate `web/src/api/schema.ts` from the API models after changing `src/radar/api_models.py`; `pnpm -C web build` then fails on any field the UI uses that no longer exists.
- `uv run radar bundle-holdings --set-secret`: refresh the HOLDINGS_BUNDLE secret used by the monthly GitHub Actions brief (run after each Yahoo import)

## Skills
- `/market-brief` → `briefs/YYYY-MM-DD.md`
- `/research <ticker>` → `research/<TICKER>.md`
- `/journal …` and `/journal review` → `journal/`

## Layout
- `config/universe.yaml`: everything tracked (ETF groups, stock lists, macro). Theme ETFs carry a UCITS `isin`, checked against `imports/positivliste.xlsx` (SKAT list; only the latest year sheet counts). `config/settings.yaml`: thresholds.
- `src/radar/`: `ingest.py` (yfinance/FRED → `data/*.parquet`), `external.py` (CFTC positioning, OECD leading indicators, FactSet Earnings Insight PDF, Yahoo analyst consensus for holdings/watchlist → `data/*.parquet`), `universe.py` (config, constituents, names, currencies, sectors, Yahoo import, positive list), `signals/` (rotation/RRG, momentum, regime, `levels.py`: rule-based trailing ATR stop / take-profit with reasons, shown for held stocks and theme ETFs and in `radar info`), `report.py` + `templates/radar.html.j2`, `snapshot.py` (rank history for "new" and "Δ rank"), `coverage.py` (per-source freshness and coverage, the update log `data/sources.json`, blind spots: the "Data & coverage" tab and `coverage` in summary.json; stale sources and missing inputs are shown but don't vote, limits in `settings.yaml` `coverage:`), `profile.py` (one ticker's full profile; `signals/technicals.py` for RSI/MACD/Bollinger/volatility/beta; Yahoo detail via `external.detail`, cached in `data/profiles/`), `api.py` + `api_models.py` (FastAPI, strict Pydantic response models).
- `web/`: Vite + React + TypeScript app served by `radar serve`. Python computes every number; the frontend only formats and draws (lightweight-charts). The static `radar.html` and the CI brief don't depend on it.
- Yahoo detail units are inconsistent (dividend yield and expense ratio in percent, margins as fractions, debt/equity ×100): `external.parse_*` normalise to fractions and drop implausible values with a note instead of showing them. Anything shown as a session (last price, day change, recent bars, chart) uses the ticker's own bars, not the forward-filled wide frames.
- `data/`, `reports/`, `imports/*` and `notes/` are gitignored: local data, personal holdings, and the user's own reading notes (`notes/bloomberg.md`, read by `/market-brief`). Exception: `data/snapshots/` is committed, because the CI brief needs the rank history for "new" and "Δ rank" (it commits its own snapshots too).

## Conventions
- Prices are adjusted closes (dividends + splits) in each listing's currency, with the traded close kept as `raw_close`. When a new dividend/split re-bases Yahoo's history, `radar update` re-downloads that ticker in full. Holding-vs-benchmark comparisons are total returns in DKK against a shadow ACWI position with identical cash flows.
- Yahoo tickers: `.CO` Copenhagen, `.ST` Stockholm, `.OL` Oslo, `.HE` Helsinki, `.DE` Xetra, `.L` London (often GBp = pence).
- Prefer the proper fix over a workaround. If a better data source or tool would clearly help, propose it.
