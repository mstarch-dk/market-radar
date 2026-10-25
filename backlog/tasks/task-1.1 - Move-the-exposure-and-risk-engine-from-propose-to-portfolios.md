---
id: TASK-1.1
title: Move the exposure and risk engine from propose/ to portfolios/
status: Done
assignee: []
created_date: '2026-10-25 09:29'
labels:
  - refactor
dependencies: []
references:
  - plans/F1-portfolio-xray.md
parent_task_id: TASK-1
priority: high
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan step 1 (sections 3 C1, 4.1). Move propose/pricing.py to portfolios/prices.py, propose/exposure.py to portfolios/exposure.py, propose/riskmodel.py (minus bootstrap, which stays in propose) plus evaluation.factors (renamed factor_tilts) to portfolios/riskmodel.py. Update every caller, the propose facade, backtest/propose_study.py and the tests; no re-exports through propose. Update docs/architecture.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 propose candidates and propose evaluate on the test world equal a JSON snapshot taken before the move
- [x] #2 No caller reads a moved name through propose (tests/test_layers.py, lint-imports)
- [x] #3 pytest, ruff, mypy and lint-imports green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Moved to portfolios/prices.py, portfolios/exposure.py and portfolios/riskmodel.py (evaluation.factors is now riskmodel.factor_tilts); the bootstrap stays in propose as propose/resample.py. The moved code reads the propose settings through typed().propose until TASK-1.2 moves them to risk:.

AC #1 was checked once, not as a committed test: the test world's dates follow date.today() (tests/world.py), so weekly W-FRI returns and every date in the output change from day to day and a stored snapshot can't stay equal. The snapshot of candidates + evaluate (floats at 6 significant digits) was taken before the move and compared equal after it on 2026-10-25; the existing proposal tests guard the behaviour from here.
<!-- SECTION:NOTES:END -->
