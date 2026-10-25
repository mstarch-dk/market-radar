---
id: TASK-4.11
title: AgendaView models, /api/calendar, cache key, no-prices behaviour
status: To Do
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
ordinal: 48000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-11 (`AgendaView` models, `/api/calendar`, cache key, no-prices behaviour; `gen:api`). PR step 3 of plans/F5-calendar.md (section 5), size M. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `test_calendar_api_contract`
- [ ] #2 `test_calendar_without_prices`
- [ ] #3 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->
