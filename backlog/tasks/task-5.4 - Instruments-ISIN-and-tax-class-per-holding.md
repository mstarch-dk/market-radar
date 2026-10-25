---
id: TASK-5.4
title: 'Instruments: ISIN and tax class per holding'
status: Done
assignee: []
created_date: '2026-10-25 18:51'
updated_date: '2026-10-25 19:48'
labels:
  - feature
dependencies:
  - TASK-5.3
references:
  - plans/F3-tax-engine.md
parent_task_id: TASK-5
priority: high
ordinal: 60400
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
userstore migration for instruments (symbol, isin, tax_class override, source, note), filled without overwriting manual rows from the import's ISIN (symbol_map), universe.yaml isin: and discovery's isin_map.csv. The class per holding and year in portfolios/taxinputs: stock by quoteType, pl_fund / fund by ISIN and that year's sheet, dk_distributing by hand, unknown otherwise; a manual class wins. radar tax classify [--unknown], radar tax isin SYMBOL ISIN. Plan: 4.2, 4.3, step 4.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Fill order import, universe, discovery; a manual row is never overwritten (tested)
- [x] #2 A fund without an ISIN or a year without a sheet is unknown with its reason, never assumed
- [x] #3 A Danish fund off the list is asked about, not guessed
- [x] #4 The migration is append-only and keeps existing data
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
instruments table, userstore.save_instrument (manual wins), portfolios/taxinputs.py fill_instruments/security_kind/classify; radar tax classify/isin.
<!-- SECTION:FINAL_SUMMARY:END -->
