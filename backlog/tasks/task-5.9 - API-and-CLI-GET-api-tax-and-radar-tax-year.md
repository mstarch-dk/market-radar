---
id: TASK-5.9
title: 'API and CLI: GET /api/tax and radar tax year'
status: To Do
assignee: []
created_date: '2026-10-25 18:51'
labels:
  - feature
  - api
  - cli
dependencies:
  - TASK-5.8
references:
  - plans/F3-tax-engine.md
parent_task_id: TASK-5
priority: high
ordinal: 60900
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
api_models/tax.py (TaxYearView and the edit models, strict), api/tax.py (GET /api/tax?year=&person=&portfolio=, instruments, persons, openings edits, tax_person_id on portfolios), radar tax year YEAR [--portfolio P] [--person N] [--json], the tax.years_back setting and schema, TypeScript types, client.ts, docs/commands.md, docs/web-app.md, CLAUDE.md main commands. Cached per year, selection, market mtime and data versions; 503 without prices. Plan: 4.4-4.6, step 9.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 radar tax year --json equals the API's view for the same selection (tested)
- [ ] #2 The view validates against TaxYearView; no prices gives 503; edits round-trip (tested)
- [ ] #3 A year without rules returns a valid view with nulls and notes, not an error
<!-- AC:END -->
