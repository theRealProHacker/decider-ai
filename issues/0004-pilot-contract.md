---
id: 4
title: Pilot ↔ decider-ai contract
labels: [wayfinder:grilling]
status: open
assignee:
parent: 1
blocked_by: []
---

## Question

What exactly crosses the boundary between Pilot and decider-ai? Pin the JSONL record schema (`external_id`, `input.text`, `labels`, `group_id`, `provenance` incl. `label_mode`), how system (a) rules and (b) Gemini predictions ride in the export, how rule-decided mails are marked and excluded, `group_id` (thread) semantics, the label vocabularies for `mail_action` and `urgency`, and whether a deadline-hint label is added (design open question 2). Pilot's internals are out of scope; only the contract.
