---
id: 10
title: HTTP API contract details
labels: [wayfinder:grilling]
status: open
assignee:
parent: 1
blocked_by: []
---

## Question

Pin the HTTP details the design leaves implicit: auth header name and failure codes, error body shape (code, message, details), idempotency of `/v1/feedback` and `/v1/examples:batch`, pagination on `/v1/models`, request size limits beyond per-task input length, versioning policy for `/v1`, and whether an OpenAPI document is published.
