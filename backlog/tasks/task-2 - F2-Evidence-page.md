---
id: TASK-2
title: F2 Evidence page
status: To Do
assignee: []
created_date: '2026-10-25 14:50'
labels:
  - feature
  - evidence
dependencies: []
references:
  - plans/F2-evidence-page.md
  - plans/analyses/product_owner.md
priority: high
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The momentum, quality, value and K+V studies in the app: IC with t, quintile spread, top-N vs universe and ACWI, holdout vs in-sample and the verdicts, next to the long-run study and a forward out-of-sample scoreboard (A/B test, picks-live, frozen proposals vs ACWI). Read-only over the study reports; the app never imports backtest/. Review: plans/analyses/product_owner.md, F2. Release 0.3. Analysis, not advice.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 One card per score study and the long-run study, each with its age, rule hash and staleness
- [ ] #2 A forward scoreboard from existing data
- [ ] #3 A missing study shows 'not run yet' with the command; a stale one is greyed with 'older rule', never mixed with current numbers
- [ ] #4 t-stats next to every mean; the holdout start quoted from settings
- [ ] #5 Available as GET /api/evidence and the /evidence page
<!-- AC:END -->
