# Commands

Always run Python through uv; the frontend uses pnpm.

## Data and report
- `uv run radar run`: incremental update of prices, FRED and non-price data (CFTC, OECD CLI, FactSet, analyst
  consensus), then build `reports/dashboard.json` (served by the web app) and `reports/summary.json` (read by the
  skills). A failing non-price source logs a warning and keeps its cached data.
- `uv run radar doctor [--offline]`: plain-language setup check (Python, web build, data age, positive list,
  portfolio, investor profile, every data service, through the network layer, so a paused host says so), with how to
  fix each problem. The start scripts run it when something fails.
- The web app can do the same without a terminal: *Update data* (Data & coverage page, stale banner, welcome page),
  and the *Portfolio* page for entering, importing and correcting trades.
- `uv run radar ops [--days N] [--errors]`: the operations log: requests per host and source (count, errors, 429s,
  p50/p95 latency, last error), paused hosts, hosts over their daily budget, the last update; `--errors` adds the
  latest error events. `run`, `update` and `discover` are recorded as jobs (`cli_run`, `cli_update`, `cli_discover`)
  with their log.
- `uv run radar update` / `uv run radar report`: the two halves of `run` (`report` downloads nothing, is refused while
  another build runs, and is the app's *Rebuild the readings*). `update --refresh-constituents` re-fetches the S&P 500
  list.
- `update` also fetches the valuation and sentiment sources: the weekly stock (Yahoo screener, a few minutes) and ETF
  (Yahoo fund data) valuation snapshots (skipped while the last is under a week old), Shiller CAPE (multpl.com),
  Damodaran's equity risk premium, ECB euro-area yields, CBOE put/call ratios and the AAII survey. Each failure keeps
  its cache.
- `update` then fetches financial statements for the companies that are due (a new report expected, or not fetched for
  `refresh_days`; at most `max_per_run` a run, so the first backfill spreads over a few days): SEC EDGAR company facts
  for US companies (needs the SEC contact, below) and Yahoo statements for every tracked stock
  (`src/radar/fundamentals/`).
- `uv run radar fundamentals update [TICKER…] [--source edgar|yahoo] [--all]`: fetch statements now (the due ones, the
  named ones, or every one with `--all`).
- `uv run radar fundamentals show TICKER [--json]`: a ticker's statement items as the scores read them: each flow's
  last twelve months with how it was built (`fy`, `ytd`, `4q`, `yahoo_ttm`), the latest balances, fiscal years stored,
  and the source's tag or line for each.
- `uv run radar fundamentals check [--tolerance 0.1]`: US companies with both sources: EDGAR against Yahoo for TTM
  revenue, operating income and operating cash flow; lists the ones further apart than the tolerance.
- `uv run radar fundamentals contact [EMAIL] [--clear]`: the contact e-mail SEC asks for in the User-Agent of each
  EDGAR request (stored in radar.db, never defaulted; also on the Data page). Without it the EDGAR step fails and says
  so, and Yahoo covers US names.
- `uv run radar discover [--refresh-universe]`: the separate discovery scan (Nordic and European stocks from Yahoo's
  screener, the STOXX 600, positive-list ETFs) → `reports/discovery.json` for the *Discover* page. Run it about
  weekly; the list of names is re-built monthly (or with `--refresh-universe`). The page's *Scan again* button does
  the same. It never touches `radar run`'s data.

## Holdings
- `uv run radar portfolios list [--json] [--archived]` / `add NAME [--virtual] [--kind ask|frie_midler|pension|other]
  [--tag T]` / `edit NAME [--rename] [--kind] [--dividends reinvested|cash]` / `tag NAME TAG…` / `untag` / `default
  NAME` / `move NAME --to OTHER [--symbol X]` / `fork NAME NEW --date D [--cash X] [--tag T]` / `archive NAME
  [--undo]` / `delete NAME`: the portfolios. Real ones are your accounts and count as yours; virtual ones
  (simulations, A/B tests, forks) only when named.
- `uv run radar portfolio list [--symbol X] [--portfolio P] [--tag T]` / `add BUY|SELL <ticker> <qty> <price> [--date]
  [--fee] [--portfolio P] [--yes]` / `export [--out file] [--portfolio P] [--all]`: the stored trades, checked like in
  the app (errors block; warnings need `--yes`). Default: your real portfolios; `add` goes into the default portfolio.
- `uv run radar sim exits [NAME…] [--variant overlay|rules|both] [--start D] [--end D] [--fill next|same] [--json]
  [--out PATH]`: your real trades replayed with the stop/take-profit rule followed, from what was known each day
  (backtest/), into sim portfolios tagged `exits-overlay` / `exits-rules`, plus `reports/sim-exits.json` with every
  exit and what it saved vs holding on.
- `uv run radar study score [--horizons 1,3,6,12] [--variants all|k1,k2] [--n 15] [--exits MONTHS] [--seasoned]
  [--since D] [--no-regime] [--signal momentum|quality|value|qv] [--json] [--out PATH]`: the momentum score tested at
  every past month-end (backtest/study.py): rank IC with Newey-West t, quintile excess over the equal-weight universe,
  top N vs universe and ACWI, splits by year / regime / group / holdout, score variants judged against the baseline,
  and with `--exits` the stop/take-profit rule (both, stop only, take-profit only) on each date's top N. Writes
  `reports/score-study.json`. `--signal quality|value|qv` tests the kvalitetsscore, værdiscore or K+V instead, on US
  stocks from SEC EDGAR as known on each date (backtest/fund.py), with their pillars and single metrics as variants
  and the rank correlation with momentum per date; it writes `reports/score-study-<signal>.json` (no `--exits`).
- `uv run radar study exits [--horizons 3,6] [--n 15] [--variants all|k1,k2] [--since D] [--no-reentry] [--json]`:
  variants of the stop/take-profit rule (`exit_rules.exit_rule_variants`: TP off, wider k, slower ATR, no extended
  tightening, % trails, moving-average exits, plus re-entry on the best) on every month-end's top-N basket against
  holding: return and risk (max DD, vol, worst 20 sessions, the 10 % worst outcome), in-sample and holdout, with a
  pass/fail verdict. Writes `reports/exit-study.json`. `radar sim exits --rule-spec KEY` replays your own trades with
  one of those variants (its own sim portfolios and `reports/sim-exits-KEY.json`).
- `uv run radar study redeploy [--horizons 6,12] [--n 15] [--buffer 3] [--cooldown 21] [--max-per-sector N]
  [--max-per-group N] [--no-trend] [--arms all|k1,k2] [--since D] [--json] [--out PATH]`: the exit rules (200-day, ATR
  stop + take-profit, take-profit only) with the money parked in ACWI against redeployed into the best-scoring name
  not held (`redeploy.Picker`: trend filter, caps, cool-down), and a month-end rotation out of names outside buffer ×
  N with and without the rules, on every month-end's top N: return, max DD, Sharpe / Sortino over the ECB deposit
  rate, Calmar, IR vs ACWI, trades and fees, Sharpe against each arm's twin, in-sample and holdout, with a verdict.
  Writes `reports/redeploy-study.json`.
- `uv run radar sim picks-candidates --asof 1M|3M|6M|1Y|today|DATE [--top N] [--blind] [--views] [--model-cutoff
  YYYY-MM] [--fund] [--json] [--out PATH]`: the stock universe ranked as of that day, nothing after it
  (backtest/picks.py); `--blind` hides tickers behind C001… ids; `--fund` adds K+V, kvalitet and værdi as known on the
  day for US stocks (SEC EDGAR, backtest/fund.py).
- `uv run radar sim picks --asof … --name NAME (--picks FILE | --rule top-n [--n 15] [--max-per-sector K]
  [--max-per-group K] [--trend] [--weighting equal|score]) [--capital DKK] [--end D] [--model-cutoff YYYY-MM] [--tag
  T] [--json]` and `--rerun NAME|tag:T`: a hindsight basket simulated into sim portfolios `<name> · hold` / `· exits`
  / `· control` (tags `picks`, `picks-<slug>`), with ACWI, the equal-weight universe, the random-basket percentile and
  that day's score check in `reports/sim-picks/<slug>.json`. `/hindsight` drives it; the monthly brief keeps a forward
  paper trail tagged `picks-live`.
- `uv run radar abtest start [--capital DKK] [--n 15] [--max-per-sector 3] [--score qv|value]` / `status [--json]` /
  `refresh`: the forward A/B test (abtest.py): virtual baskets *A/B · Kvalitet+værdi*, *A/B · Momentum* (pooled
  momentum score) and *A/B · 50/50* tagged `ab-qvm`; the first report of each month records frozen picks (top N under
  a sector cap, equal weights), traded at the next session with `backtest.fee_bps`. `GET/POST /api/abtest`. Status:
  each basket against ACWI, weekly-return correlations, rebalances with turnover, the next due date.
- `uv run radar propose candidates --portfolio NAME --amount A [--tilt momentum|value|mix] [--mode
  conviction|fill-gaps] [--n N] [--weighting equal|inverse-vol] [--max-position P] [--horizon 3|6] [--no-etf] [--top
  40] [--json] [--out PATH]`: a basket proposal for adding A DKK (`50k`, `50.000`) to one portfolio (propose/): the
  gates (each exclusion listed), the proposal score per name, the rule-only basket under the caps on the portfolio
  after the addition, sized with the portfolio's fee schedule, an ETF filler for leftover cash (ACWI UCITS; on an
  aktiesparekonto only from the positive list), the rule study's figures and a draft picks file with each pick's exit
  criteria (`draft_picks`).
