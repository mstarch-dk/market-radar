---
id: TASK-5.10
title: 'Web: Tax tab on Portfolio'
status: To Do
assignee: []
created_date: '2026-10-25 18:51'
labels:
  - feature
  - web
dependencies:
  - TASK-5.9
references:
  - plans/F3-tax-engine.md
parent_task_id: TASK-5
priority: high
ordinal: 61000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A Tax tab on Portfolio with a year picker: the estimate banner with the rules year, verified date and sources; per person share income against the progression limit, tax per rate, capital income, carried forward; per account the pool or the realised and lager tables, dividends and warnings; unknown classification with an inline fix; persons, account owners and openings in a collapsed settings section. Term tooltips via lib/glossary.ts; page_links. Plan: 4.7, step 10.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Missing values show as a dash with a reason, never 0 (pnpm -C web test)
- [ ] #2 The estimate, not tax advice banner is always shown with the rules year
- [ ] #3 Fixing an unknown holding from the tab updates the estimate
<!-- AC:END -->
