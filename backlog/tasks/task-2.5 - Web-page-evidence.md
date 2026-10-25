---
id: TASK-2.5
title: Web page /evidence
status: Done
assignee: []
created_date: '2026-10-25 14:51'
updated_date: '2026-10-25 16:56'
labels:
  - feature
dependencies:
  - TASK-2.4
references:
  - plans/F2-evidence-page.md
parent_task_id: TASK-2
priority: high
ordinal: 18000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
web/src/pages/Evidence.tsx: one card per score study (IC bar per horizon with t, quintile bars, top-N vs universe and ACWI, holdout vs in-sample, verdict table per variant), a long-run card (decades, recession splits, survivorship gauge), the forward scoreboard, a staleness badge. Nav entry. Reuse LineChart and DataTable.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Missing study: 'not run yet' and the command to run it
- [x] #2 Stale study greyed with 'older rule'
- [x] #3 t shown next to every mean; holdout start from settings
<!-- AC:END -->
