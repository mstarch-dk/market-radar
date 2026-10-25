---
id: TASK-1.1
title: Move the exposure and risk engine from propose/ to portfolios/
status: To Do
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
- [ ] #1 propose candidates and propose evaluate on the test world equal a JSON snapshot taken before the move
- [ ] #2 No caller reads a moved name through propose (tests/test_layers.py, lint-imports)
- [ ] #3 pytest, ruff, mypy and lint-imports green
<!-- AC:END -->
