---
id: TASK-3.4
title: Brinson-Fachler attribution math
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
ordinal: 28000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Pure math in model/: single-period Brinson-Fachler (allocation, selection, interaction) by segment, the currency effect in DKK, and multi-period linking with the method chosen in the plan. Golden tests with hand calculations.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Effects sum to the active return each month (tested)
- [ ] #2 Linked total equals the period's active return within the stated tolerance (tested)
- [ ] #3 Portfolio with the benchmark's weights shows zero allocation (tested)
<!-- AC:END -->
