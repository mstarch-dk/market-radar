---
id: TASK-1.9
title: 'Docs: X-ray guide chapter and textbook additions'
status: Done
assignee: []
created_date: '2026-10-25 09:29'
labels:
  - docs
dependencies:
  - TASK-1.8
references:
  - plans/F1-portfolio-xray.md
parent_task_id: TASK-1
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan step 6 (section 7). New guide chapter brugervejledning/xray.md in guide.yaml (Dig og dine penge) and page_links; links from navigation.md, beholdninger.md, afkast.md. Textbook: diversifikation.md, beta-og-alfa.md, volatilitet-og-drawdown.md, portefoeljeforslag.md, formler.md. glossary_links for the new terms. DATA_LICENSE.md and datalicenser.md Used-for column. Follow guide/STIL.md; thresholds via {{settings:...}}.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 uv run pytest -q tests/test_guide.py passes
- [x] #2 Every new threshold quoted with a settings placeholder
<!-- AC:END -->
