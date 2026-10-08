---
id: 10
title: HTTP API contract details
labels: [wayfinder:grilling]
status: closed
assignee: rharvey
parent: 1
blocked_by: []
---

## Question

Pin the HTTP details the design leaves implicit: auth header name and failure codes, error body shape (code, message, details), idempotency of `/v1/feedback` and `/v1/examples:batch`, pagination on `/v1/models`, request size limits beyond per-task input length, versioning policy for `/v1`, and whether an OpenAPI document is published.

## Resolution

Delegated by the founder ("keep it as simple as possible, don't overthink, really anything that runs is fine", 2026-10-08); simplest working option chosen from the brief where one exists.
- Auth: `Authorization: Bearer <key>` on every route except `GET /health/live`; missing/wrong key → 401.
- Errors: plain JSON `{"error": {"code": "...", "message": "...", ...fields}}` with stable codes; FastAPI validation errors mapped to 422 `VALIDATION_FAILED`.
- Field naming: `label` (singular, exactly one value) in decisions, feedback, import and the eval record format; unknown label → 422 `LABEL_NOT_IN_TASK`; unknown task → 404 `TASK_NOT_FOUND`.
- Idempotency: natural keys only (upsert on `external_id`); no Idempotency-Key header.
- Lists return an object (`{"models": [...]}`), no pagination.
- Body size: one env var `DECIDER_MAX_BODY_BYTES`, default 16 MiB → 413 `PAYLOAD_TOO_LARGE`; import is JSONL (`application/x-ndjson`).
- Versioning: only additive changes within `/v1` once 1.0 ships; 0.x may break, noted in the CHANGELOG.
- OpenAPI served at `/openapi.json`; `/docs` and `/redoc` off.
- Activate: `POST /v1/tasks/{task}/models/{version}/activate`, list: `GET /v1/tasks/{task}/models`; the load + smoke prediction + pointer flip runs inside activate; on failure 500 `ACTIVATION_FAILED`, active model unchanged.
- n8n: README documents a shared Docker network (`http://decider-ai:8080`) with a sample `docker-compose.yml`; host publish stays loopback-only.
Brief: `../docs/briefs/0010-http-api-contract.md`.
