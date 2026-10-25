---
id: TASK-1.8
title: Web page /xray
status: To Do
assignee: []
created_date: '2026-10-25 09:29'
labels:
  - web
dependencies:
  - TASK-1.6
references:
  - plans/F1-portfolio-xray.md
parent_task_id: TASK-1
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan step 6 (section 4.6). Xray.tsx in the Mine group after Holdings & watchlist; ?pf= selection; header tiles, exposure tabs with diverging active-weight bars and coverage, risk table with excluded names and realised vs ex-ante, concentration, stress, factor tilts, notes. TickerLink cells, Term tooltips via lib/glossary.ts.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Nav includes /xray (pnpm -C web test)
- [ ] #2 Negative risk shares shown as reducing tracking error
- [ ] #3 Coverage below warn_coverage shown in amber; missing values shown as missing
<!-- AC:END -->
