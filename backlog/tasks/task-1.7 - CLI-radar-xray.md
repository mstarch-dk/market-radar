---
id: TASK-1.7
title: 'CLI: radar xray'
status: To Do
assignee: []
created_date: '2026-10-25 09:29'
labels:
  - cli
dependencies:
  - TASK-1.5
references:
  - plans/F1-portfolio-xray.md
parent_task_id: TASK-1
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan step 5 (section 4.5). radar xray [NAME...] [--tag T] [--scope real|virtual|all] [--json] in cli/portfolios.py: exposure, risk, concentration and stress tables; --json prints the XrayView dict. Update docs/commands.md and the main commands in CLAUDE.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 radar xray --json runs on the test world and prints valid JSON (test_cli_smoke)
- [ ] #2 Names resolve as radar performance resolves them
<!-- AC:END -->
