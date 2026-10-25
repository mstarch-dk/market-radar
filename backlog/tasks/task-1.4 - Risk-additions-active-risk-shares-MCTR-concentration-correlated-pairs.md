---
id: TASK-1.4
title: 'Risk additions: active risk shares, MCTR, concentration, correlated pairs'
status: Done
assignee: []
created_date: '2026-10-25 09:29'
labels:
  - risk
dependencies:
  - TASK-1.1
references:
  - plans/F1-portfolio-xray.md
parent_task_id: TASK-1
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan step 4 (section 4.3). Pure functions in portfolios/riskmodel.py: active_contributions (active vector with a -1 ACWI leg), mctr, concentration (effective N, top-5, largest position, largest CTR, world-fund weight), correlated_pairs (above risk.xray.pair_corr).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Shares of total risk and of active risk (incl. the ACWI leg) each sum to 1 on a hand-computed 3-asset covariance
- [x] #2 MCTR matches a finite-difference derivative of portfolio volatility
- [x] #3 Effective N is n for n equal weights and 1 for one position
<!-- AC:END -->
