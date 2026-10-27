---
name: rules
description: Keep the user's own trading rules (caps per name and theme, a core floor, a buy-back pause, sell cooling-off, no averaging down, exit rule first, judgment questions) and check an action against them. Drafts rules from a behavioural review of the user's own trades and writes each only after the user confirms it. Also `check <action>`: whether a buy or sell breaks any rule, with the numbers. Use when the user wants to set up, review or change their trading rules, asks whether an action would break one of their rules, or runs /rules.
argument-hint: "[review] | check <buy|sell> <ticker> <amount> [portfolio] | add <rule in words>"
---

# My trading rules

The user's rules for how they want to trade, written down in calm conditions and checked when it matters. The
radar is a mirror, never a gate: it says whether an action breaks a rule, comes close or complies, with the
numbers, and blocks nothing. Never tell the user to trade or not to trade; show what their own rules say.

Read and write through the `mcp__radar__*` tools: `trading_rules` (the rules, what the holdings break now, the
kinds and templates), `rules_check`, `add_rule`, `rule_decision`. If the `radar` tools aren't connected, use the
CLI: `uv run radar rules --json`, `rules check … --json`, `rules standing --json`, `rules add --from-json FILE`,
`rules decision`, `rules replay --json`.

Rule kinds (`trading_rules().kinds`, from config/rules.yaml): weight caps per name and per theme / sector / region
(the market views' exposure vocabulary), a minimum core weight, a minimum trade size, a maximum number of names, no
buying back within N days of a sale, sell cooling-off (at most X % of the portfolio sold within N days), a maximum
number of trades a month, no averaging down below the average cost, only buying above a moving average, no
chasing a 3-month run-up, a minimum momentum score, short-term trades in one account kind, an exit rule first, and
`judgment` (a question the radar can't check: you weigh it). Each has a scope (real or all portfolios, chosen ones,
an account kind, a tag, a style: momentum, value, core or tactical) and a severity (hard, soft, reminder: the
user's own label, which only orders the output).

## Mode 1: check an action (`/rules check sell NOVO-B.CO half`)

1. `rules_check(side, ticker, amount_dkk | quantity | fraction, portfolio?, style?, horizon?)`. A sale of "half" or
   "all" is `fraction` 0.5 or 1.
2. Answer rule by rule, breaks first: the rule in the user's words, its severity, the `message` with its numbers
   (say what a weight is a share of, as the message does) and the `comply` text. Then the `judgment` rules as
   questions, answered from what you know of the action and the user's notes (`investor_notes`), marked as your
   reading. An `unknown` verdict is not compliance: name what is missing.
3. If the user then acts, log it: call `rules_check(…, log=true)` once and `rule_decision(check_id, decision,
   reason)` with their own words (`went_ahead` with the reason when against a rule, `changed`, `dropped`). For a
   trade they record, `/journal` does both.

## Mode 2: set up or change rules (`/rules`, `/rules add …`)

1. Read `trading_rules(archived=true)` and `investor_notes`. Show the active rules and the standing breaks.
2. Turn what the user says into typed rules: pick the kind and its parameters from `kinds`, a scope, a severity,
   and a `rationale` in the user's own words (why they have the rule: the lesson behind it). A rule the radar
   can't check becomes a `judgment` rule; say so.
3. For each rule, call `add_rule(…)` without `confirm`, show the rule exactly as it would be stored, and ask the
   user (one AskUserQuestion call may cover several drafts, each its own option). Only after a yes call it again
   with `confirm=true`. Never write a rule the user hasn't confirmed, and never change or archive one without
   asking (the app's *My trading rules* page edits and archives).

## Mode 3: review (`/rules review`)

A behavioural review of the user's own trades, to draft rules from what actually happened:

1. `trading_rules()` (the rules and the standing breaks), the real portfolios' trades (`portfolios`, then the
   transactions through `performance` / the journal: `journal_entries(status="closed")` and the open ones), and
   `radar rules replay --json` (CLI): today's rules on every past real trade as of its day, with what the name did
   afterwards vs ACWI.
2. Look for patterns, with dates and numbers: many sales on one day after a drawdown (→ a `sell_cooling` draft),
   buying back soon after selling (→ `no_rebuy_within`), adding to losers (→ `no_average_down`), one name or theme
   growing large (→ the caps), many small trades (→ `min_ticket`, `max_trades_per_month`), buys after a vertical
   run (→ `no_chase`), buys without an exit rule (→ `exit_rule_first`).
3. Quote the replay as descriptive and small-n: "would have flagged 3 of 11 buys; those 3 trailed ACWI by 8 % on
   average since" is what happened, not proof a rule works. Never claim significance.
4. Offer each pattern as a draft rule with the rationale in the user's words, and add only the confirmed ones
   (Mode 2, step 3).

Everything here is analysis of the user's own behaviour against their own rules, not advice.
