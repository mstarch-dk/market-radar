---
id: TASK-3.2
title: 'Data: French developed daily or weekly factors'
status: To Do
assignee: []
created_date: '2026-10-25 14:52'
labels:
  - feature
dependencies:
  - TASK-3.1
references:
  - plans/F4-attribution.md
parent_task_id: TASK-3
priority: high
ordinal: 26000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
sources/factors.py and the factors: settings: add the developed-market 5-factor and momentum files at daily (or weekly) frequency (today only monthly ff3_dev and mom_dev are configured). Same licence; update the Used-for column in DATA_LICENSE.md and guide/brugervejledning/datalicenser.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A file that parses to nothing fails loudly and keeps its cache
- [ ] #2 Each new file has its tier in paths.REGISTRY
- [ ] #3 Parser tested on a real sample fixture
<!-- AC:END -->
