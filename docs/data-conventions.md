# Data conventions

The radar's output must be truthful: a missing value is shown as missing, never as 0 or as a guess.

## Prices
- Prices are adjusted closes (dividends + splits) in each listing's currency; the traded close is kept as `raw_close`.
- When a new dividend or split re-bases Yahoo's history, `radar update` re-downloads that ticker in full rather than
  merging two adjustment bases.
- A full download never shrinks a ticker's history (`ingest.stitch`): stored bars before the new history's first bar
  or after its last are kept, moved to the new adjustment basis by the factors at the nearest bar both have (adjusted
  prices by the ratio of adjusted closes, the traded close by the ratio of traded closes, volume by its inverse). A
  ticker whose new history starts later than the stored one is reported as `short` and its download start isn't
  recorded in `prices_from.json`, so the next update asks again. A store from before raw closes were kept is
  downloaded again in full; tickers Yahoo doesn't return keep their bars with the traded close unknown. The store is
  re-read and written under a file lock (`locks.file_lock`), so an update in the app, one in a terminal and a ticker
  lookup never overwrite each other. Afterwards, tickers without a bar on the benchmark's last session are fetched
  once more; the rest are reported as `behind` (log, Operations, *Data & coverage*), not hidden: Yahoo's history for a
  whole exchange can lag a session.
- The history starts `history_years` back, or `backtest.warmup_days` before your first trade when that is earlier
  (capped at `backtest.max_years`), so your trades can be valued and the rule replayed from the day you bought. A
  shallower stored history is downloaded again in full, once (`data/prices_from.json`).
- `ingest.wide()` forward-fills up to 5 sessions, which is right for return windows. Anything shown as a session uses
  the ticker's own bars (`market.Market.bars`), so a missing Yahoo bar is a gap, not a flat day. That covers the last
  price, day change, recent bars and the chart.
- Holding-vs-benchmark comparisons are total returns in DKK against a shadow ACWI position with identical cash flows.
- DKK rates (`fxrates.fx_to_dkk`): Yahoo's `xxxDKK=X` pairs (`FX_DKK`), forward-filled over gaps; GBp uses `GBPDKK=X`
  × 0.01. Yahoo has no KRW/DKK or TWD/DKK quote, so won and Taiwan dollar go through USD (`FX_VIA_USD`: `USDDKK=X /
  USDKRW=X`, `USDDKK=X / USDTWD=X`; either leg missing means no rate). A currency without any pair (CNY) has no DKK
  value, never 1.0.
- Yahoo tickers: `.CO` Copenhagen, `.ST` Stockholm, `.OL` Oslo, `.HE` Helsinki, `.DE` Xetra, `.L` London (often GBp =
  pence).

## Sources
- A source that replaces its stored file checks the answer first (`guard.replace`): an empty answer, a series that
  ends earlier than stored or has markedly fewer rows keeps the stored file (`guard.Shrunk`); a configured series
  missing from the answer keeps its stored values, with a note in the step's message. Every source that replaces what
  it stores uses it: OECD CLI and the ECB (rolling six-year windows, so their start may move by up to two months),
  each FRED series (a series that shrinks counts as a failed series and keeps its cached values; one that starts
  later than stored, like ICE BofA's spreads that FRED serves for ~3 years only, is merged into the stored one and
  kept in history as `fred_rolling.parquet`; a web page instead of CSV, such as FRED's maintenance page, is
  `ingest.Unavailable`: the step stops asking and every series keeps its cached values), AAII, and CAPE/ERP
  (all of one source's series are checked before any is written). Discovery prices are re-downloaded whole, but names
  Yahoo didn't return keep their stored bars in the window; their last date then marks them stale.
- Reference caches remember answers, not failures: a name lookup that fails isn't cached (the ticker is shown
  meanwhile), a sector only from an answer that says what the instrument is, and an ISIN Yahoo couldn't find is
  searched again after `RETRY_UNRESOLVED_DAYS` (90). A ticker profile block (estimates, recommendations, fund data)
  that fails on a refresh keeps its cached copy, and the profile says from when.
