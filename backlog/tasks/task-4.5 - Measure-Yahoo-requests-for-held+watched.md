---
id: TASK-4.5
title: Measure Yahoo requests for held+watched
status: Done
assignee: []
created_date: '2026-10-25 18:00'
updated_date: '2026-10-25 16:20'
labels:
  - feature
dependencies:
  - TASK-4.4
references:
  - plans/F5-calendar.md
  - plans/analyses/product_owner.md
parent_task_id: TASK-4
priority: medium
ordinal: 42000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-05 (Measure Yahoo requests for held+watched; decide `detail` vs lean fetch; record in PR). PR step 1 of plans/F5-calendar.md (section 5), size S. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The number and the decision are in the PR description
- [x] #2 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Not measured yet: needs a real radar run against Yahoo, then radar ops, on the user's data folder. The step reuses external.detail (about six Yahoo calls per ticker); a held fund is read only once.

Measured 2026-10-25 on the real data folder, calendar step only: 24 names due, 35 s, 184 Yahoo requests (7.7 per name; 168 x 200, 16 x 404, no 429s), median 66 ms. Steady state about 80-190 requests a day, worst case 184: under 1% of the *.yahoo.com budget (20000). Decision: keep external.detail (shared with the profile page); no lean fetch. Recorded in plans/F5-calendar.md 4.3.
<!-- SECTION:NOTES:END -->
