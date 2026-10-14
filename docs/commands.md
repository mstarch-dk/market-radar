# Commands

Always run Python through uv; the frontend uses pnpm.

## Data and report
- `uv run radar run`: incremental update of prices, FRED and non-price data (CFTC, OECD CLI, FactSet, analyst consensus), then build `reports/dashboard.json` (served by the web app) and `reports/summary.json` (read by the skills). A failing non-price source logs a warning and keeps its cached data.
- `uv run radar doctor [--offline]`: plain-language setup check (Python, web build, data age, positive list, portfolio, investor profile, every data service, through the network layer, so a paused host says so), with how to fix each problem. The start scripts run it when something fails.
- The web app can do the same without a terminal: *Update data* (Data & coverage page, stale banner, welcome page), and the *Portfolio* page for entering, importing and correcting trades.
- `uv run radar ops [--days N] [--errors]`: the operations log: requests per host and source (count, errors, 429s, p50/p95 latency, last error), paused hosts, hosts over their daily budget, the last update; `--errors` adds the latest error events. `run`, `update` and `discover` are recorded as jobs (`cli_run`, `cli_update`, `cli_discover`) with their log.
- `uv run radar update` / `uv run radar report`: the two halves of `run`. `update --refresh-constituents` re-fetches the S&P 500 list.
- `update` also fetches the valuation and sentiment sources: the weekly stock (Yahoo screener, a few minutes) and ETF (Yahoo fund data) valuation snapshots (skipped while the last is under a week old), Shiller CAPE (multpl.com), Damodaran's equity risk premium, ECB euro-area yields, CBOE put/call ratios and the AAII survey. Each failure keeps its cache.
- `uv run radar discover [--refresh-universe]`: the separate discovery scan (Nordic and European stocks from Yahoo's screener, the STOXX 600, positive-list ETFs) → `reports/discovery.json` for the *Discover* page. Run it about weekly; the list of names is re-built monthly (or with `--refresh-universe`). The page's *Scan again* button does the same. It never touches `radar run`'s data.

## Holdings
- `uv run radar portfolios list [--json] [--archived]` / `add NAME [--virtual] [--kind ask|frie_midler|pension|other] [--tag T]` / `edit NAME [--rename] [--kind] [--dividends reinvested|cash]` / `tag NAME TAG…` / `untag` / `default NAME` / `move NAME --to OTHER [--symbol X]` / `fork NAME NEW --date D [--cash X] [--tag T]` / `archive NAME [--undo]` / `delete NAME`: the portfolios. Real ones are your accounts and count as yours; virtual ones (simulations, A/B tests, forks) only when named.
- `uv run radar portfolio list [--symbol X] [--portfolio P] [--tag T]` / `add BUY|SELL <ticker> <qty> <price> [--date] [--fee] [--portfolio P] [--yes]` / `export [--out file] [--portfolio P] [--all]`: the stored trades, checked like in the app (errors block; warnings need `--yes`). Default: your real portfolios; `add` goes into the default portfolio.
- `uv run radar performance [NAME…] [--tag T] [--start D] [--json]`: returns over time in DKK vs ACWI (TWR, MWR, drawdown) from a common start; tags pool their portfolios into one line.
- `uv run radar import-yahoo imports/yahoo_portfolio.csv`: a Yahoo Finance export into the store (it replaces the previous Yahoo import; manual and broker trades are kept). Unknown transaction types are skipped with a warning.
- Watchlist: add or remove from any ticker page in the web app (stored in `userdata/radar.db`, survives re-imports). `watchlist:` in `config/universe.yaml` still works for fixed extras.
- `uv run radar bundle-holdings [--out FILE] [--include-virtual]` / `unbundle-holdings [--file FILE]`: carry your data to another machine: the real portfolios (all with `--include-virtual`) with their transactions, kinds and tags, the watchlist edits, market views and regime vote choices, as one base64 text. Restoring takes a database backup first and gives each portfolio in the bundle exactly its rows. The file holds your holdings: keep it private.

- `uv run radar views [--json] [--archived]`: your market views (the *My market views* page) with the radar's evidence for each. Personal; the skills read it.

## Single ticker
- `uv run radar info <TICKER> [--refresh]`: the full ticker profile as JSON (price development, momentum, technicals, stop levels, analyst estimates, valuation, ETF look-through, peers). The old flat keys stay at the top for `/research`. `--refresh` re-fetches Yahoo fundamentals now.
- `uv run radar info <T1> <T2> … [--personal] [--out exports/x.json]`: several tickers side by side, for `/compare`: profiles (built anonymously unless `--personal`), ACWI's returns and risk as the benchmark candidate, weekly DKK correlations and a metrics table with the best value per row. Unknown tickers become `error` entries. One ticker keeps the single-ticker output above.
- `uv run radar serve [--open]` / `uv run radar ticker <TICKER>`: the local web app on http://127.0.0.1:8780 (dashboard pages and ticker profiles). See [web-app.md](web-app.md).

## Marketing material
- `uv run --group marketing python scripts/marketing.py workspace | seed | explore /path… | shots [ID…] | pdf | check | edition | all`: the Danish brochure in `marketing/` from a demo copy of the app (`.demo/`, port 8790, launch config `radar-demo`) with a fictional investor. The `/marketing` skill runs it; see [marketing/README.md](../marketing/README.md).

## Tests
- `uv run pytest -q` and `pnpm -C web test`. See [testing.md](testing.md).
