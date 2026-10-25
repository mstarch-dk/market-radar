---
id: TASK-5.11
title: 'Docs: tax chapter in the guide and the textbook'
status: To Do
assignee: []
created_date: '2026-10-25 18:51'
labels:
  - docs
dependencies:
  - TASK-5.10
references:
  - plans/F3-tax-engine.md
parent_task_id: TASK-5
priority: high
ordinal: 61100
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
New brugervejledning/skat.md (the tab, classification, persons and openings, booking the ASK tax, the modelled / not modelled list, the disclaimer), in guide.yaml and linked from portefolje.md and portefoljer-og-tags.md. laerebog/skat.md: replace Radaren beregner ingen skat with a Sådan gør radaren section; rates via {{tax:...}}. formler.md (DKK average, lager, pool, progression), indstillinger.md (tax.years_back, removed propose keys, tax_dk.yaml). Skills /journal and /propose-portfolio mention radar tax year --json. Follow guide/STIL.md. Plan: section 7, step 11.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 uv run pytest -q tests/test_guide.py passes
- [ ] #2 The not modelled list covers at least spouse transfer, unlisted shares, withholding tax, the negative share income's tax value and history before the first transaction
- [ ] #3 No statement in the textbook contradicts the engine's golden tests
<!-- AC:END -->
