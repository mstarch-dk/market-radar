---
name: research
description: Write or update a structured research memo for one stock or ETF (thesis, momentum/rotation context from the radar, valuation snapshot, ETF/UCITS alternatives, risks, invalidation criteria, account placement). Use when the user asks to research, evaluate or "look into" a ticker, or runs /research <ticker>.
argument-hint: <yahoo-ticker>
---

# Research memo

Read `notes/investor.md` first if it exists: the user's accounts, horizon and preferences.

**Where files are.** The user's data lives in their data folder, outside this project. Run `uv run radar paths --json` once and use its `folders`: in this skill `notes/…`, `briefs/…`, `research/…`, `journal/…` and `exports/…` are those folders inside `folders.data`, `reports/…` is `folders.reports` and `data/…` is `folders.cache`. Read and write them by their full path (pass full paths to `--out` too). If `state` is `unset` or `missing`, ask the user to start the app or run `uv run radar setup` first.

Output goes to `research/<TICKER>.md`. If the file already exists, keep the earlier content and add a new dated `## Update YYYY-MM-DD` section at the top that states what changed, especially whether the thesis still holds.

## Steps

1. **Radar context**: run `uv run radar info <TICKER>`. It returns momentum, trend, relative strength vs ACWI, rank in its region and the user's status (holding, watch, sold, or none), plus the full profile: `price` (returns in local currency and DKK, vs ACWI and vs the sector ETF), `technicals`, `levels`, `analyst` (targets, recommendation trend, EPS estimate revisions, next earnings date), `fundamentals` (valuation multiples, margins, growth, dividend yield; `fundamentals.snapshot` is the radar's weekly valuation snapshot: P/E on next year's consensus EPS, `pe_vs_sector` against its sector's median among its radar peers, EPS revisions over 4 and 12 weeks once the history exists, and the P/E over the stored weeks; for a fund, Yahoo's fund P/E against ACWI's), `etf` (holdings, sectors, expense ratio, overlap with the user's holdings) and `peers` (tracked stocks in the same industry, the sector ETF's rotation quadrant). Use these numbers for the momentum, valuation and catalyst sections instead of looking them up again; check each section's `status` and `context.notes`, and write "n/a" where a section is missing. If the ticker is ambiguous, check the Yahoo symbol first (e.g. `NOVO-B.CO`, `RHM.DE`). The user can open the same data as a page with `uv run radar ticker <TICKER>`.
   For a stock, `quality` is the radar's kvalitetsscore and værdiscore from its financial statements (SEC EDGAR for US companies, Yahoo's statements otherwise): `quality`, `value` and `qv` (K+V) 0–100 against its sector's peers across regions, `q_n` / `v_n` (how many of the four pillars / value metrics they rest on), `pillars`, every metric in `metrics` (`value`, `pct` among peers, `basis` sector or universe, `peers`, `pillar`), the fiscal years in `history` (revenue, gross and FCF margin), `fund_source`, `period_end`, `filed`, `currency` and `notes`. Use it for the *Quality & value* section and the FCF yield, ROIC and EV/EBIT figures; `status: missing` (no statements) means "n/a", not a web lookup of those numbers.
   Also read `reports/summary.json` to see how the stock's sector or theme is rotating.
2. **The user's history**: check `uv run radar portfolio list --symbol <TICKER>` and `journal/` for earlier trades or decisions on this name, and mention them briefly.
   **The user's market views**: `radar info` has a `views` section when the user has written views on the app's *My market views* page: the overall fit (`aligned` / `conflicts` / `mixed` / `unrelated`), and per view the reasons and the radar's evidence for that view (`supported` / `contradicted` / `mixed` / `unclear` / `no data`). For the full views (rationale, "what would change my mind", conviction, horizon) run `uv run radar views --json`. These are the user's subjective beliefs: use them to frame the memo, never as evidence.
3. **Web research** (send the searches together; use extended mode if results are thin):
   - Business: what the company does, segments, competitive position (2–3 sentences)
   - Last two quarters: results vs expectations, guidance, estimate revisions
   - Valuation: forward P/E and EV/EBITDA vs its own 5-year history and 2–3 peers (stockanalysis.com, company IR, Morningstar). FCF yield, ROIC and EV/EBIT come from the radar's `quality` section; search for them only when it is missing, and say so.
   - Catalysts in the next 1–6 months: earnings dates, product or regulatory events, index changes. For a name the user holds or watches, take the next report from `uv run radar calendar --json` (its item for the ticker: the date or Yahoo's window, how sure it is, and the reasons it is highlighted, the same as the app and the brief show); for any other name, from `radar info`'s `analyst`. A date that isn't known is "no date known", never a guess.
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
- Account: aktiesparekonto (17% lager, good for momentum trades) vs frie midler (realisation for stocks; lager for positive-list ETFs), named as the user's real portfolios (`uv run radar portfolios list --json`: name and tax `kind`)
- Position sizing note relative to the current portfolio (concentration, overlap)
## Sources
```

## Ground rules
- Separate facts (sourced) from interpretation. Never invent numbers. If something can't be found, write "n/a".
- The verdict describes the setup. It isn't a recommendation to buy or sell.
- The verdict comes from the data, not from the user's market views. A name that fits the views gets no bonus for that; a view the data contradicts is pointed out, not glossed over.
