# decider-ai — build plan

Ordered vertical slices for Phase 0 (Track 1, eval and model) and Phase 1 (Track 2, product), built in parallel as `docs/design.md` (Approach B) chose. Sources: `docs/design.md` (APPROVED), `docs/architecture.md`, `docs/adr/0001-licensing.md`, the map `issues/0001-map-decider-ai-engineering.md` (Decisions so far) and the closed tickets in `issues/`. This plan adds no scope. Where the docs left a low-stakes detail open, the plan takes the simplest working option (map, Notes: founder preference) and says so with "(plan choice)".

The n8n community node is not in this plan (own repository, ADR 0001). This repo ships only the shared-network `docker-compose.yml` sample its README needs (slice T2.6).

## How to use this plan

- Build each slice in order within its track. Respect the cross-track arrows below. A slice is done only when every acceptance test passes and the done-when line holds.
- Acceptance tests are observable through a module's interface: `Decider` methods, `evaluation` functions, HTTP routes, CLI output and files. Tests never reach into SQLite tables or private helpers, except where a test checks an invariant about stored bytes (marked).
- Per-push CI runs the fast suite only (`FakeBackend`, map Decisions line 43). Tests marked `laya` need the real checkpoint and run on demand. The release test runs against a built image.
- If a slice touches an item under "Contradictions found", it builds on the reading named in the slice and marks it **(see Cn)**. Where no reading is settled, the behaviour is **held**: do not build it until the founder rules.

## Standing invariants

Each is established by the slice named and must stay green from then on.

| Invariant | Source | Established in |
|---|---|---|
| No automatic retrain or activation, ever. Only `retrain` and `activate` change what trains or serves. | design.md:36, :94; architecture.md:74 | T2.4 |
| `decide` stores no message text; the only stored text is confirmed examples. | design.md:92; issues/0009 | T2.3 |
| No message text in logs, ever (no `Event` type has a text field). | design.md:92; architecture.md:76 | T2.3, T2.5, T2.6 |
| Input is never truncated: over-length input → `InputTooLong` / 413 `INPUT_TOO_LONG`. | design.md:83; issues/0019 | T2.3 (fake), T1.4 (tokens), T2.5 (HTTP) |
| One retrain job at a time per container: `Busy` / 409. | design.md:87; architecture.md:72 | T2.4, T2.5 |
| Test-split examples never reach `Backend.train`. | design.md:96; architecture.md:75 | T2.4 |
| The product never calls an LLM. | design.md:35; map line 20 | T1.3 (script lives outside `src/decider`) |

## Slice map and dependencies

```
Track 2 (product)                          Track 1 (eval and model)

T2.1 skeleton + CI ───────────────────────────┬──────────────┐
  │                                           ▼              │
T2.2 tasks + Backend port + FakeBackend ──►  T1.1 evaluation │
  │        │                                  │              │
  │        └──────────────► T1.2 datasets + baselines + fixture
  ▼                                           │      │
T2.3 Decider serving path                     │      ▼
  │                                           │   T1.3 LLM prep script
  ▼                                           │
T2.4 retrain, jobs, models, activate ◄────────┘ (needs T1.1)
  │                                        T1.4 LayaBackend (needs T2.2)
  ▼                                           │
T2.5 HTTP adapter                          T1.5 decider-eval + report (needs T1.1, T2.2)
  │                                           │
  ▼                                           │
T2.6 container + first start                  │
  │                                           │
  ▼                                           │
T2.7 JOIN: LayaBackend in the container ◄─────┘ (needs T1.4)
  │
  ▼
T2.8 Phase 1 release test (needs T1.2 fixture)   T1.6 gate run → report.json / report.md
                                                     (needs T1.2–T1.5)
```

| Slice | Depends on |
|---|---|
| T2.1 | — |
| T2.2 | T2.1 |
| T2.3 | T2.2 |
| T2.4 | T2.3, **T1.1** |
| T2.5 | T2.4 |
| T2.6 | T2.5 |
| **T2.7 (join point)** | T2.6, **T1.4** |
| T2.8 | T2.7, **T1.2** (release fixture) |
| T1.1 | T2.1 |
| T1.2 | T2.1, T2.2 (generated `tasks.yaml` must load) |
| T1.3 | T1.2 |
| T1.4 | T2.2 |
| T1.5 | T1.1, T2.2 |
| T1.6 | T1.2, T1.3, T1.4, T1.5 |

Scheduling note: build T1.1 first in Track 1, because T2.4 waits on it. T1.4 is the long pole for the join; start it as soon as T2.2 lands.

The join point is **T2.7**: `LayaBackend` from Track 1 replaces `FakeBackend` in the container. The gate does not block Track 2 (design.md:64). The gate run (T1.6) and the release test (T2.8) are independent final slices.

---

## Track 2 — Product (Phase 1)

### T2.1 — Repo skeleton and CI

**Goal:** an installable, empty `decider` package whose tests run on every push, with DCO enforced.

**Touches:** `pyproject.toml` (Python 3.12, package `decider` under `src/`, entry point `decider-eval = decider.eval_cli:main`, a `bench` dependency group for scikit-learn and the LLM client that is never installed in the image), `uv.lock` (plan choice: `uv` for the lock file, issues/0013 asks only for "a lock file"), `src/decider/__init__.py`, `tests/`, `LICENSE` (Apache-2.0), `.github/workflows/ci.yml`, `README.md` (stub).

**Acceptance tests:**
- `uv run pytest` passes locally with one smoke test (`import decider`).
- A push to any branch runs the `test` job (pytest, fast suite only; `-m "not laya"`) and it passes.
- The `dco` job fails a PR containing a commit without `Signed-off-by:` and passes once the commit is signed off.
- The workflow has a `release` job that runs only on tags `v*` (filled in by T2.6).

