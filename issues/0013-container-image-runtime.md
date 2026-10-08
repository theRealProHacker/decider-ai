---
id: 13
title: Container image and runtime
labels: [wayfinder:grilling]
status: open
assignee:
parent: 1
blocked_by: [3, 12, 16]
---

## Question

How is the single container built and run: base image, CPU-only PyTorch, whether the base checkpoint is bundled or fetched, Python dependency tooling, volume layout (`tasks.yaml`, SQLite, checkpoints, API key), process model (uvicorn workers vs one process given the in-process job runner), and arm64 support?
