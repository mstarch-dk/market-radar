---
id: TASK-3.13
title: 'Refactor: per-symbol daily values on performance.Book'
status: To Do
assignee: []
created_date: '2026-10-25 15:06'
labels:
  - refactor
dependencies:
  - TASK-3.1
references:
  - plans/F4-attribution.md
parent_task_id: TASK-3
priority: high
ordinal: 25500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
portfolios/performance.book computes each symbol's daily DKK value and drops it. Keep it on Book as a positions frame (NaN where unknown) and pool it in pool(), so attribution can weight segments by what was held each day. No behaviour change. Plan: plans/F4-attribution.md, step 2 (finding C1).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Sum of positions equals holdings each day, NaN on the same days, for single and pooled books (tested)
- [ ] #2 analyze and compare output unchanged on the test world (tested)
<!-- AC:END -->
