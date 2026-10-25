---
id: TASK-4.12
title: 'radar calendar CLI (tables, --json)'
status: Done
assignee: []
created_date: '2026-10-25 18:00'
updated_date: '2026-10-25 15:36'
labels:
  - feature
dependencies:
  - TASK-4.9
references:
  - plans/F5-calendar.md
  - plans/analyses/product_owner.md
parent_task_id: TASK-4
priority: medium
ordinal: 49000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-12 (`radar calendar` CLI (tables, `--json`)). PR step 3 of plans/F5-calendar.md (section 5), size S. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `test_cli_calendar`
- [x] #2 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->
