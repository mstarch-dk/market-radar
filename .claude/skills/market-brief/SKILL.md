---
name: market-brief
description: Refresh the market radar and write a dated market brief in Danish (optionally with a listening version for a NotebookLM podcast) covering what changed in regime, sector/theme rotation and momentum, why it happened (web research), and what it means for the user's holdings, watchlist and research queue. Use when the user asks for a market brief, a market update, "what's moving", or runs /market-brief.
---

# Market brief

Produce `briefs/YYYY-MM-DD.md`: a short, source-linked brief that turns the radar's numbers into understanding. It's analysis to support the user's own decisions, not advice. Read `notes/investor.md` first if it exists: the user's accounts, horizon and preferences.

**Write the brief in Danish.** Follow `guide/STIL.md` for tone ("du", plain and precise), number format (decimal comma, thousands with a dot, "5 %") and its fixed terminology table (fører / svækkes / halter / forbedres, markedsbredde, positivlisten, ASK / frie midler, markedssyn …). Keep tickers, indicator names and the app's UI terms as they appear in the app. Your reply to the user is in Danish too.

**Arguments:** `podcast` also writes a listening version for NotebookLM (step 7); `personal` adds the personal sections to that listening version. Example: `/market-brief podcast` or `/market-brief podcast personal`.

## Steps

