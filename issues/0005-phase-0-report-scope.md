---
id: 5
title: Phase 0 report scope
labels: [wayfinder:grilling]
status: closed
assignee: rharvey
parent: 1
blocked_by: []
---

## Question

What does the `decider-eval` report contain and how is uncertainty stated? Settle adding (d) base zero-shot as a fourth system (R3-6, step 4 + Success Criteria say three-way), and how CIs are treated across up to four repeated gate looks (R3-9: nominal vs corrected, e.g. 98.75%). Also the report's exact sections and file formats (JSON + Markdown).

## Notes (2026-10-08)

Reshaped by the approved design: the report covers public datasets, systems (b) offline LLM, (c), (d), majority, TF-IDF+LR, with macro-F1 CIs, learning curve, p95 latency and cost per 1,000 decisions; one look per dataset (no repeated-looks correction needed). Still open: which LLM and settings are baseline (b), the reference machine and CPU-hour price, and the report's file format and sections.

## Resolution

Delegated by the founder ("keep it as simple as possible, don't overthink, really anything that runs is fine", 2026-10-08); simplest working option chosen from the brief where one exists.
- Baseline (b): one LLM, Gemini 3.5 Flash-Lite, zero-shot with the task's question and label descriptions, temperature 0, lowest thinking setting, output restricted to the label set; an invalid answer counts as wrong.
- Who calls it: a standalone prep script outside `src/decider` (public data only) writes predictions with per-call latency and token counts; `decider-eval` reads them as a named system. The product never calls an LLM.
- Machine: run everything on one stated machine (specs in the report). Local cost = measured busy CPU-hours priced at Hetzner CX43's hourly rate (€0.0256/h, 2026-10-08) plus one 250-label retrain amortised over 30,000 decisions; LLM cost = list price on the run date. Token sensitivity ±30% as one extra line.
- p95: sequential single requests, one session, both sides measured from the same machine.
- CIs: nominal 95% paired bootstrap, stated as unadjusted; one look per dataset.
- Test sets: full official test partitions; subsample to 1,000 only if a run doesn't fit in a day.
- Output: `report.json` (with schema version) and `report.md` rendered from it; aggregate numbers and dataset attribution only.
Brief: `../docs/briefs/0005-phase-0-report-scope.md`.
