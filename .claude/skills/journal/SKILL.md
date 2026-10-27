---
name: journal
description: Record an investment decision (buy/sell/add/trim/pass) with thesis, horizon and exit rules in the decision journal, or run the monthly journal review that checks open theses against current radar signals. Use when the user says they bought/sold/decided something, asks to log a decision, or runs /journal or /journal review.
argument-hint: "[review] | <action> <ticker> [notes]"
---

# Decision journal

The journal makes decisions deliberate and reviewable. Each entry records *why* a decision was made and *what would prove it wrong*.

Read and write through the `mcp__radar__*` tools; their descriptions carry the units and the fields. If the `radar` tools aren't connected, use the CLI instead: `uv run radar paths --json` for the folders, then `radar info`, `views --json`, `rules check … --json --log`, `rules standing --json`, `portfolios list --json`, `propose check --json`, `portfolio add`, and read and write the files in those folders.

## Mode 1: record a decision (`/journal buy RHM.DE …`)

1. Collect the details from the user's message. If any of these are missing, ask once in a single AskUserQuestion call: action (buy, add, trim, sell, pass), account (the user's real portfolios from `portfolios`, read with what `investor_notes` says each is for; without either, e.g. aktiesparekonto or frie midler), the thesis in their own words, horizon, the style (momentum, value, core or tactical: what kind of position it is) and the exit rule.
2. Call `ticker_profile([<TICKER>])` and snapshot the key numbers into the entry. If its `views` section shows the name lines up with (or against) any of the user's market views, list those view ids in `views:` and ask in the same question whether the decision expresses one of them (the user's subjective beliefs; `market_views` has the full text).
3. **The user's own trading rules.** For a buy, add, trim or sell, call `rules_check(side, ticker, amount_dkk | quantity | fraction, portfolio, style?, horizon?, log=true)` (a trim or sell of part of a position is `fraction`). Report every verdict that is `breaks` or `near` with its numbers and `comply` text, read each `judgment` rule as a question against what the user told you, and never call an `unknown` verdict compliant. If a rule breaks and the user goes ahead, ask for their reason in their own words and record it with `rule_decision(check_id, "went_ahead", reason)` (`changed` or `dropped` if they change or drop the action). The rules are a mirror, never a gate: don't refuse or argue the decision. Without rules (`trading_rules` lists none), skip this step and the *Rules* section.
4. Link `research/<TICKER>.md` if `documents(kind="research", ticker=<TICKER>)` lists it.
   If the decision is an executed trade (buy, add, trim, sell) and the user gives the quantity and price, offer to record it in the portfolio too: `add_trade(type, symbol, quantity, price, date, portfolio=<name as portfolios shows it>)` first without `confirm`: it saves nothing and returns the checks' issues (the trading rules' breaks among them) and the position before and after, as the app checks a trade. Show them, and call it again with `confirm=true` (and `rule_reason` when it breaks a rule) only after the user says yes.
5. Write the entry with `write_memo(kind="journal", name="YYYY-MM-DD-<TICKER>-<action>", markdown=…)`:

```markdown
---
date: YYYY-MM-DD
ticker: <TICKER>
action: buy|add|trim|sell|pass
account: <real portfolio name from `portfolios`, e.g. ASK | frie midler>
horizon: <e.g. 3 months>
style: momentum|value|core|tactical   # what kind of position; the style-scoped trading rules read it
status: open        # open → closed when the position is exited or the thesis is resolved
views: []           # ids of the user's market views this decision expresses (from `market_views`), if any
review_by: YYYY-MM-DD
---
# <Action> <Name> (<TICKER>)

## Why (thesis, in the user's words)
## Market views it expresses
Only when `views` isn't empty: each view's statement, conviction, and what the radar's data said about it at decision time.
## Radar at decision time
score, trend, 1/3/6m, rel 3m vs ACWI, sector quadrant, regime
## Rules
Only with trading rules: each rule the action breaks or comes close to (statement, severity, the numbers), the
judgment rules as questions with the user's answer, and the override reason if the user goes ahead anyway.
## Exit rules
- Thesis invalidated if: …
- Stop / trend rule: …
- Target / time stop: …
## Pre-mortem
If this goes wrong, the most likely reason is: …
```

Keep the user's own wording for the thesis. Suggest a concrete invalidation rule if they give none, and mark it as a suggestion.

**From a proposal** (`/propose-portfolio`): when the buy comes from a frozen proposal (`propose_picks(id)`; `propose_review` lists the ids), take the pick's `why` as the starting thesis (and ask the user to confirm or reword it), and copy its exit criteria into *Exit rules* as written there: the review level (close below the 200-day average), the signal exit (momentum score or K+V below its level), each thesis check, and the time stop as `review_by`. Add `proposal: <id>.json` to the front matter, so the review can find it.

## Mode 2: monthly review (`/journal review`)

1. Bring the data up to date: `job_start(kind="update")`, then `job_status(kind="update")` now and then until it is `done` (several minutes; if it is refused because an update runs elsewhere, wait for that one). Then `journal_entries(status="open")`, and `read_document(kind="journal", name=…)` for each entry's exit rules.
2. Call `ticker_profile([<every open entry's ticker>], personal=true)` once (each name's profile under `tickers`) and `summary(["rotation"])`, and compare each entry's exit rules with them. For entries with `proposal:`, also call `propose_check()` once and use its status per pick (Intact / Weakening / Triggered, with the evidence; `older_rule` means the criteria were set under other settings). Classify it as **Intact**, **Weakening** (some rules are close to triggering) or **Invalidated** (a rule has triggered). For entries with `views:`, also give each linked view's current evidence from `market_views(archived=true)` (and say if the user has archived it): a position resting on a view the data now contradicts deserves a question.
3. **Trading rules**: `trading_rules()`'s `standing` lists the open positions that break or come close to the user's rules now (a name above its cap, a theme above its cap, the core below its floor); list them in the review. For entries with a *Rules* section, say how the overridden ones have done since (the radar's return since the entry vs ACWI). `radar rules replay --json` (CLI) shows how today's rules would have flagged past trades; quote it as descriptive and small-n, never as proof.
4. Also go through closed trades from the last 3 months (`journal_entries(status="closed")`): what happened after the exit, and what can be learned from it.
5. Write the review with `write_memo(kind="reviews", name="YYYY-MM", markdown=…)`, with a table (ticker | thesis | status | evidence | linked views and their data | question to consider) and 2–3 patterns noticed across decisions, such as selling winners too early, adding to losers, or theme concentration.
6. Don't change any entry's status without asking the user first.
