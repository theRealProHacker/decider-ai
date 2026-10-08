---
id: 19
title: Training procedure
labels: [wayfinder:grilling]
status: open
assignee:
parent: 1
blocked_by: []
---

## Question

How does `LayaBackend` train, given [Laya checkpoint facts](0003-laya-checkpoint-facts.md)? Pin the CPU recipe (fp32 since bf16 fails on AVX2; epochs, e.g. FINETUNING.md's 12 below ~300 examples; thread count), whether a calibration slice is carved from confirmed examples and how it interacts with the frozen split and the 50-example minimum, one checkpoint per task vs several tasks in one checkpoint (memory ~1.6–1.8 GB per loaded checkpoint, ~678 MB disk per version), the token-based input limit checked before the SDK silently truncates, and whether ~1 h per 250-example run and 8.5 GB training peak are acceptable.
