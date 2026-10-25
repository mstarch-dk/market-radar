---
id: TASK-4.3
title: 'update_calendar with the refresh schedule, parallel fetch, guard'
status: Done
assignee: []
created_date: '2026-10-25 18:00'
updated_date: '2026-10-25 15:16'
labels:
  - feature
dependencies:
  - TASK-4.1
  - TASK-4.2
references:
  - plans/F5-calendar.md
  - plans/analyses/product_owner.md
parent_task_id: TASK-4
priority: medium
ordinal: 40000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-03 (`update_calendar` with the refresh schedule, parallel fetch, guard). PR step 1 of plans/F5-calendar.md (section 5), size M. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `test_calendar_schedule`
- [x] #2 `test_calendar_append_only`
- [x] #3 `test_calendar_all_fail_loud`
- [x] #4 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->
