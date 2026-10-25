---
id: TASK-4.19
title: Nav, route, page_links, glossary terms
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
ordinal: 56000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-19 (Nav, route, `page_links`, glossary terms). PR step 5 of plans/F5-calendar.md (section 5), size S. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `test_guide.py` page-link test passes
- [x] #2 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Glossary: cal_level, cal_unconfirmed, cal_eps, cal_revision (gennemgangsniveau is the existing stop key). The glossary learned {{settings:…|pct}}.
<!-- SECTION:NOTES:END -->
