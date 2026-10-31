---
name: scout
description: Search what investors and the media are starting to talk about (new themes, sectors, regions, technologies, policy) and turn it into a short list of 3–5 investment hypotheses, each checked against the radar's numbers, placed on a narrative stage (whisper, confirming, consensus) and red-teamed. The user adopts (as a market view), dismisses or watches each one; every shortlisted candidate is frozen and followed against ACWI, and the run can be logged in the journal. Use when the user asks what the market is talking about, for new themes or trends, for investment ideas beyond momentum and value, "what are the rumours", or runs /scout.
argument-hint: "[theme hint …] [--region R] [--horizon 3m|6m|12m|3y]"
---

# Scout: hypotheses from what the market talks about

The radar's numbers see a trend once it is in prices, revisions and statements. `/scout` looks one step earlier: at the stories investors, analysts, policymakers and the media are beginning to tell. It turns them into a short list of hypotheses the user can adopt or dismiss. "Buy on the rumour, sell on the fact": the most useful thing the skill reports is not the story but **where it is in its life** (its stage). This is analysis to support the user's own decisions, not advice. Every candidate is frozen and scored later, so the scout earns (or loses) trust on the Evidence page like everything else.

Read and write through the `mcp__radar__*` tools; their descriptions carry the units and the fields. If the `radar` tools aren't connected, use the CLI instead: `uv run radar paths --json` for the folders, `radar views --json`, `radar info <T1> <T2> … `, `radar scout review --json`, and read `reports/summary.json` and write the report in `research/scout/`. Without the tools there is no `add_view` or `scout_freeze`: give the user the view's fields to enter on the *My market views* page, and say the candidates were not frozen.

**Write the report in Danish.** Follow `guide/STIL.md` for tone ("du", plain and precise), number format (decimal comma, "5 %") and its fixed terms (markedssyn, positivlisten, ASK / frie midler …). Keep tickers and the app's UI terms as they appear in the app. Your reply to the user is in Danish too.

**Arguments:** a theme hint narrows the search (`/scout nuclear`, `/scout afrika sundhed`); without one, scan broadly. `--region` (us, europe, nordic, asia, em, frontier) and `--horizon` (default 12m) shape the search and the views. Example: `/scout`, `/scout defence --region europe`.

## The stages (say this in the report)

- **Hvisken** (whisper): the talk is rising and broadening, but price and revisions have not followed. Relative strength vs ACWI is flat or negative over 3–6 months and the theme is not yet in Leading. This is the interesting stage, and also the one where you are most often wrong.
- **Bekræftes** (confirming): the story, relative strength (Improving or Leading) and earnings revisions point the same way. There is less upside to the rumour, but more evidence.
- **Konsensus** (consensus or fact): the theme is in every headline, a new wave of thematic ETFs is launching, FMS calls it crowded or positioning is extreme, valuation is far above its sector, and the catalyst is behind it or dated and widely known. This is a red flag, not a buy: say so plainly. Studies of thematic ETFs launched at peak attention find they lag the market afterwards (Ben-David, Franzoni, Kim and Moussawi, "Competition for Attention in the ETF Space", *Review of Financial Studies* 2023).

## Steps

1. **Context** (one round of calls):
   - `investor_notes`: the user's accounts, horizon and what to avoid.
   - `market_views(archived=true)`: what they already believe, so you can tell new from repeated.
   - `summary(sections=["regime","rotation","momentum_top10","momentum_new_entrants","momentum_clusters","revisions_regional","positioning_cot","sentiment"])`: where the money and the revisions already are. In `momentum_clusters`, an industry cluster with new names is a theme already forming in prices.
   - `discovery()`: off-radar names with a rising score (skip it if `stale`).
   - Earlier runs, via `documents(kind="scout")` and `read_document` for the latest one or two: what was shown, what was decided and why.
   - `scout_review()`: how earlier candidates have done.

   A candidate the user dismissed earlier comes back only with new evidence, and you say what is new.
