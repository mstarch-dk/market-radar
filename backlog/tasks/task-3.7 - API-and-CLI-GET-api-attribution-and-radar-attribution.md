---
id: TASK-3.7
title: 'API and CLI: GET /api/attribution and radar attribution'
status: To Do
assignee: []
created_date: '2026-10-25 14:52'
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
- [ ] #1 CLI --json and the API return the same view
- [ ] #2 Settings validated by config_schema
<!-- AC:END -->
