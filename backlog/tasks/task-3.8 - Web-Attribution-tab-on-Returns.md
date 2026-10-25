---
id: TASK-3.8
title: 'Web: Attribution tab on Returns'
status: Done
assignee: []
created_date: '2026-10-25 14:52'
updated_date: '2026-10-25 19:20'
labels:
  - feature
dependencies:
  - TASK-3.7
references:
  - plans/F4-attribution.md
parent_task_id: TASK-3
priority: high
ordinal: 32000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
An Attribution tab on the Returns page (Performance.tsx): Brinson tables by sector and by region per month and linked, the currency effect, factor loadings with t, and a skill-or-luck box (alpha, t, n, months needed for t = 2). The page states that benchmark segments are proxy ETFs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Proxy approximation stated on the page
- [x] #2 Missing values shown as missing
- [x] #3 pnpm -C web test passes
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Returns gets two tabs (Returns, Attribution) sharing the portfolio picker and From date; the ticked portfolios are pooled. pages/Attribution.tsx: period/TWR/active/alpha tiles; a waterfall from 0 through trading and fees, benchmark proxies vs ACWI and the five effects to the active return; By sector / By region with the linked segment table, a monthly stacked effects chart (hover readout, y-axis labels) and the months as a table; the currency table; a Skill or luck card (alpha, Newey-West t, weeks, months to t = 2, R², loadings); notes with unclassified holdings and back-drifted months. The proxy statement is on the page always; missing values show as – with a reason, and the waterfall draws no bar after a missing step. lib/attribution.ts (waterfall, extent, stack) with tests; glossary attr_* terms; guide afkast.md section. Checked in the demo copy (fictional investor), desktop and 375 px. glossary_links for attr_* come with the textbook chapter (TASK-3.9).
<!-- SECTION:FINAL_SUMMARY:END -->
