# Data conventions

The radar's output must be truthful: a missing value is shown as missing, never as 0 or as a guess.

## Prices
- Prices are adjusted closes (dividends + splits) in each listing's currency; the traded close is kept as `raw_close`.
- When a new dividend or split re-bases Yahoo's history, `radar update` re-downloads that ticker in full rather than merging two adjustment bases.
- `ingest.wide()` forward-fills up to 5 sessions, which is right for return windows. Anything shown as a session uses the ticker's own bars (`profile.Market.bars`), so a missing Yahoo bar is a gap, not a flat day. That covers the last price, day change, recent bars and the chart.
- Holding-vs-benchmark comparisons are total returns in DKK against a shadow ACWI position with identical cash flows.
- Yahoo tickers: `.CO` Copenhagen, `.ST` Stockholm, `.OL` Oslo, `.HE` Helsinki, `.DE` Xetra, `.L` London (often GBp = pence).

## Sources
- A parse that finds nothing raises. The update is then logged as failed and the cache kept, rather than storing an empty result as a success. Examples: FactSet without growth figures, CFTC with renamed columns, OECD with duplicate series, a short SPY list, a positive list without an ISIN column.
- Sources older than their `coverage.max_age` turn stale and stop voting in the regime.
- Yahoo detail units are inconsistent: dividend yield and expense ratio arrive in percent, margins as fractions, debt/equity ×100. `external.parse_*` normalise to fractions and range-check them; implausible values are dropped with a note instead of shown.
- Analyst targets are converted to the radar's price units by the ratio of our close to Yahoo's price on the fetch date. This handles GBp vs GBP and ADR ratios.

## Graded readings (gauges)
- `signals/gauges.py` grades a reading between its thresholds: anchors (value, score) are interpolated to a score in [-1, 1] (+ favourable, green; − warning, red), cut into 9 levels, with a granular word ("near overbought"). One-way risk measures (VIX, ATR %, beta, crowding) are `sequential` and never turn green.
- Specs live in `settings.yaml` `gauges:`; regime rows build theirs from the `regime:` thresholds, so a threshold is written once. The regime vote itself is unchanged.
- A missing value is not graded (no gauge), never treated as 0. Gauges are display data: `summary.json` leaves them out.
- Watch-outs are gauges at level −3 or below, excluding traits (beta, ATR %) and the hypothetical stop/target of a ticker you don't hold.

## Risk statistics (`signals/risk.py`)
- Weekly (Friday) returns in DKK; the week still in progress is left out (it covers fewer days). Windows: 1y and 3y (`settings.yaml` `risk:`), each reporting its `n_weeks`; under `min_weeks` there is no statistic.
- Beta comes with its standard error and R²; alpha (Jensen, annualised) with its t-stat. With the FRED 3-month T-bill (`DGS3MO`) returns are excess returns and Sharpe/Sortino exist; without it they are null and alpha is on raw returns (`alpha_basis` says which).
- Factor tilts regress on ACWI plus factor/sector ETFs *minus ACWI*, so a loading means exposure beyond the market. Descriptive: short samples, correlated factors.
- One-year betas are noisy (XLE's 1y beta was −0.9 while its 3y beta is +0.45): compare windows and read the standard error before relying on either.

## Your portfolio (`userstore.py`, `universe.py`, `portfolio.py`, `importers/`)
- Trades are the source of truth, in `userdata/radar.db` (SQLite, versioned migrations, a backup in `userdata/backups/` before every import and undo). Each trade records its source (manual, yahoo, nordnet, …), its import and its account.
- Positions are derived with the average-cost method (gennemsnitsmetoden): fees are part of the acquisition cost, a sale removes cost in proportion. Per account and in total; the total pools all accounts, which is right for the return vs ACWI but not for tax, where an aktiesparekonto is separate.
- Prices are per share in the instrument's quote currency (as on Yahoo). The editor and the importers flag a price about 100× off (GBp vs GBP) or far from that day's traded close, and block a sale larger than the position.
- Imports: presets for Yahoo (verified), Nordnet, Saxo and Danske Bank (unverified until a real export is added as a test fixture), generic column names otherwise. Instruments are matched to Yahoo symbols (remembered match, the radar's ISIN list, the symbol itself, Yahoo search); search hits must be confirmed. A Yahoo export is a snapshot and replaces the previous Yahoo import; other imports add rows and skip ones already stored.
- The old `imports/holdings.csv` + `transactions.csv` move into the store once, automatically; if the rebuilt positions differ, the move is undone and the CSVs stay in use (`radar doctor` says so).

