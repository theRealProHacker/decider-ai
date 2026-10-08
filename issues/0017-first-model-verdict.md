---
id: 17
title: First-model verdict
labels: [wayfinder:grilling]
status: closed
assignee: rharvey
parent: 1
blocked_by: []
---

## Question

Follow-up to reviewer concern R3-2 (found PARTIAL by [Re-verify reviewer fixes R3-1..R3-5](0002-re-verify-reviewer-fixes.md)). When a retrain finishes on a task with no active model but a frozen split already exists (e.g. after importing ≥150 Phase 0 labels, zero-shot disabled), what does the verdict compare against? If the majority-class baseline, what margin earns `recommended`; if nothing, is it `unverified`? With zero-shot enabled, does `model_version: base` count as the active model for the comparison? Does `trained` in `/health/ready` mean "a trained model exists" or "a trained model is active"?

## Resolution

Delegated by the founder ("keep it as simple as possible, don't overthink, really anything that runs is fine", 2026-10-08); simplest working option chosen from the brief where one exists.
- Keep the design's interim rule as final: with `zero_shot: true`, `base` counts as the active model for the first comparison; with no model active, the first candidate's verdict is `unverified`.
- `/health/ready`: `trained` = a trained model is active; `base` = serving zero-shot; `not_trained` = returns 503.
