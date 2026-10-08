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
