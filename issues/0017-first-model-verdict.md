---
id: 17
title: First-model verdict
labels: [wayfinder:grilling]
status: open
assignee:
parent: 1
blocked_by: [16]
---

## Question

Follow-up to reviewer concern R3-2 (found PARTIAL by [Re-verify reviewer fixes R3-1..R3-5](0002-re-verify-reviewer-fixes.md)). When a retrain finishes on a task with no active model but a frozen split already exists (e.g. after importing ≥150 Phase 0 labels, zero-shot disabled), what does the verdict compare against? If the majority-class baseline, what margin earns `recommended`; if nothing, is it `unverified`? With zero-shot enabled, does `model_version: base` count as the active model for the comparison? Does `trained` in `/health/ready` mean "a trained model exists" or "a trained model is active"?
