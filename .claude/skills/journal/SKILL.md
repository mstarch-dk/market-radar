---
name: journal
description: Record an investment decision (buy/sell/add/trim/pass) with thesis, horizon and exit rules in the decision journal, or run the monthly journal review that checks open theses against current radar signals. Use when the user says they bought/sold/decided something, asks to log a decision, or runs /journal or /journal review.
argument-hint: "[review] | <action> <ticker> [notes]"
---

# Decision journal

The journal makes decisions deliberate and reviewable. Each entry records *why* a decision was made and *what would prove it wrong*.

**Where files are.** The user's data lives in their data folder, outside this project. Run `uv run radar paths --json` once and use its `folders`: in this skill `notes/…`, `briefs/…`, `research/…`, `journal/…` and `exports/…` are those folders inside `folders.data`, `reports/…` is `folders.reports` and `data/…` is `folders.cache`. Read and write them by their full path (pass full paths to `--out` too). If `state` is `unset` or `missing`, ask the user to start the app or run `uv run radar setup` first.

## Mode 1: record a decision (`/journal buy RHM.DE …`)

1. Collect the details from the user's message. If any of these are missing, ask once in a single AskUserQuestion call: action (buy, add, trim, sell, pass), account (the user's real portfolios from `uv run radar portfolios list --json`, read with what `notes/investor.md` says each is for; without either, e.g. aktiesparekonto or frie midler), the thesis in their own words, horizon, and the exit rule.
2. Run `uv run radar info <TICKER>` and snapshot the key numbers into the entry. If its `views` section shows the name lines up with (or against) any of the user's market views, list those view ids in `views:` and ask in the same question whether the decision expresses one of them (the user's subjective beliefs; `uv run radar views --json` has the full text).
3. Link `research/<TICKER>.md` if it exists.
   If the decision is an executed trade (buy, add, trim, sell) and the user gives the quantity and price, offer to record it in the portfolio too: `uv run radar portfolio add <BUY|SELL> <TICKER> <qty> <price> --date <date> --portfolio <portfolio name>` (the name exactly as `radar portfolios list` shows it; it checks the trade like the app does; show any warnings before adding `--yes`).
4. Write `journal/YYYY-MM-DD-<TICKER>-<action>.md`:

```markdown
---
date: YYYY-MM-DD
ticker: <TICKER>
action: buy|add|trim|sell|pass
account: <real portfolio name from `radar portfolios list`, e.g. ASK | frie midler>
horizon: <e.g. 3 months>
status: open        # open → closed when the position is exited or the thesis is resolved
views: []           # ids of the user's market views this decision expresses (from `radar views`), if any
review_by: YYYY-MM-DD
---
# <Action> <Name> (<TICKER>)

## Why (thesis, in the user's words)
## Market views it expresses
Only when `views` isn't empty: each view's statement, conviction, and what the radar's data said about it at decision time.
## Radar at decision time
score, trend, 1/3/6m, rel 3m vs ACWI, sector quadrant, regime
## Exit rules
- Thesis invalidated if: …
- Stop / trend rule: …
- Target / time stop: …
## Pre-mortem
If this goes wrong, the most likely reason is: …
```

Keep the user's own wording for the thesis. Suggest a concrete invalidation rule if they give none, and mark it as a suggestion.

## Mode 2: monthly review (`/journal review`)

1. Run `uv run radar run`, then read every journal entry with `status: open`.
2. For each entry, compare the exit rules with the current `uv run radar info <TICKER>` and the rotation context. Classify it as **Intact**, **Weakening** (some rules are close to triggering) or **Invalidated** (a rule has triggered). For entries with `views:`, also give each linked view's current evidence from `uv run radar views --json` (and say if the user has archived it): a position resting on a view the data now contradicts deserves a question.
3. Also go through closed trades from the last 3 months: what happened after the exit, and what can be learned from it.
4. Write `journal/reviews/YYYY-MM.md` with a table (ticker | thesis | status | evidence | linked views and their data | question to consider) and 2–3 patterns noticed across decisions, such as selling winners too early, adding to losers, or theme concentration.
5. Don't change any entry's status without asking the user first.
