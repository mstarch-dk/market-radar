---
id: TASK-3.5
title: Portfolio factor regression and skill-or-luck
status: To Do
assignee: []
created_date: '2026-10-25 14:52'
labels:
  - feature
dependencies:
  - TASK-3.2
references:
  - plans/F4-attribution.md
parent_task_id: TASK-3
priority: high
ordinal: 29000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Regress the portfolio's weekly (or daily) DKK excess returns on the developed factors, reusing signals/risk.ols and model/stats.nw_t. Market factor converted to DKK, long-short factors treated as currency-neutral (documented assumption), risk-free rate as in model/stats.daily_rf. Report alpha with Newey-West t and n, and the months needed for alpha to reach t = 2 at this volatility.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No regression under the minimum weekly observations (setting); a note says why
- [ ] #2 Alpha never shown without t and n
- [ ] #3 Tested on the synthetic world with a known loading
<!-- AC:END -->
