# decider-ai

A self-hosted replacement for the LLM call that routes inbound messages into a fixed set of queues. It learns from the corrections operators already make, and retrains or changes the serving model only when a user explicitly asks.

## Language

### Tasks and decisions

**Task**:
One named routing question with a fixed label set, a question, a one-line description per label and a maximum input length. A task's label set never changes under its name; a changed label set is a new task.
_Avoid_: Task version, classifier, queue set

**Label**:
One of a task's fixed answers; every decision and every example carries exactly one.
_Avoid_: Labels (plural for a single value), class, category, queue

**Decision**:
The answer the serving model gives for one message on one task: a score per label, the model version that produced it and a request ID. No message text is kept for it.
_Avoid_: Prediction (for the served answer), classification, verdict

**Request ID**:
The identifier of one served decision, used only to link later feedback to it.

### Examples and labelling

**Confirmed example**:
A stored message text with its one correct label for a task; the only text decider-ai keeps. It arrives through feedback or import.
_Avoid_: Training example, sample, record, labelled data

**Feedback**:
An operator's correct label for a message, sent with the message text and an external ID, which becomes a confirmed example.
_Avoid_: Confirm, correction (as a separate concept), confirmation

**Import**:
Adding many labelled messages at once as confirmed examples, typically so a task can be trained before it goes live.
_Avoid_: Batch upload, bulk feedback, examples batch

**External ID**:
The caller's own identifier for a message; required on every confirmed example and the key for both upsert and erasure.
_Avoid_: Message ID, example ID

**Group**:
A set of confirmed examples that belong together (such as one thread) and must land on the same side of the frozen split. Without threads, each example is its own group.
_Avoid_: Thread, conversation

