# Brief: data lifecycle and erasure

Preparation for grilling ticket [0009](../../issues/0009-data-lifecycle-erasure.md). This brief collects facts and sets out the decisions. It decides nothing. Prepared 2026-10-08.

Inputs: the ticket (incl. spec-review findings R2-1, R2-2), the map ([0001](../../issues/0001-map-decider-ai-engineering.md)), `docs/design.md` (APPROVED: API, Text storage, Retrain and activation, Reviewer Concerns), and `docs/architecture.md` (`Decider.forget`, `confirm`, `Forgotten`, `Outcome`). No settled decision on erasure exists in `~/.gstack/projects/decider-ai/` (checked `decisions.jsonl`, `learnings.jsonl`).

This is engineering research, not legal advice. In a self-hosted deployment the operator is the GDPR controller. decider-ai supplies the means to comply; the operator decides how to answer each request.

## 1. Facts

Each fact is labelled **sourced** (linked source), **repo** (stated in this repo's docs), or **inference** (my reasoning from the other two).

### Law and regulator guidance

| # | Fact | Basis |
|---|---|---|
| L1 | EDPB Opinion 28/2024 (adopted 17 Dec 2024): a model trained on personal data is not anonymous in all cases. It is anonymous only if both the likelihood of extracting training data from it (including probabilistically) and the likelihood of obtaining it through queries are "insignificant", considering all means reasonably likely to be used, including by unintended third parties who get access to the model (paras 42–43). | sourced [1] |
| L2 | Same opinion: when training data was processed unlawfully, a supervisory authority may order erasure of the affected part of the dataset or, where proportionate, of the whole dataset and/or the model itself. In weighing proportionality it may take into account remedies such as retraining (para 114). Data subjects can request deletion under Art. 17 (para 115). | sourced [1] |
| L3 | Hamburg DPA discussion paper (15 Jul 2024): LLM weights do not store personal data, so data subject rights do not attach to the model itself, only to the inputs and outputs of the AI system. It is a non-binding discussion paper about LLMs, and the EDPB opinion (L1) takes the stricter, case-by-case line. | sourced [2] |
| L4 | CNIL, "Ensuring and facilitating the exercise of data subjects' rights" (AI recommendations finalised July 2025, page dated 5 Jan 2026): retraining is "the most effective" way to erase data from a model when the training data is still held. Retraining may be periodic, batching several requests. Providers should ship updated versions and encourage replacing old ones. Where retraining is disproportionate, output filters are the fallback. Erasure is weighed against cost and feasibility. Requests are answered within one month (extendable by two). Blacklists of people who exercised their rights are discouraged because they create membership-inference risk. | sourced [3][4] |
| L5 | Membership inference against trained classifiers is an established attack: from a model's output scores one can infer whether a given record was in its training set. Overfitted models leak more. | sourced [5] |
| L6 | A decider-ai checkpoint is a full fine-tune of a 321.9M-parameter model on 50–250 examples, stored as a 678 MB file per version on the operator's volume. It outputs label scores only, never text. | repo (`docs/research/laya-checkpoint-facts.md`) |
| L7 | From L1, L5, L6: decider-ai cannot claim its checkpoints are anonymous. Query-based extraction of text is unlikely (it only outputs scores), but membership inference is plausible, and the checkpoint file itself is reachable by anyone with volume access. The design's current wording ("weights derived from deleted data persist until the user retrains and activates") is the honest position, and L4 shows a regulator accepting "retrain, possibly batched" as the remedy. | inference |

### How comparable self-hosted tools handle deletion

| # | Fact | Basis |
|---|---|---|
| T1 | Label Studio: `DELETE /api/tasks/{id}/` deletes a task ("This action cannot be undone"); a separate endpoint deletes single annotations by ID. Its GDPR advice is to keep the source data in external storage referenced by presigned URLs so a deletion in primary storage propagates. Nothing about models trained on the data. | sourced [6][7] |
| T2 | Argilla 2.x: `dataset.records.delete(records=...)` deletes records. Argilla 1.x `delete_records` had a `discard_only` flag (mark as discarded instead of deleting). No guidance on models trained on deleted records. | sourced [8][9] |
| T3 | Rasa Pro: `DELETE /conversations/{conversation_id}/tracker` deletes one conversation. The caller has to map a person to their conversation IDs. Training data lives in YAML the user maintains; removing it from a model means editing the files and retraining. | sourced [10][11] |
| T4 | None of these tools tracks which model versions were trained on a deleted record, and none retrains on deletion. decider-ai's `Forgotten.versions_trained_on` already goes further than all three. | inference from T1–T3 |

### Storage

| # | Fact | Basis |
|---|---|---|
| S1 | SQLite's `secure_delete` is normally off. With it off, deleted content stays in the file until overwritten. SQLite: applications that want no forensic traces "should enable the secure_delete pragma prior to performing the delete or update, or else run VACUUM". `FAST` still leaves traces on freelist pages. | sourced [12] |
| S2 | In WAL mode, old page images also sit in the `-wal` file until a checkpoint overwrites or truncates it. | inference (not stated in [12]; verify against sqlite.org/wal.html before relying on it) |

### Facts from the repo that shape the question

| # | Fact | Basis |
|---|---|---|
| R1 | `Decider.forget(ref: ExternalId \| RequestId)` already accepts a `RequestId`. The by-request erasure path exists in the module interface; only the HTTP route is missing. The design's API section still says records without `external_id` "cannot be deleted by this endpoint". | repo (architecture.md, design.md API) |
| R2 | `Imported(task, text, labels, external_id, ...)` has `external_id` as a required field, so every imported example has one. The only confirmed examples without `external_id` come from `decide(...)` without `external_id` followed by `confirm(FromRequest)`. | repo (architecture.md) |
| R3 | Unconfirmed decision text is also stored personal data (kept up to 30 days by default). The ticket and R2-1 talk about confirmed examples; an erasure request may also hit a decision that is still within retention. | repo (design.md Text storage) |
| R4 | `forget` and `DELETE /v1/examples/{external_id}` take no task, so an `external_id` erasure is container-wide unless decided otherwise. Nothing says whether `external_id` is unique per task, per container, or may repeat across several decisions. | repo |
| R5 | The decided `410 REQUEST_EXPIRED` (vs `404` for an unknown request) means the store must remember a purged `request_id` after its text is gone, i.e. a tombstone row without text. The same mechanism can serve forgotten requests. | inference from design.md API |
| R6 | `external_id` may itself be personal data (an email address, a customer number, a mail Message-ID). A tombstone or suppression list that keeps it undoes part of the erasure. | inference |
| R7 | Verdicts are a paired bootstrap of candidate − active on the frozen split, and `Comparison` already records `n`. A deletion makes later comparisons run on fewer items than earlier ones. | repo (architecture.md `evaluation.compare`) |
| R8 | Invariant: "Only `retrain` and `activate` change what trains or what serves." So `forget` may not unload, deactivate or replace the active model. Deleting inactive checkpoint files changes neither, so it is not excluded by the invariant, but it does remove rollback targets. There is no `Decider` method that deletes a model version today. | repo (architecture.md invariants) |
| R9 | A retrain job snapshots its examples when it starts. A `forget` during a running job leaves the erased example in the version that job is about to produce, which `versions_trained_on` cannot list yet because the version does not exist. | inference from architecture.md (`retrain`, `job`, one job at a time) |

## 2. Decisions for the founder

In the order to ask them. The first three settle what gets erased, the rest settle the consequences.

### D1. Erasure path for records without `external_id` (R2-1)

The gap is narrower than R2-1 states (R1, R2): only decisions made without `external_id` and then confirmed via feedback lack a path, and the module interface already accepts a `RequestId`.

| Option | Pros | Cons |
|---|---|---|
| **A. Expose `forget(RequestId)` over HTTP**, e.g. `DELETE /v1/requests/{request_id}` (route shape left to ticket 0010). Erases the decision text and any example confirmed from it. | No interface change. Keeps the drop-in promise (`external_id` stays optional). Covers unconfirmed decisions too (R3). | Works only if the caller kept the `request_id`. A caller that stored neither ID cannot find the record. |
| B. Require `external_id` on `confirm(FromRequest)` (feedback must name one). | Every confirmed example gets a stable, caller-meaningful key. | Changes `FromRequest` and the n8n "Send feedback" operation. Does nothing for unconfirmed decisions. A caller who doesn't know the ID at feedback time can't confirm. |
| C. Require `external_id` on every `decide`. | One erasure key everywhere. | Breaks the drop-in shape of the LLM call it replaces. |
| D. A + a lookup by text (find records whose stored text contains a string). | Recovers records whose IDs were lost. | Adds a text-returning or text-matching surface to a product sold on "no text leaves the server"; more to secure. |

**Recommendation: A.** The interface already supports it, so this is an HTTP route plus doc wording, and it closes R2-1 for every stored record. Docs should tell callers to pass `external_id` or store `request_id` if they may receive erasure requests. Reject D for Phase 1 (CNIL [3] lets a controller who cannot identify a record say so, and asks it to anticipate; storing the ID is that anticipation).

### D2. What one `forget` call erases

R3, R4 and R6 leave the reach of a single call undefined.

| Option | Pros | Cons |
|---|---|---|
| **A. `forget(ExternalId)` erases every decision and example with that ID in every task; `forget(RequestId)` erases that decision and the example confirmed from it.** Keep only a text-free, `external_id`-free tombstone of affected `request_id`s. No suppression list. | Matches what an erasure request means (all of this person's records). Tombstone stores no personal data (R6). Agrees with CNIL's warning about blacklists [3]. | A later import with the same `external_id` re-adds the data; that is the caller's responsibility and must be documented. |
| B. Scope `forget` to one task (add a `task` argument). | Precise; avoids hitting an unrelated task that reuses IDs. | Interface change; an erasure across several tasks needs several calls and is easy to get incomplete. |
| C. As A, plus keep a suppression list of erased `external_id`s that blocks re-import. | Prevents accidental re-ingestion. | Retains the identifier the person asked to erase; CNIL [3] flags such lists as a membership-inference risk. |

**Recommendation: A.** It keeps the interface as is and errs on the side of erasing more. `Forgotten` should count decisions as well as examples, or the doc should say `examples_removed` includes unconfirmed decisions; that is a field-level detail for the session.

### D3. Physical erasure in SQLite

"Erases stored text" is not true by default (S1, S2).

| Option | Pros | Cons |
|---|---|---|
| **A. `PRAGMA secure_delete = ON` on every connection, plus a WAL checkpoint with truncate after each `forget`.** | Deleted text is zeroed in the main file and leaves the WAL promptly. Cost is small at this data size. Also covers the retention purge. | Slightly more write I/O on every delete and update. |
| B. `VACUUM` after each `forget`. | Rewrites the file without the deleted content. | Rewrites the whole database and blocks writers; grows with the store. |
| C. Document only ("deleted rows may persist on disk until compaction"). | No code. | Contradicts "erases stored text" and the privacy pitch. |

**Recommendation: A.** It makes the API's claim true for the database file. The docs still need to say that volume backups and snapshots are the operator's responsibility.

### D4. Feedback on a forgotten request (confirm the decided 410)

`410 REQUEST_EXPIRED` for purged requests is decided. The only possible conflict: a forgotten request is not "expired", and `confirm`'s per-item reasons ("unknown or expired request") don't name erasure.

| Option | Pros | Cons |
|---|---|---|
| **A. Treat forgotten like purged: same tombstone (R5), same `410 REQUEST_EXPIRED`, same `Outcome` reason.** | One rule, one code; nothing new for the n8n node. Reveals nothing about why the text is gone. | The code name is slightly inaccurate for an erasure. |
| B. Separate code, e.g. `410 REQUEST_ERASED`. | Precise. | A second code clients must handle, for a case they can't act on differently. |
| C. Drop the tombstone on erasure, so feedback returns `404`. | Erases even the `request_id`. | Indistinguishable from a typo; the `request_id` is a random ID, not personal data, so there is little gained. |

**Recommendation: A.** No conflict with the decided 410; it extends it.

### D5. The frozen split after a deletion (R2-2, first half)

| Option | Pros | Cons |
|---|---|---|
| **A. Shrink and stay frozen. The ≥10-per-label minimum applies only at freeze time. `status` shows the split's current size and names labels now below 10. Top-up only via explicit `refresh_split`.** | Nothing changes by itself (matches the no-automatic-change rule). Later comparisons stay paired on a stable set. | The split can erode until verdicts get wide CIs; the operator has to notice and refresh. |
| B. Shrink; unfreeze automatically when any label drops below 10, so new candidates become `unverified` until a refresh. | Never gives verdicts on a thin label. | One erasure can silently remove recommendations for every future job; an automatic state change. |
| C. Top up automatically from confirmed examples. | Keeps size at 100. | Any confirmed non-split example may already be in an existing version's training data, which would contaminate that version's evaluation; an automatic change to evaluation. |

**Recommendation: A.** It is the reviewer's first suggested remedy, keeps every change explicit, and the bootstrap CI already widens honestly as `n` falls. Interacts with ticket 0008 (rare-label fallback): whatever 0008 decides for "split never formed" should not be reused for "split formed, then shrank" without saying so.

### D6. Verdicts computed before a deletion (R2-2, second half)

| Option | Pros | Cons |
|---|---|---|
| **A. Keep existing verdicts unchanged. Each verdict records the split revision and `n` it was computed on; `models()` and `GET /v1/models` show both, so older verdicts are visibly on a different split.** | Cheap; no recomputation; history is truthful. | The operator compares verdicts across revisions by reading `n`. |
| B. Recompute all stored verdicts on the shrunken split, from stored per-example predictions of each version. | All verdicts comparable. | Must store per-example predictions per version (and delete them on `forget`); a verdict can flip from `recommended` to `not_recommended` without the user acting. |
| C. Mark pre-deletion verdicts `stale`. | Clear signal. | Every erasure stales every verdict; a new state for clients to handle. |

**Recommendation: A.** `Comparison` already carries `n` (R7); adding a split revision is the minimum that lets a reader tell verdicts apart.

### D7. Checkpoints trained on erased data (R3-12, architecture.md open question)

Constraint: `forget` may not change what serves (R8), and nothing retrains by itself.

| Option | Pros | Cons |
|---|---|---|
| A. Keep, report only: `forget` returns `versions_trained_on`, docs say weights persist until the user retrains and activates. (Current interim.) | Already designed. Matches CNIL's "periodic retraining" [3]. | The fact is visible only in the `forget` response; a later `activate` of an affected version gives no hint. |
| **B. A + persistent flag: each version records how many of its training examples were later erased; `models()` shows it; `activate` of a flagged version succeeds with a warning (as for `unverified`).** | Reuses the existing warn-don't-block pattern. Keeps the evidence an operator needs for a one-month response deadline (L4). | A counter per version; one more warning text. |
| C. B + a new `Decider` method to delete a model version's checkpoint (refusing the active one). | Lets the operator remove old checkpoints that hold erased data without waiting for new training; frees 678 MB per version. | Interface change (a 9th method); removes rollback targets. |
| D. Refuse `activate` of flagged versions. | Stops rolling back to erased data. | A single erasure can block every rollback target; contradicts the warn-don't-block rule for activation. |

**Recommendation: B.** It turns a one-time response into lasting state without breaking any invariant. Raise C as a candidate follow-up; it is the only option that actually removes erased data from disk short of overwriting versions, but it changes the interface, so it is the founder's call. Docs should state plainly (L7) that the checkpoint is not anonymous and that retrain + activate is the remedy.

### D8. `forget` while a retrain job is running (R9)

| Option | Pros | Cons |
|---|---|---|
| **A. Allow it; record the erasure against the running job, so its version is flagged (D7) when it finishes; `Forgotten` names the job.** | `forget` never blocks; the flag stays correct. | `Forgotten` needs a job field, or the doc says pending versions are flagged later. |
| B. Cancel the running job. | The erased example never reaches a finished version. | `forget` would change what trains, against the invariant in R8. |
| C. Raise `Busy` and make the caller retry after the job. | Simple. | An erasure request waits up to an hour (training at 250 examples). |

**Recommendation: A.**

## 3. Facts that change the ticket's question

1. **The request-ID path already exists in the interface (R1).** "Deleting by `request_id` when no `external_id` exists" is an HTTP-route and doc question, not a design gap. design.md's API section and R2-1 predate or ignore `forget(ExternalId | RequestId)`.
2. **The gap is only feedback-confirmed decisions without `external_id` (R2).** Imports always carry an ID.
3. **Unconfirmed decisions are in scope (R3).** The ticket only names confirmed examples, but text within the 30-day retention window is also stored and must be erasable.
4. **"Erases stored text" is false under SQLite defaults (S1).** The ticket does not mention physical deletion; D3 is new.
5. **A running job breaks `versions_trained_on` (R9).** D8 is new.
6. **"Keep until next retrain" is only half a policy.** A retrain produces a new version; it does not remove old checkpoints. Without D7 option C (or a retention rule for versions), erased data stays on disk in every older version indefinitely, regardless of what is active.
7. **The regulator position supports the interim design (L1, L4).** The checkpoint can't be called anonymous, but retraining (batched) is the accepted remedy, so "report, don't auto-retrain" is defensible, provided the operator can see which versions are affected over time (D7 B).

## Sources

1. EDPB, Opinion 28/2024 on certain data protection aspects related to the processing of personal data in the context of AI models, adopted 17 Dec 2024. https://www.edpb.europa.eu/system/files/2024-12/edpb_opinion_202428_ai-models_en.pdf (paras 42–43, 114–115; accessed 2026-10-08)
2. HmbBfDI (Hamburg DPA), Discussion Paper: Large Language Models and Personal Data, 15 Jul 2024. https://datenschutz-hamburg.de/fileadmin/user_upload/HmbBfDI/Datenschutz/Informationen/240715_Discussion_Paper_Hamburg_DPA_KI_Models.pdf
3. CNIL, "Ensuring and facilitating the exercise of data subjects' rights", page dated 5 Jan 2026. https://cnil.fr/en/ensuring-and-facilitating-exercise-data-subjects-rights (accessed 2026-10-08)
4. PPC Land, "CNIL finalizes recommendations for AI system development under GDPR" (on the 22 Jul 2025 publication). https://ppc.land/cnil-finalizes-recommendations-for-ai-system-development-under-gdpr/
5. Shokri, Stronati, Song, Shmatikov, "Membership Inference Attacks Against Machine Learning Models", IEEE S&P 2017. https://arxiv.org/abs/1610.05820
6. Label Studio API reference, Delete task. https://api.labelstud.io/api-reference/api-reference/tasks/delete (accessed 2026-10-08)
7. Label Studio API reference, Delete annotation. https://api.labelstud.io/api-reference/api-reference/annotations/delete (accessed 2026-10-08)
8. Argilla docs, Records how-to guide (2.x). https://docs.argilla.io/latest/how_to_guides/record/ (accessed 2026-10-08)
9. Argilla 1.x Python client reference, `delete_records`. https://docs.v1.argilla.io/en/v1.26.0/reference/python/python_client.html
10. Rasa Pro HTTP API, Delete tracker for a specific conversation. https://rasa.com/docs/reference/api/pro/http-api/tracker/delete-tracker-for-a-specific-conversation.md (accessed 2026-10-08)
11. Rasa forum, "Delete a conversation log with its sender_id". https://forum.rasa.com/t/delete-a-conversation-log-with-its-sender-id/50144
12. SQLite, PRAGMA statements: `secure_delete`. https://www.sqlite.org/pragma.html#pragma_secure_delete (accessed 2026-10-08)