- A parse that finds nothing raises. The update is then logged as failed and the cache kept, rather than storing an
  empty result as a success. Examples: FactSet without growth figures, CFTC with renamed columns, OECD with duplicate
  series or no observations, a short SPY list, a positive list without an ISIN column.
- Sources older than their `coverage.max_age` turn stale and stop voting in the regime.
- Yahoo detail units are inconsistent: dividend yield and expense ratio arrive in percent, margins as fractions,
  debt/equity ×100. `external.parse_*` normalise to fractions and range-check them; implausible values are dropped
  with a note instead of shown.
- Discovery market caps: Yahoo's screener reports `marketCap` in the quote currency, except that GBp (pence) quotes
  have caps in GBP. They are converted to DKK at the latest FX close; a missing cap or rate stays missing (size
  unknown), never 0. Traded value uses `raw_close × volume`, divided by 100 for GBp.
- Discovery market caps need a DKK rate for each market's currency (`scan.FX_NEEDED`): from the price store when it is
  recent, else Yahoo, with a rate Yahoo misses taken from the store at any age; one missing everywhere raises rather
  than leaving a market without caps. The screener is paged until a page comes back short, or until Yahoo's `total`
  when it gives one.
- A yfinance answer without Close / Adj Close for a ticker skips that ticker (reported as missing); none having them
  raises (the download format changed). Yahoo detail is stored as JSON with missing dates as null, never the text
  "NaT".
- The discovery universe is today's listings only (no delisted names: survivorship bias), and its sectors come from
  the screener's own sector filter (for the S&P 500 market, which skips that filter: the index's GICS sector from the
  iShares file, mapped to Yahoo's names). Industries are shown only where the radar's sector cache already has them.
- Analyst targets are converted to the radar's price units by the ratio of our close to Yahoo's price on the fetch
  date. This handles GBp vs GBP and ADR ratios.

## Valuation (`sources/valuation.py`, `signals/valuation.py`)
- **Stocks**: a weekly snapshot (one per ISO week; a re-run replaces it) of Yahoo's screener per exchange
  (`discovery.yaml` markets + `valuation.us`), plus one-by-one lookups for tracked names it misses (Asia). Every
  exchange must return its minimum count, or the step fails and the last snapshot stays.
- **Mixed currencies in one quote**: when a company reports in another currency than it trades in (Shell: pence / USD,
  Vestas: DKK / EUR), Yahoo's trailing and next-year EPS come converted into the trading currency (pounds for pence
  quotes), this year's EPS in the reporting currency. So `pe_ttm` and `pe_fy1` are price / EPS in the trading currency
  (they match Yahoo's own trailing and forward P/E), and `pe_cy` uses the price converted into the reporting currency.
  Yahoo's own `priceEpsCurrentYear` is wrong for those names and isn't used. No rate (Yahoo has no CNY/DKK quote)
  means no `pe_cy`, never a mixed ratio.
- **Bases**: `pe_fy1` = next fiscal year's consensus EPS (the tables' "P/E next yr"), `pe_cy` = this fiscal year,
  `pe_ttm` = trailing 12 months. Negative or zero earnings, a P/E outside 1–300, and (one-by-one lookups only) a
  next-year EPS more than 3× or under ⅓ of the trailing one give no P/E, with a note in the snapshot.
- **P/E vs sector**: `pe_fy1` divided by the median of the same Yahoo sector among the stock's peers: its radar group
  (Momentum, holdings) or its Discover market. At least `valuation.min_peers` names with a P/E, else missing.
