---
id: 15
title: Public benchmark datasets
labels: [wayfinder:research]
status: open
assignee:
parent: 1
blocked_by: []
---

## Question

Which 2–3 open-source datasets does decider-ai use as its public benchmark while Pilot data is pending, and how is it scored? Pin for each candidate: exact source and revision, licence (commercial use allowed; non-commercial sets like 10kGNAD are excluded), language (at least one German set), label count and class balance, and how it maps onto a decider-ai task (question + label options; which class plays "ignore"). Candidates to check: MASSIVE `de-DE` (CC-BY-4.0), CLINC150 with out-of-scope (CC-BY-3.0), Banking77 (CC-BY-4.0), a German/English support-ticket set with queue + priority labels (e.g. `Tobi-Bueck/customer-support-tickets`, licence unverified). Define the baselines (majority class, TF-IDF + logistic regression, base zero-shot (d)) and confirm the `evaluation` module and `decider-eval` run on it unchanged (no Gemini system). Whether a set can also serve as release-test data or the tutorial dataset is a secondary note. This benchmark does not replace the Phase 0 Pilot gate. Output: a linked markdown summary with sources.
