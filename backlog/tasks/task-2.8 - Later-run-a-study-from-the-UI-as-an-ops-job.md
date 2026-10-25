---
id: TASK-2.8
title: 'Later: run a study from the UI as an ops job'
status: To Do
assignee: []
created_date: '2026-10-25 14:51'
labels:
  - feature
dependencies:
  - TASK-2.5
references:
  - plans/F2-evidence-page.md
  - plans/analyses/product_owner.md
parent_task_id: TASK-2
priority: low
ordinal: 21000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
'Run study' buttons on the evidence cards start the study as an ops job (api/operations.py jobs) with progress; refused while a report build runs (locks.py).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Job shows progress in the ops log
- [ ] #2 Refused while a report build holds the lock
<!-- AC:END -->
