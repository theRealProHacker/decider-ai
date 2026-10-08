---
id: 3
title: Laya checkpoint facts
labels: [wayfinder:research]
status: open
assignee:
parent: 1
blocked_by: []
---

## Question

Which exact Laya checkpoint does decider-ai use (root vs multilingual), and is it fit for German legal mail? Pin: licence of the exact revision (commercial use OK?), parameter count, full fine-tune vs adapters, CPU fine-tune time per run at ~50/100/250 examples, resident memory per loaded task checkpoint, disk per kept version, max input tokens, and what the existing Laya fine-tuning project's code contributes to `LayaBackend`. Covers design open question 1 and R3-14. Output: a linked markdown summary with sources.

## Sources

- Laya fine-tuning project (founder, 2026-10-08): https://github.com/tehtommeh/laya-finetuning — the training/eval code `LayaBackend` reuses. Start here.
