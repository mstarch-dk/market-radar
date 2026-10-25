---
id: TASK-5.2
title: 'Tax rules per year: config/tax_dk.yaml'
status: To Do
assignee: []
created_date: '2026-10-25 18:51'
labels:
  - feature
  - config
dependencies:
  - TASK-5.1
references:
  - plans/F3-tax-engine.md
parent_task_id: TASK-5
priority: high
ordinal: 60200
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
config/tax_dk.yaml with one block per income year (2025, 2026): share-income rates and progression limit, ASK rate and deposit cap, PAL rate, loss pools; every number with its skat.dk source and the day it was verified. config_schema.TaxRules, portfolios/taxrules.py (rules(year) raises NoRules for a year without a verified block), a {{tax:...}} placeholder for the guide. Move propose.ask_deposit_cap and ask_cap_year into the file (propose/draft.ask_account reads it there). Check the loss-pool rules against Den juridiske vejledning and record the outcome. DATA_LICENSE.md and datalicenser.md: rules typed in by hand from skat.dk. Plan: 4.2, 4.4, step 2.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A year without a verified block raises NoRules; nothing is reused from another year (tested)
- [ ] #2 Every number in the file has a source URL and a verified date
- [ ] #3 propose reads the ASK cap from the rules file; the old settings keys are gone with a CHANGELOG note
- [ ] #4 {{tax:...}} renders in the guide and an unknown path fails tests/test_guide.py
- [ ] #5 Loss-pool rules checked against Den juridiske vejledning, with the outcome in the file and the plan
<!-- AC:END -->