**Done when:** CI is green on `main` and the DCO check is a required status.

### T2.2 — `tasks`, the `Backend` port and `FakeBackend`

**Goal:** `tasks.yaml` loads into validated `TaskSpec`s, and every later slice has a deterministic backend to run on.

**Touches:** `src/decider/tasks.py`, `src/decider/backend/__init__.py` (`Backend` protocol, `ModelRef`), `src/decider/backend/fake.py`, `tests/test_tasks.py`, `tests/test_fake_backend.py`.

`tasks.yaml` fields per task: `name`, `question`, `labels` (name → one-line description), `max_input_tokens`, `zero_shot` (default `false`). Single-label only (design.md:78). `TaskSpec` carries a hash of the label set so `Decider` can detect a changed label set at startup **(see C14, C15)**.

**Acceptance tests (through `tasks.load` and the `Backend` methods):**
- A valid file with two tasks returns two `TaskSpec`s with the given question, labels and descriptions; `zero_shot` defaults to `false` when omitted.
- Each of these raises `ConfigError` whose message names the file path and the reason: missing `question`; a task with fewer than 2 labels; a label without a description; duplicate task names; `zero_shot` not a boolean; `max_input_tokens` missing or not a positive integer; unknown top-level keys.
- Two specs differing only in a label's description have the same label-set hash; adding or removing a label changes it.
- `FakeBackend.predict` on the base `ModelRef` returns, for each text, a score for every label of the task, deterministically (same input, same output).
- `FakeBackend.train` with examples returns a new `ModelRef`; `predict` on it returns the memorised label as the top score for a training text. `train` calls `progress` with values ending at `1.0` and writes into `out_dir`.
- `FakeBackend.max_input(task)` returns a fixed token budget; it counts tokens as whitespace-separated words (plan choice, test adapter only).
- `FakeBackend` can be told to fail `predict` for a given `ModelRef` (needed for the activation-failure test in T2.4).

**Done when:** both test files pass in CI in under a second.

### T2.3 — `Decider` serving path: decide, confirm, forget, status

**Goal:** a `Decider` on `FakeBackend` serves cold-start decisions, stores confirmed examples, erases them by `external_id` and reports per-task status.

**Touches:** `src/decider/core.py` (`Decider.__init__`, `decide`, `confirm`, `forget`, `status`, `close`; `DeciderError` subclasses with stable `code`s; `Events`, `LogEvents`, `RecordedEvents`; `Clock`), `src/decider/store.py` (internal; schema is a slice detail, map line 43), `tests/test_decider_serving.py`.

**Acceptance tests (all through `Decider` methods, `db_path` a temp file, `RecordedEvents`):**
- Cold start, `zero_shot: true`: `decide` returns a `Decision` with `model_version == "base"`, a fresh `request_id` and a score for every label.
- Cold start, `zero_shot: false`: `decide` raises `NotTrained` (code `MODEL_NOT_TRAINED`).
- `decide` on an unknown task raises `UnknownTask` (code `TASK_NOT_FOUND`).
- **Never truncate:** a text one token over the task's limit raises `InputTooLong(limit)` (code `INPUT_TOO_LONG`); a text exactly at the limit is served. The effective limit is the smaller of the task's `max_input_tokens` and `Backend.max_input(task)` **(see C13)**.
- **`decide` stores no text (stored-bytes check):** after `decide` with a sentinel text, the sentinel occurs in neither the SQLite file nor its WAL, and no recorded `Event` holds it. The `decide` event carries only request ID, task, label and scores.
- `confirm([Example(...)])` returns one `Outcome` per item in order: `added` for a new `(task, external_id)`, `updated` when the same `external_id` is confirmed again (upsert; the stored label changes), `rejected` with reason `LABEL_NOT_IN_TASK` for a label outside the task's set, `rejected` with `TASK_NOT_FOUND` for an unknown task, `rejected` with `INPUT_TOO_LONG` for an over-length text. A rejected item never stops the others.
- `confirm` requires `external_id` on every item (`Example` has no default for it).
- `request_id` is stored with the example as an opaque link. Rejecting an unknown `request_id` is **held (see C5)**.
- `status()` per task reports: serving `not_trained` (or `base` with `zero_shot: true`, plus an `unmeasured` flag for the base model, issues/0007), input limit, active version `None`, confirmed count, split `Pending(blocking_labels)`.
- `forget(external_id)` removes that ID's examples in every task and returns `Forgotten(examples_removed, split_members_removed=0, versions_trained_on=[])`; the confirmed count in `status()` drops; `forget` of an unknown ID raises `NotFound`. **Stored-bytes check:** after `forget`, the forgotten text occurs in neither the SQLite file nor its WAL (`secure_delete` on, WAL truncated).
- **No text in logs:** across `decide`, `confirm` and `forget` with a sentinel text, `RecordedEvents` holds no field equal to or containing the sentinel, and `caplog` shows no record containing it.
- **Label-set change refuses startup:** a `Decider` opened on a `db_path` that stored task `x` with labels {a, b}, now given `x` with labels {a, b, c}, raises `ConfigError` naming the task and telling the user to choose a new task name (issues/0018). A changed description alone starts fine. A task removed from `tasks.yaml` leaves its data in place.
- Restart: close and reopen `Decider` on the same `db_path`; confirmed examples are still counted.
- `Decider` is thread-safe: 8 threads calling `decide` and `confirm` concurrently for 200 calls finish without error and the confirmed count is exact.

**Done when:** the suite passes on `FakeBackend` in CI; the stored-bytes and no-text checks are part of it.

### T2.4 — Retrain, jobs, models, activate

**Goal:** explicit retrain jobs produce candidates with a verdict, and only an explicit `activate` changes what serves, with rollback, erasure counts and restart recovery.

