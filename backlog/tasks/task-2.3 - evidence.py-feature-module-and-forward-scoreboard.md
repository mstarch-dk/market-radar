---
id: TASK-2.3
title: evidence.py feature module and forward scoreboard
status: To Do
assignee: []
created_date: '2026-10-25 14:51'
updated_date: '2026-10-25 15:01'
labels:
  - feature
dependencies:
  - TASK-2.2
references:
  - plans/F2-evidence-page.md
parent_task_id: TASK-2
priority: high
ordinal: 16000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
src/radar/evidence.py assembles the page: a card per score study and the long-run study, header rows for the propose, exit and redeploy studies, and a forward scoreboard of the A/B test (abtest.summary), the picks-live baskets (portfolios) and frozen proposals (propose/store.review), each vs ACWI over the same days. Move the picks strategies and baskets() from backtest/picks.py to portfolios/simulate.py. New evidence: settings (max_age_days, forward_min_months, cohort_age_months, cohort_min) in settings.yaml and config_schema.py. No math of its own; never imports backtest/. Add it to the features layer and the app contract in pyproject.toml. Plan: plans/F2-evidence-page.md, step 2 and 4.3-4.4.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Forward records below a minimum length are labelled as too short, not ranked
- [ ] #2 uv run lint-imports and tests/test_layers.py pass
- [ ] #3 Missing data is None with a note, never 0
- [ ] #4 A stale report's numbers never appear next to current ones (tested)
<!-- AC:END -->
