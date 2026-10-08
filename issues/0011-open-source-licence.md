---
id: 11
title: Open-source licence
labels: [wayfinder:grilling]
status: closed
assignee: rharvey
parent: 1
blocked_by: []
---

## Question

Which licence does decider-ai ship under (Apache-2.0, MIT, AGPL-3.0, other), given the later SaaS + consulting business and the Laya checkpoint licence? Hard to reverse — likely an ADR.

## Resolution

Founder, 2026-10-08 ([ADR 0001](../docs/adr/0001-licensing.md), brief `../docs/briefs/0011-open-source-licence.md`):
- Container and core: Apache-2.0.
- n8n community node: MIT, in its own repository.
- Contributions: DCO, checked in CI.
- Model weights and datasets: not bundled; downloaded at first start (weights) or by the eval script (datasets) from pinned revisions, attributed in the docs. This reverses "the image bundles the base checkpoint"; the offline install path goes to [Container image and runtime](0013-container-image-runtime.md).
