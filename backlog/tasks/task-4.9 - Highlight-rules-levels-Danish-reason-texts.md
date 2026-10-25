---
id: TASK-4.9
title: 'Highlight rules, levels, reason texts'
status: Done
assignee: []
created_date: '2026-10-25 18:00'
updated_date: '2026-10-25 15:29'
labels:
  - feature
dependencies:
  - TASK-4.8
references:
  - plans/F5-calendar.md
  - plans/analyses/product_owner.md
parent_task_id: TASK-4
priority: medium
ordinal: 46000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-09 (Highlight rules, levels, Danish reason texts; settings `calendar.highlight`, `days`, `soon_days`, `include`). PR step 2 of plans/F5-calendar.md (section 5), size M. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `test_highlight_rules` (one case per reason)
- [x] #2 `test_levels`
- [x] #3 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Reason texts are English like the app's interface (guide/STIL.md); the Danish brief words them from key and value. Plan 4.5 updated.
<!-- SECTION:NOTES:END -->
