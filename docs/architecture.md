# decider-ai — module design

Implements `docs/design.md` (Phase 0 eval, Phase 1 single-container endpoint). Language: Python 3.12 for everything except the n8n node (TypeScript). Storage: stdlib `sqlite3`. HTTP: FastAPI.

## Module map

```
             HTTP adapter (FastAPI)        decider-eval (Phase 0 CLI)
                     │                              │
                     ▼                              │
     ┌──────────── Decider ─────────────┐           │
     │ decide · confirm · forget        │           │
     │ retrain · jobs · models · health │           │
     │                                  │           │
     │  internal: store (sqlite)        │           │
     │            registry (active ptr) │           │
     │            job runner            │           │
     └───────┬───────────────┬──────────┘           │
             │               │                      │
             ▼               ▼                      ▼
        Backend port     evaluation  ◄──────────────┘
        ├ LayaBackend    (split · compare · verdicts)
        └ FakeBackend
             ▲
          tasks (tasks.yaml → TaskSpec)
```

Five modules. `Decider` and `evaluation` are the deep ones; `Backend` is the only true-external port (`Runner` and `Events` are in-process ports with two adapters each); the HTTP adapter and n8n node are thin adapters.

## Modules

### `Decider` — the product, one deep module

Everything the HTTP API offers, as plain method calls. The HTTP adapter maps routes onto it; tests call it directly. Chosen 2026-10-08 by a design-it-twice round (four designs: minimal `submit`/`state`, command bus, hot-path + operator facet, ports & adapters); this is the ports-and-adapters design with parts borrowed from the others.

Interface:

```python
class Decider:
    def __init__(self, tasks: list[TaskSpec], *, backend: Backend, runner: Runner,
                 db_path: str | Path, model_dir: Path,
                 clock: Clock = time.time, events: Events = LogEvents()): ...

    def decide(self, task: str, text: str, *, external_id: str | None = None) -> Decision
    def confirm(self, items: Iterable[Example]) -> list[Outcome]
    def forget(self, external_id: str) -> Forgotten
    def retrain(self, task: str, *, refresh_split: bool = False) -> JobId
    def job(self, job_id: JobId) -> Job
    def models(self, task: str) -> list[ModelVersion]
    def activate(self, task: str, version: str) -> Activation
    def status(self) -> dict[str, TaskStatus]
    def close(self) -> None
```

| Operation | Returns | Errors |
|---|---|---|
| `decide` | `Decision(request_id, model_version, predictions: {label: score})` | `UnknownTask`, `InputTooLong(limit)`, `NotTrained` |
| `confirm` | one `Outcome(index, kind: added \| updated \| rejected, reason)` per item, in order | per item, never raised: unknown or expired request, invalid label |
| `forget` | `Forgotten(examples_removed, split_members_removed, versions_trained_on)` | `NotFound` |
| `retrain` | `JobId` | `Busy(job_id)`, `TooFewExamples(have, need=50)` |
| `job` | `Job(state, progress, verdict, metrics)` | `NotFound` |
| `models` | `[ModelVersion(version, verdict, metrics, active)]` | `UnknownTask` |
| `activate` | `Activation(warning: str \| None)` | `NotFound` |
| `status` | per task: serving `base` / `trained` / `not_trained`, input limit, active version, confirmed count, split `Frozen` or `Pending(blocking_labels)` | |

- `confirm` is the single confirmed-example path. `Example(task, text, label, external_id, group_id=None, label_mode="assisted", request_id=None)` covers both operator feedback and batch import: the caller always sends the text, and `request_id` only links a correction to the served decision. Upsert on `external_id`. `decide` stores no text (decision 2026-10-08, ticket "Data lifecycle and erasure"), so there is no retention purge and no expired-request case.
- `forget` hard-deletes every example with that `external_id` in all tasks (SQLite `secure_delete`, WAL truncated) and removes it from the frozen split, which shrinks and stays frozen. It never retrains or deletes versions; each version records the IDs it was trained on, so `models()` reports how many were later erased and `activate` warns.
- Every error is a `DeciderError` with a stable `code` and structured fields. Decider never builds a response body; the HTTP adapter owns the body shape (map ticket "HTTP API contract details").

Invariants callers can rely on:
- Input is never truncated.
- At most one retrain job runs per container. `Busy` is raised by `Decider`, not by a runner, so it holds under every runner adapter.
- `decide` always serves the active model; training never blocks it.
- Nothing retrains or goes live by itself. Only `retrain` and `activate` change what trains or what serves; no other call and no elapsed time does. Each job reports a verdict (`recommended` / `not_recommended` / `unverified`) to inform the `activate` call; activating an `unverified` or `not_recommended` version succeeds with a warning.
- Test-split examples never reach `Backend.train`.
- Message text never reaches logs: no `Event` type has a text field.
- `Decider` is thread-safe.

Ordering: `activate` needs a version a finished job produced. 

What it hides: the SQLite schema, split freezing (100 examples at ≥150 confirmed, at least `min(10, 100 // number_of_labels)` per label, group-aware, `label_mode: blind` preferred, via `evaluation.split`), verdicts (via `evaluation.compare` and `evaluation.recommend`), the first-model rule and the `unverified` state, the atomic model swap (load, smoke prediction, flip active pointer, release old), recovery of a job orphaned by a restart, seed handling and the checkpoint layout under `model_dir`.

Dependencies:

