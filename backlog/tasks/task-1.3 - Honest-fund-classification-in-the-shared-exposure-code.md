---
id: TASK-1.3
title: Honest fund classification in the shared exposure code
status: Done
assignee: []
created_date: '2026-10-25 09:29'
labels:
  - correctness
dependencies:
  - TASK-1.1
  - TASK-1.2
references:
  - plans/F1-portfolio-xray.md
parent_task_id: TASK-1
priority: high
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan step 3 (sections 3 C3-C5, 4.3). Classify each holding as world / sector_fund / fund_sectors / fund / stock. A fund is looked through or labelled 'fund: not looked through', never filed under its listing region or quote currency. Add external.cached_detail (never fetches). Align universe.region_for with acwi_region (Canada, Australia). exposures() returns coverage per dimension. Proposals use it too: note the change for held funds in CHANGELOG and laerebog/portefoeljeforslag.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 test_fund_classes covers every class; a CSPX-like fund is not filed under europe
- [x] #2 'fund: not looked through' never counts as active weight in a real region
- [x] #3 cached_detail never reaches the network (test with the network layer failing)
- [x] #4 Every region key acwi_region can produce, region_for can produce, and vice versa
- [x] #5 propose_study output unchanged on the test world
<!-- AC:END -->
