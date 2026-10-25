---
id: TASK-1
title: F1 Portfolio X-ray
status: To Do
assignee: []
created_date: '2026-10-25 09:28'
labels:
  - feature
  - xray
dependencies: []
references:
  - plans/F1-portfolio-xray.md
  - plans/analyses/product_owner.md
priority: high
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Live view of what the real portfolio is exposed to and where its risk comes from, against ACWI, in DKK, for one account, several accounts or a tag. It shares one exposure and risk engine with propose evaluate, so a proposal and the X-ray never disagree about the same holdings. Plan: plans/F1-portfolio-xray.md (review: plans/analyses/product_owner.md, F1). Analysis, not advice.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Sector, region and currency weights and active weights vs ACWI, with world funds looked through and coverage per dimension
- [ ] #2 Ex-ante volatility, beta and tracking error vs ACWI, with each position's share of total and active risk
- [ ] #3 Concentration: effective N, top-5 share, largest position, largest risk contributor, correlated pairs
- [ ] #4 Stress windows and factor tilts of today's holdings next to ACWI
- [ ] #5 Available as GET /api/xray, radar xray [--json] and the /xray page
- [ ] #6 Proposals and the X-ray share one code path (tested); missing data shown as missing, never 0
<!-- AC:END -->
