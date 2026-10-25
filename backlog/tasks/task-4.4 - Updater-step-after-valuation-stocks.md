---
id: TASK-4.4
title: Updater step after valuation_stocks
status: Done
assignee: []
created_date: '2026-10-25 18:00'
updated_date: '2026-10-25 15:17'
labels:
  - feature
dependencies:
  - TASK-4.3
references:
  - plans/F5-calendar.md
  - plans/analyses/product_owner.md
parent_task_id: TASK-4
priority: medium
ordinal: 41000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-04 (Updater step after `valuation_stocks`; settings `calendar.refresh`, `stale_days` (yaml + schema)). PR step 1 of plans/F5-calendar.md (section 5), size S. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `radar run` on the test world writes rows
- [x] #2 Settings test passes
- [x] #3 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Covered by test_every_external_source_is_tried_even_when_one_raises (the step runs after valuation_stocks with calendar.refresh). stale_days moves to TASK-4.7, where resolve_earnings reads it.
<!-- SECTION:NOTES:END -->
