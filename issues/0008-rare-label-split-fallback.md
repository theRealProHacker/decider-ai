---
id: 8
title: Rare-label split fallback
labels: [wayfinder:grilling]
status: closed
assignee: rharvey
parent: 1
blocked_by: []
---

## Question

What happens when a label never reaches the ≥10-per-label minimum, so the frozen split never forms and every candidate stays `unverified` (R3-8)? Options: configurable per-label minimum, merging rare labels for the check, surfacing blocking labels in `/health/ready`.

## Resolution

Delegated by the founder ("keep it as simple as possible, don't overthink, really anything that runs is fine", 2026-10-08); simplest working option chosen from the brief where one exists.
- The per-label minimum for freezing the split is `min(10, 100 // number_of_labels)` (e.g. 5 for 18 labels), so tasks with more than 10 labels can still freeze.
- A label that never reaches the minimum keeps the split unfrozen; candidates stay `unverified` and `/health/ready` names the blocking labels. No merging of rare labels.
