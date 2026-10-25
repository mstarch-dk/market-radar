---
id: TASK-4.21
title: SoonStrip on Home
status: Done
assignee: []
created_date: '2026-10-25 18:00'
labels:
  - feature
dependencies:
  - TASK-4.17
references:
  - plans/F5-calendar.md
  - plans/analyses/product_owner.md
parent_task_id: TASK-4
priority: medium
ordinal: 58000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-21 (`SoonStrip` on Home; `navigation.md` *Forsiden*). PR step 6 of plans/F5-calendar.md (section 5), size S. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Hidden when empty; same items as the page's `soon`
- [x] #2 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
SoonStrip shares the query key and request with /calendar's default view, so it shows the same soon items; it renders nothing when the list is empty or the request fails. Checked on the real data folder: the same three items in the same order.
<!-- SECTION:NOTES:END -->