1. **Refresh the data**: run `uv run radar run` from the project root. If the output lists tickers with no data, mention them at the end of the brief.
2. **Read `reports/summary.json`**:
   - `regime` and `indicators`. These now include breadth (200d and 50d), net new highs, RSP/SPY, the VIX term structure, copper/gold, oil, the OECD CLI and FactSet revisions.
   - `rotation` per group: quadrant, relative returns, rank and rank change. `quadrant_local` is the European sectors' quadrant vs the STOXX 600 rather than ACWI.
   - `momentum_top10` (with sector and industry), new entrants and drop-outs per region, and `momentum_clusters`: industries or sectors over-represented among a region's leaders.
   - `positioning_cot`: CFTC net positioning, with `3y high` / `3y low` flags.
   - `leading_indicators`: OECD CLI cycle phase per area.
   - `valuation`: Shiller CAPE (`value`, `pct_all` since 1871, `pct_1990`), Damodaran's implied equity risk premium (`erp.value`, `erp.pct` since 2008) and the `yield_gap` (forward earnings yield minus the US 10Y real yield). `null` = no data. Whether these vote is in `regime.voting_groups` (the user switches valuation on or off on the Regime page); say which way they would tilt the vote when they don't count.
   - `revisions_regional`: EPS-revision breadth from Yahoo consensus per radar region and Discover market (`windows[].rows`: `up`, `down`, `net` over 4 and 12 weeks). Empty windows mean the weekly snapshots don't go back far enough yet: say "building history", not "no revisions".
   - `sentiment`: the AAII survey (`spread` = bull − bear, `pct` since 1987, `flag` extreme fear / euphoria) and CBOE's equity put/call (`equity_10d`, `pct` over 3 years). Contrarian and US-centred; they never vote.
   - Per row in `momentum_top10` and `me`: `pe_fy1` (P/E on next year's consensus EPS), `pe_vs_sector` (vs its sector's median among its peers: 0.8 = 20% cheaper) and `eps_rev_4w` / `eps_rev_12w`; in `rotation`: the fund `pe` and `pe_vs_acwi`.
   - `earnings_factset`: S&P 500 growth estimate vs the start of the quarter, guidance, forward P/E, and the sectors with upward or downward revisions.
   - The `me` list: holdings, watchlist and sold positions with flags (the user's real portfolios pooled; virtual ones are never in it).
   - `portfolios`: each real portfolio's returns over time in DKK (time-weighted, 1m / 3m / YTD / 1y and since its start) next to ACWI's, with its tax kind and notes (gaps, funding). Report these as they are; a `null` is missing data, not zero.
   - `coverage`: how many regime indicators have current data (`regime.na` = no data, `regime.stale` = too old, both left out of the vote), failing or stale sources, and the radar's blind spots. If any indicator is n/a or stale, or a source failed, say which near the regime reading and how much that weakens it. Fill a blind spot with web research only when it matters for this month's story (for example valuation when leadership looks stretched).

   - If `reports/discovery.json` exists and its `asof` is under 10 days old, read it too: per market, rows with `off_radar` true and a high `score`, a big `d_score`, `new_high` or `trend_turn`, leaving out `thin`, `check_data` and `stale` rows. These are names outside the radar's own lists. If it is older, say the discovery scan is stale and skip it.
   - Run `uv run radar views --json` for the user's market views (their subjective beliefs from the app's *My market views* page) with the radar's evidence per view. If there are none, skip the views section.

   If `earnings_factset` is present, also read `data/factset_latest.txt` (FactSet's own text on revisions and valuation) and cite the PDF URL at its top.
3. **Pick what matters (at most 6–8 items).** Prioritise:
   - A change in the regime reading or in any indicator's status
   - ETFs that moved **Improving → Leading** or **Leading → Weakening**, and the biggest rank changes
   - Themes in Leading or Improving that have a UCITS ticker
   - Momentum clusters and new entrants, especially an industry cluster with NEW names, which suggests a theme forming
   - **Confirmation or divergence.** For example, a sector leading in the RRG that also has upward FactSet revisions is confirmed; leadership without revisions or breadth is fragile. Outside the US, use `revisions_regional` the same way. A momentum leader on a P/E far above its sector (`pe_vs_sector` well above 1) with falling estimates is the most fragile kind. Also flag CFTC `3y high`/`3y low` readings in markets that matter to the rotation (crowding risk).
   - Holdings flagged `losing momentum` or `below 200d`, watchlist names flagged `turning up`, and sold names with a strong move since the sale
4. **Research the "why"**: use WebSearch (standard mode; send the searches together) for the drivers behind the top items over the last 2–4 weeks: earnings, guidance, macro data, policy, flows. Prefer primary or reputable sources. Every factual claim about news needs a link. Useful free sources:
   - Bloomberg markets headlines RSS (`https://feeds.bloomberg.com/markets/news.rss`): headlines and short summaries only. Don't try to read paywalled articles.
   - BofA Global Fund Manager Survey (mid-month, via press coverage): most crowded trade, cash level, biggest tail risk.
   - The Fed Beige Book (8 times a year), IMF World Economic Outlook (April and October), and the ECB monetary policy statements.
   - Company IR pages and earnings call coverage for momentum names.

   **The user's own notes:** if `notes/` has reading notes (e.g. `notes/bloomberg.md`), read the entries from the last month. They are takeaways the user pasted from paid sources. Treat them as leads to verify and link, not as sources to cite.
5. **Write the brief** in the structure below. Keep it under about 900 words, and use tables for numbers.
6. Reply in Danish with a 3–5 line summary and a link to the file.
7. **Only with `podcast`: write the listening version** `briefs/lyt/YYYY-MM-DD.md` (see *Listening version* below). It lives in a subfolder so the app's Notebook page doesn't list it as a second brief. Add one line to the reply with its path and "upload it in NotebookLM and pick Dansk".

## Brief structure

Headings and labels are in Danish, exactly as below; the notes under each heading say what goes there.

```markdown
# Markedsbrief – YYYY-MM-DD
*Data pr. <asof>. Regime: <label> (<on> for / <off> imod).*

## TL;DR
3–5 bullets: the most important things that changed and why.

## Regime
Indicator table (only those that changed or matter), plus one paragraph of interpretation.

## Positionering og cyklus
One short paragraph covering: the earnings revision trend (FactSet, and the regional breadth once it has history) and which sectors it favours, the cycle phase from the OECD CLI, any CFTC extremes, the market's valuation (CAPE and ERP percentiles, the yield gap) and sentiment (AAII, put/call) when either is at an extreme. Say whether they confirm or contradict the price-based rotation. Valuation is context for the 1–6-month horizon, not a timing signal.

## Rotation – sektorer, regioner og temaer
What's leading, what's rotating in or out, and the drivers (with links). For themes, give the UCITS ticker and its positive-list status.

## Momentum – nye ledere
New entrants by region, grouped by theme where possible, each with one line on why it's moving.

## Nyt på radaren (Discover)
Only when the discovery scan is fresh: 3–5 names from outside the radar's lists (Nordic, Europe, positive-list ETFs), each with its score, Δscore or flag, size and one line on why it may be moving. State the scan date. Small caps are noisier: say so when a name is small or near the liquidity floor.

## Dine markedssyn mod data
Only when the user has active views. One line per view (highest conviction first): the statement, the radar's verdict (supported / contradicted / mixed / unclear / no data) and the readings behind it, plus anything from this month's research that bears on it. Where the data contradicts a high-conviction view, say so plainly and quote the user's own "what would change my mind". Frame it as their beliefs against the data, never as a forecast.

## Din portefølje i den sammenhæng
- Returns: each real portfolio vs ACWI over 3m and YTD (from `portfolios`), one line each; say plainly when a portfolio trails ACWI
- Holdings: trend status, and any flags worth acting on (review, not trade)
- Watchlist names turning up
- Sold names: was the exit right? (since-sell move)

## Research-kø
2–4 concrete candidates for `/research <ticker>`, each with a one-line reason.

## Kilder
```

## Listening version (only with `podcast`)

`briefs/lyt/YYYY-MM-DD.md` is a source for a NotebookLM Audio Overview: the same story as the brief, written in Danish to be heard rather than read. NotebookLM's hosts read it and talk about it, so it must stand on its own.

- **Prose only**: no tables, no inline links, no ticker lists. Round numbers and say them in words ("knap 3 procent bedre end ACWI over tre måneder"). Name a company or fund in full before its ticker.
- **Explain as you go**: spell out each acronym the first time (RRG, CAPE, ERP, ASK, OECD CLI) and give the "why" behind every move. Keep the confirmation/divergence logic: what supports a move and what makes it fragile.
- **Length**: about 600–900 words, in the brief's order (TL;DR as an opening, then regime, positioning and cycle, rotation, momentum, Discover, research queue).
- **Private by default**: the file is uploaded to Google, so leave out everything personal: *Dine markedssyn mod data*, *Din portefølje i den sammenhæng*, holdings, watchlist, sold names and anything from `notes/`. With `personal`, include them in the same spoken style.
- Say "dette er analyse, ikke rådgivning" in the opening, and frame actions as things to review, as in the brief.
- End with a short plain list of the sources (publisher and title, then the URL).

Start the file with this block (fill in the date and variant):

```markdown
# Markedsbrief til lytning – YYYY-MM-DD
*Kilde til NotebookLM. Variant: kun marked | med personlige afsnit. Fuld brief med tabeller og links: briefs/YYYY-MM-DD.md.*

> **Sådan laver du podcasten:** Åbn notebooklm.google.com eller NotebookLM-appen → ny notesbog → tilføj denne fil som kilde (upload, eller indsæt teksten) → *Audio Overview* → *Customize*: vælg sproget Dansk og indsæt prompten herunder → *Generate*. Lyt i NotebookLM-appen.
>
> **Prompt:** Lav en dansk samtale på cirka 10 minutter mellem to værter til en privat dansk investor med en horisont på 1–6 måneder. Fokusér på hvad der har ændret sig siden sidst og hvorfor. Forklar fagudtryk kort, når de dukker op. Hold jer til kilden, og sig tydeligt at det er analyse, ikke rådgivning: ingen køb- eller salgsanbefalinger.

---
```

## Ground rules
- Facts come from the radar data or linked sources. Clearly label interpretation as interpretation.
- Momentum is a starting point for research, not a buy signal. Say when a move looks news-driven and fragile.
- Danish context: for ETF ideas, name a UCITS alternative and its positive-list status. Point out where account placement matters (aktiesparekonto vs frie midler).
- Don't give personalised buy or sell instructions. Frame actions as questions to review ("værd at gennemgå", "overvej at se på"), never "køb" or "sælg".
