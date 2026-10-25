---
id: TASK-4
title: 'F5 Calendar: the coming weeks for what you own and watch'
status: To Do
assignee: []
created_date: '2026-10-25 18:00'
labels:
  - feature
  - calendar
dependencies: []
references:
  - plans/F5-calendar.md
  - plans/analyses/product_owner.md
priority: medium
ordinal: 37000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A calendar under Mine of the earnings and ex-dividend dates of held and watched names, plus journal review dates and proposal time stops, with stated highlight rules (position size, near review level, weak momentum, estimate cuts, unconfirmed or moved dates). Feeds the monthly brief through summary.json and the CLI (radar calendar). The calendar half of F5; the change feed and notifications follow in plans/F5-feed.md. Review: plans/analyses/product_owner.md, F5. Release 0.3. Analysis, not advice.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Held and watched earnings dates in the next weeks, as a range when Yahoo gives one, with source and read-on date
- [ ] #2 A held stock with no known date is listed, never dropped; funds are counted
- [ ] #3 Highlight levels follow the rules in plans/F5-calendar.md 4.5, each item with its reasons
- [ ] #4 The Me flag, the Home strip and the page use one code path
- [ ] #5 summary.json['calendar'] and a Kommende uger step in /market-brief
- [ ] #6 Available as GET /api/calendar, radar calendar and the /calendar page
<!-- AC:END -->