**Touches:** `src/decider/core.py` (`retrain`, `job`, `models`, `activate`; `Runner` port with `ThreadRunner`, `InlineRunner`, `ManualRunner`; split freezing; atomic swap; orphaned-job recovery), `src/decider/store.py`, `tests/test_decider_training.py`. Calls `evaluation.split`, `evaluation.compare`, `evaluation.recommend` from T1.1.

Behaviour this slice establishes (design.md:95–99, issues/0008, 0009, 0017, 0019):
- `retrain` needs ≥50 confirmed non-split examples, else `TooFewExamples(have, need=50)`.
- The split freezes at the first `retrain` once ≥150 confirmed examples exist and every label has ≥ `min(10, 100 // number_of_labels)` (100 examples, group-aware, `label_mode: blind` preferred). It changes again only with `refresh_split=True`, which also re-evaluates the active model on the new split.
- Verdict per finished job: `recommended` when the lower 95% CI bound of macro-F1 (candidate − active) on the frozen split is > 0, `not_recommended` otherwise, `unverified` when no split is frozen or no model is active (with `zero_shot: true` and nothing trained active, `base` is the active model).
- Product retrains use a random seed stored on the version (issues/0019).
- `activate` runs the swap: load the candidate, one smoke prediction, flip the active pointer in SQLite, release the old model. On failure it raises an activation error (code `ACTIVATION_FAILED`) and the active model is unchanged **(see C6)**.

**Acceptance tests (through `Decider`, `FakeBackend`, `FakeClock`):**
- `retrain` with 49 confirmed examples raises `TooFewExamples(have=49, need=50)` (code `TOO_FEW_EXAMPLES`).
- **No auto retrain or activate:** confirming the 50th and the 150th example creates no job (`models()` stays empty); advancing `FakeClock` by 30 days changes nothing; after a job finishes, `status()` still shows the previous active version and `decide` still returns its `model_version`.
- **One job at a time (`ManualRunner`):** while a job for task A is held, `retrain` for task A and for task B both raise `Busy(job_id)` with the running job's ID; `job(id)` shows `running` with progress; `decide` on A keeps serving the active model. After the runner releases the work, a new `retrain` succeeds.
- Below 150 examples (`InlineRunner`): `retrain` returns a `JobId`; `job(id)` reports `succeeded` with verdict `unverified`; `models(task)` lists the version, not active. `activate(task, version)` returns `Activation(warning=...)` saying it has no reliable evaluation; `decide` now returns that `model_version`; `status()` reports `trained`.
- First model with a frozen split and `zero_shot: false`: verdict `unverified` (issues/0017). With `zero_shot: true`: the verdict compares against `base` and is `recommended` or `not_recommended`.
- Frozen split: with 160 confirmed examples over 3 labels and every label ≥10, `retrain` freezes a 100-example split; `status()` shows `Frozen`; the job's verdict is `recommended` or `not_recommended` with `ci_low`/`ci_high` and split revision and size in `job(id).metrics`; the active model is unchanged until `activate`.
- **Split never trains:** a recording backend wrapper shows no external ID from the frozen split in any `Backend.train` call, across two retrains.
- `label_mode: blind` preference: with 120 blind and 100 assisted examples, every split member is blind.
- Rare label: one label stuck at 3 examples keeps the split `Pending(blocking_labels=[that label])`; the job verdict is `unverified`.
- Activating a `not_recommended` version succeeds with a warning.
- Rollback: after activating v2, `activate(task, v1)` makes `decide` return v1 again.
- `activate` with an unknown version, or a version from another task, raises `NotFound` (issues/0018).
- Activation failure: with `FakeBackend` set to fail the smoke prediction for v3, `activate(task, v3)` raises `ACTIVATION_FAILED` and `decide` still returns the previous version.
- Erasure after training: `forget` an ID that v1 trained on and that sits in the frozen split. `Forgotten` reports `split_members_removed=1` and `versions_trained_on=[v1]`; the split stays `Frozen` and shrinks to 99; `models(task)` shows v1 with an erased-examples count of 1; the verdicts already recorded are unchanged; `activate(task, v1)` succeeds with a warning naming the erased count. `status()` names labels now below the per-label minimum **(see C7)**.
- `refresh_split=True` on a later retrain draws a new split; `models(task)` shows the new split revision on the new verdict and the active model's re-evaluation.
- Restart recovery: close `Decider` while a `ManualRunner` job is held; reopen; `job(id)` reports `failed`, the job's partial files under `model_dir` are gone, and a new `retrain` is accepted (lock released).
- Restart persistence: after close/reopen, `models(task)` and the active version are unchanged.
- `ThreadRunner` smoke: a retrain on `ThreadRunner` finishes and `job(id)` goes `running` → `succeeded`; `decide` returns during training. The training thread runs at `nice` priority with the thread cap (default half the CPUs).

**Done when:** the suite passes on `FakeBackend` in CI; every behaviour in the architecture's "What it hides" list for these methods has a test above.

### T2.5 — HTTP adapter

**Goal:** every route in design.md:82–90 maps onto `Decider` with Bearer auth, the decided error shape and the body cap.

**Touches:** `src/decider/http.py` (`create_app(decider, api_key, max_body_bytes)`), `tests/test_http.py` (FastAPI `TestClient`, `FakeBackend`, `InlineRunner`).

Error body `{"error": {"code", "message", ...fields}}` (issues/0010). Status map: `INPUT_TOO_LONG` 413, `PAYLOAD_TOO_LARGE` 413, `MODEL_NOT_TRAINED` 503, `BUSY` 409 (plan choice of code name; carries `job_id`), `TOO_FEW_EXAMPLES` 422 (`have`, `need`), `LABEL_NOT_IN_TASK` 422, `VALIDATION_FAILED` 422, `TASK_NOT_FOUND` 404, `NOT_FOUND` 404 (plan choice for job, version and example), `UNAUTHORIZED` 401 (plan choice of code name), `ACTIVATION_FAILED` 500.

