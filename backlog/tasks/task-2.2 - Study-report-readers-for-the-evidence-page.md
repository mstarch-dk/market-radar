---
id: TASK-2.2
title: Study report readers for the evidence page
status: To Do
assignee: []
created_date: '2026-10-25 14:51'
labels:
  - feature
dependencies:
  - TASK-2.1
references:
  - plans/F2-evidence-page.md
parent_task_id: TASK-2
priority: high
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
model/artifacts.py: add entries for the fund-score reports (score-study-quality.json, score-study-value.json, score-study-qv.json, written by backtest/study.py via file=), so all four scores load through artifacts.load. Extend the models only for the fields the page shows; bump schema_version where a consumed field changes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All four score studies, longrun, propose, exit and redeploy load with status ok/stale/missing/invalid (tested)
- [ ] #2 A stale report is never mixed with current numbers
- [ ] #3 Older reports still load
<!-- AC:END -->