**Label mode**:
How a label was produced: **blind** (given without seeing any model's answer) or **assisted** (given in normal operation, where a served decision may have been seen). Blind labels are preferred for the frozen split and the Phase 0 test set.
_Avoid_: Provenance, label source

### Evaluation

**Frozen split**:
A fixed, group-aware set of up to 100 confirmed examples per task, held out from all training and used to compare model versions. It freezes once enough confirmed examples exist with enough per label; until then the task has no frozen split.
_Avoid_: Test split, test set, holdout, eval set

**Blocking label**:
A label with too few confirmed examples for the frozen split to freeze.
_Avoid_: Rare label

**Split revision**:
The identity of one frozen split for a task; a new revision exists only after an explicit refresh. Every verdict records the split revision and size it was computed on.
_Avoid_: Split version

**Blind test set**:
In Phase 0, a benchmark dataset's official test partition, treated as blind-labelled and never trained on.
_Avoid_: Frozen split (that is the product's per-task set)

### Models

**Base model**:
The pinned, untrained question-plus-options checkpoint every model version is fine-tuned from; it can answer a task zero-shot. Shown as model version `base`.
_Avoid_: Base checkpoint, pretrained model, foundation model

**Zero-shot**:
A task served by the base model before any trained model exists, opted into per task.
_Avoid_: Cold-start model, untrained mode

**Model version**:
One trained checkpoint for one task, produced by a retrain job, with its metrics, verdict, split revision and the external IDs it was trained on. Versions are never deleted.
_Avoid_: Model, checkpoint, candidate (as the general name)

**Candidate**:
A model version, in its role of being judged against the active model by its verdict. A candidate goes live only by activation.
_Avoid_: New model, challenger

**Active model**:
The one model (a model version, or `base` under zero-shot) that currently serves a task's decisions.
_Avoid_: Production model, live model, current version, deployed model

**Serving state**:
What a task currently serves: `base` (zero-shot), `trained` (a model version is active) or `not_trained` (no answer is served).
_Avoid_: Readiness, health

### Lifecycle

**Retrain job**:
One explicitly requested training run for one task that produces a candidate and its verdict. At most one runs per container.
_Avoid_: Training run, retrain (as a noun), fine-tune job

**Verdict**:
The advisory outcome of comparing a candidate with the active model on the frozen split: **recommended** (clearly better), **not_recommended**, or **unverified** (no frozen split, or no active model to compare against). A verdict never changes the active model and is not recomputed later.
_Avoid_: Recommendation, promotion, approval, eval result

**Activate**:
The explicit user act that makes a chosen model version a task's active model. Nothing else changes the active model.
_Avoid_: Deploy, promote, publish, go live

**Rollback**:
Activating an earlier model version of the same task.
_Avoid_: Revert, restore

**Erasure**:
Hard deletion of every confirmed example with a given external ID, across all tasks, including its place in the frozen split. Model versions trained on it are kept.
_Avoid_: Forget, delete (as the domain term), purge

**Erased-examples count**:
For a model version, how many of the examples it was trained on were later erased.
_Avoid_: Tainted count, stale count

### Phase 0 benchmark

**Gate**:
The one cost-benefit rule on public benchmark data that decides whether to re-scope before launch: re-scope only if, on every dataset, (b) beats (c) on cost per 1,000 decisions, p95 latency and macro-F1 at 250 training labels. Otherwise the launch headline states the measured trade-off.
_Avoid_: Action gate, urgency gate, launch gate

**System**:
One named way of producing predictions that the benchmark scores against the others.
_Avoid_: Baseline (for all systems), arm

**(b) LLM baseline**:
One hosted LLM answering each task's question zero-shot, run offline on public data only; the product itself never calls an LLM.
_Avoid_: Gemini baseline, LLM fallback

**(c) Fine-tuned**:
The base model fine-tuned on a task's training labels, run over several seeds.
_Avoid_: Laya, the model

**(d) Base zero-shot**:
The base model answering the task's question and options with no training.
_Avoid_: Zero-shot baseline

**Majority**:
The system that always answers the most frequent label.
_Avoid_: Majority-class baseline (fine in prose), (a)

**TF-IDF+LR**:
A classic bag-of-words logistic-regression system, the bar (d) must clear for zero-shot to become the default.
_Avoid_: (b), classic baseline

**Learning curve**:
(c)'s quality measured at a series of label budgets (50 / 100 / 250 / all).
_Avoid_: Scaling curve

**Label budget**:
The number of training labels a system is given for a task.
_Avoid_: Training labels (as a count), N labels, sample size

## Flagged ambiguities

These are inconsistencies in the source docs; the docs are left unchanged.

- **"feedback" vs "confirm"**: the API calls it feedback (`docs/design.md:84`), the module calls the same storage path `confirm` and uses it for import too (`docs/architecture.md:12,45,58,66`; also `docs/design.md:53`). Canonical: **Feedback** for the operator's correction, **Import** for bulk, **Confirmed example** for what both store. `confirm` stays a method name only.
- **"candidate" vs "model version"**: the API and model list say version (`docs/design.md:88,89`; `docs/architecture.md:49,62`), the retrain and verdict rules say candidate (`docs/design.md:80,97,98,118`; `issues/0008-rare-label-split-fallback.md:19`; `issues/0002-re-verify-reviewer-fixes.md:20,22`). Canonical: **Model version**; **Candidate** only for the version's role while its verdict is being weighed. "Candidate" also means unrelated things: Pilot records and the SetFit fallback backend (`docs/design.md:72`).
- **"erasure" vs "forget" vs "delete"**: the API deletes (`docs/design.md:86`), the module forgets (`docs/architecture.md:12,46,59,67`), the model list counts erased examples (`docs/design.md:88`), and an open note still names `delete_example` (`docs/architecture.md:159`). Canonical: **Erasure**.
- **"test split" vs "frozen split" vs "split"**: `docs/design.md:96` says test split, `docs/design.md:86,89,97` frozen split, and `docs/architecture.md:64` reports it as `Frozen` or `Pending`. Canonical: **Frozen split**. It is separate from the Phase 0 **Blind test set** (`docs/design.md:70`).
- **"label" vs "labels"**: `label` (singular) is settled (`docs/design.md:78`; `issues/0010-http-api-contract.md:20`), but the erasure resolution still writes feedback as `{task, text, labels, external_id, request_id?}` (`issues/0009-data-lifecycle-erasure.md:22`).
- **"base" as a model version**: `model_version: base` (`docs/design.md:80,117`) and "`base` counts as the active model" (`docs/design.md:97`; `issues/0017-first-model-verdict.md:18`) treat the base model as a version, but it has no retrain job, verdict or split revision. Read it as the active model under zero-shot, not as a model version. The design also says both "base checkpoint" and "base model" (`docs/design.md:80`). Canonical: **Base model**.
- **System letters (a)–(d)**: (a) rules and (b) Gemini are Pilot-era (`docs/architecture.md:130`). One closed ticket says TF-IDF+LR "stands in for (b)" (`issues/0015-public-benchmark-datasets.md:22`). Current use: (b) is the LLM baseline, (c) fine-tuned, (d) base zero-shot, and majority and TF-IDF+LR go by name (`docs/design.md:42,69`). (a) is retired.
- **Gate**: `docs/architecture.md:103-104` still names `action_gate` and `urgency_gate`, and `issues/0015-public-benchmark-datasets.md:23,25` refers to the "Phase 0 Pilot gate". These were replaced by the one cost-benefit **Gate** (`docs/design.md:72`; `issues/0006-combined-gate-outcome.md:17`).
- **Task version**: the module still keys on `TaskSpec.version` with a "version hash", where a label change "changes the version" (`docs/architecture.md:81,125`). The settled rule is no task versioning: a changed label set needs a new task name (`docs/design.md:78`; `issues/0018-task-versioning.md:18`).
- **Per-label split minimum**: `docs/architecture.md:81` and `issues/0009-data-lifecycle-erasure.md:24` say "≥10 per label" / "below 10". The settled rule is `min(10, 100 // number_of_labels)` (`docs/design.md:96`; `issues/0008-rare-label-split-fallback.md:18`). The same "below 10" appears at `docs/design.md:86`.
- **"decision"**: it means both a served answer (`/v1/decisions`, `docs/design.md:83`) and a founder ruling ("decision 83b5e76c", `docs/design.md:36`). In this glossary, **Decision** means only the served answer.
- **"activate" vs "deploy" vs "promotion"**: the founder rule says "retrains or deploys" (`docs/design.md:14,94`), and the verdict rule says "Recommendation, not promotion" (`docs/design.md:97`). Canonical: **Activate**.
- **Label mode "assisted"** appears only as a default value (`docs/architecture.md:66`) and is never defined. The definition above is inferred from its contrast with blind.
- **Label budget** is not a term the docs use. They say "training labels" (`docs/design.md:43,70`) and "N labels". The glossary adds it as the name for that count.
