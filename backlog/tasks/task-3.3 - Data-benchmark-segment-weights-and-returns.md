---
id: TASK-3.3
title: 'Data: benchmark segment weights and returns'
status: Done
assignee: []
created_date: '2026-10-25 14:52'
updated_date: '2026-10-25 15:27'
labels:
  - feature
dependencies:
  - TASK-3.1
references:
  - plans/F4-attribution.md
parent_task_id: TASK-3
priority: high
ordinal: 27000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ACWI's aggregate weights (sector, region, country, currency and the sector/region x currency and region x country cross-tabs; no stock rows) appended once per ISO week by radar run to the history-tier file acwi_segments.csv, with the holdings file's as-of date (iShares serves no past holdings: see the plan's spike). portfolios/segments.py: monthly benchmark weights with their basis (snapshot, or back-drifted from the first snapshot with the proxies' returns before it), daily DKK segment returns from the proxies and each segment's currency mix. Proxies in universe.yaml attribution:: Xtrackers MSCI World sector UCITS (Real Estate: SPYJ.DE), falling back to sector_etfs.us before their first price; regions as country ETFs weighted by ACWI's country weights inside the region, with min_proxy_coverage. Update DATA_LICENSE.md and datalicenser.md (iShares aggregate history, proxy tickers). Plan: 4.2, 4.3, step 4. Merge early: every week it waits is a snapshot lost.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A missing month or proxy is shown as missing, never 0
- [x] #2 History file is append-only and never deletes user data
- [x] #3 Every ACWI weight key is one the radar's classification can produce
- [x] #4 Back-drifted months flagged as such, tested on a hand example
- [x] #5 Licence outcome for the iShares aggregate history recorded in DATA_LICENSE.md and datalicenser.md
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
radar run records ACWI's aggregate weights (sector, region, country, currency and cross-tabs) once per ISO week in history/acwi_segments.csv, append-only, from the holdings file's as-of date. portfolios/segments.py gives the daily benchmark weights (drifted from the last snapshot, back-drifted before the first, with the basis) and the segments' daily DKK returns from universe.yaml attribution: (Xtrackers MSCI World sectors with the US sector ETFs before them; country ETFs mixed by ACWI's country weights, min_proxy_coverage). Missing returns stay missing. DATA_LICENSE.md, datalicenser.md, indstillinger.md, Data & coverage row, docs updated.
<!-- SECTION:FINAL_SUMMARY:END -->
