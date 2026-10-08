---
id: 7
title: Zero-shot policy
labels: [wayfinder:grilling]
status: closed
assignee: rharvey
parent: 1
blocked_by: []
---

## Question

Is zero-shot a per-task setting in `tasks.yaml` (default?), and what threshold decides whether base zero-shot is useful — majority-class baseline is too low a bar (R3-7)? Define the rule and what `/health/ready` and `/v1/decisions` do in each case.

## Notes (2026-10-08)

The approved design commits to a per-task `zero_shot` flag, default `false`. Open: the usefulness threshold that would flip the default. Input from [Laya checkpoint facts](0003-laya-checkpoint-facts.md): the multilingual base scored 0.342 vs a 0.461 majority baseline on its card's typed-decisions benchmark, so zero-shot is likely off.

## Resolution

Founder, 2026-10-08. `zero_shot` stays a per-task flag in `tasks.yaml`, default `false`. The default flips to `true` only if Phase 0 shows base zero-shot (d) macro-F1 ≥ TF-IDF + logistic regression at 50 training labels on every benchmark dataset. The majority baseline is not a bar (≤0.014 macro-F1 on the chosen sets). A user may always opt a task in; `/health/ready` then states that the base model is unmeasured for that task. Laya's card shows zero-shot near chance (0.342 vs 0.461 majority), so the default is expected to stay `false`.
