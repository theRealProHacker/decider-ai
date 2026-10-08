---
id: 9
title: Data lifecycle and erasure
labels: [wayfinder:grilling]
status: open
assignee:
parent: 1
blocked_by: []
---

## Question

Define the lifecycle of stored text and labels: the response to feedback on a request purged by retention (R3-11, e.g. 410 REQUEST_EXPIRED), deleting by `request_id` when no `external_id` exists, removing deleted examples from the frozen split, and the policy for checkpoints trained on later-deleted examples — keep until next retrain, or force retrain/flag (R3-12, architecture.md open question).

## Notes (2026-10-08)

Also carries spec-review findings on the approved design: R2-1 (a confirmed example without `external_id` has no erasure path; commit one for every stored record) and R2-2 (what the frozen split does after a deletion: shrink, top up, unfreeze; how earlier verdicts are labelled). The design's interim behaviour: DELETE removes text, labels and split membership, lists versions trained on the example, never retrains.
