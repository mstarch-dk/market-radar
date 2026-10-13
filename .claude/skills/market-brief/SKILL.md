---
name: market-brief
description: Refresh the market radar and write a dated market brief covering what changed in regime, sector/theme rotation and momentum, why it happened (web research), and what it means for the user's holdings, watchlist and research queue. Use when the user asks for a market brief, a market update, "what's moving", or runs /market-brief.
---

# Market brief

Produce `briefs/YYYY-MM-DD.md`: a short, source-linked brief that turns the radar's numbers into understanding. It's analysis to support the user's own decisions, not advice.

## Steps

1. **Refresh the data**: run `uv run radar run` from the project root. If the output lists tickers with no data, mention them at the end of the brief.
2. **Read `reports/summary.json`**:
   - `regime` and `indicators`. These now include breadth (200d and 50d), net new highs, RSP/SPY, the VIX term structure, copper/gold, oil, the OECD CLI and FactSet revisions.
   - `rotation` per group: quadrant, relative returns, rank and rank change. `quadrant_local` is the European sectors' quadrant vs the STOXX 600 rather than ACWI.
   - `momentum_top10` (with sector and industry), new entrants and drop-outs per region, and `momentum_clusters`: industries or sectors over-represented among a region's leaders.
   - `positioning_cot`: CFTC net positioning, with `3y high` / `3y low` flags.
   - `leading_indicators`: OECD CLI cycle phase per area.
   - `earnings_factset`: S&P 500 growth estimate vs the start of the quarter, guidance, forward P/E, and the sectors with upward or downward revisions.
   - The `me` list: holdings, watchlist and sold positions with flags.
   - `coverage`: how many regime indicators have current data (`regime.na` = no data, `regime.stale` = too old, both left out of the vote), failing or stale sources, and the radar's blind spots. If any indicator is n/a or stale, or a source failed, say which near the regime reading and how much that weakens it. Fill a blind spot with web research only when it matters for this month's story (for example valuation when leadership looks stretched).

   If `earnings_factset` is present, also read `data/factset_latest.txt` (FactSet's own text on revisions and valuation) and cite the PDF URL at its top.
3. **Pick what matters (at most 6–8 items).** Prioritise:
   - A change in the regime reading or in any indicator's status
   - ETFs that moved **Improving → Leading** or **Leading → Weakening**, and the biggest rank changes
   - Themes in Leading or Improving that have a UCITS ticker
   - Momentum clusters and new entrants, especially an industry cluster with NEW names, which suggests a theme forming
   - **Confirmation or divergence.** For example, a sector leading in the RRG that also has upward FactSet revisions is confirmed; leadership without revisions or breadth is fragile. Also flag CFTC `3y high`/`3y low` readings in markets that matter to the rotation (crowding risk).
   - Holdings flagged `losing momentum` or `below 200d`, watchlist names flagged `turning up`, and sold names with a strong move since the sale
4. **Research the "why"**: use WebSearch (standard mode; send the searches together) for the drivers behind the top items over the last 2–4 weeks: earnings, guidance, macro data, policy, flows. Prefer primary or reputable sources. Every factual claim about news needs a link. Useful free sources:
   - Bloomberg markets headlines RSS (`https://feeds.bloomberg.com/markets/news.rss`): headlines and short summaries only. Don't try to read paywalled articles.
   - BofA Global Fund Manager Survey (mid-month, via press coverage): most crowded trade, cash level, biggest tail risk.
   - The Fed Beige Book (8 times a year), IMF World Economic Outlook (April and October), and the ECB monetary policy statements.
   - Company IR pages and earnings call coverage for momentum names.

   **The user's own notes:** if `notes/bloomberg.md` exists, read the entries from the last month. The user pastes takeaways there from a subscription. Treat them as leads to verify and link, not as sources to cite.
5. **Write the brief** in the structure below. Keep it under about 900 words, and use tables for numbers.
6. Reply with a 3–5 line summary and a link to the file.

## Brief structure

```markdown
# Market brief – YYYY-MM-DD
*Data as of <asof>. Regime: <label> (<on> on / <off> off).*

## TL;DR
3–5 bullets: the most important things that changed and why.

## Regime
Indicator table (only those that changed or matter), plus one paragraph of interpretation.

## Positioning & cycle
One short paragraph covering three things: the earnings revision trend and which sectors it favours, the cycle phase from the OECD CLI, and any CFTC extremes. Say whether they confirm or contradict the price-based rotation.

## Rotation – sectors, regions & themes
What's leading, what's rotating in or out, and the drivers (with links). For themes, give the UCITS ticker and its positive-list status.

## Momentum – new leaders
New entrants by region, grouped by theme where possible, each with one line on why it's moving.

## My portfolio in this context
- Holdings: trend status, and any flags worth acting on (review, not trade)
- Watchlist names turning up
- Sold names: was the exit right? (since-sell move)

## Research queue
2–4 concrete candidates for `/research <ticker>`, each with a one-line reason.

## Sources
```

## Ground rules
- Facts come from the radar data or linked sources. Clearly label interpretation as interpretation.
- Momentum is a starting point for research, not a buy signal. Say when a move looks news-driven and fragile.
- Danish context: for ETF ideas, name a UCITS alternative and its positive-list status. Point out where account placement matters (aktiesparekonto vs frie midler).
- Don't give personalised buy or sell instructions. Frame actions as questions to review.
