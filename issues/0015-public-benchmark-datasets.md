---
id: 15
title: Public benchmark datasets
labels: [wayfinder:research]
status: closed
assignee: rharvey
parent: 1
blocked_by: []
---

## Question

Which 2–3 open-source datasets does decider-ai use as its public benchmark while Pilot data is pending, and how is it scored? Pin for each candidate: exact source and revision, licence (commercial use allowed; non-commercial sets like 10kGNAD are excluded), language (at least one German set), label count and class balance, and how it maps onto a decider-ai task (question + label options; which class plays "ignore"). Candidates to check: MASSIVE `de-DE` (CC-BY-4.0), CLINC150 with out-of-scope (CC-BY-3.0), Banking77 (CC-BY-4.0), a German/English support-ticket set with queue + priority labels (e.g. `Tobi-Bueck/customer-support-tickets`, licence unverified). Define the baselines (majority class, TF-IDF + logistic regression, base zero-shot (d)) and confirm the `evaluation` module and `decider-eval` run on it unchanged (no Gemini system). Whether a set can also serve as release-test data or the tutorial dataset is a secondary note. This benchmark does not replace the Phase 0 Pilot gate. Output: a linked markdown summary with sources.

## Resolution

Full answer with sources: [Public benchmark datasets](../docs/research/public-benchmark-datasets.md).

- **Core benchmark:** MASSIVE 1.1 `de-DE` at scenario level (German, CC BY 4.0, 18 labels, `general` plays "ignore"). Also CLINC150 `oos_plus` at domain level (English, CC BY 3.0, 10 domains + `out_of_scope`, which plays "ignore"). Banking77 (CC BY 4.0, 77 labels, no ignore class) is optional, and runs only if Laya fits 77 options in one input. All three are pinned to upstream commits, with file sha256s.
- **Rejected:** `Tobi-Bueck/customer-support-tickets` is CC BY-NC 4.0 at every revision, and synthetic. GermEval 2017 is the best German fit (relevance as ignore, sentiment as a second label), but its sources conflict: CC BY on the organisers' page, CC BY-NC 4.0 on the lab's own HF card. 10kGNAD is NC.
- **No commercially usable public set has an urgency-like ordinal label**, so the public benchmark cannot exercise `urgency_gate`.
- **Baselines:** majority class; TF-IDF (word 1–2 + char 2–5) + logistic regression, which stands in for (b); (d) base zero-shot; and (c) fine-tuned at 50/100/250 examples × 5 seeds. Reference TF-IDF + LR macro-F1 at 250 examples: 0.64 on MASSIVE, 0.59 on CLINC.
- **Running without rules (a) and Gemini (b):** a data-prep step converts each set to the record format with baselines as named prediction columns. Set `group_id = external_id`. The official test partition is the blind set (`label_mode: blind`), with no re-split. `evaluation.compare` runs unchanged; `action_gate` and `urgency_gate` are not called. `decider-eval` needs its external systems to be generic and optional (a refinement to `docs/architecture.md`).
- **Release-test fixture:** a MASSIVE `de-DE` subset. The tutorial keeps the synthetic German dataset; public-set numbers can appear only as an appendix.
- **This benchmark does not replace the Phase 0 Pilot gate.**
