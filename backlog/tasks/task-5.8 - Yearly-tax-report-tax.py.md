---
id: TASK-5.8
title: 'Yearly tax report: tax.py'
status: Done
assignee: []
created_date: '2026-10-25 18:51'
updated_date: '2026-10-25 19:48'
labels:
  - feature
dependencies:
  - TASK-5.2
  - TASK-5.4
  - TASK-5.5
  - TASK-5.6
  - TASK-5.7
references:
  - plans/F3-tax-engine.md
parent_task_id: TASK-5
priority: high
ordinal: 60800
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
portfolios/taxinputs.py (trades with DKK rates, dividends regardless of the dividend policy, deposits and withdrawals, year-start and year-end values from Book.positions, classes, openings) and the feature module tax.py: per account and per person for a year, unknowns with their value, notes, incomplete flags. userstore tax_openings (manual losses carried in per pool) and radar tax opening list|add|remove. pyproject.toml layers and contracts; docs/architecture.md, docs/data-conventions.md. A warning when an ASK FEE row in January looks like the tax debit. Plan: 4.1-4.3, step 8.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 An ETF that leaves the positive list is share income in one year and capital income the next, with an ASK warning (tested)
- [x] #2 An unknown holding is listed with its value and reason and left out of every estimate (tested)
- [x] #3 A year without rules computes the bases with taxes null and a note (tested)
- [x] #4 performance.analyze and compare output unchanged on the test world (regression test)
- [x] #5 Opening losses are used in the year they are carried into
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
tax.py year_report; tax_openings; layers and contracts; docs/architecture.md and data-conventions.md; January FEE warning on ASK.
<!-- SECTION:FINAL_SUMMARY:END -->
