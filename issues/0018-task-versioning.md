---
id: 18
title: Task versioning
labels: [wayfinder:grilling]
status: closed
assignee: rharvey
parent: 1
blocked_by: []
---

## Question

Spec-review finding R2-3 on the approved design. After a `tasks.yaml` label-set change creates a new task version, what stops `activate` from turning on a model trained on the old label set? Define: `activate` rejects a model from another task version (named error) or a label-set rollback restores the old version and its models; when `tasks.yaml` changes are picked up (restart only, or reload); how a task version is identified in `/v1/models`; and the error for feedback whose label left the set (R2-4).

## Resolution

Delegated by the founder ("keep it as simple as possible, don't overthink, really anything that runs is fine", 2026-10-08); simplest working option chosen from the brief where one exists.
- No task versioning. A task's label set is fixed for its name: on startup, if a task's labels in `tasks.yaml` differ from those stored, the container refuses to start and tells the user to give the changed task a new name (the old task's data stays until its name is removed from `tasks.yaml`).
- `activate` takes the task in the path and rejects a version from another task (404).
- This removes version tracking, migration of examples and split resets.