- `uv run radar propose freeze FILE`: stamps a picks file and stores it in `exports/proposals/<date>_<portfolio>.json`
  (never overwritten), so the picks are fixed before the model's numbers are seen.
- `uv run radar propose evaluate FILE [--max-position P] [--tolerance T] [--light] [--json] [--out PATH]`: a frozen
  proposal's sizing and constraints, exposures before → after vs ACWI (sector, region, currency, factors), ex-ante
  risk (shrunk covariance of weekly DKK returns), the drawdown three ways (rule study, vol-scaled block bootstrap,
  stress windows), the modelled excess from the rule study net of costs, the alternatives A0–A6 (ACWI, rule-only,
  other tilts, the n-frontier, topping up, sector ETFs, random baskets) and the decision rule. Saved as
  `<name>-evaluation.json` next to the picks file.
- `uv run radar propose shadow FILE --name NAME`: virtual copies of the portfolio plus the amount with the proposal,
  ACWI and the rule basket (tags `proposal`, `proposal-<date>`); `uv run radar propose review [--json]`: every frozen
  proposal since its day vs ACWI, vs its rule basket and its modelled drawdown band; `uv run radar propose check
  [--portfolio P] [--json]`: each open proposal's exit criteria today (Intact / Weakening / Triggered, and an "older
  rule" flag).
