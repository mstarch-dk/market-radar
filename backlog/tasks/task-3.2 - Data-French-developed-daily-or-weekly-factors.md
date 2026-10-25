---
id: TASK-3.2
title: 'Data: French developed daily or weekly factors'
status: To Do
assignee: []
created_date: '2026-10-25 14:52'
updated_date: '2026-10-25 15:07'
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
sources/factors.py and the factors: settings: a new factors.french_daily block with the developed-market 5-factor and momentum files at daily frequency (Developed_5_Factors_Daily_CSV, Developed_Mom_Factor_Daily_CSV; French has no weekly developed files), a daily row parser (YYYYMMDD), a separate cache file factors/daily.parquet so the monthly file's month-end contract stays, and compounding to W-FRI weeks (a week with a missing day is missing). Same licence; update the Used-for column in DATA_LICENSE.md and guide/brugervejledning/datalicenser.md. Plan: plans/F4-attribution.md, 4.2 and step 3.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A file that parses to nothing fails loudly and keeps its cache
- [ ] #2 Each new file has its tier in paths.REGISTRY
- [ ] #3 Parser tested on a real sample fixture
<!-- AC:END -->
