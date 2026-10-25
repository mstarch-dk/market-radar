---
id: TASK-5
title: F3 Danish tax engine and after-tax returns
status: To Do
assignee: []
created_date: '2026-10-25 18:49'
labels:
  - feature
  - tax
dependencies: []
references:
  - plans/F3-tax-engine.md
  - plans/analyses/product_owner.md
priority: high
ordinal: 60000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Estimate the Danish tax the radar's own records imply, per account and tax year: realised gains and losses with the average-cost method in DKK (per tax person across their frie midler accounts), dividends, lager gains on lager-taxed holdings, the ASK's and the pension account's tax base with losses carried forward, share income against the progression limit, and capital income from funds off the positive list. Every number labelled an estimate with its rules year; unclassifiable holdings named with their value, never assumed. Later: after-tax TWR with an after-tax ACWI twin, the year-end planner, an after-tax mode for simulations and studies, a withholding-tax estimate. Review: plans/analyses/product_owner.md, F3. Plan: plans/F3-tax-engine.md. Release 0.4. Analysis, not advice, and not tax advice.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Golden tests pass for ASK lager with a loss year, frie midler average-cost realisation over partial sales, a positive-list ETF on lager with a mid-year purchase, and an ETF that leaves the positive list
- [ ] #2 An unclassifiable holding is shown as unknown classification, excluded from the estimate with its value named, never assumed
- [ ] #3 A year without verified rules shows no rules for that year, never another year's numbers
- [ ] #4 Pre-tax numbers are unchanged by the feature (regression test on performance.analyze)
- [ ] #5 Available as GET /api/tax, radar tax year [--json] and a Tax tab on Portfolio
<!-- AC:END -->
