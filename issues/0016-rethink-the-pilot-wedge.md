---
id: 16
title: Rethink the Pilot wedge
labels: [wayfinder:grilling]
status: closed
assignee: rharvey
parent: 1
blocked_by: []
---

## Question

Pilot's model call does more than classify: besides the action, it also produces structured fields that a fixed-label decision endpoint cannot return. Switching Pilot to `local` would either drop those fields or keep calling the LLM (text still leaves the server; the privacy headline fails).

Given that, what is decider-ai's wedge and what does it replace in Pilot? Revisit via `/office-hours` (founder chose "Rethink the wedge", 2026-10-08) and update `docs/design.md` (+ canonical copy) with the outcome. Options on the table when this ticket was opened: action-only classifier with deterministic matching; per-request options (candidate targets) in `decide`; local gate + Gemini extraction; a different product shape.

## Resolution

Resolved by `/office-hours` (2026-10-08), design APPROVED in `../docs/design.md`. Pilot is dropped as the case study; the product targets generic fixed-label message routing with no named user yet, so the launch is the demand test. The Phase 0 gate moves to public datasets and is cost-benefit: re-scope only if, on every dataset, an offline LLM baseline is cheaper, faster and better than the fine-tune at 250 labels (95% CI above zero), with one retrain amortised over 30,000 decisions. Full Phase 1 incl. n8n, built in parallel tracks (eval/model and product).