**Acceptance tests (HTTP only):**
- Auth: `GET /health/live` → 200 without a key. Every other route without `Authorization`, or with a wrong key → 401, error body, `WWW-Authenticate: Bearer`.
- `POST /v1/decisions {task, text, external_id?}` → 200 `{request_id, model_version, predictions}` on a zero-shot task; 503 `MODEL_NOT_TRAINED` on a non-zero-shot task; 404 `TASK_NOT_FOUND`; **413 `INPUT_TOO_LONG` with `limit` for an over-length text (never truncated)**; 422 `VALIDATION_FAILED` for a missing `text`.
- `POST /v1/feedback {task, text, label, external_id, request_id?}` → 200 with the outcome (`added` / `updated`); a label outside the task → 422 `LABEL_NOT_IN_TASK` naming the allowed labels; missing `external_id` → 422 `VALIDATION_FAILED`. Sending the same body twice gives `added` then `updated` and one stored example (natural-key idempotency).
- `POST /v1/examples:batch` with `Content-Type: application/x-ndjson` → 200 `{"outcomes": [...]}`, one per line in order; a bad line yields a `rejected` outcome with its code and the rest are stored.
- Body cap: a body over `DECIDER_MAX_BODY_BYTES` (set small in the test) → 413 `PAYLOAD_TOO_LARGE`, counted on streamed bytes, also when `Content-Length` is absent.
- `DELETE /v1/examples/{external_id}` → 200 with `examples_removed`, `split_members_removed`, `versions_trained_on`; unknown → 404.
- `POST /v1/retrain {task}` → 202 `{job_id}`; with fewer than 50 examples → 422 `TOO_FEW_EXAMPLES`; **a second retrain while one runs (`ManualRunner`) → 409 `BUSY` with the running `job_id`**. `{task, refresh_split: true}` is accepted.
- `GET /v1/jobs/{id}` → status, progress, verdict and metrics; unknown → 404.
- `GET /v1/tasks/{task}/models` → `{"models": [...]}` with version, verdict, CI, metrics, split revision and size, erased-examples count, `active`.
- `POST /v1/tasks/{task}/models/{version}/activate` → 200 `{warning}` (null or text); version of another task → 404; smoke failure → 500 `ACTIVATION_FAILED`.
- `GET /health/ready` → 200 with, per task: serving `base` / `trained` / `not_trained`, the input limit, active version, confirmed count, split state with blocking labels, labels below the minimum, the unmeasured flag for opted-in zero-shot.
- `GET /openapi.json` is served (behind auth, plan choice: issues/0010 says only "served"); `/docs` and `/redoc` → 404.
- **No text in logs:** with a sentinel text sent to decisions, feedback and import, no captured log record (app and uvicorn access loggers) contains it.

**Done when:** the route suite passes in CI; the adapter holds no logic beyond mapping (architecture.md:129).

### T2.6 — Container and first start

**Goal:** `docker run` on an empty `/data` volume starts the service, creates the API key, downloads the pinned base checkpoint and serves on `FakeBackend`; tags publish the image to GHCR.

**Touches:** `src/decider/__main__.py` (composition root: reads `/data/tasks.yaml`, creates or reads `/data/api_key`, ensures the base checkpoint in `/data/hf-cache`, builds `Decider` with `ThreadRunner`, `db_path=/data/decider.db`, `model_dir=/data/models`, starts one uvicorn worker bound to `0.0.0.0:8080`), `Dockerfile` (`python:3.12-slim`, CPU-only torch index, lock-file install, x86-64 only, `HEALTHCHECK` on `/health/live`), `.github/workflows/ci.yml` (`release` job: build and push `ghcr.io/<owner>/decider-ai:<tag>` on tag), `docker-compose.yml` sample, `README.md` (run section). This slice still wires `FakeBackend`; T2.7 swaps it. Small composition file: architecture.md's layout has no entry point (plan choice).

Base checkpoint: `convaiinnovations/laya-multilingual` at revision `1720e3e3357cfe1e281542e223f8273b0890ca34`, `model.safetensors` sha256 `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204` (docs/research/laya-checkpoint-facts.md:34).

