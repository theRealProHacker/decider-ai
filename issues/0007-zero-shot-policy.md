---
id: 7
title: Zero-shot policy
labels: [wayfinder:grilling]
status: open
assignee:
parent: 1
blocked_by: []
---

## Question

Is zero-shot a per-task setting in `tasks.yaml` (default?), and what threshold decides whether base zero-shot is useful — majority-class baseline is too low a bar (R3-7)? Define the rule and what `/health/ready` and `/v1/decisions` do in each case.

## Notes (2026-10-08)

The approved design commits to a per-task `zero_shot` flag, default `false`. Open: the usefulness threshold that would flip the default. Input from [Laya checkpoint facts](0003-laya-checkpoint-facts.md): the multilingual base scored 0.342 vs a 0.461 majority baseline on its card's typed-decisions benchmark, so zero-shot is likely off.
