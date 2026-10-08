---
id: 18
title: Task versioning
labels: [wayfinder:grilling]
status: open
assignee:
parent: 1
blocked_by: []
---

## Question

Spec-review finding R2-3 on the approved design. After a `tasks.yaml` label-set change creates a new task version, what stops `activate` from turning on a model trained on the old label set? Define: `activate` rejects a model from another task version (named error) or a label-set rollback restores the old version and its models; when `tasks.yaml` changes are picked up (restart only, or reload); how a task version is identified in `/v1/models`; and the error for feedback whose label left the set (R2-4).