**Acceptance tests (shell script `tests/container/test_first_start.sh` against the built image):**
- First start on an empty volume with `DECIDER_API_KEY` unset: the log prints the generated key exactly once; `/data/api_key` exists; a second start prints no key and accepts the same key.
- With `DECIDER_API_KEY` set, that key works and no key is generated.
- The base checkpoint lands in `/data/hf-cache` at the pinned revision and the sha256 matches; a second start downloads nothing.
- A corrupted `model.safetensors` in the cache makes startup fail with a message naming the checksum mismatch.
- Offline (`--network none`) with an empty cache: the container exits non-zero with a message that names the missing checkpoint and the documented pre-download command. With a pre-populated volume (`huggingface-cli download convaiinnovations/laya-multilingual --revision 1720e3e… --local-dir …`, as in the README) it starts offline.
- A `tasks.yaml` error makes the container exit non-zero with the `ConfigError` message.
- Published as documented (`-p 127.0.0.1:8080:8080 -v decider-data:/data`): `curl 127.0.0.1:8080/health/live` → 200; `/health/ready` with the key → 200.
- `docker compose up` with the sample file starts decider-ai and a `curlimages/curl` service on one shared network; the curl service reaches `http://decider-ai:8080/health/live` → 200 (the README's n8n wiring, issues/0010).
- **No text in logs:** after posting a sentinel text to decisions and feedback, `docker logs` does not contain it.
- Pushing tag `v0.1.0-rc1` publishes `ghcr.io/<owner>/decider-ai:v0.1.0-rc1`; docs name pinned tags only, never `latest`.

**Done when:** the script passes locally and the tag build pushes the image.

### T2.7 — Join: `LayaBackend` in the container

**Goal:** the container serves and trains with `LayaBackend` from T1.4 instead of `FakeBackend`.

**Depends on:** T2.6 and T1.4.

**Touches:** `src/decider/__main__.py` (wire `LayaBackend` with the cached base checkpoint), `Dockerfile` (pinned `laya` SDK from T1.4's lock), `README.md` (documented host: x86-64 with AVX2, 4+ vCPU, 16 GB RAM; ~678 MB disk per kept version; training peak ~8.5 GB; scores are uncalibrated; weights keep what they learned after erasure until the operator retrains; volume backups are the operator's responsibility).

**Acceptance tests (against the built image on the documented host; `laya` marker):**
- A `zero_shot: true` task returns `model_version: base` from the real base model with a score per label.
- A MASSIVE text longer than the task limit in tokens → 413 `INPUT_TOO_LONG`; one exactly at the limit is served.
- Importing 60 fixture examples and calling retrain produces a job that progresses (epoch/step visible in `GET /v1/jobs/{id}`), finishes, and leaves a candidate under `/data/models`; `/v1/decisions` answers during training.
- All T2.6 container checks still pass.

**Done when:** the image built from `main` passes these checks and T2.6's script.

### T2.8 — Phase 1 release test (final slice, Track 2)

**Goal:** the design's Phase 1 Success Criteria (design.md:116–120), run on a clean machine with `docker run` and a `tasks.yaml`.

**Depends on:** T2.7, and the release fixture from T1.2.

**Touches:** `tests/release/release_test.py` (HTTP client against a running container; plan choice: pytest with `httpx`), `tests/release/tasks.yaml`, `README.md` (the steps double as the tutorial walkthrough).

Setup: a clean x86-64 host matching the documented host, Docker only. Fixture: `bench/fetch.py --release-fixture` (T1.2) writes 200 MASSIVE 1.1 `de-DE` scenario records from the train partition, seeded and stratified with ≥10 per scenario; stage A is its first 60 lines, stage B the other 140 (plan choice; data chosen so the split freezes, design.md:119). `tasks.yaml` holds two tasks with the 18 MASSIVE scenario labels and question (docs/research/public-benchmark-datasets.md:64–85): `massive_zs` with `zero_shot: true` and `massive` with `zero_shot: false`.

**Acceptance tests (verbatim from design.md Success Criteria, each step asserted over HTTP):**
1. **Cold start:** with zero-shot enabled, a decision returns `model_version: base` (`massive_zs`); with it disabled, `503 MODEL_NOT_TRAINED` (`massive`).
2. **Below 150 examples:** import labels (stage A, 60 lines, via `POST /v1/examples:batch`), send feedback (`POST /v1/feedback` for one new `external_id`), run a retrain job (`POST /v1/retrain` → 202) and poll it (`GET /v1/jobs/{id}` until finished); the candidate is `unverified`; activate it manually (200 with a warning); decisions now serve it (`model_version` equals the candidate).
3. **Once the split is frozen** (stage B imported, ≥150 confirmed examples meeting the per-label minimum): retrain; the job reports `recommended` or `not_recommended` (with its CI); the active model is unchanged until an explicit `activate` (decisions and `/v1/tasks/massive/models` still show the stage-2 version); then activate the new version and see decisions serve it.
4. **Activate the previous version** (the stage-2 version; decisions serve it), **delete an example** (`DELETE /v1/examples/{external_id}` → 200; confirmed count drops by one), **restart** (`docker restart`) **without losing labels or the active version** (after restart, `/health/ready` shows the same confirmed count and active version, and decisions serve that version).

**Done when:** the release test passes end to end on a clean machine against the pinned release image, and its log is attached to the release.

---

## Track 1 — Eval and model (Phase 0)

### T1.1 — `evaluation` module

**Goal:** the pure statistics both phases share: split, paired bootstrap, recommendation and the Phase 0 gate.

**Touches:** `src/decider/evaluation.py`, `tests/test_evaluation.py` (literal arrays only).

Functions: `split(examples, size, min_per_label, prefer_blind=True) -> Split | NotEnough(blocking_labels)`; `compare(gold, a, b_by_seed, groups, metric="macro_f1", resamples=2000) -> Comparison(delta, ci_low, ci_high, n)` with `delta = metric(a) − mean over seeds of metric(b)`, seeds averaged inside each resample; `recommend(cmp, split_frozen) -> Recommended | NotRecommended | Unverified`; and the cost-benefit gate of design.md:72 **(see C1)**. `action_gate` and `urgency_gate` are not built **(see C1)**.

**Acceptance tests:**
- `split` returns exactly `size` examples with every label at ≥ `min_per_label`; no group is split across test and rest; with enough blind examples every member is blind; with one label short it returns `NotEnough(blocking_labels=[that label])`; same input and seed gives the same split.
- `compare` with `a == b` gives `delta == 0` and a CI containing 0; with `a` perfect and `b` at chance on 200 items gives `ci_low > 0`; with 5 identical seeds equals the 1-seed result; resampling is by group (all items of one group move together, checked with a 2-group fixture); `n` equals the number of items; fixed seed gives identical output.
- `recommend`: `ci_low > 0` and frozen → `Recommended`; `ci_low ≤ 0` and frozen → `NotRecommended`; not frozen → `Unverified`.
- Gate: given per-dataset inputs for (b) and (c) at 250 labels (cost per 1,000, p95 latency, the F1 `Comparison` of b − c), it returns `ReScope` only when, on every dataset, (b) has lower cost, lower p95 and `ci_low > 0`; flipping any single axis on any single dataset returns `Launch`.

**Done when:** the suite passes in CI; T2.4 can import it.

### T1.2 — Pinned datasets, record conversion, majority and TF-IDF baselines, release fixture

**Goal:** one script fetches the pinned public sets, converts them to decider-ai records and benchmark `tasks.yaml`s, writes the training subsets, runs the two cheap baselines, and cuts the release fixture.

**Touches:** `bench/fetch.py`, `bench/convert.py`, `bench/baselines.py` (scikit-learn, `bench` group only; never imported by `src/decider`), `bench/tasks/massive_de_scenario.yaml`, `bench/tasks/clinc_domain.yaml`, `tests/bench/` (small synthetic inputs), `.gitignore` (`data/`, `predictions/`). Datasets are downloaded, never committed (ADR 0001).

Datasets (map line 45; pins and checksums in docs/research/public-benchmark-datasets.md:23–27): MASSIVE 1.1 `de-DE` scenario level (18 labels) and CLINC150 `oos_plus` domain level (10 domains + `out_of_scope`). Banking77 is optional and not built. Records: one JSON line per example with `external_id`, `text`, `label`, `group_id = external_id`, `label_mode` (`blind` for the official test partition, `assisted` for train) **(see C8)**. External IDs as in the research doc (`massive-de-DE-<id>`, `clinc-<split>-<row>`). Training subsets: for each budget 50 / 100 / 250 and seed 0–4, one example per label first, then random fill (research doc :150), written as ID lists that every system reads. Budget "all" **(see C9)**: the scripts accept any budget list; the run config in T1.6 is what changes.

Prediction file format (plan choice, shared by T1.3 and T1.5): `predictions/<dataset>/<system>.jsonl`, one line per test record and (budget, seed) with `external_id`, `budget`, `seed`, `label` (or `null` for an invalid answer), `latency_ms`, and for API systems `input_tokens`, `output_tokens`; plus `<system>.meta.json` with `kind` (`local` / `api`), training seconds per (budget, seed), and for API systems model ID, settings, prices and price date.

**Acceptance tests (CLI output and files):**
- `bench/fetch.py` downloads each pinned file and verifies its sha256; a tampered file fails with the expected and actual hashes; a second run downloads nothing.
- `bench/convert.py` writes record counts equal to the official partitions (MASSIVE test 2,974; CLINC test 5,500) and the per-label counts in the research doc; every test record is `blind`, every train record `assisted`; no message text appears outside the data directory.
- `tasks.load` accepts both generated benchmark `tasks.yaml`s (18 and 11 labels, descriptions from the research doc).
- Subsets: each (budget, seed) list has exactly `budget` IDs, every label at least once, only train IDs; re-running gives identical lists.
- `bench/baselines.py` writes `majority` and `tfidf_lr` prediction files for every (budget, seed) in the spec of research doc :145–146, with per-prediction `latency_ms` from sequential single predictions and training seconds in the meta file. Its TF-IDF + LR macro-F1 at 250 is within 0.03 of the research reference (0.638 MASSIVE, 0.594 CLINC, mean of 5 seeds).
- `bench/fetch.py --release-fixture` writes the 200-record MASSIVE fixture used by T2.8 (≥10 per scenario, seeded, deterministic), with a NOTICE line crediting MASSIVE (CC BY 4.0).

**Done when:** both datasets convert and both baselines run from a clean checkout with one documented command sequence.

### T1.3 — Standalone LLM baseline prep script

**Goal:** a script outside `src/decider` produces baseline (b) predictions from Gemini 3.5 Flash-Lite on the public test sets.

**Touches:** `bench/llm_baseline.py`, `tests/bench/test_llm_baseline.py` (with a stubbed client).

Settings (issues/0005): model `gemini-3.5-flash-lite`; zero-shot with the task's question and label descriptions; temperature 0; lowest thinking setting; output restricted to the label set; an invalid answer is recorded as `label: null` and counts as wrong. Sequential single synchronous requests, one session, from the reference machine.

**Acceptance tests:**
- With a stubbed client, the script writes one prediction line per test record with `latency_ms`, `input_tokens`, `output_tokens`; the meta file records model ID, thinking setting, temperature, prompt template hash, price per million input and output tokens with retrieval date, and run date.
- A stubbed reply outside the label set is written as `label: null`; the script's summary prints the invalid count.
- `grep -r` finds no import of the LLM client anywhere under `src/decider` (the product never calls an LLM), and the image from T2.6 does not contain the client package.
- The script resumes after an interruption without re-calling records already written.
- One live smoke run on 20 MASSIVE test records (needs an API key; not in CI) produces a valid file.

**Done when:** a stubbed run passes in CI and the live smoke run succeeds.

### T1.4 — `LayaBackend` on the pinned `laya` SDK

**Goal:** the real `Backend` adapter: zero-shot and fine-tuned prediction, CPU fine-tuning, and a token check that runs before the SDK can truncate.

**Touches:** `src/decider/backend/laya.py`, `pyproject.toml` / `uv.lock` (pin `laya` ≥0.4.0 to one exact version, CPU torch), `tests/test_laya_backend.py` (`laya` marker). Built fresh on the Apache-2.0 SDK and official notebook; nothing is copied from tehtommeh/laya-finetuning (issues/0020).

Recipe (issues/0019): `laya.train`, fp32, gradient checkpointing on, thread cap half the CPUs; 12 epochs below 300 training examples, else 4; SDK default learning rates; no calibration **(see C12)**; one checkpoint per task in the SDK's layout; `seed` argument passed through (Phase 0 uses 0–4, the product a random stored seed). A task is encoded as its question plus label options.

**Acceptance tests (through `Backend` methods, real base checkpoint):**
- `predict(base, task, texts)` returns a score for every label of a MASSIVE task, for each text.
- `max_input(task)` returns the message budget in tokens, counted with the SDK's tokenizer the same way the SDK tokenises (mask token replaced); `predict` on a text one token over raises `InputTooLong` before calling the model; a text at the limit is served.
- `train(base, task, 50 MASSIVE examples, seed=0, out_dir, progress)` finishes on CPU, calls `progress` up to 1.0, writes one checkpoint into `out_dir`, and `predict` on the result returns scores for every label. The run time and peak RSS are printed.
- Same seed and data twice: the predicted labels on 100 test texts agree on at least 95% (CPU determinism is unmeasured; this records it).
- **Stop check (design.md:72):** record the token count of question + options for both benchmark tasks with the SDK tokenizer. If either exceeds the SDK's 256-token head budget, or if the licence of the pinned checkpoint/SDK no longer reads Apache-2.0, or if a 50-example CPU fine-tune does not finish on the documented host, **stop Track 1 and return the backend choice to the founder** (named fallback: a SetFit-style encoder behind the same port).

**Done when:** the `laya` suite passes on the reference machine and the stop check is recorded as passed in the PR.

### T1.5 — `decider-eval` and the report

**Goal:** one CLI turns records, prediction files and the `Backend` into `report.json` and `report.md` for any number of datasets and named optional systems.

**Touches:** `src/decider/eval_cli.py`, `tests/test_eval_cli.py` (`FakeBackend`, tiny records and prediction files).

CLI: `decider-eval --dataset <records> --tasks <tasks.yaml> --subsets <dir> --predictions <dir> [--budgets 50,100,250] [--seeds 0-4] --machine "<specs>" --price-per-hour 0.0256 --currency EUR --fx <rate,date> --out <dir>` (plan choice for flag names; the FX rate puts local and LLM cost in one currency). It runs (c) via `Backend.train` + `predict` for each (budget, seed) and (d) via `Backend.predict` on the base model, reads every prediction file present as a named system (`majority`, `tfidf_lr`, `llm` or any other name), and computes everything through `evaluation`.

Report content (design.md:71, :115; issues/0005), aggregate numbers only, no message text:
- Header: run date, git SHA, dataset pins and sha256s, Laya revision, SDK version, LLM model ID and settings, machine specs, prices with retrieval date, FX rate.
- Per dataset and system: macro-F1 per budget with the paired-bootstrap Δ vs (c) and its 95% CI (2,000 resamples, seeds averaged inside each resample), test-set size n, stated as nominal and unadjusted.
- Learning curve for (c) and TF-IDF + LR.
- p95 latency per decision per system (sequential single requests).
- Cost per 1,000 decisions per system: LLM at list price; local as busy CPU-hours at the hourly rate, plus one 250-label retrain (mean over seeds) amortised over 30,000 decisions; training CPU-hours as their own line; a ±30% token-count sensitivity line for the LLM.
- Gate outcome per dataset (three axes for (b) vs (c) at 250) and overall `ReScope` / `Launch`, with the headline sentence of the measured trade-off.
- Zero-shot rule outcome: whether (d) ≥ TF-IDF + LR at 50 on every dataset (issues/0007).
- Dataset attribution (name, authors, licence, link).

**Acceptance tests:**
- On a tiny fixture with `FakeBackend`, the CLI writes `report.json` (with `schema_version`) and `report.md`; every number in `report.md` is read from `report.json` (re-rendering from the JSON alone gives byte-identical Markdown).
- With no prediction files the report has (c) and (d) only; adding `foo.jsonl` adds a system named `foo` — no system name is hard-coded.
- A missing (budget, seed) prediction for a system fails with a message naming the file and budget.
- A fixture where `llm` beats (c) on all three axes in both datasets yields `ReScope`; making one dataset's LLM slower yields `Launch`.
- An invalid (`null`) LLM label counts as wrong and the report shows the invalid count.
- No test text from the fixture appears in `report.json`, `report.md` or the CLI's output.

**Done when:** the suite passes in CI on `FakeBackend`.

### T1.6 — Gate run (final slice, Track 1)

**Goal:** the Phase 0 report on MASSIVE `de-DE` and CLINC150 with every system, and the gate outcome recorded (design.md:115).

**Depends on:** T1.2, T1.3, T1.4, T1.5.

**Touches:** `reports/<run-id>/report.json`, `reports/<run-id>/report.md` (committed, aggregates only), `README.md` (results section and headline from `report.md`).

Run (issues/0005): all systems on one stated machine (specs in the report), priced at Hetzner CX43's €0.0256/h; full official test partitions (subsample to a fixed, seeded 1,000 only if a run does not fit in a day, with the ID list committed); one look per dataset; budgets 50 / 100 / 250 × seeds 0–4 **(see C9)**.

**Acceptance tests:**
- `report.json` and `report.md` exist for the run, cover both datasets, and contain for every system (majority, `tfidf_lr`, `llm`, (c), (d)) macro-F1 with CI, the learning curve, p95 latency, cost per 1,000 decisions and sample sizes (Phase 0 Success Criterion).
- The gate outcome (`ReScope` or `Launch`) and the zero-shot rule outcome are stated in `report.md`.
- `grep` for any test text from either dataset in `reports/` finds nothing.
- If the outcome is `ReScope`, stop and hand the report to the founder before launch (design.md:43). If `Launch`, the README's results section carries the headline as measured.
- The zero-shot default in `tasks.py` changes to `true` only if the report's zero-shot rule outcome says so (expected: stays `false`).

**Done when:** the report is committed and the gate outcome is stated in `report.md` and handed to the founder.

---

## Contradictions found

Listed, not resolved. Where a slice needs a reading, it names the one it builds on and points here.

- **C1 — Gate functions.** `docs/architecture.md:103–104` defines `action_gate(cmp, n_test, per_class) -> Proceed | ReScope | LabelMore` and `urgency_gate`, the Pilot-era gates. `docs/design.md:72` (and :43) has one cost-benefit gate on cost, p95 and macro-F1; `issues/0006-combined-gate-outcome.md:17` retires the action/urgency gates. T1.1 builds the design's gate and not the two functions.
- **C2 — `decider-eval` inputs.** `docs/architecture.md:130` says it "reads the Pilot JSONL export. Systems (a) rules and (b) Gemini come as predictions inside the export." `docs/design.md:69`, `issues/0015-public-benchmark-datasets.md:23` and the map (`issues/0001-map-decider-ai-engineering.md:45`) say it reads public-set records with any named, optional prediction systems.
- **C3 — Where the n8n node lives.** `docs/architecture.md:3`, `:131` and `:147` (layout `n8n-nodes-decider-ai/` in this repo) vs `docs/adr/0001-licensing.md:1` and `issues/0011-open-source-licence.md:19` (MIT, its own repository).
- **C4 — Stale "Open" section.** `docs/architecture.md:157–160` lists the checkpoint-after-erasure policy as open and an Pilot `DecisionClient` seam; `issues/0009-data-lifecycle-erasure.md:26` decided the policy, and Pilot left the launch (`issues/0016-rethink-the-pilot-wedge.md:19`).
- **C5 — Unknown or expired `request_id` on confirm.** `docs/architecture.md:58` lists "unknown or expired request" as a per-item rejection; `docs/architecture.md:66`, `docs/design.md:84` and `issues/0009-data-lifecycle-erasure.md:22` say `request_id` only links and there is no expired-request case. `decide` stores nothing (`docs/design.md:92`), so there is nothing to check an unknown ID against. T2.3 holds the rejection.
- **C6 — Activation failure error.** `docs/architecture.md:63` lists only `NotFound` for `activate`; `docs/design.md:89` and `issues/0010-http-api-contract.md:26` require 500 `ACTIVATION_FAILED`. The HTTP status map at `docs/architecture.md:129` has no entry for it either.
- **C7 — "Below 10" vs the per-label minimum.** `docs/design.md:86`, `issues/0009-data-lifecycle-erasure.md:24` and `docs/architecture.md:81` ("≥10 per label") use a fixed 10; `docs/design.md:96` and `issues/0008-rare-label-split-fallback.md:18` use `min(10, 100 // number_of_labels)`. The canonical design copy (`~/.gstack/projects/decider-ai/rharvey-main-design-20261008-040445.md:86`) already says "labels now below the minimum", so the repo copy of `docs/design.md` is out of sync with it. T2.4 reports labels below `min(10, 100 // number_of_labels)`.
- **C8 — Record format field names.** `docs/research/public-benchmark-datasets.md:168` names `input.text`, `labels`, `provenance` (pinned by the now out-of-scope Pilot contract, `issues/0004-pilot-contract.md:21`); `issues/0009-data-lifecycle-erasure.md:22` sends `labels`. `docs/design.md:78` and `issues/0010-http-api-contract.md:20` fix `label` (singular) for the eval record format too, and `docs/architecture.md:66` uses a flat `text`. T1.2 writes `text` and `label`.
- **C9 — Learning curve "all".** `docs/design.md:70` runs (c) at 50 / 100 / 250 / all; the map (`issues/0001-map-decider-ai-engineering.md:45`) says (c) at 50 / 100 / 250 × 5 seeds, and `docs/research/public-benchmark-datasets.md:150` reports "all" for TF-IDF + LR only. T1.5 takes the budget list as an argument; T1.6's run config waits on the ruling for (c) at "all".
- **C10 — Role of the public benchmark and the tutorial dataset.** `issues/0015-public-benchmark-datasets.md:24–25` and `docs/research/public-benchmark-datasets.md:5`, `:175`, `:185` say the public benchmark does not replace the Pilot gate, the gates are not called on it, and the tutorial keeps a synthetic German dataset. `docs/design.md:72`, `:105`, `:128` and the map (`issues/0001-map-decider-ai-engineering.md:43`) make the public sets the gate and the tutorial data, with no synthetic dataset.
- **C11 — Who calls the LLM.** `docs/design.md:35` and `:42` say the eval script runs the LLM baseline; `issues/0005-phase-0-report-scope.md:23` and the map (`issues/0001-map-decider-ai-engineering.md:20`, `:35`) say a standalone prep script does, and `decider-eval` only reads its predictions. T1.3 follows the latter.
- **C12 — Calibration slice.** `issues/0019-training-procedure.md:20` says no calibration slice is carved; `docs/briefs/0019-training-procedure.md:34` and `:70` say `laya.train` always holds out `min(400, 10%)` of the training items for temperature fitting (`calib_frac=0.1`). Whether the pinned SDK lets T1.4 turn that off is unstated.
- **C13 — Input limit source and unit.** `docs/design.md:78` and `:83` put a per-task max input length in `tasks.yaml` without a unit; `docs/architecture.md:115` puts the limit on `Backend.max_input(task)` and `issues/0019-training-procedure.md:22` makes it a token check with the SDK tokenizer. Neither says how the two combine. T2.2/T2.3 read it as tokens, smaller of the two wins.
- **C14 — "Multi-class flag" on `TaskSpec`.** `docs/architecture.md:125` gives `TaskSpec` a multi-class flag; `docs/design.md:78` makes Phase 1 single-label with any number of classes. If the flag means multi-label it contradicts the design; if it means more than two classes it has no effect. T2.2 builds no flag.
- **C15 — Task versions.** `docs/architecture.md:81` ("schema and migrations (keyed by `TaskSpec.version`)") and `:125` ("version hash. Changing the label set changes the version") vs `issues/0018-task-versioning.md:18–20` (no task versioning; it "removes version tracking, migration of examples and split resets"). T2.2 keeps only a label-set hash for the startup refusal.
