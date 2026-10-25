---
id: TASK-5.5
title: 'Tax persons: which accounts belong to one person'
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
ordinal: 60500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
userstore migrations: tax_persons (name, capital_income_rate, note) and portfolios.tax_person_id. The migration creates Me and links every real ask, frie_midler and pension portfolio to it; virtual portfolios stay null. radar tax person list|add|set; PATCH /api/portfolios accepts tax_person_id later (TASK-5.9). Plan: C3, C4, 4.2, step 5.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The default links real tax accounts to Me and leaves virtual ones null (tested)
- [ ] #2 A person without a capital-income rate shows the base and no tax on it
- [ ] #3 The migration is append-only and keeps existing data
<!-- AC:END -->
