---
id: TASK-4.7
title: 'resolve_earnings (detail → snapshot ≥ today → none, moved_from)'
status: Done
assignee: []
created_date: '2026-10-25 18:00'
updated_date: '2026-10-25 15:29'
labels:
  - feature
dependencies:
  - TASK-4.3
references:
  - plans/F5-calendar.md
  - plans/analyses/product_owner.md
parent_task_id: TASK-4
priority: medium
ordinal: 44000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-07 (`resolve_earnings` (detail → snapshot ≥ today → none, `moved_from`)). PR step 2 of plans/F5-calendar.md (section 5), size S. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `test_resolve_earnings_order`
- [x] #2 `test_snapshot_past_date_ignored`
- [x] #3 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Also test_moved_and_narrowed_dates: a window narrowing inside the old one is not a move; a passed report starts a new cycle.
<!-- SECTION:NOTES:END -->
