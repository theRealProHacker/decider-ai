# Brief: HTTP API contract details (ticket 0010)

Prepared 2026-10-08 for a live grilling session. This brief decides nothing. It collects facts, lists the decisions in the order to ask them, and gives a recommendation for each. Inputs: `issues/0010-http-api-contract.md`, `issues/0001-map-decider-ai-engineering.md`, `docs/design.md` (API, Network and auth, R2-9..R2-12), `docs/architecture.md` (Decider interface, `DeciderError.code`, HTTP adapter). No settled API decisions exist in `~/.gstack/projects/decider-ai/` (only decision 18271c16, which does not touch the API).

## 1. Facts

### What the repo already commits to

- Every `Decider` error is a `DeciderError` with a stable `code` and structured fields. The HTTP adapter owns the body shape and maps `InputTooLong`→413, `NotTrained`→503, `Busy`→409, `TooFewExamples`→422, `NotFound`→404 (`docs/architecture.md`, HTTP adapter).
- Codes already named in the design: `INPUT_TOO_LONG` (413), `MODEL_NOT_TRAINED` (503), `REQUEST_EXPIRED` (410). Unknown request on feedback is 404 (`docs/design.md`, API).
- `confirm` is the single path for feedback and import. It returns one `Outcome(index, kind: added | updated | rejected, reason)` per item and never raises per item. Its idempotency is "upsert on `external_id`" (`docs/architecture.md`).
- `Decider.activate(task, version)` takes a task. The HTTP route `POST /v1/models/{version}/activate` does not (`docs/design.md`).
- The API key comes from `DECIDER_API_KEY`, or is generated on first start, printed once and stored on the volume. The docs publish the port only on host loopback (`-p 127.0.0.1:8080:8080`) (`docs/design.md`, Network and auth).
- Laya's input limit is 1,024 tokens (map, Laya checkpoint facts). Each kept model version is about 678 MB.

### Error bodies

