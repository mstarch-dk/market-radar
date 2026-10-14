---
name: journal
description: Record an investment decision (buy/sell/add/trim/pass) with thesis, horizon and exit rules in the decision journal, or run the monthly journal review that checks open theses against current radar signals. Use when the user says they bought/sold/decided something, asks to log a decision, or runs /journal or /journal review.
argument-hint: "[review] | <action> <ticker> [notes]"
---

# Decision journal

The journal makes decisions deliberate and reviewable. Each entry records *why* a decision was made and *what would prove it wrong*.

## Mode 1: record a decision (`/journal buy RHM.DE …`)

1. Collect the details from the user's message. If any of these are missing, ask once in a single AskUserQuestion call: action (buy, add, trim, sell, pass), account (the accounts listed in `notes/investor.md`; without that file, e.g. aktiesparekonto or frie midler), the thesis in their own words, horizon, and the exit rule.
2. Run `uv run radar info <TICKER>` and snapshot the key numbers into the entry.
3. Link `research/<TICKER>.md` if it exists.
4. Write `journal/YYYY-MM-DD-<TICKER>-<action>.md`:

```markdown
---
date: YYYY-MM-DD
ticker: <TICKER>
action: buy|add|trim|sell|pass
account: <account name from notes/investor.md, e.g. ASK | frie-midler>
horizon: <e.g. 3 months>
status: open        # open → closed when the position is exited or the thesis is resolved
review_by: YYYY-MM-DD
---
# <Action> <Name> (<TICKER>)

## Why (thesis, in the user's words)
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
2. For each entry, compare the exit rules with the current `uv run radar info <TICKER>` and the rotation context. Classify it as **Intact**, **Weakening** (some rules are close to triggering) or **Invalidated** (a rule has triggered).
3. Also go through closed trades from the last 3 months: what happened after the exit, and what can be learned from it.
4. Write `journal/reviews/YYYY-MM.md` with a table (ticker | thesis | status | evidence | question to consider) and 2–3 patterns noticed across decisions, such as selling winners too early, adding to losers, or theme concentration.
5. Don't change any entry's status without asking the user first.
