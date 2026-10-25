---
id: TASK-3.3
title: 'Data: benchmark segment weights and returns'
status: To Do
assignee: []
created_date: '2026-10-25 14:52'
labels:
  - feature
dependencies:
  - TASK-3.1
references:
  - plans/F4-attribution.md
parent_task_id: TASK-3
priority: high
ordinal: 27000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ACWI sector and region weights per month as a history-tier, append-only file (backfilled if the spike in the plan allows), and segment returns in DKK from the proxy ETFs (sector and regional), configured in universe.yaml with the fallback chosen in the plan.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A missing month or proxy is shown as missing, never 0
- [ ] #2 History file is append-only and never deletes user data
- [ ] #3 Every ACWI weight key is one the radar's classification can produce
<!-- AC:END -->
