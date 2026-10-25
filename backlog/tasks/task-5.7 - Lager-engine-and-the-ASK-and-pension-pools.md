---
id: TASK-5.7
title: Lager engine and the ASK and pension pools
status: Done
assignee: []
created_date: '2026-10-25 18:51'
updated_date: '2026-10-25 19:48'
labels:
  - feature
dependencies:
  - TASK-5.1
references:
  - plans/F3-tax-engine.md
parent_task_id: TASK-5
priority: high
ordinal: 60700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
model/tax: lager per holding and year (year-end value plus sale proceeds minus year-start value minus buy costs, in DKK), account_pool for ASK and pension (return, carried loss, taxable, tax at the year's rate, carried out), share_income per person (realised, dividends, positive-list lager, loss pools as the rules list them, progression), capital income from funds off the list at the person's rate. Pure functions, golden tests. Plan: 4.3, step 7.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The textbook's three-year ASK example gives 2,040 / 0 / 510 with the loss carried into year 3 (tested)
- [x] #2 The textbook's positive-list example (50,000 bought mid-year, 56,000 at year end) gives 6,000 share income (tested)
- [x] #3 Progression below, at and above the limit, and a pension year with carry-forward at the PAL rate (tested)
- [x] #4 A missing year-start or year-end value makes that holding's lager missing, never 0
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
model/tax lager, account_pool (negative tax carried), share_income, capital_tax, ask_headroom; golden tests from the textbook.
<!-- SECTION:FINAL_SUMMARY:END -->
