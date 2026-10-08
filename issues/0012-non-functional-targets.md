---
id: 12
title: Non-functional targets
labels: [wayfinder:grilling]
status: closed
assignee: rharvey
parent: 1
blocked_by: [3]
---

## Question

What are the release targets the build must meet: CPU decision latency (p50/p95) per task, RAM with N tasks loaded, disk per kept model version and version retention, image size, minimum supported hardware (cores, RAM, x86/arm), and training wall-clock budget?

## Resolution

Delegated by the founder ("keep it as simple as possible, don't overthink, really anything that runs is fine", 2026-10-08); simplest working option chosen from the brief where one exists.
- No hard performance targets for launch: "it runs" on the documented host, and the README reports measured latency and training time.
- Documented host: x86-64 with AVX2, 4+ vCPU, 16 GB RAM (training peak ~8.5 GB). arm64 not supported at launch.
- All tasks load at startup; fp32 serving (the evaluated model is the served model); int8 ruled out (breaks answers), bf16 later if memory bites.
- Training: no time budget; job progress shows epoch/step. Thread cap default half the CPUs.
- Retention: keep every model version (no automatic pruning, consistent with "don't delete yet"); disk use is documented (~678 MB per version).
- Image: CPU-only torch wheel; no size budget.
Brief: `../docs/briefs/0012-non-functional-targets.md` (its latency numbers were measured on a loaded laptop and are pessimistic).