2. **Search broadly, through fixed lenses**, so the list isn't just this week's loudest story. Run WebSearch with the searches sent together. Use standard mode first, and extended for niche or frontier markets or when a lens comes back thin. Cover each lens, narrowed by the hint if there is one:
   - Flows and products: ETF flows, new thematic ETF and UCITS launches, notable fund-manager buying.
   - Surveys and positioning: BofA Global Fund Manager Survey (most crowded trade, biggest overweight changes), via press coverage.
   - Policy and public money: legislation, subsidies, state procurement and defence budgets (EU, US, China, Gulf), and central-bank shifts.
   - Capex and supply chains: corporate capex plans, bottlenecks, order backlogs and long-term contracts.
   - Outlooks: sell-side and asset-manager theme pieces (the free summaries).
   - Technology and regulatory milestones: approvals (FDA/EMA), licences (reactors, spectrum), standards and breakthroughs.
   - Emerging and frontier markets: reforms, IMF programmes, index inclusions and new listings.
   - Commodities: supply deficits, stockpiling, export bans.
   - **Contrarian:** deeply unloved sectors or regions where the tone is turning.

   Prefer primary and reputable sources. Read headlines and free summaries only; never try to get around a paywall. Every factual claim needs a link; summarise in your own words, with no long quotes. The user's reading notes in `folders.notes` are leads to verify, not sources.
3. **Long list (8–12 stories).** For each, note:
   - the narrative in one sentence
   - who is telling it, and **how independent the sources are**: several unrelated sources, or one press release echoed? Is it issuer marketing, paid promotion or retail-forum hype?
   - whether the talk is **accelerating** (newer and more frequent coverage than 1–3 months ago)
   - the **"fact"**: the catalyst that would confirm or end the story, with a date if there is one
4. **Map each story to instruments.**
   - One or two proxy ETFs: the radar's own themes first (the `rotation` table, with their UCITS listing), then a UCITS fund. Say whether it is on positivlisten (ASK) when you know; never guess.
   - 3–8 representative stocks.
   - Call `ticker_profile(symbols=[…])` once per story: the names side by side with ACWI. It gives momentum, relative return over 1/3/6 months, the sector and its quadrant, analyst targets and EPS revisions, P/E vs sector, and correlation.
   - **Novelty check:** does the basket move with a theme ETF the radar already tracks, or with one of the user's views (the profile's `views` section)? If so, say so plainly ("this is mostly SMH again") and score novelty low.
