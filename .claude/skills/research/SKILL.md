---
name: research
description: Write or update a structured research memo for one stock or ETF (thesis, momentum/rotation context from the radar, valuation snapshot, ETF/UCITS alternatives, risks, invalidation criteria, account placement). Use when the user asks to research, evaluate or "look into" a ticker, or runs /research <ticker>.
argument-hint: <yahoo-ticker>
---

# Research memo

Read the radar through the `mcp__radar__*` tools; their descriptions carry the units and what each field means.
Send independent calls together. If the `radar` tools aren't connected, use the CLI instead: `uv run radar paths
--json` for the folders, `uv run radar info <TICKER>`, `views --json`, `calendar --json`, `portfolios list --json`,
and read `notes/investor.md` and `reports/summary.json` from those folders.

Read `investor_notes` first (the user's accounts, horizon and preferences); if it has none yet, go on without.

Output goes to `research/<TICKER>.md` in the data folder (`data_paths`: `folders.research`). If `documents(kind=
"research", ticker=<TICKER>)` lists a memo already, read it with `read_document`, keep the earlier content and add a
new dated `## Update YYYY-MM-DD` section at the top that states what changed, especially whether the thesis still
holds.

## Steps

1. **Radar context**: `ticker_profile([<TICKER>])`. The flat keys at the top are momentum, trend, relative strength
   vs ACWI, rank in its region and `my_status` (holding, watch, sold or none); then the full profile, each section
   with `status` and `context.notes`. Use its numbers for the momentum, valuation, quality and catalyst sections
   instead of looking them up again, and write "n/a" where a section is missing. Valuation: P/E vs its sector
   (`fundamentals.snapshot.pe_vs_sector`, on next year's EPS) and the EPS revisions. Quality: for a stock,
   `quality` has the kvalitetsscore, værdiscore and K+V with every metric's percentile among its peers;
   `status: missing` (no statements) means "n/a", not a web lookup of those numbers. If the ticker is ambiguous,
   check the Yahoo symbol first (e.g. `NOVO-B.CO`, `RHM.DE`). The user can open the same data as a page with
   `uv run radar ticker <TICKER>`.
   Also `summary(["rotation"])`: how the stock's sector or theme is rotating, and the report's age.
2. **The user's history**: `identity.my_position` in the profile, and `documents(ticker=<TICKER>)` for earlier
   journal entries and memos on this name (read one with `read_document` if it matters). Mention them briefly.
   **The user's market views**: the profile's `views` section is how the name fits them (`aligned` / `conflicts` /
   `mixed` / `unrelated`, with the radar's evidence per view). For the full views (rationale, "what would change
   my mind", conviction, horizon) call `market_views`. They are the user's subjective beliefs: use them to frame
   the memo, never as evidence.
3. **Web research** (send the searches together; use extended mode if results are thin):
   - Business: what the company does, segments, competitive position (2–3 sentences)
   - Last two quarters: results vs expectations, guidance, estimate revisions
   - Valuation: forward P/E and EV/EBITDA vs its own 5-year history and 2–3 peers (stockanalysis.com, company IR, Morningstar). FCF yield, ROIC and EV/EBIT come from the radar's `quality` section; search for them only when it is missing, and say so.
   - Catalysts in the next 1–6 months: earnings dates, product or regulatory events, index changes. For a name the user holds or watches, take the next report from `calendar(symbols=[<TICKER>])` (the date or Yahoo's window, how sure it is, and why it is highlighted, as the app and the brief show it); for any other name, from the profile's `analyst`. A date that isn't known is "no date known", never a guess.
   - For an ETF: index, TER, size, replication, top-10 concentration, overlap with the user's holdings, UCITS version, positive-list status (justETF)
4. **Write the memo** with the template below. Link sources inline.
5. Reply with the verdict line and a link to the file.

## Template

```markdown
# <Name> (<TICKER>) – research memo
*Updated YYYY-MM-DD · Price <last> <ccy> · Radar score <score>/100 (rank <rank>/<n> in <region>) · My status: <status>*

**Verdict (not advice):** Strong setup / Watch / Avoid for now – one sentence on why.

## Thesis (bull case in 3 bullets)
## Momentum & rotation context
Trend (50/200d), 1/3/6m and 12-1m returns, relative to ACWI, and what the sector or theme is doing on the rotation graph.
## Fundamentals & valuation
Small table: metric | now | 5y avg | peers. Include the radar's P/E vs sector median (`fundamentals.snapshot.pe_vs_sector`, naming the basis: next year's EPS) and its EPS revisions. Then a note on whether momentum is supported by estimates rising.
## Quality & value
Kvalitetsscore, værdiscore and K+V with what they rest on (e.g. "4/4 pillars, 3/4 value metrics"), the source and the period the figures reach. Then a small table from `quality.metrics`: metric | value | percentile among peers (sector or all) for the ones that stand out, high or low. One line each on the business (profitability, moat proxies, balance sheet, dividend record) and the price (FCF yield, EBIT/EV, shareholder yield, against its own history). Say how the scores sit with the momentum score: a strong trend in a high-quality, reasonably priced business is a different setup from a strong trend in a weak, expensive one. "n/a" when there are no statements.
## Fit with my market views
Only when the user has views. Which views this name expresses or works against (and why: sector, region, or moving with a theme ETF), each view's conviction and what the radar's data currently says about it. Then one honest line: does the case for this name depend on a view being right, and what happens to it if the view is wrong (use the view's "what would change my mind")? Say plainly that these are the user's subjective beliefs. Leave the section out when there are no views.
## Catalysts (next 1–6 months)
## Risks / bear case
## What would invalidate the thesis
Concrete and observable: e.g. close below the 200d average, a guidance cut, the sector rotating into Lagging.
## Implementation
- Instrument: the stock itself, or a UCITS ETF alternative (ticker, TER, positive list yes/no)
- Account: aktiesparekonto (17% lager, good for momentum trades) vs frie midler (realisation for stocks; lager for positive-list ETFs), named as the user's real portfolios (`portfolios`: name and tax `kind`)
- Position sizing note relative to the current portfolio (concentration, overlap)
## Sources
```

## Ground rules
- Separate facts (sourced) from interpretation. Never invent numbers. If something can't be found, write "n/a".
- The verdict describes the setup. It isn't a recommendation to buy or sell.
- The verdict comes from the data, not from the user's market views. A name that fits the views gets no bonus for that; a view the data contradicts is pointed out, not glossed over.
