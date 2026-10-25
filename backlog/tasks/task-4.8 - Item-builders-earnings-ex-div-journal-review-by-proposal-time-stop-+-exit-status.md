---
id: TASK-4.8
title: >-
  Item builders: earnings, ex-div, journal review_by, proposal time_stop + exit
  status
status: Done
assignee: []
created_date: '2026-10-25 18:00'
updated_date: '2026-10-25 15:29'
labels:
  - feature
dependencies:
  - TASK-4.7
references:
  - plans/F5-calendar.md
  - plans/analyses/product_owner.md
parent_task_id: TASK-4
priority: medium
ordinal: 45000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-08 (Item builders: earnings, ex-div, journal `review_by`, proposal `time_stop` + exit status). PR step 2 of plans/F5-calendar.md (section 5), size M. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `test_agenda_items_kinds`, funds counted in `excluded_funds`
- [x] #2 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Pure: agenda.build takes the holdings rows, weights, calendar history, screener dates, journal and exit check as arguments; gathering them (and the API) is TASK-4.11. Overdue open reviews are included. Proposal picks count when the proposal's portfolio is in the selection; sold picks (held False) are left out.
<!-- SECTION:NOTES:END -->
