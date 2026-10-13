# Commands

Always run Python through uv; the frontend uses pnpm.

## Data and report
- `uv run radar run`: incremental update of prices, FRED and non-price data (CFTC, OECD CLI, FactSet, analyst consensus), then build `reports/dashboard.json` (served by the web app) and `reports/summary.json` (read by the skills). A failing non-price source logs a warning and keeps its cached data.
- `uv run radar update` / `uv run radar report`: the two halves of `run`. `update --refresh-constituents` re-fetches the S&P 500 list.

## Holdings
- `uv run radar import-yahoo imports/yahoo_portfolio.csv`: replays BUY/SELL transactions (average-cost method) into `imports/holdings.csv` and `imports/transactions.csv`. Unknown transaction types are skipped with a warning.
- Watchlist: add or remove from any ticker page in the web app (stored in `userdata/radar.db`, survives re-imports). `watchlist:` in `config/universe.yaml` still works for fixed extras.
- `uv run radar bundle-holdings --set-secret`: refresh the HOLDINGS_BUNDLE secret used by the monthly GitHub Actions brief (holdings, transactions and the watchlist edits). Run it after each Yahoo import or watchlist change you want the brief to see.

## Single ticker
- `uv run radar info <TICKER> [--refresh]`: the full ticker profile as JSON (price development, momentum, technicals, stop levels, analyst estimates, valuation, ETF look-through, peers). The old flat keys stay at the top for `/research`. `--refresh` re-fetches Yahoo fundamentals now.
- `uv run radar serve [--open]` / `uv run radar ticker <TICKER>`: the local web app on http://127.0.0.1:8780 (dashboard pages and ticker profiles). See [web-app.md](web-app.md).

## Tests
- `uv run pytest -q` (also run in CI) and `pnpm -C web test`. See [testing.md](testing.md).
