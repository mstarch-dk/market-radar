---
id: TASK-3.6
title: attribution.py feature module
status: To Do
assignee: []
created_date: '2026-10-25 14:52'
labels:
  - feature
dependencies:
  - TASK-3.3
  - TASK-3.4
  - TASK-3.5
references:
  - plans/F4-attribution.md
parent_task_id: TASK-3
priority: high
ordinal: 30000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
src/radar/attribution.py: from the portfolio's daily books (portfolios/performance.book) build monthly segment weights and returns by sector and by region through portfolios/exposure, run the attribution and the regression, and add coverage and notes (unclassified value, proxy approximations, today's classification used for past months). No math of its own. Add to the features layer in pyproject.toml.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No attribution under 12 months (setting), with a note
- [ ] #2 Unclassified or unvalued holdings are listed, never counted as 0 % return
- [ ] #3 uv run lint-imports and tests/test_layers.py pass
<!-- AC:END -->
