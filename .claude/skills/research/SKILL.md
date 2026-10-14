---
name: research
description: Write or update a structured research memo for one stock or ETF (thesis, momentum/rotation context from the radar, valuation snapshot, ETF/UCITS alternatives, risks, invalidation criteria, account placement). Use when the user asks to research, evaluate or "look into" a ticker, or runs /research <ticker>.
argument-hint: <yahoo-ticker>
---

# Research memo

Read `notes/investor.md` first if it exists: the user's accounts, horizon and preferences.

Output goes to `research/<TICKER>.md`. If the file already exists, keep the earlier content and add a new dated `## Update YYYY-MM-DD` section at the top that states what changed, especially whether the thesis still holds.

## Steps

1. **Radar context**: run `uv run radar info <TICKER>`. It returns momentum, trend, relative strength vs ACWI, rank in its region and the user's status (holding, watch, sold, or none), plus the full profile: `price` (returns in local currency and DKK, vs ACWI and vs the sector ETF), `technicals`, `levels`, `analyst` (targets, recommendation trend, EPS estimate revisions, next earnings date), `fundamentals` (valuation multiples, margins, growth, dividend yield), `etf` (holdings, sectors, expense ratio, overlap with the user's holdings) and `peers` (tracked stocks in the same industry, the sector ETF's rotation quadrant). Use these numbers for the momentum, valuation and catalyst sections instead of looking them up again; check each section's `status` and `context.notes`, and write "n/a" where a section is missing. If the ticker is ambiguous, check the Yahoo symbol first (e.g. `NOVO-B.CO`, `RHM.DE`). The user can open the same data as a page with `uv run radar ticker <TICKER>`.
   Also read `reports/summary.json` to see how the stock's sector or theme is rotating.
2. **The user's history**: check `imports/transactions.csv` and `journal/` for earlier trades or decisions on this name, and mention them briefly.
   **The user's market views**: `radar info` has a `views` section when the user has written views on the app's *My market views* page: the overall fit (`aligned` / `conflicts` / `mixed` / `unrelated`), and per view the reasons and the radar's evidence for that view (`supported` / `contradicted` / `mixed` / `unclear` / `no data`). For the full views (rationale, "what would change my mind", conviction, horizon) run `uv run radar views --json`. These are the user's subjective beliefs: use them to frame the memo, never as evidence.
3. **Web research** (send the searches together; use extended mode if results are thin):
   - Business: what the company does, segments, competitive position (2–3 sentences)
   - Last two quarters: results vs expectations, guidance, estimate revisions
   - Valuation: forward P/E, EV/EBITDA and FCF yield vs its own 5-year history and 2–3 peers (stockanalysis.com, company IR, Morningstar)
   - Catalysts in the next 1–6 months: earnings dates, product or regulatory events, index changes
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
Small table: metric | now | 5y avg | peers. Then a note on whether momentum is supported by estimates rising.
## Fit with my market views
Only when the user has views. Which views this name expresses or works against (and why: sector, region, or moving with a theme ETF), each view's conviction and what the radar's data currently says about it. Then one honest line: does the case for this name depend on a view being right, and what happens to it if the view is wrong (use the view's "what would change my mind")? Say plainly that these are the user's subjective beliefs. Leave the section out when there are no views.
## Catalysts (next 1–6 months)
## Risks / bear case
## What would invalidate the thesis
Concrete and observable: e.g. close below the 200d average, a guidance cut, the sector rotating into Lagging.
## Implementation
- Instrument: the stock itself, or a UCITS ETF alternative (ticker, TER, positive list yes/no)
- Account: aktiesparekonto (17% lager, good for momentum trades) vs frie midler (realisation for stocks; lager for positive-list ETFs)
- Position sizing note relative to the current portfolio (concentration, overlap)
## Sources
```

## Ground rules
- Separate facts (sourced) from interpretation. Never invent numbers. If something can't be found, write "n/a".
- The verdict describes the setup. It isn't a recommendation to buy or sell.
- The verdict comes from the data, not from the user's market views. A name that fits the views gets no bonus for that; a view the data contradicts is pointed out, not glossed over.
