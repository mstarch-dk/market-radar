---
id: TASK-4.20
title: Guide chapter kalender.md, navigation.md
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
ordinal: 57000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-20 (Guide chapter `kalender.md`, `navigation.md`; textbook sections). PR step 5 of plans/F5-calendar.md (section 5), size M. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `test_guide.py` passes; `{{settings:…}}` used for every threshold
- [x] #2 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Chapter brugervejledning/kalender.md after xray; textbook: estimatrevisioner#regnskaber-i-kalenderen, stop-og-storrelse#regnskaber-og-kursgab. Also hvad-er-market-radar (page map), kommandolinjen (radar calendar), maanedsbrief, beholdninger.
<!-- SECTION:NOTES:END -->
