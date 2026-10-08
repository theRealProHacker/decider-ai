---
id: 9
title: Data lifecycle and erasure
labels: [wayfinder:grilling]
status: closed
assignee: rharvey
parent: 1
blocked_by: []
---

## Question

Define the lifecycle of stored text and labels: the response to feedback on a request purged by retention (R3-11, e.g. 410 REQUEST_EXPIRED), deleting by `request_id` when no `external_id` exists, removing deleted examples from the frozen split, and the policy for checkpoints trained on later-deleted examples — keep until next retrain, or force retrain/flag (R3-12, architecture.md open question).

## Notes (2026-10-08)

Also carries spec-review findings on the approved design: R2-1 (a confirmed example without `external_id` has no erasure path; commit one for every stored record) and R2-2 (what the frozen split does after a deletion: shrink, top up, unfreeze; how earlier verdicts are labelled). The design's interim behaviour: DELETE removes text, labels and split membership, lists versions trained on the example, never retrains.

## Resolution

Founder, 2026-10-08 (brief `../docs/briefs/0009-data-lifecycle-erasure.md`):
- Store as little as possible: `decide` stores no text. Feedback sends `{task, text, label, external_id, request_id?}`; `external_id` is required. No retention purge, no `REQUEST_EXPIRED`, no tombstones. (Supersedes the session's earlier answers on delete-by-`request_id` and tombstones.)
- Erasure: `DELETE /v1/examples/{external_id}` hard-deletes that ID's examples in all tasks; SQLite `secure_delete` on and WAL truncated after each erasure; backups are the operator's job.
- Frozen split after deletion: shrinks and stays frozen; the per-label minimum applies only at freeze time; status names labels now below 10; top-up only via `refresh_split`.
- Verdicts are kept; each records split revision and size.
- Checkpoints: never deleted by decider-ai ("this is self-hosted"). Each version records its training IDs; `/v1/models` shows the count later erased and `activate` warns. Erasure during a running job is covered by the same count.