- `uv run radar study longrun [--panel all|french49,countries] [--horizons 1,3,6,12] [--variants all|k1,k2] [--since
  D] [--fetch] [--json] [--out PATH]`: the momentum score's rule on long monthly histories without survivorship bias
  (backtest/longrun.py): US industries since 1926 (French 49) and developed-market countries since 1986 (JKP), the
  same statistics and verdict rule as `radar study score` plus effective N and top N vs the panel's market, splits by
  decade / market trend / US recession, the base rates of the long-short factors (`longrun.factors`) and a
  survivorship gauge against `reports/score-study.json`. `--fetch` downloads the histories first
  (`factors.update_factors`, also a monthly step of `radar update`). Writes `reports/longrun-study.json`.
- `uv run radar study propose [--tilts momentum,value,mix] [--ns 3,5,8] [--horizons 3,6] [--since D] [--no-regime]
  [--json]`: the proposal rule at every past month-end (backtest/propose_study.py), held and with the proposal's
  exits, in DKK vs ACWI after costs: mean, median, 10/90 %, Newey-West t, effective N, hit rate, drawdowns, holdout
  and regime splits, the composite's IC, turnover. Writes `reports/propose-study.json` with the rule's settings hash
  (a changed rule makes it stale). Value and mix: US stocks only.
- `uv run radar performance [NAME…] [--tag T] [--start D] [--json]`: returns over time in DKK vs ACWI (TWR, MWR,
  drawdown) from a common start; tags pool their portfolios into one line.
- `uv run radar import-yahoo imports/yahoo_portfolio.csv`: a Yahoo Finance export into the store (it replaces the
  previous Yahoo import; manual and broker trades are kept). Unknown transaction types are skipped with a warning.
