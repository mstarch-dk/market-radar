---
id: TASK-5.3
title: Positive list per year
status: To Do
assignee: []
created_date: '2026-10-25 18:51'
labels:
  - feature
dependencies:
  - TASK-5.1
references:
  - plans/F3-tax-engine.md
parent_task_id: TASK-5
priority: high
ordinal: 60300
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
sources/positive_list.py: load_years() returns every year's ISIN set, status(isin, year) gives yes, no, no_sheet or no_isin; load() and isins() keep their meaning. Move POSITIVE_LIST_FILE from config.ROOT to paths with a tier in REGISTRY. Settle which sheet applies to an income year from SKAT's own wording. datalicenser.md Used for: the tax engine's classification per year. Plan: C6, step 3.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 status per year from a two-sheet sample; a year without a sheet is no_sheet (tested)
- [ ] #2 load() and isins() unchanged for existing callers
- [ ] #3 The file path comes from paths with a REGISTRY tier
- [ ] #4 Which sheet applies to an income year is recorded in the plan and the guide
<!-- AC:END -->
