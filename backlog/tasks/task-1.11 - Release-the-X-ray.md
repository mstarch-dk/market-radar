---
id: TASK-1.11
title: Release the X-ray
status: To Do
assignee: []
created_date: '2026-10-25 09:29'
labels:
  - release
dependencies:
  - TASK-1.7
  - TASK-1.9
references:
  - plans/F1-portfolio-xray.md
parent_task_id: TASK-1
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan step 8. CHANGELOG.md and guide Nyheder (incl. the settings keys moved to risk:), marketing features.yaml entry, /market-brief reads radar xray --json for the holdings section, screenshot check in the demo copy (fictional investor), never the user's data folder.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Nyheder tells users with edited propose.stress or propose.look_through where the keys moved
- [ ] #2 Full suite green: pytest, ruff, mypy, lint-imports, pnpm -C web test
<!-- AC:END -->
