---
id: 19
title: Training procedure
labels: [wayfinder:grilling]
status: closed
assignee: rharvey
parent: 1
blocked_by: []
---

## Question

How does `LayaBackend` train, given [Laya checkpoint facts](0003-laya-checkpoint-facts.md)? Pin the CPU recipe (fp32 since bf16 fails on AVX2; epochs, e.g. FINETUNING.md's 12 below ~300 examples; thread count), whether a calibration slice is carved from confirmed examples and how it interacts with the frozen split and the 50-example minimum, one checkpoint per task vs several tasks in one checkpoint (memory ~1.6–1.8 GB per loaded checkpoint, ~678 MB disk per version), the token-based input limit checked before the SDK silently truncates, and whether ~1 h per 250-example run and 8.5 GB training peak are acceptable.

## Resolution

Delegated by the founder ("keep it as simple as possible, don't overthink, really anything that runs is fine", 2026-10-08); simplest working option chosen from the brief where one exists.
- Train with the Apache-2.0 `laya` SDK's `laya.train` at a pinned version (≥0.4.0); fp32, gradient checkpointing on, thread cap = half the CPUs.
- Epochs: 12 below 300 training examples, else 4; SDK default learning rates; no pilot grid.
- No calibration at launch: scores are uncalibrated and the docs say so; no calibration slice, so the 50-example minimum and frozen split are untouched.
- One checkpoint per task.
- Token limit: check with the SDK's tokenizer before predicting and on import; over-long input → 413 `INPUT_TOO_LONG`, never truncated.
- Seeds: Phase 0 uses 0–4; product retrains use a random seed stored on the version.
- Checkpoints in the SDK's layout; every version kept.
Brief: `../docs/briefs/0019-training-procedure.md`.
