---
id: TASK-4.16
title: Market-brief SKILL.md *Kommende uger*
status: Done
assignee: []
created_date: '2026-10-25 18:00'
labels:
  - feature
dependencies:
  - TASK-4.15
  - TASK-4.12
references:
  - plans/F5-calendar.md
  - plans/analyses/product_owner.md
parent_task_id: TASK-4
priority: medium
ordinal: 53000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-16 (`market-brief` SKILL.md *Kommende uger*; `research`/`propose-portfolio` read `radar calendar --json`; `maanedsbrief.md`). PR step 4 of plans/F5-calendar.md (section 5), size S. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A dry-run brief on the demo copy has the section with the given reasons
- [x] #2 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Dry run on the demo copy: the Kommende uger section written from .demo summary.json's calendar (MSFT high with its reasons, NOVO-B and NVDA normal, watched names in one line, ASML, DSV and SAAB-B under no date known). Web research left out of the dry run.
<!-- SECTION:NOTES:END -->
