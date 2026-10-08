---
id: 5
title: Phase 0 report scope
labels: [wayfinder:grilling]
status: open
assignee:
parent: 1
blocked_by: []
---

## Question

What does the `decider-eval` report contain and how is uncertainty stated? Settle adding (d) base zero-shot as a fourth system (R3-6, step 4 + Success Criteria say three-way), and how CIs are treated across up to four repeated gate looks (R3-9: nominal vs corrected, e.g. 98.75%). Also the report's exact sections and file formats (JSON + Markdown).

## Notes (2026-10-08)

Reshaped by the approved design: the report covers public datasets, systems (b) offline LLM, (c), (d), majority, TF-IDF+LR, with macro-F1 CIs, learning curve, p95 latency and cost per 1,000 decisions; one look per dataset (no repeated-looks correction needed). Still open: which LLM and settings are baseline (b), the reference machine and CPU-hour price, and the report's file format and sections.
