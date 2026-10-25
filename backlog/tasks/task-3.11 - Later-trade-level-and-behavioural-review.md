---
id: TASK-3.11
title: 'Later: trade-level and behavioural review'
status: To Do
assignee: []
created_date: '2026-10-25 14:53'
labels:
  - feature
dependencies:
  - TASK-3.6
references:
  - plans/F4-attribution.md
  - plans/analyses/product_owner.md
parent_task_id: TASK-3
priority: low
ordinal: 35000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Each closed position's return vs ACWI over the same days (mine.vs_shadow), what happened 1/3/6 months after the sale (counterfactual hold as in backtest/exits.py, via the model layer), PGR minus PLR (Odean 1998) on days with a sale, holding period of winners vs losers, turnover and fee drag per year.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 PGR and PLR computed only on days the user sold anything (tested)
- [ ] #2 Missing prices after a sale shown as missing
<!-- AC:END -->