| Dependency | Category | Seam | Adapters |
|---|---|---|---|
| Laya / PyTorch | true external | `Backend` port | `LayaBackend`, `FakeBackend` |
| Training execution | in-process, varies | `Runner` port: `start(work: Callable[[], None])` | `ThreadRunner` (owns `nice` and the thread cap), `InlineRunner`, `ManualRunner` (holds work so tests can observe mid-training state) |
| Time | in-process | `Clock = Callable[[], float]` | `time.time`, `FakeClock` |
| Observability | in-process | `Events` port: `emit(Event)` | `LogEvents`, `RecordedEvents` |
| SQLite | local-substitutable | none, `db_path` (`":memory:"` in tests) | — |
| Checkpoint files | local-substitutable | none, `model_dir` (`tmp_path` in tests) | — |
| `tasks.yaml` | pure | none, caller passes `list[TaskSpec]` from `tasks.load` | — |
| `evaluation` | pure | called directly | — |

Rejected in the design-it-twice round: a command bus (`handle(Command)`, adds tenant/policy/event seams with nothing varying across them, against decision 18271c16 (supersedes 6ef66611)); `submit`/`state` (per-item outcomes let `Busy` pass unnoticed, whole-container snapshot per job poll); `feedback(labels=None)` and `job_id == version` (anchoring bias; breaks for `refresh_split` re-evaluation and failed jobs); an `operator` namespace (cosmetic, auth lives in the adapter).

### `evaluation` — pure statistics, shared by both phases

Interface:
- `split(examples, size, min_per_label, prefer_blind=True) -> Split | NotEnough(blocking_labels)`: group-aware.
- `compare(gold, a, b_by_seed, groups, metric="macro_f1", resamples=2000) -> Comparison(delta, ci_low, ci_high, n)`: paired bootstrap on the difference; it averages seeds inside each resample.
- `gate(per_dataset: list[GateInput]) -> Rescope | Launch`: the Phase 0 cost-benefit rule; `GateInput` holds the LLM-vs-(c) macro-F1 comparison at 250 labels plus both systems' cost per 1,000 decisions and p95 latency. `Rescope` only if the LLM is cheaper, faster and better (CI above zero) on every dataset.
- `recommend(cmp, split_frozen) -> Recommended | NotRecommended | Unverified`: advisory only.

In-process, no I/O. Two callers, `Decider` and `decider-eval`, so the rules that decide both the tutorial headline and the retrain recommendation exist exactly once. Tests feed literal arrays.

### `Backend` — the true-external port

```python
class Backend(Protocol):
    def predict(self, model: ModelRef, task: TaskSpec, texts: list[str]) -> list[dict[str, float]]: ...
    def train(self, base: ModelRef, task: TaskSpec, examples: list[Example], seed: int, out_dir: Path, progress: Callable[[float], None]) -> ModelRef: ...
    def max_input(self, task: TaskSpec) -> int: ...
```

- `LayaBackend`: tokenisation, encodes question and options, CPU fine-tuning, writes checkpoints.
- `FakeBackend`: deterministic keyword scorer whose "training" memorises labels. Every `Decider` test runs on it in milliseconds.

It is a true external dependency (a third-party model and PyTorch), so it gets a port with a test adapter. A later ONNX backend becomes a third adapter.

### `tasks` — `tasks.yaml` to `TaskSpec`

`load(path) -> list[TaskSpec]`, which raises `ConfigError` with the path and reason. `TaskSpec` holds the name, question, labels with descriptions, max length and `zero_shot` flag. Phase 1 is single-label. A task's label set is fixed for its name; the store rejects a changed label set at startup. Pure.

### Adapters

- **HTTP** (`http.py`): routes onto `Decider`, maps `DeciderError.code` to statuses (`InputTooLong`→413, `NotTrained`→503, `Busy`→409, `TooFewExamples`→422, `NotFound`→404) and renders per-item `confirm` outcomes as `{"error": {"code", "message", ...}}`, and handles Bearer API-key auth (every route except `/health/live`). No logic. Tested with a handful of route tests only.
- **`decider-eval`** (`eval_cli.py`): reads labelled JSONL in the record format with any number of named, optional external prediction systems (majority, TF-IDF + LR, and (b) the LLM baseline, whose predictions, latency and token counts come from a standalone prep script; the product never calls an LLM). (c) is the fine-tune over 5 seeds via `Backend`; (d) is zero-shot via `Backend`. Runs `evaluation`, writes a report (JSON + Markdown) of aggregate numbers only.
- **n8n node**: in its own MIT-licensed repository (ADR 0001); one node with two operations, Decide and Send feedback, plus an API-key credential. HTTP calls only.

## Layout

```
src/decider/
  core.py          Decider
  store.py         internal to core
  evaluation.py
  tasks.py
  backend/__init__.py   Backend protocol, ModelRef
  backend/laya.py
  backend/fake.py
  http.py
  eval_cli.py
tests/             through Decider and evaluation interfaces; FakeBackend
scripts/           dataset fetch + LLM baseline prep (public data, outside the container)
Dockerfile
```

## Seams deliberately not introduced

- **Store port.** SQLite runs in memory for tests, and Postgres is deferred. One adapter is a hypothetical seam.
- **LLM adapter in the product.** The LLM baseline is produced by a standalone prep script and read as predictions, so no LLM client ships in the container.
- **Separate trainer service.** The job runner lives inside `Decider` until a second tenant appears (decision 18271c16 (supersedes 6ef66611)).

## Open

None. Both former open items are settled: checkpoints trained on erased data are kept and flagged (ticket "Data lifecycle and erasure"); the Pilot `DecisionClient` question left with Pilot ("Rethink the Pilot wedge").
