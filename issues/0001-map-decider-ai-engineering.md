---
id: 1
title: "Map: decider-ai engineering plan"
labels: [wayfinder:map]
status: open
assignee:
parent:
blocked_by: []
---

## Destination

A build-ready spec for Phase 0 (`decider-eval`) and Phase 1 (the single-container endpoint) in full: `docs/design.md` and `docs/architecture.md` have no open questions left, the hard-to-reverse choices are ADRs in `docs/adr/`, a `CONTEXT.md` glossary exists, and `docs/build-plan.md` has ordered vertical slices with acceptance tests.

## Notes

- Domain: a private decision endpoint that learns from corrections. Pilot is customer #1. Sources: `docs/design.md` (product), `docs/architecture.md` (modules), `DESIGN.md` (visual).
- Skills: `/grilling` and `/domain-modeling` for grilling tickets (resolve terms into `CONTEXT.md` as they settle; ADRs only when hard to reverse, surprising, and a real trade-off). `/prototype` for prototype tickets.
- `docs/design.md` has a canonical copy at `~/.gstack/projects/decider-ai/rharvey-unknown-design-20261008-015741.md`. Keep both in sync when a resolution edits the design.
- Standing rules: no automatic retrain or activation, ever (decision 83b5e76c). decider-ai never calls Gemini. No message text in logs. Deferred under decision 6ef66611: web UI, Postgres, a trainer service, GPU, CLI, AGENTS.md, multi-tenancy, ONNX.
- Laya fine-tuning project: https://github.com/tehtommeh/laya-finetuning (reused by `LayaBackend`).
- Planning only. Write no application code on this map.
- The tracker is local markdown. See `docs/agents/issue-tracker.md`.

## Decisions so far

- The n8n node stays in the Phase 1 launch, per `docs/design.md`. Its planning happens outside this map. Reviewer concern R3-13 stays as recorded.
- [Decider interface](../docs/architecture.md) (2026-10-08, design-it-twice round, no ticket): 8 methods with ports and adapters. `confirm` merges feedback and import, `forget` reports facts without deciding a policy, errors are a `code` plus fields, and the `Runner`/`Events` ports have two adapters each.
- [Re-verify reviewer fixes R3-1..R3-5](0002-re-verify-reviewer-fixes.md) — R3-1, R3-3, R3-4, R3-5 resolved; R3-2 partial (no comparison target for a first model), carried by First-model verdict.

## Not yet specified

- Training procedure: hyperparameters, epochs, seeds, checkpoint format, how 5-seed eval runs are scheduled on CPU. Graduates after [Laya checkpoint facts](0003-laya-checkpoint-facts.md).
- SQLite schema, migrations, and how the store upgrades across releases. Graduates after [Data lifecycle and erasure](0009-data-lifecycle-erasure.md) and [HTTP API contract details](0010-http-api-contract.md).
- CI and the GHCR release pipeline: tag scheme, image signing, what CI tests run (FakeBackend vs a real Laya smoke test).
- How the synthetic German example dataset in the repo is generated and licensed.
- The docs site build: README vs a site, use of DESIGN.md and the Libron fonts.

## Out of scope

- Pilot internals: the confirmation queue UI, `label_mode` storage, the labelling view, the `DecisionClient` seam. That is Pilot's own effort. Only the contract is on this map.
- The n8n community node. It is in the launch but planned separately (founder, 2026-10-08).
- Writing the SEO tutorial and blog posts.
- The SaaS and §203 hosting question (decided after launch signals).
- Everything deferred under decision 6ef66611.
