---
id: 13
title: Container image and runtime
labels: [wayfinder:grilling]
status: closed
assignee: rharvey
parent: 1
blocked_by: [3, 12]
---

## Question

How is the single container built and run: base image, CPU-only PyTorch, whether the base checkpoint is bundled or fetched, Python dependency tooling, volume layout (`tasks.yaml`, SQLite, checkpoints, API key), process model (uvicorn workers vs one process given the in-process job runner), and arm64 support?

## Notes (2026-10-08)

From [Open-source licence](0011-open-source-licence.md): the image does not bundle the base checkpoint; it is downloaded at first start from a pinned revision. Decide the download mechanism, checksum check, behaviour when offline, and a pre-download path for air-gapped hosts.

## Resolution

Delegated by the founder ("keep it as simple as possible, don't overthink, really anything that runs is fine", 2026-10-08); simplest working option chosen from the brief where one exists.
- Base image `python:3.12-slim`; dependencies pinned in a lock file, CPU-only torch index.
- One process, one uvicorn worker; retrain runs in the in-process background thread as designed (switch to a subprocess only if memory is not released after training).
- Volume `/data`: `tasks.yaml`, `decider.db`, `models/`, `hf-cache/` (base checkpoint), `api_key`.
- Base checkpoint: downloaded on first start into `/data/hf-cache` from the pinned revision with checksum check; if offline and missing, the container exits with a clear message. Air-gapped hosts pre-populate the volume (documented `huggingface-cli download` command).
- x86-64 image only.
