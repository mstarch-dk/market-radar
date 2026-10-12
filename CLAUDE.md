# Market Radar

A personal investing toolkit for a Danish investor (frie midler + aktiesparekonto). It focuses on proactively spotting trends, sector and theme rotation, and 1–6-month momentum. Portfolio tracking itself stays in Yahoo Finance. Benchmark: MSCI ACWI. Everything produced here is analysis, not advice.

## Commands (always run through uv)
- `uv run radar run`: incremental update of prices, FRED and non-price data (CFTC, OECD CLI, FactSet), then build `reports/radar.html` and `reports/summary.json`. A failing non-price source logs a warning and keeps its cached data.
- `uv run pytest -q`: tests for the parsers and signals (also run in CI)
- `uv run radar update` / `uv run radar report`: the two halves of `run`
- `uv run radar import-yahoo imports/yahoo_portfolio.csv`: replays BUY/SELL transactions into `imports/holdings.csv` and `imports/transactions.csv`
- `uv run radar info <TICKER>`: JSON radar context for one ticker
- `uv run radar bundle-holdings --set-secret`: refresh the HOLDINGS_BUNDLE secret used by the monthly GitHub Actions brief (run after each Yahoo import)

## Skills
- `/market-brief` → `briefs/YYYY-MM-DD.md`
- `/research <ticker>` → `research/<TICKER>.md`
- `/journal …` and `/journal review` → `journal/`

## Layout
- `config/universe.yaml`: everything tracked (ETF groups, stock lists, macro). Theme ETFs carry a UCITS `isin`, checked against `imports/positivliste.xlsx` (SKAT list; only the latest year sheet counts). `config/settings.yaml`: thresholds.
- `src/radar/`: `ingest.py` (yfinance/FRED → `data/*.parquet`), `external.py` (CFTC positioning, OECD leading indicators, FactSet Earnings Insight PDF → `data/*.parquet`), `universe.py` (config, constituents, names, currencies, sectors, Yahoo import, positive list), `signals/` (rotation/RRG, momentum, regime), `report.py` + `templates/radar.html.j2`, `snapshot.py` (rank history for "new" and "Δ rank").
- `data/`, `reports/`, `imports/*` and `notes/` are gitignored: local data, personal holdings, and the user's own reading notes (`notes/bloomberg.md`, read by `/market-brief`).

## Conventions
- Prices are adjusted closes in each listing's currency. Holding-vs-benchmark comparisons are done in DKK against a shadow ACWI position with identical cash flows.
- Yahoo tickers: `.CO` Copenhagen, `.ST` Stockholm, `.OL` Oslo, `.HE` Helsinki, `.DE` Xetra, `.L` London (often GBp = pence).
- Prefer the proper fix over a workaround. If a better data source or tool would clearly help, propose it.
