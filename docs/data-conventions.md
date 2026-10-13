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
