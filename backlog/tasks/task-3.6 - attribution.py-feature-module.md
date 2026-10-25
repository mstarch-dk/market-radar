---
id: TASK-3.6
title: attribution.py feature module
status: Done
assignee: []
created_date: '2026-10-25 14:52'
updated_date: '2026-10-25 17:02'
labels:
  - feature
dependencies:
  - TASK-3.3
  - TASK-3.4
  - TASK-3.5
  - TASK-3.13
references:
  - plans/F4-attribution.md
parent_task_id: TASK-3
priority: high
ordinal: 30000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
src/radar/attribution.py: from the portfolio's daily books (portfolios/performance.book) build monthly segment weights and returns by sector and by region through portfolios/exposure, run the attribution and the regression, and add coverage and notes (unclassified value, proxy approximations, today's classification used for past months). No math of its own. Add to the features layer in pyproject.toml.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 No attribution under 12 months (setting), with a note
- [x] #2 Unclassified or unvalued holdings are listed, never counted as 0 % return
- [x] #3 uv run lint-imports and tests/test_layers.py pass
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
src/radar/attribution.py (build, cached, reset): daily Brinson-Fachler by sector and region on local returns from Book.positions, exposure.ticker_meta and portfolios/segments; currency effect and cross term; Carino linking to months and the period with the linking error checked against attribution.tolerance; reconciliation (TWR - ACWI = trading and fees + proxies vs ACWI + attributed); unclassified holdings listed; days with unknown values left out and counted; factor regression with notes when data or weeks are short. model/attribution gains vectorised brinson_panel and currency_panel. Settings attribution.min_months, min_weeks, nw_lag, tolerance, factors. Added to the features layer and the app-never-imports-backtest contract.
<!-- SECTION:FINAL_SUMMARY:END -->
