---
id: 2
title: Re-verify reviewer fixes R3-1..R3-5
labels: [wayfinder:task]
status: closed
assignee: rharvey
parent: 1
blocked_by: []
---

## Question

Reviewer concerns R3-1..R3-5 (blocking) in `docs/design.md` were fixed after the review but never re-verified. Does an independent reviewer, given only the current design doc and the concern texts, confirm each is resolved? Update the Reviewer Concerns section to record the outcome per concern; reopen any that fail as new tickets on this map.

## Resolution

Independent re-verification against the current `docs/design.md` body. Evidence is quoted under each concern in the Reviewer Concerns section.

- R3-1: RESOLVED. Step 5 sends every blind label to the test set until the gate decision is recorded (branch-3 growth included), and blind labels go to training only after it.
- R3-2: PARTIAL. No candidate activates itself and the 503 ends only on an explicit `activate`. The verdict is still defined as candidate − active, so it is undefined when no active model exists and the split is already frozen.
- R3-3: RESOLVED. The split is a fixed 100, frozen at ≥150 confirmed examples (leaving ≥50 for training). Any confirmed example is test-eligible, and split examples never enter training.
- R3-4: RESOLVED. The release test covers both cold-start modes, the `unverified` candidate with manual activation, and the recommend-only verdict at ≥150 examples.
- R3-5: RESOLVED. The Assignment and Dependencies ask for consent until the gate is decided, with a bound sized after one week to reach 400 rule-unmatched mails. One minor leftover: the "~250" in Open Questions.

### Suggested new tickets

- R3-2 follow-up: when a retrain job finishes and the task has no active model (zero-shot disabled, nothing activated yet) but the frozen split already exists, what does the verdict compare against? If the majority-class baseline, what margin earns `recommended`; if nothing, does the job report `unverified`? When zero-shot is enabled, does `model_version: base` count as the "active" model for the candidate − active bootstrap? Does `/health/ready`'s `trained` mean "a trained candidate exists" or "a trained model is active"?
