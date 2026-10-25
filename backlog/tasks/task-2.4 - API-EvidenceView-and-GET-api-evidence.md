---
id: TASK-2.4
title: 'API and CLI: EvidenceView, GET /api/evidence, radar evidence'
status: Done
assignee: []
created_date: '2026-10-25 14:51'
updated_date: '2026-10-25 15:44'
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
api_models/evidence.py strict views, api/evidence.py router with GET /api/evidence (included last), uv run radar evidence [--json] in cli/study.py, TypeScript types regenerated and client.ts (docs/web-app.md); docs/commands.md and CLAUDE.md main commands. Plan: plans/F2-evidence-page.md, step 3 and 4.5-4.6.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Strict view; missing fields are null
- [x] #2 TypeScript types regenerated and pnpm -C web test passes
- [x] #3 radar evidence --json prints valid JSON on the test world
<!-- AC:END -->
