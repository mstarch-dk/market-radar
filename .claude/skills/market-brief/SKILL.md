---
name: market-brief
description: Refresh the market radar and write a dated market brief covering what changed in regime, sector/theme rotation and momentum, why it happened (web research), and what it means for the user's holdings, watchlist and research queue. Use when the user asks for a market brief, a market update, "what's moving", or runs /market-brief.
---

# Market brief

Produce `briefs/YYYY-MM-DD.md`: a short, source-linked brief that turns the radar's numbers into understanding. It's analysis to support the user's own decisions, not advice.

## Steps

1. **Refresh the data**: run `uv run radar run` from the project root. If the output lists tickers with no data, mention them at the end of the brief.
2. **Read `reports/summary.json`**: regime and indicators, rotation per group (quadrant, relative returns, rank and rank change), momentum top-10 and new entrants or drop-outs per region, and the `me` list (holdings, watchlist and sold positions with flags).
3. **Pick what matters (at most 6–8 items).** Prioritise:
   - A change in the regime reading or in any indicator's status
   - ETFs that moved **Improving → Leading** or **Leading → Weakening**, and the biggest rank changes
   - Themes in Leading or Improving that have a UCITS ticker
   - New momentum entrants, especially if several come from the same industry, which suggests a theme forming
   - Holdings flagged `losing momentum` or `below 200d`, watchlist names flagged `turning up`, and sold names with a strong move since the sale
4. **Research the "why"**: use WebSearch (standard mode; send the searches together) for the drivers behind the top items over the last 2–4 weeks: earnings, guidance, macro data, policy, flows. Prefer primary or reputable sources. Every factual claim about news needs a link.
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
