---
id: TASK-4.15
title: Summary["calendar"] + contract docstring
status: Done
assignee: []
created_date: '2026-10-25 18:00'
labels:
  - feature
dependencies:
  - TASK-4.9
references:
  - plans/F5-calendar.md
  - plans/analyses/product_owner.md
parent_task_id: TASK-4
priority: medium
ordinal: 52000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-15 (`summary["calendar"]` + contract docstring). PR step 4 of plans/F5-calendar.md (section 5), size S. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `test_summary_calendar_key`
- [x] #2 `test_summary_deterministic`
- [x] #3 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
summary['calendar'] is agenda.collect for the real portfolios without selection and generated; None (and an ops error) when it can't be built. AgendaView gained soon_days (TASK-4.17) so the key carries it too.
<!-- SECTION:NOTES:END -->
