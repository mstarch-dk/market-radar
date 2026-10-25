---
id: TASK-4.17
title: 'Calendar.tsx: picker, *De næste 7 dage*, Agenda tab with filters, *Ingen dato kendt*'
status: Done
assignee: []
created_date: '2026-10-25 18:00'
labels:
  - feature
dependencies:
  - TASK-4.11
references:
  - plans/F5-calendar.md
  - plans/analyses/product_owner.md
parent_task_id: TASK-4
priority: medium
ordinal: 54000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
F5-17 (`Calendar.tsx`: picker, *De næste 7 dage*, Agenda tab with filters, *Ingen dato kendt*). PR step 5 of plans/F5-calendar.md (section 5), size M. See the plan's sections 3-4 for the design and section 7 for the tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `pnpm -C web test` (`nav.test.ts` includes `/calendar`), `pnpm -C web build`
- [x] #2 Green on uv run pytest -q, ruff, mypy, lint-imports; guide changes in the same PR
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
UI labels are English like the rest of the app: Calendar, Next N days (from soon_days), Agenda | Month, No date known. Filters ?who= and ?kinds=. Mine now has eight pages: nav.test.ts allows eight per group (it went 6 -> 7 for Quality before).
<!-- SECTION:NOTES:END -->
