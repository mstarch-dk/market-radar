---
id: TASK-3.5
title: Portfolio factor regression and skill-or-luck
status: Done
assignee: []
created_date: '2026-10-25 14:52'
updated_date: '2026-10-25 16:35'
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
Regress the portfolio's weekly DKK excess returns (TWR index minus the weekly compounded model/stats.daily_rf) on the French developed daily factors compounded to weeks. Add model/stats.ols_nw (coefficients via signals/risk.ols, Newey-West standard errors), nw_lag (the floor(4 (n/100)^(2/9)) rule unless attribution.nw_lag is set) and months_to_t; nw_t stays. Market factor converted to DKK, long-short factors treated as currency-neutral (documented assumption). Window ends at the last factor date. Report alpha with Newey-West t and n, loadings with NW t, and the months needed for alpha to reach t = 2 at this volatility. Plan: 4.4, step 6.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 No regression under the minimum weekly observations (setting); a note says why
- [x] #2 Alpha never shown without t and n
- [x] #3 Tested on the synthetic world with a known loading
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
model/stats: ols_nw (Newey-West standard errors; equals nw_t for an intercept, White's at lag 0), nw_lag (Newey-West 1994 rule), periods_to_t. model/attribution: regression_frame (weekly DKK excess returns; French's market in DKK via USD/DKK, long-short factors as given) and factor_regression (None under min_weeks, alpha always with t and n, weeks/months to t = 2 or reached, loadings with NW t). Tested on generated weeks with known loadings. The note under the minimum is written by attribution.py (TASK-3.6), from the None this returns.
<!-- SECTION:FINAL_SUMMARY:END -->
