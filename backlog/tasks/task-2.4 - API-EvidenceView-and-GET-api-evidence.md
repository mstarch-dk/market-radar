---
id: TASK-2.4
title: 'API: EvidenceView and GET /api/evidence'
status: To Do
assignee: []
created_date: '2026-10-25 14:51'
labels:
  - feature
dependencies:
  - TASK-2.3
references:
  - plans/F2-evidence-page.md
parent_task_id: TASK-2
priority: high
ordinal: 17000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
api_models/evidence.py strict views, api/evidence.py router with GET /api/evidence, TypeScript types regenerated (docs/web-app.md).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Strict view; missing fields are null
- [ ] #2 TypeScript types regenerated and pnpm -C web test passes
<!-- AC:END -->
