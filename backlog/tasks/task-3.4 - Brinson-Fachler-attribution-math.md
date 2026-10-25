---
id: TASK-3.4
title: Brinson-Fachler attribution math
status: To Do
assignee: []
created_date: '2026-10-25 14:52'
updated_date: '2026-10-25 15:07'
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
Pure math in model/attribution.py: single-period Brinson-Fachler (allocation, selection, interaction) by segment on local returns, the currency effect in DKK with the cross term shown, and Carino linking of daily periods to months and to the whole period (tolerance 1e-8). Golden tests with hand calculations. Plan: 4.3, step 5.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Effects sum to the active return each month (tested)
- [ ] #2 Linked total equals the period's active return within the stated tolerance (tested)
- [ ] #3 Portfolio with the benchmark's weights shows zero allocation (tested)
<!-- AC:END -->
