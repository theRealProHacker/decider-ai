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

- Domain: a self-hosted replacement for the LLM classification call that learns from corrections. No named user yet; the launch is the demand test. Sources: `docs/design.md` (product), `docs/architecture.md` (modules), `DESIGN.md` (visual).
- Skills: `/grilling` and `/domain-modeling` for grilling tickets (resolve terms into `CONTEXT.md` as they settle; ADRs only when hard to reverse, surprising, and a real trade-off). `/prototype` for prototype tickets.
- `docs/design.md` has a canonical copy at `~/.gstack/projects/decider-ai/rharvey-main-design-20261008-040445.md`. Keep both in sync when a resolution edits the design.
- Standing rules: no automatic retrain or activation, ever (decision 83b5e76c). The product never calls an LLM (a standalone eval prep script calls one on public data only). No message text in logs. Deferred under decision 18271c16 (supersedes 6ef66611): web UI, Postgres, a trainer service, GPU, CLI, AGENTS.md, multi-tenancy, ONNX.
- Laya: `LayaBackend` is built fresh on the Apache-2.0 `laya` SDK; https://github.com/tehtommeh/laya-finetuning (no licence) is reference reading only, never copied.
- Founder preference (2026-10-08): "keep it as simple as possible, don't overthink, really anything that runs is fine." Low-stakes details take the simplest working option without grilling; only hard-to-reverse or scope calls go to the founder.
- Planning only. Write no application code on this map.
- The tracker is local markdown. See `docs/agents/issue-tracker.md`.

## Decisions so far

- The n8n node stays in the Phase 1 launch, per `docs/design.md`. Its planning happens outside this map. Reviewer concern R3-13 stays as recorded.
- [Decider interface](../docs/architecture.md) (2026-10-08, design-it-twice round, no ticket): 8 methods with ports and adapters. `confirm` merges feedback and import, `forget` reports facts without deciding a policy, errors are a `code` plus fields, and the `Runner`/`Events` ports have two adapters each.
- [Rethink the Pilot wedge](0016-rethink-the-pilot-wedge.md) — Pilot dropped as the case; generic routing, no named user; gate is cost-benefit on public data (LLM cheaper, faster and better at 250 labels on every dataset ⇒ re-scope); full Phase 1 in parallel tracks. Design approved.
- [laya-finetuning licence](0020-laya-finetuning-licence.md) — build `LayaBackend` fresh from the Apache-2.0 `laya` SDK; laya-finetuning is inspiration only, no code copied.
- [Zero-shot policy](0007-zero-shot-policy.md) — per-task `zero_shot`, default `false`; default flips only if (d) ≥ TF-IDF+LR@50 on every benchmark dataset; opt-in allowed, flagged unmeasured in `/health/ready`.
- [Open-source licence](0011-open-source-licence.md) — Apache-2.0 core, MIT n8n node in its own repo, DCO, weights and datasets downloaded from pinned revisions not bundled ([ADR 0001](../docs/adr/0001-licensing.md)).
- [Data lifecycle and erasure](0009-data-lifecycle-erasure.md) — `decide` stores no text; feedback resends text with a required `external_id`; erasure is a hard delete by `external_id` (secure_delete); split shrinks and stays frozen; versions are never deleted, only flagged with an erased-examples count.
- [Phase 0 report scope](0005-phase-0-report-scope.md) — one LLM baseline (Gemini 3.5 Flash-Lite) run by a standalone prep script on public data only; local CPU-hours priced at Hetzner CX43's rate; nominal CIs; full test sets; `report.json` + `report.md`.
- [Rare-label split fallback](0008-rare-label-split-fallback.md) — per-label minimum `min(10, 100 // labels)`; a label below it keeps the split unfrozen and is named in `/health/ready`.
- [HTTP API contract details](0010-http-api-contract.md) — Bearer auth except `/health/live`; `{"error": {code, message}}`; `label` singular; natural-key idempotency; task in the activate path; 16 MiB body cap; n8n over a shared Docker network.
- [Non-functional targets](0012-non-functional-targets.md) — no hard targets; documented host x86-64/AVX2, 4 vCPU, 16 GB; fp32; all tasks loaded at start; keep every version; x86-64 only.
- [Container image and runtime](0013-container-image-runtime.md) — `python:3.12-slim`, CPU torch, one process, in-process training thread; `/data` volume; base checkpoint downloaded at first start with checksum, pre-download for offline hosts.
- [First-model verdict](0017-first-model-verdict.md) — `base` counts as active with zero-shot on; otherwise the first verdict is `unverified`; `trained` = a trained model is active.
- [Task versioning](0018-task-versioning.md) — none: a changed label set needs a new task name, startup refuses otherwise.
- [Training procedure](0019-training-procedure.md) — `laya.train` pinned; fp32; 12 epochs under 300 examples else 4; no calibration; one checkpoint per task; token check before SDK truncates; random stored seed.
- Fog settled without tickets (simplest that runs): SQLite schema is an implementation detail of the build slices; CI is GitHub Actions (pytest on `FakeBackend` per push, DCO check, image build and push to GHCR on tag); no synthetic dataset, the README and tutorial use the public MASSIVE `de-DE` set; docs are the README only.
- [Re-verify reviewer fixes R3-1..R3-5](0002-re-verify-reviewer-fixes.md) — R3-1, R3-3, R3-4, R3-5 resolved; R3-2 partial (no comparison target for a first model), carried by First-model verdict.
- [Public benchmark datasets](0015-public-benchmark-datasets.md) — MASSIVE 1.1 `de-DE` (scenario level, CC BY 4.0) + CLINC150 `oos_plus` (domain level, CC BY 3.0); Banking77 optional; Tobi-Bueck rejected (NC). Baselines: majority, TF-IDF+LR, zero-shot (d), fine-tune (c) at 50/100/250 × 5 seeds. `decider-eval` must accept any named optional prediction systems.
- [Laya checkpoint facts](0003-laya-checkpoint-facts.md) — `convaiinnovations/laya-multilingual` @ `1720e3e`, Apache-2.0, 321.9M params, full fine-tune, ~678 MB per version, 1,024-token input; CPU fp32 fine-tune 11.8 min at 50 examples (measured), ~1 h at 250; ~1.6–1.8 GB RAM per loaded checkpoint, 8.5 GB training peak; zero-shot likely below majority.

## Not yet specified

(none — the remaining fog was settled directly under the founder's "simplest that runs" preference; see the last Decisions entry)

## Out of scope

- Pilot: dropped from the launch by [Rethink the Pilot wedge](0016-rethink-the-pilot-wedge.md). Ruled out with it: [Pilot ↔ decider-ai contract](0004-pilot-contract.md) and [Combined gate outcome](0006-combined-gate-outcome.md).
- The n8n community node. It is in the launch but planned separately (founder, 2026-10-08).
- Writing the SEO tutorial and blog posts.
- The SaaS and §203 hosting question (decided after launch signals).
- Everything deferred under decision 18271c16 (supersedes 6ef66611).