- Watchlist: add or remove from any ticker page in the web app (stored in `radar.db` in the data folder, survives
  re-imports). `watchlist:` in `config/universe.yaml` still works for fixed extras.
- `uv run radar bundle-holdings [--out FILE] [--include-virtual]` / `unbundle-holdings [--file FILE]`: carry your data
  to another machine: the real portfolios (all with `--include-virtual`) with their transactions, kinds and tags, the
  watchlist edits, market views and regime vote choices, as one base64 text. Restoring takes a database backup first
  and gives each portfolio in the bundle exactly its rows. The file holds your holdings: keep it private.

## Data folder, backups, export
- Every command takes `--home PATH` (use that data folder this once) and `radar --version` prints the version. Without
  a data folder, only `setup`, `paths`, `serve`, `doctor`, `openapi` and `ticker` run; data from a newer version is
  refused (read-only).
- `uv run radar paths [--json]`: where the data folder, its parts, the history and the cache are, and how they were
  found (`option`, `env`, `portable`, `pointer`); before setup, the old folders found with data in them.
- `uv run radar setup [--from OLD] [--to DIR] [--fresh] [--use DIR] [--no-market-data] [--yes]`: choose the data
  folder. With no options it lists this install folder and its siblings that hold data from before the data folder and
  copies the chosen one (verified; the old folder only gets `MOVED.txt`). `--fresh` starts empty, `--use` points to a
  data folder that exists (moved, another drive). Remembered in the pointer file unless `MARKET_RADAR_HOME` or a
  `portable.json` decides.
- `uv run radar backup [--reason WORD] [--mirror PATH|off]`, `uv run radar backups`, `uv run radar restore FILE
  [--yes]`: back up the data folder now (also daily and before a new version's first use), list backups here and in
  the mirror folder, put one back (what is there is backed up first).
- `uv run radar export [--out FILE]` / `uv run radar import-export FILE [--yes]`: everything of yours as
  CSV/JSON/Markdown with `EXPORT.md`; reading one back replaces the portfolios it names and adds documents that aren't
  there.
- `uv run radar updates [--on|--off]`: the opt-in daily check for a new release (settings.yaml `updates.repo`).
- Environment: `MARKET_RADAR_HOME`, `MARKET_RADAR_CACHE`, `MARKET_RADAR_CONFIG` (the pointer file's folder).

- `uv run radar views [--json] [--archived]`: your market views (the *Market views* page) with the radar's evidence
  for each. Personal; the skills read it.

## Single ticker
- `uv run radar info <TICKER> [--refresh]`: the full ticker profile as JSON (price development, momentum, technicals,
  stop levels, analyst estimates, valuation, kvalitetsscore and værdiscore with each metric's percentile (`quality`,
  stocks with stored statements), ETF look-through, peers). The old flat keys stay at the top for `/research`.
  `--refresh` re-fetches Yahoo fundamentals now.
- `uv run radar info <T1> <T2> … [--personal] [--out exports/x.json]`: several tickers side by side, for `/compare`:
  profiles (built anonymously unless `--personal`), ACWI's returns and risk as the benchmark candidate, weekly DKK
  correlations and a metrics table with the best value per row. Unknown tickers become `error` entries. One ticker
  keeps the single-ticker output above.
- `uv run radar serve [--open]` / `uv run radar ticker <TICKER>`: the local web app on http://127.0.0.1:8780
  (dashboard pages and ticker profiles). See [web-app.md](web-app.md).
- `.\scripts\restart.ps1 [-Pull] [-Report] [-Open] [-Port N]` (Windows): after a `git pull`, restart from source in
  one step: `pnpm install` and `build` (the old server keeps running if that fails), stop the server on the port (and
  the start script's window), `uv sync`, optionally `radar report`, then `radar serve` in this window.

## Marketing material
- `uv run --group marketing python scripts/marketing.py workspace | seed | explore /path… | shots [ID…] | pdf | check
  | edition | all`: the Danish brochure in `marketing/` from a demo copy of the app (`.demo/`, port 8790, launch
  config `radar-demo`) with a fictional investor. The `/marketing` skill runs it; see
  [marketing/README.md](../marketing/README.md).

## Tests
- `uv run pytest -q` and `pnpm -C web test`. See [testing.md](testing.md).
