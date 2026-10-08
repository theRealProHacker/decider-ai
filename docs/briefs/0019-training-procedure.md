# Brief: Training procedure (ticket 0019)

Prepared 2026-10-08 for the founder's live grilling of [issue 0019](../../issues/0019-training-procedure.md). This brief **decides nothing**. It collects the facts, lays out each decision with options, and gives a recommendation per decision for the founder to accept or overrule.

Inputs read: the ticket, the [map](../../issues/0001-map-decider-ai-engineering.md), `docs/design.md` (Retrain and activation, frozen split rules, Track 1), `docs/architecture.md` (`Backend.train`, `evaluation`), [Laya checkpoint facts](../research/laya-checkpoint-facts.md), [Public benchmark datasets](../research/public-benchmark-datasets.md), and the upstream sources below.

Fact labels as in the checkpoint-facts note: **sourced** (stated in a linked source), **measured** (run on the founder's laptop for ticket 0003), **estimated** (derived; derivation shown).

## Sources pinned

| Short name | Source | Revision |
|---|---|---|
| SDK | [NandhaKishorM/laya](https://github.com/NandhaKishorM/laya), Apache-2.0 | `3cf26cbcb18725dbc2d127bb8bb2c4c43243ae63` (HEAD, 2026-10-07; `pyproject.toml` version 0.4.0) |
| SDK wheel | [`laya` on PyPI](https://pypi.org/project/laya/), Apache-2.0 | 0.4.0 (uploaded 2026-10-07). Its `laya/train.py` is byte-identical to the repo file at `3cf26cb` (sha256 `71c83361…d9fed34`). |
| Guide | SDK `docs/finetune.md` | same commit |
| Notebook | SDK `notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb` | same commit |
| Card | [`convaiinnovations/laya-multilingual` README](https://huggingface.co/convaiinnovations/laya-multilingual/blob/1720e3e3357cfe1e281542e223f8273b0890ca34/README.md) | `1720e3e3` (current `sha`) |
| #963 | [laya issue #963](https://github.com/NandhaKishorM/laya/issues/963), "the fixed 4-epoch default collapses to the class prior on small datasets" | open |
| lft | [tehtommeh/laya-finetuning](https://github.com/tehtommeh/laya-finetuning) `docs/FINETUNING.md`, `docs/EXPERIMENTS.md`. **No licence: read for facts only. Nothing here assumes its code is reused.** | `2c39f675f512ffacdd567c7541aef6ad3631cf61` |

Links below of the form `train.py L78–124` point into `https://github.com/NandhaKishorM/laya/blob/3cf26cbcb18725dbc2d127bb8bb2c4c43243ae63/laya/<file>#L<n>`.

## 1. Facts

### 1.1 The SDK now ships the training loop, and it runs on CPU

- **`laya.train` is part of the Apache-2.0 package.** `finetune(data, model_dir, output_dir, config, device)` runs the full loop: build items, hold out a calibration slice, train, fit temperatures, save a checkpoint `laya.load` opens (`train.py` L959–1245). The lower-level halves are public too: `train_model` (L621–706), `calibration_records` (L709–721), `split_calibration` (L474–490), `load_checkpoint` (L573–587, loads to **CPU in fp32**), `save_checkpoint` (L590–604), `dry_run` (L1248). A CLI wraps it: `laya-train` (`train_cli.py`). (sourced)
- **CPU is a supported device.** Guide L21–23: "`laya-train` … runs on one device: CUDA, MPS or CPU." This contrasts with laya-finetuning, which exits without CUDA (checkpoint facts §5). (sourced)
- **It is very new.** First PyPI release containing `laya/train.py` is **0.3.28 (2026-10-05)**. 0.3.24–0.3.27 do not contain it (checked wheel listings). It was added to the repo on 2026-10-03 (commit `deb477d`). Later changes: CLI and CSV loaders (`fb74cb9`, 10-04), `--eval` and abstention thresholds (`212bdfa`, 10-05), the prior-collapse warning (`923ff82`, 10-06). 0.4.0 followed on 10-07 with a breaking router change (`3cf26cb`, "feat(router)!"). (sourced)
- **The canonical design copy already says "built fresh".** `~/.gstack/projects/decider-ai/rharvey-main-design-20261008-040445.md` line 68 reads: "`LayaBackend` (built fresh on the Apache-2.0 `laya` SDK; https://github.com/tehtommeh/laya-finetuning is reference reading only)". Its Dependencies section says the same. The repo's `docs/design.md` (Track 1 item 1, Dependencies) still says "reusing" laya-finetuning. The two copies disagree. (sourced; not edited here)

### 1.2 Recipe defaults (SDK = notebook)

- `TrainConfig` defaults (`train.py` L91–124; Guide L106–118): `epochs=4`, `micro_batch=8`, `grad_accum=8` (effective batch 64), `encoder_lr=2.5e-5`, `head_lr=1e-4`, `min_lr=1e-6`, AdamW with `weight_decay=0.01`, cosine schedule, `grad_clip=1.0`, `loss="rlcd"`, `calib_max=400`, `calib_frac=0.1`, `calib_seed=20260922`, `seed=0`, `max_len`/`head_max_len` from the checkpoint config (1024/256 for laya-multilingual). (sourced)
- The notebook uses the same values (notebook cell 8: `EPOCHS = 4`, `MICRO_BATCH = 8`, `GRAD_ACCUM = 4` × 2 GPUs, `LR_ENCODER = 2.5e-5`, `LR_HEAD = 1.0e-4`, cosine `eta_min=1e-6`). (sourced)
- **The cosine schedule is sized in optimiser updates**: `updates = ceil(ceil(n_items / micro_batch) / grad_accum) × epochs` (`train.py` L649–650). (sourced)
- Options worth knowing (Guide L106–149):
  - `--loss soft-ce` scored 0.790 vs 0.7715 for `rlcd` on typed-decisions (one seed, one T4).
  - `--shuffle-options` re-encodes choice options in random order each epoch. At 20 options (MASSIVE intent, English) it raised accuracy by 0.55 points and cut reorder-flips by about a quarter, for ~14% more training time. "Use it when questions have many options." MASSIVE `de-DE` scenario has 18 options.
  - `--freeze-encoder` trains only the head: "fits a small GPU or a CPU, but gains much less than a full fine-tune".

  (sourced)

### 1.3 Data size: the epoch question is an update-count question

- **lft's "12 epochs below ~300 cases" is measured on multi-question cases.** In the typed-decisions setup each case carries 5 questions (FINETUNING.md L115–139: "150 cases (≈750 answers)"). At 150 cases, 4 epochs = 48 updates and 12 epochs = 144 updates, which gave +3.2 points (EXPERIMENTS.md L91–97). Seed variation was under 1 point there (EXPERIMENTS.md L93). Gains flatten at ~150 cases **per question set** (FINETUNING.md L135). (sourced)
- **A decider example is one question, so one sequence.** One decider example is a fifth of an lft case. 250 decider examples ≈ 50 lft cases in sequences. (estimated)
- **Updates at decider sizes with the SDK defaults** (estimated with the formula above, after the SDK's 10% calibration slice):

  | Confirmed training examples | SDK calibration slice | Items trained | Updates at 4 epochs | at 12 epochs |
  |---|---|---|---|---|
  | 50 | 5 | 45 | **4** | 12 |
  | 100 | 10 | 90 | 8 | 24 |
  | 250 | 25 | 225 | 16 | 48 |

- **#963 measured silent collapse at 72 updates.** Multilingual, ~1,100 items, 4 options, notebook defaults: "With the defaults (72 optimiser updates in total), the model ended at chance". It took up to 32 epochs at constant LR to learn, and "Takeoff depended on the seed": 9 of 15 runs left the ln K plateau, 6 never did. For comparison, the typed-decisions default budget is ~375 updates. #963 proposals: early stopping on the calibration slice, budget in updates not epochs, document a minimum number of updates. Only the **warning** landed: `prior_collapse_message` (`train.py` L930–956) warns when the mean within-row logit range is below 0.05 or calibration CE is within 2% of ln K. (sourced)
- **CPU time scales with sequences × epochs, not with updates.** A smaller effective batch (lower `grad_accum`) gives more updates for the same CPU time. Tripling the epochs triples the time. (estimated, from checkpoint facts §5: 3.5 s per ~456-token sequence)
  - 4 epochs: 50 examples 11.8 min (measured), 250 examples ~59 min (estimated).
  - 12 epochs: ~35 min at 50 and **~3 h at 250** on the laptop (estimated, ×3).

### 1.4 Precision, threads, memory

- **bf16 training fails on the laptop CPU** (AVX2-VNNI, no AMX): oneDNN refuses bf16 backward (checkpoint facts §5). (measured)
- **The SDK trains CPU in fp32 by default.** `amp` defaults to on for CUDA only (`train.py` L86, L629). Its CPU inference is fp32 unless `LAYA_CPU_AMP=bf16`, "only on hardware with native BF16 instructions, which is why it stays opt-in" (`agent.py` L313–320). (sourced)
- **Gradient checkpointing is off on CPU by default**: it "defaults to following `amp`" (`train.py` L86, L630). **The 8.5 GB training peak was measured with checkpointing on** (checkpoint facts §6: "Training, 4 threads, batch 8, gradient checkpointing"). The SDK-default CPU peak is therefore unmeasured and will be higher. (sourced + judgement)
- **Threads.** `laya.train` never calls `torch.set_num_threads`. Only the SDK's HTTP server honours `LAYA_THREADS` (`serve.py` L818–834). On the laptop, 8 threads were slower than 4 (5.0 vs 3.5 s per sequence; 4 P-cores + 4 E-cores) (measured). The design's default cap is half the CPUs. **Unverified:** whether a training thread and the serving threads can hold different intra-op thread counts inside one Python process. `torch.set_num_threads` is process-wide in practice, which matters because decider trains in a background thread of the serving process. (judgement; needs a prototype)

### 1.5 Calibration

- **The temperature is fitted on a slice held out before training**: `min(calib_max=400, int(n × 0.1))` items, shuffled with the fixed `calib_seed`, independent of the run seed (`train.py` L474–490, L984). The slice is **random: not stratified, not group-aware**. (sourced)
- **Floors.**
  - Fewer than **10** items of a type (`MIN_TYPE_N`, `calibrate.py` L39): no fit, temperature stays 1.0, with a warning (`train.py` L761–763).
  - Fewer than **50** items (`CALIB_WARN_N`, `train.py` L66): fitted, with a warning "on only N items".
  - Per-option-count buckets need **2,000** items (`MIN_BUCKET_N`, `calibrate.py` L37). At decider sizes only the type-level scalar is ever fitted.

  (sourced)
- **What the slice means at decider sizes** (estimated, with the SDK default): 50 training examples → 5 items held out → **no temperature fitted, and 10% of the data lost for nothing**. 100 → 10 items, fitted on the minimum. 250 → 25 items, fitted with a warning.
- **Interaction with the frozen split.** At 149 confirmed examples, everything is training data (14 calibration items). At 150 the split freezes (100 examples), so training drops to **50** and calibration falls back below the floor again. It only returns at ≥200 confirmed. (estimated from `docs/design.md` split rules)
- **Temperature scaling does not move the argmax**, so accuracy and macro-F1 are unchanged (Guide L237–238). A verdict computed on the frozen split is unaffected by whatever temperature is fitted. (sourced)
- The card: the checkpoint "Ships uncalibrated … systematically over-confident". Refitting "on held-out data moves mean ECE 0.314 → 0.106. Do this on your own data before trusting the probabilities." (sourced)
- **Recalibration without retraining is supported.** `calibration_records` + `fit_temperature_map` (`calibrate.py` L250) work on any labelled records, and `Agent.save_calibration` (`agent.py` L2008) / `apply_calibration_payload` (`calibrate.py` L506–698) persist a temperature payload. The Guide warns to drop inherited `temperature_by_options` (Guide L232–235; `train.py` L1187 does it). (sourced)

### 1.6 One checkpoint, several questions

- **A checkpoint can be trained on several questions at once.** A JSONL row "may ask several questions of any type" (Guide L52–60). The typed-decisions checkpoint is one model over 4 workflows × 5 questions. `laya.Agent.predict(state, questions)` answers several questions in one call. Each question is still its own sequence, so a multi-question call saves the state tokenisation, not the forward passes (`agent.py` L1132–1185, "Tokenize the shared state once"). (sourced)
- Memory per loaded checkpoint is ~1.6 GB (1.8 GB RSS for one), with a 4.2 GB transient peak while loading. Disk is 678 MB per version (checkpoint facts §6–7). (measured)

### 1.7 Token limit and truncation

- **`laya.common.state_room(tok, q, max_len, head_max_len)`** returns exactly how many state tokens a question leaves. "Anything past the return value is cut off" (`common.py` L350–358). It depends on the question and its options, so it is fixed per task version. (sourced)
- `build_sequence` clamps the state silently, and the docstring warns that character thresholds are wrong both ways (#174) (`common.py` L178–190, L199–204). `Agent.predict` reports `usage["truncated"]`, `state_tokens` and `state_tokens_dropped` (`agent.py` L1915–1918). (sourced)
- **Training truncates silently too.** `encode_state` caps state ids at `max_len` (`train.py` L287–290), `build_sequence` clamps to the room, and `finetune`'s `skipped` counts only head problems (`options_collapsed`, `options_beyond_max_len`), never state truncation (`train.py` L293–314; Guide L77–86). (sourced)
- `serialize_state(str)` returns the string unchanged (`common.py` L94–97), and the SDK replaces the mask token with a space before tokenising (`train.py` L289; `agent.py` L1149–1153). A pre-check must tokenise the same way to agree with the SDK. (sourced)
- The card: "Keep `choice` questions under ~20 options", because options share the 256-token head budget. (sourced)

### 1.8 Seeds and determinism

- **SDK seeding:** `torch.manual_seed(config.seed)` once, option-order RNG `random.Random(seed)`, epoch shuffle `random.Random(seed + epoch)` (`train.py` L654–660). The calibration slice uses the separate fixed `calib_seed` (L984). There is **no `torch.use_deterministic_algorithms`** and no thread pinning, and dropout is active in training. (sourced)
- The MPS script uses `seed=42` with the same `calib_seed=20260922` (`notebooks/laya_finetune_typed_decisions_mps.py` L110–115). (sourced)
- lft: "GPU kernels are not bit-deterministic, so exact decimals will differ", and reruns reproduce "within about a point" (EXPERIMENTS.md L202–203). **CPU rerun determinism for this model is unmeasured.** fp32 reductions can differ with thread count. (sourced + judgement)
- #963: whether training takes off at all depended on the seed (§1.3). (sourced)

### 1.9 Checkpoint layout

- `save_checkpoint` writes `model.safetensors` (**fp16**), `encoder/` config, `tokenizer/`, and `rl_agent_config.json` (written atomically via `.tmp` + `os.replace`) (`train.py` L590–604).
- `finetune` additionally writes `questions.json`, `train_report.json` and a rolling **`checkpoint_latest/`**: a second full copy rewritten after every epoch (`train.py` L1091–1093; Guide L90–92). On CPU that is another ~678 MB written per epoch.
- The trained model is fp32 in memory but saved in fp16, so the model that serves after reload is not bit-identical to the one that just trained.

(sourced)

## 2. Decisions for the founder

One per section, in the order to grill them.

### D1. Rebuild from the SDK, or wait for the laya-finetuning licence (dependency note only)

**Ticket 20 owns this decision.** It is listed here only because every later decision assumes an answer.

| Option | Pros | Cons |
|---|---|---|
| A. Build `LayaBackend` on `laya.train` (SDK, Apache-2.0) | No licence dependency. CPU is supported. Calibration, collapse warning and checkpoint writer are maintained upstream. Matches the canonical design copy (§1.1). | The API is 3 days old on PyPI and changing daily (§1.1). A version must be pinned, and the checkpoint facts (measured on laya 0.3.6 + the lft loop) re-measured. |
| B. Wait for a licence on laya-finetuning | Its loop is the one measured in ticket 0003. | Blocks Track 1 on a third party. Its code is CUDA-only and needs the same CPU changes anyway. The SDK now covers what it was wanted for. |

**Recommendation: A**, as an input to ticket 20. The SDK now contains the loop that was the reason to reuse laya-finetuning. Ticket 20 can probably close as "not needed". Separately: decide the pin (0.3.28 first had `laya.train`; 0.4.0 is current, one day old). Also reconcile the repo `docs/design.md` with the canonical copy that already says "built fresh".

### D2. Precision and threads

| Option | Pros | Cons |
|---|---|---|
| A. fp32 always. Thread cap = design default (half the CPUs), configurable. Gradient checkpointing explicitly on. | Works on every x86 CPU. Matches what was measured (8.5 GB peak needs checkpointing on, §1.4). One code path. | Leaves AMX/AVX-512-BF16 server speed unused. Half the CPUs is wrong on hybrid P/E chips (on the laptop, 4 was optimal because 4 were P-cores). |
| B. fp32 by default, bf16 autocast opt-in when the CPU supports bf16 backward | Possibly much faster on server CPUs. | Unmeasured for training speed and accuracy. Two numerical paths to test. The verdict compares models trained under different precisions. |
| C. A as default, plus `freeze_encoder` as a low-memory mode | Head-only training needs far less memory and time. | Guide: "gains much less than a full fine-tune". It would be a second recipe whose quality Phase 0 does not measure. |

Sub-point to settle either way: the thread cap must be applied to the training thread without starving `decide`. Whether that is possible inside one process is unverified (§1.4), so it needs a prototype before the default is written down.

**Recommendation: A.** fp32 is the only precision measured to work on the target class of hardware, and checkpointing on is what made the 8.5 GB figure true. Keep the cap configurable (`DECIDER_TRAIN_THREADS`), defaulting to the design's half the CPUs. Revisit bf16 only after a server CPU is measured (ticket 0012 / 0013).

### D3. Epochs and learning-rate schedule by data size

| Option | Updates at 50 / 100 / 250 examples | CPU time (laptop, ~460-token mail) | Evidence |
|---|---|---|---|
| A. SDK defaults: 4 epochs, effective batch 64, cosine | 4 / 8 / 16 | 12 min / ~24 min / ~1 h | Defaults are tuned for ~6,000 items. #963 collapsed at 72 updates. |
| B. lft rule: 12 epochs below 300 examples, else 4. Same LR and batch. | 12 / 24 / 48 | ~35 min / ~72 min / **~3 h** | +3.2 points at 150 lft cases (48 → 144 updates). That was measured on English, multi-question data, and its update counts are still above decider's. |
| C. Budget in updates: smaller effective batch (e.g. `grad_accum=1`, batch 8) plus epochs chosen to reach a minimum of N updates | e.g. 24 / 48 / 116 at 4 epochs | same as A at the same epochs | #963 proposal 3. Untested on Laya: a batch of 8 is noisier, and the LRs were tuned at 64. |
| D. Early stopping: train up to E_max epochs at constant LR, keep the best epoch on a held-out slice | variable | up to E_max × the per-epoch cost | #963 proposal 2. Not in the SDK. Needs a held-out slice big enough to choose on, which competes with the 50-example minimum and the calibration slice. |

Two related knobs to fix in the same breath:

- **`shuffle_options=("choice",)`**: the Guide recommends it for many options, and MASSIVE has 18. It costs ~14% more time.
- **Loss**: keep `rlcd`, which is what was measured, or switch to `soft-ce` (0.790 vs 0.7715, one seed, and untested for the #963 plateau).

**Recommendation: B as the pinned starting recipe, plus a Phase 0 pilot that compares B with C before the 5-seed grid**, with `shuffle_options` on and the loss left at `rlcd`. B is the only option with a measured gain on Laya. A is very likely under-trained at every decider size (4–16 updates). C is free in CPU time but unproven. The pilot is one dataset × {50, 250} × 2 seeds × 2 recipes, run on the laptop. Accept that B triples training time below 300 examples (~3 h at 250 on the laptop). Whether that is acceptable belongs to [Non-functional targets](../../issues/0012-non-functional-targets.md).

### D4. Calibration slice, the frozen split and the 50-example minimum

| Option | Pros | Cons |
|---|---|---|
| A. SDK default inside `finetune`: random 10%, fixed `calib_seed`, not group-aware | Zero code. | At 50 examples, 5 are held out and nothing is fitted (§1.5), so 10% of the data is lost for nothing. Threads (`group_id`) can leak between train and calibration. Calibration disappears again when the split freezes at 150. |
| B. decider-owned slice: carved group-aware from the training pool only when the pool has ≥100 examples (so ≥10 items), otherwise train on everything. Temperature stays 1.0 and the version is marked "uncalibrated" in `models()`. Uses `train_model` + `calibration_records` + `fit_temperature_map`. | The 50 minimum stays fully usable. The splitting logic lives in `evaluation`, which already owns group-aware splits (architecture). The test split stays clean. | Calibration rests on 10–25 items for most Phase 1 users (the SDK warns below 50). More code than A. |
| C. Fit the temperature on the frozen 100-example test split, after the verdict is computed | 100 items, always above the floor. No training data lost. The macro-F1 verdict is unaffected, because temperature does not move the argmax (§1.5). | No split exists below 150, so it needs a fallback anyway. Test data fits a parameter, so no calibration metric can be reported honestly on that split. It strains the invariant "Test-split examples never reach `Backend.train`". |
| D. No calibration in Phase 1: ship temperature 1.0 and document scores as uncalibrated | Simplest. | The card says the base is over-confident and to calibrate "before trusting the probabilities". decider's design makes callers threshold on scores (the caller owns the low-confidence fallback). |

**Recommendation: B.** It is the only option that keeps a 50-example retrain whole, respects group-awareness, and keeps the frozen split purely for verdicts. State the cost honestly in the docs: confidences are calibrated on few items, and are uncalibrated below 100 training examples, including right after the split freezes at 150. If the founder values calibration quality over split purity, C is the strongest alternative.

### D5. One checkpoint per task, or one checkpoint for several tasks

| Option | Pros | Cons |
|---|---|---|
| A. One checkpoint per task (current design) | Per-task retrain, verdict, activate and rollback stay independent. Task versioning (ticket 0018) stays per task. Matches `Backend.train(base, task, …)`. | ~1.6 GB RAM per loaded task and 678 MB disk per version. |
| B. One multi-task checkpoint trained on all tasks' questions | One resident model (~1.6 GB) whatever the task count. Supported by the SDK (§1.6). | Retraining one task changes every task's answers, so a per-task verdict and rollback lose their meaning. Every retrain needs every task's data. Collides with per-task versions and the frozen split per task. |
| C. A, plus lazy load or a cap on resident checkpoints | Bounds RAM with many tasks. | Cold-task latency includes a load with a 4.2 GB transient peak. More moving parts in the atomic swap. |

**Recommendation: A**, with the memory formula published (≈ 0.25 + N_tasks × 1.6 + 1.6 swap + training peak GB). B breaks the per-task activation model the whole product is built on. C is a later answer if users run many tasks (ticket 0012).

### D6. Token-limit check before the SDK truncates

| Option | Pros | Cons |
|---|---|---|
| A. Pre-check. `LayaBackend.max_input(task)` = `laya.common.state_room(...)`, computed once per task version. `decide` tokenises the text the same way the SDK does (§1.7) and returns `INPUT_TOO_LONG` above the limit. The same check runs on `confirm(Imported)`, so no over-length example reaches training. | Exact. No wasted forward pass. Training never truncates silently either (§1.7). | Each request is tokenised twice (cheap compared with the forward pass). Relies on the SDK's mask-replacement detail staying stable, so pin the version. |
| B. Post-check. Call `predict` and reject when `usage["truncated"]` is set. | Uses the SDK's own measure. No duplicated tokenisation logic. | Spends ~0.3 s of CPU per rejected request. Does not cover import or training. |
| C. Character limit in `tasks.yaml` | Trivial. | The SDK documents it as wrong both ways (#174). |
| D. Raise `max_len` (the encoder supports 8,192) so the limit rarely binds | Fewer 413s for long mail. | Changes the measured recipe: training time and memory grow with sequence length. Out of step with the 1,024-token training default. |

Linked sub-point: `tasks.yaml` "max input length" can only *lower* the limit, because the question and options fix the room. Either drop the field and derive it, or validate it as ≤ `state_room` in tokens at load.

**Recommendation: A, with B's `usage["truncated"]` asserted as a defensive check.** Derive the limit from `state_room` and let `tasks.yaml` only lower it. A is the only option that also covers the import and training path, which the SDK truncates without reporting.

### D7. Seeds: Phase 0 vs product retrains

| Option | Pros | Cons |
|---|---|---|
| A. Phase 0: seeds 0–4. Each seed drives the training subset (as for TF-IDF+LR), the SDK `seed`, and decider's calibration slice. Product: always seed 0. | Simple. Product runs are reproducible on the same machine and thread count. | A retrain on the same data repeats the same outcome, including a #963-style collapse. The user cannot "try again". |
| B. Phase 0 as A. Product: a fresh random seed per job, **stored on the model version**. | Retrying a collapsed or unlucky run is just another `retrain`. Still reproducible from the record. | Two retrains on identical data can disagree, which can surprise a user comparing versions. |
| C. Phase 0 as A. Product: train k seeds per job and keep the best on the calibration slice. | Hedges #963's seed dependence. | k× CPU (hours on a laptop). Selection on a 10–25-item slice is noise. |

In every option, also fix and record the torch version and thread count for Phase 0, because CPU bit-determinism is unmeasured (§1.8).

**Recommendation: B.** Phase 0 measures the expected outcome over seeds, which is what a product user gets from one run with an arbitrary seed. A recorded seed keeps every version reproducible. A fixed product seed would turn a seed-dependent collapse into a permanent one for that dataset.

### D8. Checkpoint format and retention

| Option | Pros | Cons |
|---|---|---|
| A. SDK layout as-is, every version kept until the user deletes it | No automatic loss of a rollback target, in line with "nothing changes by itself". | Disk grows 678 MB per retrain (e.g. ~14 GB for 2 tasks × 10 versions). Needs an explicit delete-version operation (API shape belongs to 0010; erasure to 0009). |
| B. Keep the last K versions per task automatically, never the active or previous one | Bounded disk. | Silently removes rollback targets. Arguably against the spirit of the no-automatic rule (decision 83b5e76c), which covers retrain and activation, not deletion. Interacts with erasure policy (0009). |
| C. Keep only active + previous + newest candidate | Smallest disk. | Strong automatic deletion, and the history in `models()` points at missing files. |

Applies under every option:

- Write fp16 safetensors via `save_checkpoint` (SDK layout, loads with `laya.load`).
- Delete `checkpoint_latest/` after a successful run, or skip `finetune` and call `train_model` + `save_checkpoint` directly, which avoids writing it at all.
- Discard partial outputs when a job is interrupted (R2-11).
- **Score the candidate from the reloaded fp16 checkpoint**, not the in-memory fp32 model, so the verdict describes what will serve (§1.9).

**Recommendation: A.** It is the only option where nothing disappears without a user action. Disk cost is predictable and can be documented. Ask tickets 0009/0010 for the explicit delete operation rather than inventing pruning here.

## 3. Facts that change the ticket's question

1. **"Pin the CPU recipe" is now "configure `laya.train`", not "port a GPU loop".** The SDK trains on CPU in fp32 out of the box (§1.1, §1.4). This mostly moots ticket 20 for code purposes (D1). The ticket's framing ("given laya-finetuning") is out of date, and so is the repo copy of `docs/design.md`, which disagrees with the canonical copy.
2. **"12 epochs below ~300 examples" does not transfer one-to-one.** lft's number is per multi-question case (5 sequences each). decider's examples are single sequences, so decider runs get far fewer optimiser updates (4–16 at defaults). #963 shows silent collapse to the prior at 72. The real parameter is the update budget (§1.3, D3).
3. **The ~1 h per 250-example run and the 8.5 GB peak are both conditional.**
   - The hour was measured at 4 epochs. At the recommended 12 epochs it is ~3 h.
   - The 8.5 GB needs gradient checkpointing, which the SDK switches **off** on CPU by default.
   - Both were measured on laya 0.3.6 + the lft loop, not on `laya.train`.

   Re-measure on the pinned SDK before ticket 0012 judges them "acceptable". That judgement belongs to [Non-functional targets](../../issues/0012-non-functional-targets.md), not here.
4. **The calibration slice and the 50-example minimum collide.** The SDK fits no temperature below 100 training examples. The frozen split freezes at exactly the point (150 confirmed) where training drops back to 50 (§1.5). The ticket asked "whether a calibration slice is carved". The sharper question is the size threshold below which none is carved (D4).
5. **Truncation is not only an inference problem.** `laya.train` truncates long training states silently and does not count them (§1.7). The token check has to cover import as well as `decide` (D6).
6. **`tasks.yaml` "max input length" cannot be set freely.** The question and options fix the room for the state (`state_room`). The field can only lower it (D6).
7. **Only the type-level temperature is reachable.** Per-option-count buckets need 2,000 calibration items (§1.5). decider will never get them, so "calibrated" means one scalar per question type.
8. **Seed matters more than lft's "<1 point" suggests at these sizes.** On small data, #963 saw whether training learned at all vary with the seed (§1.8). That bears on D7.
