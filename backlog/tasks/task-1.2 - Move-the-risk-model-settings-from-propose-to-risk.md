---
id: TASK-1.2
title: 'Move the risk-model settings from propose: to risk:'
status: To Do
assignee: []
created_date: '2026-10-25 09:29'
labels:
  - refactor
  - config
dependencies:
  - TASK-1.1
references:
  - plans/F1-portfolio-xray.md
parent_task_id: TASK-1
priority: high
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan step 2 (section 4.2). Move history_weeks/min_weeks/shrink to risk.covariance, look_through to risk.world_funds and stress to risk.stress, in settings.yaml and config_schema.py, with the same values. Keep propose.min_weeks if a proposal-only reader needs it. Add the risk.xray block (min_coverage 0.5, warn_coverage 0.8, pair_corr 0.7). Update guide/brugervejledning/indstillinger.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Rule hash of the shipped settings unchanged (test)
- [ ] #2 A proposal's numbers unchanged on the test world
- [ ] #3 An old propose.stress or propose.look_through key fails on load, naming the key
<!-- AC:END -->
