---
id: TASK-3
title: F4 Attribution and decision analytics
status: To Do
assignee: []
created_date: '2026-10-25 14:52'
labels:
  - feature
  - attribution
dependencies:
  - TASK-1
references:
  - plans/F4-attribution.md
  - plans/analyses/product_owner.md
priority: high
ordinal: 24000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Why the portfolio beat or lagged ACWI, and whether it is skill: a Brinson-Fachler attribution vs ACWI by sector and region (allocation, selection, interaction, plus a currency effect in DKK), linked over the period; a returns-based factor regression (developed-market French factors) with alpha, its Newey-West t and the months of data needed for t = 2. Later: trade-level and behavioural review, journal theses vs outcomes; after-tax attribution waits on F3. Builds on F1's exposure code. Review: plans/analyses/product_owner.md, F4. Release 0.4. Analysis, not advice.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Allocation + selection + interaction sum to the active return each month
- [ ] #2 The linked total equals the period's active return within a stated tolerance
- [ ] #3 A synthetic portfolio with ACWI's sector weights shows zero allocation
- [ ] #4 Alpha always shown with t and n; no attribution under 12 months, no regression under the minimum weekly observations
- [ ] #5 Available as GET /api/attribution, radar attribution [--json] and an Attribution tab on Returns
<!-- AC:END -->
