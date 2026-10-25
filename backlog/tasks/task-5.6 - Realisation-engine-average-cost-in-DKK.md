---
id: TASK-5.6
title: 'Realisation engine: average cost in DKK'
status: To Do
assignee: []
created_date: '2026-10-25 18:51'
labels:
  - feature
dependencies:
  - TASK-5.1
references:
  - plans/F3-tax-engine.md
parent_task_id: TASK-5
priority: high
ordinal: 60600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
model/tax.replay_dkk: the average-cost replay in DKK at each trade's rate (its fx_rate, else Yahoo's rate that day, as performance.trade_fx), buy fees in the cost and sale fees out of the proceeds, gains per sale, an oversized sale capped and reported, a trade without a rate making the group's gains missing from that day. Grouped per (tax person, security) for frie midler and per (portfolio, security) otherwise. trades.replay unchanged. Plan: C1, C2, 4.3, step 6.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The textbook's partial-sale example gives a gain of 145 DKK; the same with rates other than 1 matches a hand calculation (tested)
- [ ] #2 Buys in two frie midler accounts of one person share one average; an ASK buy doesn't move it (tested)
- [ ] #3 A missing rate makes the gains missing, never 0
<!-- AC:END -->
