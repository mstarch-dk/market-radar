---
id: TASK-1.6
title: 'API: XrayView and GET /api/xray'
status: To Do
assignee: []
created_date: '2026-10-25 09:29'
labels:
  - api
dependencies:
  - TASK-1.5
references:
  - plans/F1-portfolio-xray.md
parent_task_id: TASK-1
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan step 5 (section 4.4). api_models/xray.py (extra=forbid, re-exported), api/xray.py router included last in api/app.py, selection via portfolio/tag/scope, a cache per (selection, market mtime, transactions version). Regenerate web/src/api/schema.ts (pnpm -C web gen:api); add xray() to client.ts. Update docs/web-app.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Response validates against XrayView; an empty selection returns 200 with notes; no prices returns 503
- [ ] #2 OpenAPI order of the existing routers unchanged
- [ ] #3 pnpm -C web build passes
<!-- AC:END -->
