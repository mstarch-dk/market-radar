---
id: TASK-1.5
title: xray.py feature module
status: To Do
assignee: []
created_date: '2026-10-25 09:29'
labels:
  - feature
dependencies:
  - TASK-1.2
  - TASK-1.3
  - TASK-1.4
references:
  - plans/F1-portfolio-xray.md
parent_task_id: TASK-1
priority: high
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan step 5 (sections 4.1, 4.3). src/radar/xray.py builds the X-ray for a portfolio selection: holdings book, cash from performance.cash_balance for ledger portfolios, unvalued positions, classification, exposures, shrunk covariance, risk figures with coverage rules, realised vol and drawdown from performance.compare, concentration, stress, factor tilts, notes. No math of its own. Add xray to the features layer in pyproject.toml.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Exposure and before-risk equal propose evaluate's for the same holdings (test_xray_same_as_proposal)
- [ ] #2 A holding without a price is listed as unvalued and absent from weights, never a 0 % return
- [ ] #3 Below min_coverage risk is null with a note; between min and warn coverage it carries a warning
- [ ] #4 Ledger portfolios show cash; implicit ones show none, and a note names them
<!-- AC:END -->
