---
id: 14
title: Build plan slicing
labels: [wayfinder:grilling]
status: closed
assignee: rharvey
parent: 1
blocked_by: [2, 3, 5, 7, 8, 9, 10, 11, 12, 13, 15, 17, 18, 19, 20]
---

## Question

Cut Phase 0 and Phase 1 into ordered vertical slices in `docs/build-plan.md`, each with acceptance tests, so the build proceeds slice by slice with no open questions. Confirms the design docs have zero open questions left; the map's destination.

## Resolution

`../docs/build-plan.md`: Track 2 (product) T2.1–T2.8 and Track 1 (eval and model) T1.1–T1.6, built in parallel; T2.4 needs T1.1, the join T2.7 needs T1.4, the release test T2.8 needs the T1.2 fixture; final slices are the Phase 1 release test (T2.8) and the gate run (T1.6). The 15 contradictions the plan surfaced were resolved in the docs. Every ticket on the map is closed; `docs/design.md` and `docs/architecture.md` have no open questions; ADR 0001 records the hard-to-reverse licensing choice; `CONTEXT.md` holds the glossary.
