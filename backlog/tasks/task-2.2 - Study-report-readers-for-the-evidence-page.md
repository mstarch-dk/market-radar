---
id: TASK-2.2
title: Study report readers for the evidence page
status: Done
assignee: []
created_date: '2026-10-25 14:51'
updated_date: '2026-10-25 15:17'
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
model/artifacts.py: SCORE_SIGNALS (signal -> label, file) moved down from backtest/study.py SIGNALS; load(name, file=) like write, cache keyed by file, so all four score reports (score-study.json, score-study-quality/value/qv.json, all kind score-study) load. study_rule_hash(kind, signal) of the raw settings each study depends on plus a hand-bumped SCORE_REVISION, stamped by the score and long-run writers; a report without a hash is stale with 'written before rules were recorded'. Type the consumed fields (in_sample, top_excess_t, monotone, top_vs_market_t, panel variants) and add top_vs_acwi(_t) to model/stats.summarize; SCHEMA_VERSION 2. Plan: plans/F2-evidence-page.md, steps 1 and 4.1-4.2.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 All four score studies, longrun, propose, exit and redeploy load with status ok/stale/missing/invalid (tested)
- [x] #2 A stale report is never mixed with current numbers
- [x] #3 Older reports still load
- [x] #4 Rule hash moves with its settings keys and revision; every hashed key exists in settings.yaml (tested)
- [x] #5 top_vs_acwi and its Newey-West t in summarize (hand-computed test)
<!-- AC:END -->
