---
id: TASK-4.13
title: Earnings in N d flag in /api/me from agenda.next_earnings_map
status: Done
assignee: []
created_date: '2026-10-25 18:00'
updated_date: '2026-10-25 15:36'
labels:
  - feature
dependencies:
  - TASK-4.7
references:
  - plans/F5-calendar.md
  - plans/analyses/product_owner.md
parent_task_id: TASK-4
priority: medium
ordinal: 50000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-13 (`earnings in N d` flag in `/api/me` from `agenda.next_earnings_map`). PR step 3 of plans/F5-calendar.md (section 5), size S. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `test_me_flag_matches_calendar`
- [x] #2 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
agenda.with_earnings_flags runs agenda.build over soon_days; mine.live is the shared holdings-rows builder for /api/me and the calendar.
<!-- SECTION:NOTES:END -->