- RFC 9457 (July 2023, Standards Track) obsoletes RFC 7807. Media type `application/problem+json`. Members: `type` (URI, defaults to `about:blank`), `title`, `status`, `detail`, `instance`. Problem types may add extension members, and clients "MUST ignore any such extensions that they don't recognize". For validation it shows a 422 with an `errors` array of `{detail, pointer}` (JSON Pointer). For several unrelated problems it recommends returning the most urgent one, and notes that batch problem types "do not map well into HTTP semantics". [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html)
- FastAPI's defaults: `HTTPException` renders `{"detail": ...}`. Request validation fails with 422 and `{"detail": [{loc, msg, type}, ...]}`. Any other shape needs custom handlers for `StarletteHTTPException` and `RequestValidationError`. [FastAPI, Handling errors](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- Hugging Face TEI: `{"error": "...", "error_type": "..."}`, with `error_type` mapped to status (validation and tokenizer 422, empty batch 400, overloaded 429, backend 424, unhealthy 503). [TEI server.rs](https://github.com/huggingface/text-embeddings-inference/blob/main/router/src/http/server.rs)
- Ollama: `{"error": "message"}` with 400/404/429/500/502. [Ollama API errors](https://docs.ollama.com/api/errors)
- OpenAI-compatible servers (vLLM, LocalAI, llama-cpp-python) use `{"error": {"message", "type", "param", "code"}}`. Verified in llama-cpp-python's `ErrorResponse` and LocalAI's docs. vLLM builds errors through `create_error_response(message, type, status)`, but I did not verify its exact fields. [vLLM serving API](https://docs.vllm.ai/en/v0.23.0/api/vllm/entrypoints/openai/engine/serving/), [llama-cpp-python errors.py](https://huggingface.co/MebinThattil/tiny-llama-q4_0/blob/main/llama_cpp/server/errors.py)

### Auth

- TEI: `--api-key` / `API_KEY`. Requests must send `Authorization: Bearer <key>`, or they get 401. `/health`, `/`, `/ping`, `/metrics` and the Swagger docs are merged outside the auth layer, so they are open. [TEI CLI arguments](https://huggingface.co/docs/text-embeddings-inference/cli_arguments), [TEI server.rs](https://github.com/huggingface/text-embeddings-inference/blob/main/router/src/http/server.rs)
- vLLM: `--api-key` / `VLLM_API_KEY`. It "only authenticates requests to endpoints under the `/v1`, `/v2`, and `/inference` path prefixes". The docs warn that `/invocations` serves inference without auth and advise against relying on the key alone. This is the failure mode of a prefix allowlist. [vLLM OpenAI-compatible server](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/)
- Qdrant accepts both an `api-key` header and `Authorization: Bearer`. [Qdrant security](https://qdrant.tech/documentation/security/)
- Ollama has no API auth. [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md)
- FastAPI's `HTTPBearer` and `APIKeyHeader` return 401 with a `WWW-Authenticate` header when credentials are missing (since 0.122.0; earlier versions returned 403). [FastAPI security reference](https://fastapi.tiangolo.com/reference/security/), [FastAPI 403 → 401](https://fastapi.tiangolo.com/how-to/authentication-error-status-code/)
- n8n's HTTP Request node ships generic "Bearer Auth" (the `Authorization` header) and "Header Auth" (any header name) credentials. A community node credential injects headers through `authenticate: {type: 'generic', properties: {header: {...}}}`, so either scheme is one line in the node. [n8n HTTP Request credentials](https://docs.n8n.io/integrations/builtin/credentials/httprequest/), [n8n credentials files](https://docs.n8n.io/integrations/creating-nodes/build/reference/credentials-files/)

### Idempotency

- IETF `Idempotency-Key` header: `draft-ietf-httpapi-idempotency-key-header-07`, last revised 2025-10-15. The datatracker marks it expired ("no longer active"). Its rules: a missing required key returns 400, a key reused with a different payload returns 422, a retry while the original is in flight returns 409, and a server publishes its key-expiry policy. [Datatracker](https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/), [draft -07](https://www.ietf.org/archive/id/draft-ietf-httpapi-idempotency-key-header-07.html)
- Stripe stores the status and body of the first response for each key, including 500s, and replays them. Keys are up to 255 characters and can be pruned after 24 h. A key reused with different parameters is an error. Validation failures and concurrency conflicts are not stored. GET and DELETE ignore keys. [Stripe idempotent requests](https://docs.stripe.com/api/idempotent_requests)

### Pagination, versioning and path style

- Google AIP-158: `page_size`, `page_token`, `next_page_token`. Adding pagination to an existing list method is a breaking change, so it should be included from the start. [AIP-158](https://google.aip.dev/158)
- AIP-185: the major version goes in the path (`/v1`). Minor and patch versions are never exposed, and the major version is updated in place with backward-compatible changes. [AIP-185](https://google.aip.dev/185)
- AIP-136: custom methods use `:verb` on a resource or collection with POST. `POST /v1/examples:batch` follows this style. [AIP-136](https://google.aip.dev/136)

### OpenAPI

- FastAPI generates OpenAPI 3.1.0 and serves `/openapi.json`, `/docs` (Swagger UI) and `/redoc` by default. Setting `openapi_url`, `docs_url` or `redoc_url` to `None` disables them. These routes are not covered by the app's auth dependencies. [FastAPI, Extending OpenAPI](https://fastapi.tiangolo.com/how-to/extending-openapi/)
- From general FastAPI knowledge, not verified this session: the default `/docs` and `/redoc` pages load their JS and CSS from cdn.jsdelivr.net in the viewer's browser.

### Request size

- Starlette and FastAPI have no default request-body limit. Maintainers point to middleware. Uvicorn has no body-size flag. A limit has to count bytes as they arrive, not just trust `Content-Length`. [Starlette issue #2155](https://github.com/encode/starlette/issues/2155), [Starlette discussion #1516](https://github.com/encode/starlette/discussions/1516)
- TEI's comparable defaults: `--payload-limit` 2,000,000 bytes, and `--max-client-batch-size` 32 inputs (an oversized batch returns 413). [TEI CLI arguments](https://huggingface.co/docs/text-embeddings-inference/cli_arguments)

### Docker networking for n8n

- Containers on the same user-defined bridge network resolve each other by name and reach all ports without `-p`. The default bridge has no name resolution. [Docker bridge driver](https://docs.docker.com/engine/network/drivers/bridge/), [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/)
- With `-p 127.0.0.1:...`, "only the Docker host can access the published container port". Docker releases before 28.0.0 may expose it to the same L2 segment. Without an address, Docker publishes on all interfaces, which the docs call "insecure by default". [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/)
- Docker's published-port rules bypass ufw ("Docker and ufw ... are incompatible"). So publishing on `0.0.0.0` so that n8n can reach the service exposes it beyond what ufw shows. [Docker packet filtering](https://docs.docker.com/engine/network/packet-filtering-firewalls/)
- n8n's own docs (for Ollama): when both run in containers, put them on the same network and use the container name as the host. When only n8n is in Docker, use `host.docker.internal`, which on Linux needs `--add-host host.docker.internal:host-gateway`, and bind the service to `0.0.0.0` on the host. [n8n Ollama common issues](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.lmollama/common-issues/)
- Inference, not verified by test: `host-gateway` resolves to the bridge gateway address, not 127.0.0.1. So the documented loopback publish is unreachable from an n8n container even with `host.docker.internal`. A shared network is the only setup that keeps the loopback-only publish.

## 2. Decisions, in the order to ask

The order is chosen so that each answer feeds the next: auth sets the 401 shape, the error shape is needed by every later rule, and the field and 422 rules fix what idempotency deduplicates.

### D1. Auth header, and which endpoints are open

Failure codes: missing or wrong key gives 401 with `WWW-Authenticate: Bearer`. A single key has no scopes, so 403 is never used. Compare keys in constant time (`hmac.compare_digest`).

| Option | Pros | Cons |
|---|---|---|
| A. `Authorization: Bearer <key>` only | Same as TEI, vLLM and OpenAI clients. n8n has a built-in Bearer credential. FastAPI `HTTPBearer` returns the right 401 out of the box. | Can clash with a reverse proxy that uses `Authorization` for its own auth (rare for this audience). |
| B. `X-API-Key: <key>` only | Never clashes with proxy auth. Obvious in curl examples. | Not standard. Generic OpenAI or TEI tooling will not send it. |
| C. Accept both (like Qdrant) | Any client works. | Two code paths, two things to document and test. Little gain before a named user exists. |

Which endpoints are open:

- (i) `/health/live` only.
- (ii) `/health/live` and `/health/ready`.
- (iii) Everything protected, including `/openapi.json`.

`/health/ready` exposes per-task state, active versions, input limits and blocking label names. Label names describe a user's queues.

**Recommendation: A, with (i), plus `/openapi.json` open if D8 serves it.** Bearer is what this class of server uses, and the n8n credential is built in. Protect by default and allow named exceptions only: never a prefix allowlist, which is how vLLM left `/invocations` open. A Docker `HEALTHCHECK` only needs `/health/live`. Readiness detail is integration data, and a caller that has the key can read it.

### D2. Error body shape

| Option | Pros | Cons |
|---|---|---|
| A. RFC 9457 `application/problem+json`: `type` (docs URL per code, or `about:blank`), `title`, `status`, `detail`, plus extension members `code` (stable, SCREAMING_SNAKE) and the error's fields flat (`limit`, `job_id`, `blocking_labels`, …). Validation errors add `errors: [{pointer, detail}]`. | An IETF standard. `DeciderError(code, fields)` maps onto it with no wrapper. Unknown members must be ignored, so new fields are safe. One shape for 401, 404, 413, 422, 503. | Needs custom FastAPI handlers for validation, HTTP and auth errors. Some clients branch on `application/json` only. Check that the n8n node parses `problem+json` (verify in the node's slice). |
| B. Envelope `{"error": {"code", "message", "details"}}` (the ticket's wording, close to OpenAI's) | Familiar to anyone who has called an LLM API. Plain `application/json`. | Not a standard, and `details` becomes a free-form bag. Still needs the same custom handlers. |
| C. FastAPI default `{"detail": ...}`, plus a `code` | Least code. | Two shapes (a validation list and a string or object). Clients must branch on the shape. |

**Recommendation: A.** The architecture already models errors as `code` plus structured fields, and RFC 9457 is that shape as a standard. Whichever option is chosen, keep `code` as the field clients branch on, and list every code in one table in the docs (see D3 for the per-item rule).

### D3. `labels` vs `label`, and the 422 rules (R2-9, R2-4)

Naming:

| Option | Pros | Cons |
|---|---|---|
| A. Rename to `label: "<one>"` in feedback, the import JSONL and the `decider-eval` record format | Matches Phase 1 (single-label). Removes a whole error class (list length ≠ 1). Free to change before launch. | Multi-label later needs a new field (`labels`), which is additive within `/v1`. |
| B. Keep `labels: ["<one>"]`, and return 422 when the length ≠ 1 | Forward-compatible wire format if multi-label comes. | Every client wraps one value in a list. A permanent 422 trap for a feature that does not exist. |
| C. Accept either, normalise internally | Lenient. | Two spellings in docs, the OpenAPI document and the n8n node. |

422 rules to fix along with the name (codes are suggestions):
- A label not in the task's current set → 422 `LABEL_NOT_IN_TASK`, with the allowed labels in the body. This also covers a label that left the set after a task-version change (R2-4, shared with ticket 0018).
- Unknown task → 404 `TASK_NOT_FOUND` (not a 422).
- A missing or blank field, or the wrong type → 422 `VALIDATION_FAILED` with `errors[]`.
- `TooFewExamples` → 422 `TOO_FEW_EXAMPLES` with `have` and `need` (the architecture already maps this to 422).

A contradiction to settle here: `confirm` never raises per item, but the design gives single feedback 404 (unknown request) and 410 (`REQUEST_EXPIRED`). Two options:
- (a) `POST /v1/feedback` takes one item and maps a `rejected` outcome to the HTTP status (404, 410 or 422 with a `problem` body). `POST /v1/examples:batch` returns 200 with one outcome per line, and each rejected outcome carries the same `code` it would have as a single error.
- (b) Both return 200 with outcomes.

**Recommendation: A for naming, plus (a).** Single-label is the Phase 1 rule, so the wire format should say so. A single feedback call that silently returns 200 on a rejection is a bug for n8n users. Per-item outcomes in a batch follow RFC 9457's own advice that batch problems do not map well onto one status.

### D4. Idempotency of `/v1/feedback` and `/v1/examples:batch`

| Option | Pros | Cons |
|---|---|---|
| A. Natural keys. Feedback upserts on `request_id`: one confirmed example per request, so a retry returns `added` then `updated`. Import upserts on `external_id`, which import requires. | Uses the existing `added | updated` outcomes and `external_id` upsert. No response cache. A retry is safe by construction. | A batch without `external_id`s cannot be imported. Re-sending feedback with a different label overwrites the first, so "last write wins" must be documented. |
| B. Natural keys for feedback, and import without `external_id` allowed (not idempotent, document "do not retry blindly") | Lowest friction for one-off imports. | A retried import duplicates examples, which can skew the split and training. |
| C. `Idempotency-Key` header (Stripe or IETF draft), storing responses for 24 h | A general mechanism, and it also covers `retrain`. | A response-cache table, request fingerprinting and in-flight 409s. Built on a draft that has expired. The natural keys already exist. |
| D. A + C | Belt and braces. | All of C's cost for little extra gain. |

**Recommendation: A.** The data model already has the keys. Requiring `external_id` on import also gives every imported record an erasure handle (relevant to ticket 0009 and R2-1). `retrain` stays non-idempotent and is protected by `409 Busy` with the running `job_id`.

### D5. Pagination on `GET /v1/models`

| Option | Pros | Cons |
|---|---|---|
| A. No pagination, bare JSON array | Simplest. | Adding pagination or metadata later is breaking (AIP-158), because the top-level type changes. |
| B. No pagination, object envelope `{"models": [...]}` | The list stays small in practice: each version is about 678 MB, so disk caps the count. A `next_page_token` can be added later without a breaking change. | One extra key for clients. |
| C. Cursor pagination now (`page_size`, `page_token`, `next_page_token`) | Future-proof. | Code and tests for a list that holds a handful of rows. |
| D. `limit`/`offset` | Familiar. | Same cost as C, and unstable when versions are added. |

**Recommendation: B.** It costs nothing and keeps C open. Use the same envelope rule for every list response (outcomes in import, versions in DELETE).

### D6. Request size limits beyond per-task input length

The per-task limit is in tokens (413 `INPUT_TOO_LONG`). A separate body-byte cap is needed because the stack has none (see Facts).

| Option | Pros | Cons |
|---|---|---|
| A. One global body cap for all routes (e.g. 2 MB, as TEI does) | One number. | Either too tight for JSONL imports or far too loose for `/v1/decisions`. |
| B. Per-route caps, configurable by env var: JSON routes about 1 MiB; `/v1/examples:batch` larger (e.g. 16 MiB) plus a maximum line count; 413 `PAYLOAD_TOO_LARGE` (a code distinct from `INPUT_TOO_LONG`), enforced on streamed bytes | Tight where traffic is hot, roomy for import. The two 413 causes stay distinguishable. | Two or three settings to document. Import above the cap means splitting the file. |
| C. No app cap, document a reverse-proxy limit | No code. | The default `docker run` path has no proxy, so a single request can exhaust memory. |

Reference sizes: 1,024 tokens is a few KB of text. MASSIVE `de-DE` and CLINC150 are each around 10–15k short utterances, about 1–2 MB as JSONL (estimate).

**Recommendation: B.** The numbers are the founder's call. The suggested defaults (1 MiB, 16 MiB, 50,000 lines) fit both benchmark datasets in one import. Also settle the import content type here: `application/x-ndjson` or `application/jsonl`, versus a JSON array. JSONL is what the design says, and it affects the OpenAPI document and the n8n node.

### D7. `/v1` versioning policy

| Option | Pros | Cons |
|---|---|---|
| A. Additive-only within `/v1` (new endpoints, optional fields, new response fields, new error `code`s). Clients must ignore unknown fields and fall back on the status for unknown codes. A breaking change ships as `/v2`, served alongside `/v1` for at least one minor release. The API major version is tied to the image's semver major. | A clear promise. Matches AIP-185 and RFC 9457's "ignore unknown members". | Running two versions side by side, once. |
| B. `/v1` is frozen only from 1.0.0. Before that, 0.x image tags may break `/v1`, with changes noted in the CHANGELOG. | Freedom while the product finds users (the launch is the demand test). | Early adopters, including the n8n node, may break between tags. |
| C. No path version, the image tag is the contract | Simplest. | The design already uses `/v1`. Removing it is churn, and there is no way to run two versions. |

**Recommendation: A, with B's escape hatch stated for 0.x tags.** Docs pin image versions (no `latest`), so a user upgrades on purpose. A written additive-only rule also decides in advance whether a new error code is a breaking change (it is not).

### D8. OpenAPI publication

| Option | Pros | Cons |
|---|---|---|
| A. FastAPI defaults: `/openapi.json`, `/docs` and `/redoc` served, open | Zero work. Interactive try-it in the browser. | Docs pages pull assets from a CDN (unverified, see Facts). The schema is open while everything else needs the key. |
| B. Serve `/openapi.json` only (open). Disable `/docs` and `/redoc`. | Machine-readable at runtime, and no CDN dependency. | No built-in try-it UI. |
| C. Generated `openapi.json` committed to the repo, checked in CI (fails on unreviewed diffs), and published on the docs site. Nothing served at runtime. | A reviewable contract with breaking-change detection (backs D7). Feeds the n8n node and the docs. | No runtime discovery. |
| D. B + C | Contract in the repo, plus discovery at runtime. | Two outputs to keep identical (both are generated, so cheap). |

**Recommendation: D.** The committed file is what enforces D7's additive-only rule in CI. A runtime `/openapi.json` costs nothing and helps n8n and generic clients. Leave the HTML docs off by default.

### D9. Activate path, including the task (R2-10)

| Option | Pros | Cons |
|---|---|---|
| A. Task in the path: `GET /v1/tasks/{task}/models`, `POST /v1/tasks/{task}/models/{version}/activate` | Matches `Decider.activate(task, version)`. Makes the "wrong task version" check (ticket 0018) a lookup inside one task. Version IDs can stay short (`v3`). | Mixed style: `decisions` and `retrain` take `task` in the body. |
| B. Keep `/v1/models/{version}/activate`, with globally unique version IDs (e.g. `triage-7` or a ULID) | No route change. | The ID format becomes part of the contract. The task check moves into a lookup. |
| C. Keep the path, with `{task}` in the body | Small change. | A POST with an ID in both path and body, which is easy to get wrong. |
| D. A, using AIP-136 style: `POST /v1/tasks/{task}/models/{version}:activate` | Consistent with `examples:batch`. | The colon style becomes the house rule, and the docs must say so. |

R2-10 also asks for two things to settle here: the swap (load, smoke prediction, flip, release) runs inside `activate`, and what a failed smoke prediction returns. Suggestion: 500 `ACTIVATION_FAILED`, with the active model unchanged and stated in the body. A version from another task version returns 409 `TASK_VERSION_MISMATCH` (owned by 0018). The warning for `unverified` or `not_recommended` goes in a `warning` field of the 200 body, not in a header.

**Recommendation: A.** The task is already the unit of models, splits and versions, and the path should say so. Pick D only if the founder wants the colon style everywhere.

### D10. n8n networking docs (R2-12)

| Option | Pros | Cons |
|---|---|---|
| A. Document a shared user-defined network: `docker network create decider`, run both containers on it, and n8n calls `http://decider-ai:8080`. Keep `-p 127.0.0.1:8080:8080` for host access. | Keeps the loopback-only publish. No firewall surprises. This is what n8n's own docs recommend for container-to-container. | Users who already run n8n must attach it to the network (`docker network connect`). |
| B. Ship a `docker-compose.yml` example with n8n and decider-ai on one network | Copy-paste setup that is tested in CI. | One more file to maintain, and it pins an n8n image version. |
| C. Publish on a host or LAN IP or `0.0.0.0`, and use `host.docker.internal` with `--add-host ...:host-gateway` | Works with any existing n8n container. | Exposes the API beyond the host, and Docker bypasses ufw. It contradicts the loopback rule. |
| D. Host networking (`--network host`) for both | Simple on Linux. | Linux-only behaviour, no isolation, and n8n is rarely run that way. |

**Recommendation: A + B.** A is the rule, and B is the tested example of it. Mention C only as "not recommended, here is why" (ufw bypass). Also state that containers on the shared network reach decider-ai without going through the host, so the API key is the access control there (backs D1).

## 3. Facts that change the ticket's question

1. **The ticket omits R2-10 and R2-12.** The founder asked for "activate path including task" and "n8n networking docs" to be decided here (D9, D10). The ticket text lists neither, so the resolution should name them.
2. **Feedback and `confirm` disagree.** The design gives feedback 404 and 410 statuses. The architecture says `confirm` never raises per item. The ticket's "error body shape" cannot be settled without choosing how a single rejected outcome becomes an HTTP status (D3).
3. **Idempotency mostly exists already.** The architecture's `confirm` upserts on `external_id`. The real open points are whether feedback upserts on `request_id`, and whether import requires `external_id`. Whether to add an `Idempotency-Key` header is secondary, and the IETF draft for it has expired.
4. **"Request size limits beyond per-task input length" is not optional.** FastAPI, Starlette and uvicorn ship no body cap, so without a decision the default `docker run` accepts unbounded bodies. Two different 413 causes need two codes.
5. **FastAPI's defaults decide some answers unless they are overridden.** 422 `{"detail": [...]}` for validation, 401 + `WWW-Authenticate` for missing credentials (since 0.122.0), and open `/openapi.json`, `/docs` and `/redoc`. "Whether an OpenAPI document is published" is really "whether to turn the default off".
6. **The loopback-only publish rules out every n8n-in-a-container setup except a shared Docker network** (inference, see Facts). That makes R2-12's remedy a constraint, not one option among several.
7. **The activate path overlaps with ticket 0018 (task versioning).** The path decision (D9) here and the version-mismatch rule there must agree. The `LABEL_NOT_IN_TASK` 422 (D3) also answers 0018's R2-4 error question. Resolve the two in the same session, or record the dependency.
8. **The `labels` rename reaches beyond HTTP.** It changes the import JSONL and the `decider-eval` record format (`docs/design.md` Track 1, step 2), which Phase 0 code reads.
