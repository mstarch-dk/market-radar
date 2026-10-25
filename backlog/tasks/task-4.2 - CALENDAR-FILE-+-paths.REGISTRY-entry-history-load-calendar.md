---
id: TASK-4.2
title: 'CALENDAR_FILE + paths.REGISTRY entry (history), load_calendar'
status: Done
assignee: []
created_date: '2026-10-25 18:00'
updated_date: '2026-10-25 15:16'
labels:
  - feature
dependencies: []
references:
  - plans/F5-calendar.md
  - plans/analyses/product_owner.md
parent_task_id: TASK-4
priority: medium
ordinal: 39000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-02 (`CALENDAR_FILE` + `paths.REGISTRY` entry (history), `load_calendar`). PR step 1 of plans/F5-calendar.md (section 5), size S. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `test_registry` covers the file
- [x] #2 Layout docs list it
- [x] #3 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
No doc lists history files one by one; the REGISTRY comment in paths.py is the list.
<!-- SECTION:NOTES:END -->