5. **Score each story on the rubric**, 1–5 per axis, each with a short reason: *Fortælling* (strength, breadth, acceleration), *Kursbekræftelse* (has it already happened in prices?), *Fundamental bekræftelse* (revisions and targets), *Trængsel* (crowding: COT, FMS, valuation, ETF launches), *Investerbarhed* (UCITS / positivlisten, liquidity, for a Danish investor), *Katalysator* (a dated "fact" within the horizon) and *Nyhed* (not already in the user's views or holdings). Derive the **stage** from narrative against price and revisions, not from the scores' sum. Missing data is "n/a", never a low score.
6. **Red team each survivor**:
   - the strongest bear case
   - hype or pump risk and source independence
   - what is already in the price
   - the thematic-ETF base rate when it is near consensus
   - currency or country risk
   - a **falsifier**: one concrete, checkable sentence that becomes the view's "what would change my mind"
7. **Short list of 3–5**: whispers and confirmings first, and at most one consensus (named as a warning). Write the report (below) with `write_memo(kind="scout", name="YYYY-MM-DD")`. If a report for today exists, read it and write `YYYY-MM-DD-2`.
8. **Decide with the user.** Present the short list in a few lines each, then one AskUserQuestion call with one question per candidate, the options *Adoptér* (as a market view), *Følg* (watch: freeze and follow, no view) and *Afvis* (dismiss). Ask for a reason in their own words (the free-text option or a follow-up line). Then:
   - **Adopted:**
     1. Build the view: statement, conviction (ask; default 2–3 for a whisper), the horizon, rationale, the falsifier, exposures (`etf` for the proxy, plus a `sector`, `industry`, `region` or `ticker` where it is specific) and indicators from the catalogue that would confirm it (e.g. `defence` up, `clean_energy` up, `em` up; leave them out rather than force one).
     2. Call `add_view(..., origin="scout:YYYY-MM-DD:<slug>")` **without** `confirm` and show the dry run: the view, the radar's evidence now and the issues (an overlap or contradiction with an existing view is worth a sentence).
     3. Call it again with `confirm=true` only after the user says yes.
   - **Every shortlisted candidate**, whatever the decision: `scout_freeze(slug, statement, stage, decision, horizon, proxies, stocks, reason, view_id, report)`. The dismissed and watched are the control group that shows whether the adopt calls add anything; say so if the user hesitates. If it refuses a symbol (no Yahoo prices), fix or drop the symbol and freeze again.
   - Update the report's front matter and *Beslutninger* section with the decisions (`read_document`, then `write_memo(..., replace=true)` keeping everything else).
9. **Suggest a journal entry** in one line: "Skal jeg skrive beslutningerne i journalen?" Only on a yes, write `write_memo(kind="journal", name="YYYY-MM-DD-scout")` (template below), with `review_by` set to the earliest horizon among the adopted and watched candidates. `/journal review` will then check each hypothesis's catalyst and falsifier and its frozen basket against ACWI.
10. Reply in Danish: 3–5 lines with the candidates and their stages, what was decided, and links to the report (and journal entry). If the user wants to act on a candidate, point to `/research <ticker>`, `/compare` or `/propose-portfolio`, and to their trading rules. Never suggest a trade size.

## Report structure

```markdown
---
date: YYYY-MM-DD
hint: <the theme hint, or null>
candidates:              # filled in after step 8
  - {slug: nuclear-smr, stage: whisper, decision: adopted, view_id: 12, freeze_id: 2026-10-31_nuclear-smr}
---
# Scout – YYYY-MM-DD
*Analyse, ikke rådgivning. Kandidaterne er hypoteser, ikke anbefalinger. Hver af dem fryses og følges mod ACWI.*

## Kort fortalt
3–5 bullets: the short list with stage, and the one thing that would most change the picture.

## Kandidater
### 1. <Hypothesis in one sentence> · <Hvisken | Bekræftes | Konsensus>
- **Fortællingen:** what is being said, and since when it has been accelerating (links)
- **Hvem taler:** the sources and how independent they are
- **Radarens tal:** a table of the proxy and 3–8 names: 1/3/6m vs ACWI, quadrant, EPS revisions, P/E vs sector, UCITS / positivlisten; n/a where missing
- **Rubrik:** the seven scores with one-line reasons
- **Katalysator ("faktum"):** what and when
- **Red team:** bear case, hype risk, what is priced, base rate
- **Falsifier:** one checkable sentence
- **Nyhed:** overlap with your views, holdings or the radar's themes
- **Proxy-kurv:** proxies · stocks (what will be frozen)

## Afviste fra langlisten
One line each: the story and why it didn't make the list (already priced, one source, not investable …).

## Tidligere kandidater: hvad skete der
From `scout_review`: each earlier candidate's excess vs ACWI since it was frozen, by decision and stage. Once `enough`, say whether the adopted beat the dismissed and whether whispers beat consensus. Until then say how many there are, and that it says nothing yet.

## Beslutninger
Filled in after step 8: per candidate the decision, the user's reason, the view id and the freeze id.

## Kilder
```

## Journal entry (only after a yes)

```markdown
---
date: YYYY-MM-DD
type: hypothesis
action: scout
status: open
horizon: <the longest horizon among adopted and watched>
review_by: YYYY-MM-DD
views: [<ids of the adopted views>]
---
# Scout-beslutninger – YYYY-MM-DD

## Kandidater og beslutninger
A table: hypothesis | stage | decision | reason (the user's words) | view | freeze id

## Hvad skal være sandt (per adopted or watched candidate)
The catalyst ("faktum") with its date, and the falsifier.

## Gennemgang
- Look again by: review_by, or when a catalyst's date has passed
- Report: research/scout/YYYY-MM-DD.md
```
