---
id: TASK-3.1
title: 'Plan: F4 attribution, with the data decisions'
status: In Progress
assignee: []
created_date: '2026-10-25 14:52'
updated_date: '2026-10-25 15:07'
labels:
  - docs
dependencies: []
references:
  - plans/analyses/product_owner.md
parent_task_id: TASK-3
priority: high
ordinal: 25000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Write plans/F4-attribution.md following section 7 of the review, and record three decisions: (1) sector proxies: MSCI World sector UCITS where history allows, else the US sector ETFs, with a note; (2) the linking method (Carino or Menchero), named; (3) ACWI's sector and region weights per past month: acwi_holdings.csv is a cache snapshot that is overwritten, so spike whether the iShares holdings endpoint serves past dates (asOfDate) and check its terms; if not, record a monthly snapshot from now on and state the approximation for earlier months.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Plan written and approved before code
- [x] #2 Spike outcome and licence check recorded in the plan (section 2); the DATA_LICENSE.md rows land with TASK-3.2 and TASK-3.3
<!-- AC:END -->