- **EPS revisions**: the change in the next-year EPS between the latest snapshot and the one closest to 4 or 12 weeks
  earlier (±4 days); missing until those exist. When the fiscal year has rolled over (this year's estimate is now last
  time's next year), the same year is compared. Names with `cross_ccy` are left out: Yahoo converts their estimate at
  today's rate, so an FX move would look like a revision.
- **Funds**: Yahoo's `funds_data.equity_holdings` stores multiples inverted (earnings yield: 0.0312 for a fund on 32×
  earnings); they are turned around and range-checked (P/E 3–150). Yahoo doesn't say whether a fund's P/E is trailing
  or forward. `pe_vs_acwi` divides by ACWI's own fund P/E (same basis); `pe_pct` (percentile in its own history) needs
  26 weekly snapshots. A new snapshot needs fund data for `valuation.etf_min_share` of the last snapshot's ETFs, else
  the last one is kept (a throttled run returns a handful). A second run in the same ISO week replaces that week's
  rows but carries over the names it missed, noted "carried from <date>" (stocks too).
- **Market**: Shiller CAPE monthly since 1871 from multpl.com (Shiller's method; it matches Shiller's own file where
  both are final; Shiller's public file stopped at Sep 2024), Damodaran's implied ERP on trailing-12-month cash flows
  (his headline number, monthly since 2008), and the yield gap: 100 / FactSet's forward P/E − FRED `DFII10`.
  Percentiles exclude the latest point.

## Sentiment (`sources/sentiment.py`)
- CBOE: one JSON per trading day; a 403/404 day is skipped (holiday, not yet published) and, within
  `sentiment.putcall_retry_days`, asked again on later runs instead of staying a hole; a week of new weekdays with
  nothing raises. A failure part-way stores the days already fetched and raises `sourcelog.PartialFailure` (logged as
  a failed update that says what was kept). The equity ratio's 10-day average is ranked against ~3 years, once 60 days
  exist.
- AAII: the weekly `.xls`; the header row must read Bullish / Neutral / Bearish and the three shares must add up to
  ~100%. The bull − bear spread is ranked since 1987. Both are contrarian readings and never vote.

## Regime votes
- Rows carry a `group`; groups in `settings.yaml regime.votes` (credit_eu on, valuation off by default) can be
  switched off. A switched-off row keeps its reading and gauge but leaves the vote. Your choice (the Regime page) is
  stored in `userdata` (`meta.regime_votes`), applied live by `/api/regime`, `/api/me` and the ticker pages, used by
  the next `radar report` (summary.json) and carried in the holdings bundle.

## Graded readings (gauges)
- `signals/gauges.py` grades a reading between its thresholds: anchors (value, score) are interpolated to a score in
  [-1, 1] (+ favourable, green; − warning, red), cut into 9 levels, with a granular word ("near overbought"). One-way
  risk measures (VIX, ATR %, beta, crowding) are `sequential` and never turn green.
- Specs live in `settings.yaml` `gauges:`; regime rows build theirs from the `regime:` thresholds, so a threshold is
  written once. The regime vote itself is unchanged.
- A missing value is not graded (no gauge), never treated as 0. Gauges are display data: `summary.json` leaves them
  out.
- Watch-outs are gauges at level −3 or below, excluding traits (beta, ATR %) and the hypothetical stop/target of a
  ticker you don't hold.

## Risk statistics (`signals/risk.py`)
- Weekly (Friday) returns in DKK; the week still in progress is left out (it covers fewer days). Windows: 1y and 3y
  (`settings.yaml` `risk:`), each reporting its `n_weeks`; under `min_weeks` there is no statistic.
- Beta comes with its standard error and R²; alpha (Jensen, annualised) with its t-stat. With the FRED 3-month T-bill
  (`DGS3MO`) returns are excess returns and Sharpe/Sortino exist; without it they are null and alpha is on raw returns
  (`alpha_basis` says which).
- Factor tilts regress on ACWI plus factor/sector ETFs *minus ACWI*, so a loading means exposure beyond the market.
  Descriptive: short samples, correlated factors.
- One-year betas are noisy (XLE's 1y beta was −0.9 while its 3y beta is +0.45): compare windows and read the standard
  error before relying on either.

## Your portfolios (`userstore/`, `universe.py`, `portfolios/checks.py`, `importers/`)
- Trades are the source of truth, in `radar.db` in the data folder (SQLite, versioned migrations, a copy in `backups/`
  before every import, undo, move and schema upgrade). Each row records its portfolio, its source (manual, yahoo,
  nordnet, fork, sim, …) and its import.
- **Portfolios**: a real portfolio is one of your accounts (tax kind ask / frie_midler / pension / other); a virtual
  one is a simulation or an A/B test. Only real, non-archived portfolios count as yours: holdings, `summary.json`,
  `radar info --personal`, the holdings bundle and the skills see virtual ones only when they are chosen (by id or
  tag). Tags are free-form labels for grouping (A/B groups); they never change what counts as yours. Trades from
  before portfolios, without an account, are in a real portfolio "Main" (the default) until moved.
- Positions are derived with the average-cost method (gennemsnitsmetoden): fees are part of the acquisition cost, a
  sale removes cost in proportion. Per portfolio and pooled; the pool is right for the return vs ACWI but not for tax,
  where an aktiesparekonto is separate.
- **Cash rows** (DEPOSIT, WITHDRAW, DIVIDEND, FEE, INTEREST) carry an amount in DKK. A trade's DKK cash effect is
  quantity × price ± fee at its booked `fx_rate`, else Yahoo's rate that day. A virtual portfolio can only spend what
  was deposited; a real one with a cash ledger warns; a real one without cash rows isn't checked. DIVIDEND rows count
  only under the dividend policy `cash`: with the default `reinvested`, adjusted prices already contain the dividends.

## External requests and the operations log (`net.py`, `ops.py`)
- **Pacing**: limits per host pattern (settings.yaml `network.hosts`, glob patterns, first match wins, else
  `network.default`): a token bucket (`rate`, `burst`) and a cap on parallel requests (`concurrency`). Hosts matching
  one pattern share them (all of Yahoo's hosts are one budget). Plain HTTP (`net.get`) retries 429, 5xx, timeouts and
  connection errors with exponential backoff and jitter, obeying `Retry-After` (one longer than `max_wait` gives up);
  anything else (a 404, a parse error later) is not retried, it fails loudly. A host's pause lives in `ops.db`, so
  the CLI and the server share it.
- Every external request is recorded with its host and **path only**: the query string is never stored, and `key=`,
  `api_key=`, `token=`, `crumb=` and the like in a path are masked. Rows hold status (None when no answer came),
  duration (time on the wire, not the waits between retries), size, attempt number and the source/job it belongs to.
- An error is a request with no answer or an HTTP status ≥ 400, except statuses a caller marks as expected (FactSet's
  daily probe and CBOE's holidays answer 403/404). A 429 is counted separately; `trip` of them within `window_min`
  pause the host (15 min, doubling per repeat within a day, at most `max_cooldown_min`). While paused, requests fail
  at once with `Throttled` and the step keeps its cached data, like any failure.
- Budgets are soft: going over a host's daily count is a warning event, never a block. Latency percentiles are left
  out (None), not 0, when nothing was timed.
- yfinance requests are paced and recorded but retried by yfinance itself; our retry policy applies to plain HTTP
  only.

## Returns over time (`portfolios/performance.py`)
- Each portfolio is valued in DKK at every close of the benchmark's calendar (a row on a non-trading day counts on the
  next session). `reinvested` (default): adjusted closes, each lot's shares scaled by adjusted/traded close on its
  trade date (as the holdings table's shadow method, `mine.vs_shadow`); `cash`: traded closes plus DIVIDEND rows.
- **Funding**: `ledger` when the portfolio has deposits or withdrawals (value = holdings + cash; only deposits and
  withdrawals are money in or out); `implicit` otherwise (every buy is new money, every sale or income money taken
  out).
- **TWR**: inflows count at the start of a day, outflows at its end: r = (V + out) / (V_prev + in) − 1, chained into
  an index of 100. So money that arrives and is invested at the close sits idle that day: one day of cash drag, not an
  error. **MWR**: XIRR of the external flows and the final value, only with a year of history (as TWR p.a.).
- **Gaps, never zeros**: a held symbol without a price (forward-filled 5 sessions at most) or DKK rate leaves that
  day's value unknown (None), as does a day without capital; the return is chained across the gap from the last
  valid value. Rows older than the price history (`history_years`) can't be valued then: the series opens on the
  first day everything can be valued, from what was held then. A trade whose DKK value is unknown breaks the chain
  on its day (left out, and said so), and the money-weighted figures are dropped.
- **ACWI**: the benchmark in DKK from the first day's close, and "ACWI with the same cash flows": the external flows
  buy and sell ACWI units at each day's close (stops with a note if a withdrawal is larger than its value).
- **Comparisons** (A/B): portfolios and tag groups (pooled) from a common start, each opening at its value on that
  close; a fork (`simulate.fork`) is a virtual copy at a day's close, so the two start level.
- Prices are per share in the instrument's quote currency (as on Yahoo). The editor and the importers flag a price
  about 100× off (GBp vs GBP) or far from that day's traded close, and block a sale larger than the position.
- Imports: presets for Yahoo (verified), Nordnet, Saxo and Danske Bank (unverified until a real export is added as a
  test fixture), generic column names otherwise. Instruments are matched to Yahoo symbols (remembered match, the
  radar's ISIN list, the symbol itself, Yahoo search); search hits must be confirmed. A Yahoo export is a snapshot and
  replaces the previous Yahoo import; other imports add rows and skip ones already stored. An import that replaced
  earlier rows can't be undone (that would leave both sets gone): it records how many it replaced and the name of the
  database copy taken before it, and undo points there. Because it replaces, the quick Yahoo import
  (`importers.import_yahoo_csv`) refuses a file with a buy/sell it can't read (no purchase price or trade date) or
  dated in the future, before anything changes, and notes prices about 100× off or far from the day's close
  (`portfolio.price_check`). A trade whose file currency differs from the listing's (`fxrates.currencies`; pence and
  pounds count as one) is a preview warning, on the fee too when there is one: prices and fees are stored in the
  listing's currency. Numbers: a preset's decimal mark, else one per column inferred from the whole file
  (`importers.infer_decimal`; a column with no evidence follows the file's other numeric columns); a value still
  ambiguous (`1.234`) is a warning in the preview, not a guess. Spreadsheet cells that are numbers are taken as they
  are (`read_table` marks them in `attrs["native"]`).
- The old `imports/holdings.csv` + `transactions.csv` move into the store once, automatically; if the rebuilt
  positions differ, the move is undone and the CSVs stay in use (`radar doctor` says so).

## Attribution's benchmark segments (`sources/constituents.py`, `portfolios/segments.py`)
- **ACWI's weights over time**: iShares serves only today's holdings file, so `radar run` keeps its own record
  (`history/acwi_segments.csv`): once per ISO week of the file's date (`Fondsposition per`), the stock rows'
  weights summed by sector, region, country (English names), currency and the cross-tabs sector × currency,
  region × currency and region × country. Aggregates only, never the stock list. A file from a week already
  recorded, or older than the newest snapshot, adds nothing; rows are never changed or removed. The file holds stock
  rows only: what SSAC holds through funds and futures (most of India and Brazil) is left out, so those countries
  weigh almost nothing in it.
- **Weights on a day**: the last snapshot on or before the day, drifted with the segments' DKK returns since (buy
  and hold: w_s(t) ∝ w_s(a) · G_s(t) / G_s(a)); before the first snapshot that snapshot rolled back the same way
  (`back-drifted`), which misses index changes and GICS reclassifications. A weighted segment with a missing return
  between the day and the snapshot leaves the day's weights missing.
- **Segment returns** (DKK, close to close on the benchmark's calendar): sectors from the MSCI World sector UCITS
  ETFs, from the `sector_etfs.us` ETF on days before the proxy's first return (with a note); regions from the country
  ETFs mixed by ACWI's country weights inside the region (the last snapshot's, undrifted), missing on a day the
  countries with an ETF cover less than `attribution.min_proxy_coverage` of the region or one of them has no return.
  A missing segment return is never 0 %.

## Attribution (`attribution.py`, `model/attribution.py`)
- **Days are the periods**: weights at the previous close (each holding's DKK value from `Book.positions`, cash
  from the ledger, over the book's value), returns from DKK closes (adjusted, as `reinvested`). Trades, fills
  versus closes and fees aren't in these returns; they show as *trading and fees* = TWR − the attribution's
  portfolio return. The period's first day only opens it. A day where a held value or price, a proxy, a rate or
  ACWI's weights is unknown, or a break in the book, is left out and counted (`days_missing`); the TWR still spans
  it, so the reconciliation absorbs it.
- **Segments**: a stock its sector and region; a sector fund its sector; a world fund spread with ACWI's weights and
  a fund with Yahoo sector weights spread by them, each slice getting the segment's benchmark return plus the
  fund's own difference to that mix; everything else `unclassified` with its own return. Cash is a segment with
  return 0 and benchmark return 0 (the cash drag, as allocation). Today's classification, for every past day.
- **Currency**: each return splits as 1 + r = (1 + local)(1 + f): a stock's f is its quote currency's DKK return, a
  world fund's ACWI's currency mix, a US sector fund's USD, a benchmark segment's its currency mix in ACWI; unknown
  currency counts as f = 0 (all local). Brinson runs on local returns; the currency effect on the currency weights;
  the cross term is the rest of the DKK active return, so the five add up exactly. ACWI's currencies without a DKK
  rate on Yahoo (small ones) are left out of its mix and renormalised, with a note.
- **Linking**: Carino over the valid days, for the period in one go and for each month on its own (the months don't
  sum to the period exactly). A linking error beyond `attribution.tolerance` is an error, not a figure.
- **Factor regression**: weekly (W-FRI) TWR returns of the selection less the ECB deposit rate compounded over the
  week, on French's daily developed factors compounded to weeks, the market factor converted to DKK; the window ends
  where the factor files end (about two months back).

## Long histories (`sources/factors.py`, `backtest/longrun.py`)
- **French**: each ZIP holds one CSV with several blocks; a block is a header line starting with "," followed by rows
  dated YYYYMM, titled by the text line above it. The configured block is matched on its title (`block`), else the
  first monthly block; annual blocks (YYYY) are skipped. Percent → decimals; -99.99 and -999 are missing (NaN), never
  a return. Month-end dates.
- **French, daily** (`factors.french_daily`, the attribution's factor regression): the same layout with rows dated
  YYYYMMDD, kept in `factors/daily.parquet` so the monthly file stays month-end only. Returns are USD; `Mkt-RF` is in
  excess of the US one-month T-bill (`RF`). The files run to the end of a month about two months back. Weeks are
  compounded from the days (`factors.to_weeks`, W-FRI): a week with a missing day is missing, and the last week is
  left out when the data stops before its Friday.
- **JKP**: long CSVs (location, name, date, ret …) pivoted wide by country (`location`) or by factor (`name`). Returns
  are decimals in USD **in excess of the US one-month T-bill**: `factors.total` adds French's RF back (a month without
  RF stays missing). Duplicate rows for a series and month raise. JKP's `vw_cap` weights cap big firms (at the NYSE
  80th percentile), so its "market" is not the cap-weighted market: the country panel uses `vw`, the factor themes
  `vw_cap` (JKP's own default).
- **Storage and refresh**: one long file; a dataset is fetched again when its copy is older than
  `factors.max_age_days`, and `guard.check` refuses an answer with fewer series, a later start, an earlier end or
  markedly fewer rows (`row_tol` 2 %), keeping the stored rows. Both sources rebuild their whole history at each
  release, so past values may change slightly between downloads.
- **Windows on months**: the score's 12-1, 6- and 3-month returns are compounded monthly returns over months
  t-11..t-1, t-5..t and t-2..t; the forward return over months t+1..t+H. A missing month anywhere in a window leaves
  that member's value missing on that date (not skipped, not 0). A date needs `min_names` ranked members.
- **DKK**: FRED `DEXDNUS` (DKK per USD, the noon rate in New York) at the last value of each month; without it the DKK
  columns are missing. **Recessions**: FRED `USREC` (NBER's dates, set after the fact): a label for a split, never an
  input.
- **The proposals' prior** (`model/prior.tilt_prior`): per JKP characteristic, the top tercile's compounded return
  over H months less the mean of the three terciles' (same weighting, so the capped weights cancel), at every
  month-end since `propose.prior.since` (overlapping windows; Newey-West standard error, lag H−1); the tilt's
  characteristics weighted by `prior_weights` (momentum over its characteristics, K+V half value, half quality); a
  characteristic missing makes the prior missing, never partial. The trend split takes the terciles' mean at the start
  of each window against its `trend_months` average; the split's t-statistics come from non-contiguous windows and are
  optimistic.
- **What it is not**: the panels are industries and countries, value-weighted and rebalanced by the researchers,
  before costs and taxes. The rule (lookbacks, weights) and the base rates carry over to stocks; basket figures don't.

## Point-in-time backtests (`backtest/`)
- **Every input is cut at the day D it decides on.** Own metrics (`momentum.metrics_panel`, row D =
  `metrics(closes.loc[:D])`), the momentum percentile against the stock universe on D, ATR at D, analyst consensus
  fetched on or before D (`levels.analyst_view` with its max age). The RRG quadrant (a note only) is the last
  completed W-FRI week's.
- **Regime**: computed at the last session of each week (the last 320 sessions of prices) and held until the next;
  FRED counts from `backtest.fred_lag_days` after its date, OECD CLI `oecd_lag_days`, CAPE/ERP `valuation_lag_days`,
  FactSet from its report date; `apply_freshness` against that day; voted with today's groups. Missing (None) with
  fewer than 200 benchmark sessions.
- **Missing inputs** move nothing: no k adjustment, a reason row, and a count in the report.
- **Triggers on adjusted closes, fills at traded closes**: a close at or through the stop (anchor − k × ATR, k
  recomputed daily) or the take-profit triggers; the sale is at the next session's traded close (`backtest.fill:
  next`; `same` = that close), at the symbol's own bar. Both sides of the comparison are rebased alike by later
  dividends, so the trigger is unaffected.
- **Take-profit fixed at the buy** (and set again at each add): it is measured from the price, so recomputed daily it
  would never be reached. The anchor runs from the first buy of the episode (bought while flat).
- **Parking**: proceeds buy `backtest.park` (fractional units) and fund the next buys first (cash, then parked units,
  then a deposit). Implicitly funded real portfolios: each mirrored sale's proceeds are withdrawn, as the real
  portfolio's are; with the rule off a sim's TWR equals the real one's.
- **Costs**: rule and parking trades pay the real portfolio's broker fee schedule (minimum, maximum, the FX
  surcharge), else `backtest.fee_bps` of their value; your own trades keep the fees they had. A buy whose money
  doesn't cover the minimum fee isn't made. The run's params record the fee model.
- **Evaluation** (not a decision input, so it may look ahead): each exit's position value (adjusted ratio × traded
  fill price × DKK rate) vs the parked units' value, at the end and at your next real sale of the symbol.
- **Limitations**: today's universe lists (survivorship), today's FRED/OECD vintages (revisions), today's regime
  voting groups and level eligibility, no tax, ACWI not on the positive list (an ASK sim is not literally
  feasible), analyst history only since it began being fetched.
