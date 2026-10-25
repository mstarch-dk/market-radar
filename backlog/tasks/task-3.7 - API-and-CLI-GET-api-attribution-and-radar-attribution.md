---
id: TASK-3.7
title: 'API and CLI: GET /api/attribution and radar attribution'
status: Done
assignee: []
created_date: '2026-10-25 14:52'
updated_date: '2026-10-25 18:35'
labels:
  - feature
dependencies:
  - TASK-3.6
references:
  - plans/F4-attribution.md
parent_task_id: TASK-3
priority: high
ordinal: 31000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
api_models/attribution.py strict views, GET /api/attribution, and uv run radar attribution [NAME...] [--tag T] [--start D] [--json]. New settings in config/settings.yaml and config_schema.py. TypeScript types regenerated. docs/commands.md updated.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 CLI --json and the API return the same view
- [x] #2 Settings validated by config_schema
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
api_models/attribution.py: strict AttributionView (dims keyed sector | region, reconciliation, months with basis, currency table, unclassified with `class` on the wire, the factor regression). GET /api/attribution?portfolio=&tag=&scope=&start=&end= (dates YYYY-MM-DD, 422 otherwise; 503 without prices; router last). uv run radar attribution [NAME...] [--tag T] [--scope] [--start D] [--end D] [--json] in cli/portfolios.py. The attribution settings came with TASK-3.6 and are validated by config_schema; the guide's settings chapter now lists them. A test holds the CLI's --json equal to the API's view on a full attribution. TS types regenerated, client.attribution(sel, start?). docs/commands.md, docs/web-app.md, CLAUDE.md, guide kommandolinjen.md updated.
<!-- SECTION:FINAL_SUMMARY:END -->
