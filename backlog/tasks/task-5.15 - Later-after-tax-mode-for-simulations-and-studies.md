---
id: TASK-5.15
title: 'Later: after-tax mode for simulations and studies'
status: To Do
assignee: []
created_date: '2026-10-25 18:52'
labels:
  - feature
dependencies:
  - TASK-5.6
  - TASK-5.7
references:
  - plans/F3-tax-engine.md
parent_task_id: TASK-5
priority: low
ordinal: 61500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A tax_model argument for sim, propose evaluate and study redeploy, off by default so studies stay comparable, so an experiment's verdict can include tax drag. Uses model/tax.py. Own short plan when it starts.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Off by default; a study's output is unchanged without it (tested)
- [ ] #2 The after-tax result names the account kind and rules year it assumed
<!-- AC:END -->
