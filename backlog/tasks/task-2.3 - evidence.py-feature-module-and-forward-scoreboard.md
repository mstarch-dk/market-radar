---
id: TASK-2.3
title: evidence.py feature module and forward scoreboard
status: To Do
assignee: []
created_date: '2026-10-25 14:51'
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
src/radar/evidence.py assembles the page: the parsed study headers and summary blocks, and a forward scoreboard of the A/B test (abtest.summary), picks-live portfolios and frozen proposals (propose/store.review), each vs ACWI over the same days. No math of its own; never imports backtest/. Add it to the features layer in pyproject.toml.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Forward records below a minimum length are labelled as too short, not ranked
- [ ] #2 uv run lint-imports and tests/test_layers.py pass
- [ ] #3 Missing data is None with a note, never 0
<!-- AC:END -->
