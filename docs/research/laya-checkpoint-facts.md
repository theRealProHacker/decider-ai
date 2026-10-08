# Laya checkpoint facts

Research for [issue 0003](../../issues/0003-laya-checkpoint-facts.md). It answers design Open Question 1 and reviewer concern R3-14. Researched 2026-10-08.

Each fact is labelled:

- **sourced**: stated in a linked source.
- **measured**: run on this machine for this ticket (method in [Measurement method](#measurement-method)).
- **estimated**: derived from sourced or measured numbers. The derivation is shown.

## Summary

| Item | Answer | Basis |
|---|---|---|
| Checkpoint | `convaiinnovations/laya-multilingual` at revision `1720e3e3357cfe1e281542e223f8273b0890ca34` | sourced |
| Root vs multilingual | Multilingual. The root checkpoint is English-only. | sourced |
| Fit for German legal mail | Unproven. German is a supported language, but there are no German or legal-domain numbers. Zero-shot is near chance. Phase 0 has to decide this. | sourced + judgement |
| Licence of that revision | Apache-2.0 (model-card metadata). Commercial use is allowed. The encoder it builds on, mmBERT-base, is MIT. | sourced |
| Parameters | 321,908,998 | sourced + measured |
| Full fine-tune or adapters | Full fine-tune of encoder and head. No adapters. Each version is a complete checkpoint. | sourced |
| CPU fine-tune time, 4 epochs, ~460-token mails | 50 examples: **11.8 min** (measured). 100: ~24 min. 250: ~59 min (estimated). | measured / estimated |
| Peak memory while training | **8.5 GB RSS** | measured |
| Resident memory per loaded checkpoint | **1.8 GB RSS** (fp32 on CPU), with a 4.2 GB peak while loading | measured |
| Disk per kept version | **678 MB** (647 MiB) | measured (matches the sourced 615 MB weights file, which is the same file in MiB) |
| Max input tokens | 1,024 per question sequence, of which up to 256 go to question and options. That leaves about 768 for the mail. The encoder supports up to 8,192 at inference. | sourced |
| laya-finetuning reuse | The recipe and `train/ckpt.py`, `calibrate.py`, parts of `data.py` and `evaluate.py`. But **the repo has no licence**, so none of its code can be copied until that is fixed. | sourced |

## 1. Which checkpoint

**Use `convaiinnovations/laya-multilingual` at `1720e3e3357cfe1e281542e223f8273b0890ca34`.** (sourced)

- The Laya family has three checkpoints. The root `convaiinnovations/laya` is ModernBERT-large, 421M parameters, English. `multilingual` is mmBERT-base, 322M parameters, 100+ languages. `typed-decisions` is fine-tuned on four English workflows. Sources: [model card @ 7b928d8](https://huggingface.co/convaiinnovations/laya/blob/7b928d828b7b0e022f929d9bd2e44165aa270148/README.md) (Architecture section) and the [laya-finetuning README](https://github.com/tehtommeh/laya-finetuning/blob/2c39f675f512ffacdd567c7541aef6ad3631cf61/README.md).
- The root checkpoint is **English only**. The card says "English only on root: Use `laya-multilingual` for anything outside English". On non-Latin scripts it collapses while staying confident. The laya-finetuning guide says: "fine-tune `BASE=multilingual` if your traffic is not English" ([FINETUNING.md](https://github.com/tehtommeh/laya-finetuning/blob/2c39f675f512ffacdd567c7541aef6ad3631cf61/docs/FINETUNING.md#what-to-collect)).
- **The same weights are published in two places.** `convaiinnovations/laya-multilingual/model.safetensors` and `convaiinnovations/laya` subfolder `multilingual/model.safetensors` have the same LFS sha256 (`9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204`, 643,835,514 bytes). They have not changed since the weights were first uploaded on 2026-09-19. That makes them identical to the revision laya-finetuning pinned (`1c5edc17a7ac`, [download.lock.json](https://github.com/tehtommeh/laya-finetuning/blob/2c39f675f512ffacdd567c7541aef6ad3631cf61/models/download.lock.json)). Source: the HF `paths-info` API at `1720e3e3`, `1c5edc17` and `7b928d82`.
- Pin the standalone repo. It holds only the 8 files needed (678 MB), while the umbrella repo is 2.3 GB.

### Fit for German legal mail

There is no direct evidence either way.

- German (`de`) is in the language list on the [laya-multilingual card](https://huggingface.co/convaiinnovations/laya-multilingual/blob/1720e3e3357cfe1e281542e223f8273b0890ca34/README.md). (sourced)
- The only cross-lingual numbers are aggregates. On XNLI, the 14 non-English languages (German among them) average 0.731, against 0.521 for the root. On MASSIVE, 45 of 51 languages are usable. No German-specific and no legal-domain number is published, and none exists in [NandhaKishorM/laya](https://github.com/NandhaKishorM/laya) either. (sourced)
- **Zero-shot is near chance.** On typed-decisions it scores 0.342, against 0.318 random and a 0.461 majority baseline. The card says: "Fine-tune for a specific workflow; that is where the capability comes from". (sourced) The design's cold-start rule (macro-F1 must beat the majority baseline) will therefore probably disable zero-shot. Phase 0 baseline (d) is likely to fail. (judgement)
- **Fine-tuned, the multilingual base is about as good as the English one.** In laya-finetuning's experiments on English data with 300 cases, it scored 0.649 against 0.657 for the English base. It trained twice as fast ([EXPERIMENTS.md §5](https://github.com/tehtommeh/laya-finetuning/blob/2c39f675f512ffacdd567c7541aef6ad3631cf61/docs/EXPERIMENTS.md)). (sourced)
- **The card lists limits that affect Pilot's two tasks.** (sourced, [laya-multilingual card, Limits](https://huggingface.co/convaiinnovations/laya-multilingual/blob/1720e3e3357cfe1e281542e223f8273b0890ca34/README.md))
  - Ordinal `score` questions have a **measured position bias** on this checkpoint: it "rarely picks the first-listed level", 0 of 290 in one run ([laya#131](https://github.com/NandhaKishorM/laya/issues/131)). This affects `urgency` 1–5 if it is encoded as `score`.
  - `noul` can under-report "true".
  - The checkpoint ships uncalibrated (temperature 1.0). laya-finetuning refits temperatures after every training run.
(Pilot detail removed)

**Verdict:** multilingual is the only candidate. Whether it is fit for German legal mail is exactly what the Phase 0 fine-tune arm (c) measures. No published source settles it.

## 2. Licence

(sourced)

- **The model is Apache-2.0.** The card YAML at `1720e3e3` says `license: apache-2.0` and carries the tag `commercial-use` ([raw README](https://huggingface.co/convaiinnovations/laya-multilingual/raw/1720e3e3357cfe1e281542e223f8273b0890ca34/README.md), line 2). The repo has **no `LICENSE` file**, so the card metadata is the only grant. Apache-2.0 allows commercial use, modification and redistribution, including inside a Docker image, provided the licence and NOTICE are kept. This matches the Constraint in `docs/design.md`.
- **The base encoder is MIT.** `jhu-clsp/mmBERT-base` at `c5955035435e2bf121cde7f3c8863ef52ff35d82` has card licence `mit` ([HF API](https://huggingface.co/api/models/jhu-clsp/mmBERT-base)). MIT is compatible with Apache-2.0.
- **The SDK is Apache-2.0.** The `laya` package is Apache-2.0 on [PyPI](https://pypi.org/project/laya/) (laya-finetuning pins 0.3.6; the latest is 0.4.0), and so is [NandhaKishorM/laya](https://github.com/NandhaKishorM/laya) on GitHub. The official fine-tuning notebook (`notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb`) is in that Apache-2.0 repo.
- **laya-finetuning has no licence.** [tehtommeh/laya-finetuning](https://github.com/tehtommeh/laya-finetuning) is a public repo by user `tehtommeh` (Tom). It has no LICENSE file: `gh api repos/tehtommeh/laya-finetuning/license` returns 404, and no source file states one. By default that means all rights are reserved, so its code cannot be copied into an open-source decider-ai without the author's written permission or a licence added to the repo. Its *recipe* comes from the Apache-2.0 official notebook (per the `train/train.py` docstring), so it can be reimplemented from the notebook and the SDK without a grant.

## 3. Parameter count

- **321,908,998 parameters** per the HF safetensors metadata for `laya-multilingual` (sourced). Loading through `ckpt.load_model` gives 321,908,995 parameters (measured). The difference is 3 non-parameter tensors.
- The split is mmBERT-base at 307M (22 layers, hidden size 768, a 256k vocabulary that alone accounts for ~197M) plus a 2-layer decision head (sourced, card Architecture section).

## 4. Full fine-tune or adapters

**Full fine-tune.** (sourced)

- `train/train.py` describes itself as "full fine-tune of encoder and head". AdamW runs over all encoder and head parameters (lr 2.5e-5 for the encoder, 1e-4 for the head).
- `ckpt.save_checkpoint` writes the full state dict in fp16 and copies `encoder/` and `tokenizer/` from the base.
- The repo has no LoRA, PEFT or adapter code.
- So every task version is a self-contained 678 MB checkpoint. Shapes and vocabulary never change.

The training objective is RLCD: REINFORCE with a group-mean baseline over Gaussian-perturbed logits, scored by a strictly proper reward, plus soft cross-entropy. Defaults are 4 epochs, batch 8, effective batch 64, gradient checkpointing.

## 5. CPU fine-tune time per run

**laya-finetuning does not support CPU training.** `train.py` exits with "No CUDA GPU visible. Fine-tuning a 322-421M encoder on CPU is impractical". [FINETUNING.md](https://github.com/tehtommeh/laya-finetuning/blob/2c39f675f512ffacdd567c7541aef6ad3631cf61/docs/FINETUNING.md#hardware-and-timings) says "CPU: not supported … even a 100-case run would take hours". Its only measured timings are GPU: on an RTX 3090 the multilingual base takes ~0.7 min per 100 cases for 4 epochs. (sourced)

I measured CPU instead, using the same loop on CPU in fp32. Setup: one question per example (a decider task is one question), ~456-token German mail states, 4 epochs, 4 threads (the design's default thread cap of half the CPUs).

| Examples | Sequences (×4 epochs) | Time | Basis |
|---|---|---|---|
| 50 | 200 | **11.8 min** (705 s, 3.5 s per sequence, 129 tokens/s) | measured, full run |
| 100 | 400 | ~24 min | estimated: 400 × 3.5 s |
| 250 | 1,000 | ~59 min | estimated: 1,000 × 3.5 s |

Further measurements and estimates:

- **A short probe ran faster.** The first 3 batches ran at 2.2 s per sequence. The 12-minute sustained run averaged 3.5 s. That is consistent with laptop thermal throttling, so treat 3.5 s as realistic on this machine. (measured)
- **8 threads were slower than 4:** 5.0 s per sequence. The 258V has 4 performance cores and 4 low-power efficiency cores. (measured)
- **bf16 training does not work on this CPU.** oneDNN refuses bf16 backward on AVX2-VNNI ("DNNL does not support bf16/f16 backward"). Training has to run in fp32 unless the CPU has AMX or AVX-512-BF16. (measured)
- **Long mails cost about twice as much.** Mails near the 768-token state limit (~1,024-token sequences) should take ~2.2× per sequence, assuming time is roughly linear in tokens at this length. (estimated)
- **Extras per run.** Each run also needs about 15–45 s to load the model and a calibration pass over 10% of the data. Each candidate is then scored on the frozen 100-example split at ~0.3 s per item through the SDK (below), so ~0.5 min for the candidate and ~0.5 min for the active model. (estimated)
- **Phase 0 cost.** Arm (c) uses 5 seeds, so at ~250 training examples it takes ~5 h on this laptop. (estimated)
- **Server CPUs are unmeasured.** A server CPU with AVX-512 or AMX will be faster; how much faster was not measured.

## 6. Memory

| What | RSS | Basis |
|---|---|---|
| Process with torch and laya imported, no model | 0.23 GB | measured |
| One loaded checkpoint, fp32 (`laya.Agent(path, device="cpu")` or `ckpt.load_model`) | **1.81 GB** total, so ~1.6 GB per checkpoint | measured |
| Transient peak during load (fp16 file → fp32 parameters) | 4.18 GB | measured |
| Training, 4 threads, batch 8, gradient checkpointing | **8.47 GB** peak | measured |

- The training peak is roughly fp32 weights + gradients + two AdamW moments (4 × 1.29 GB = 5.2 GB) plus activations.
- The SDK keeps fp32 parameters on CPU. A bf16 copy would be ~0.65 GB of weights, but that was not tested for serving accuracy.
- **Container sizing** (estimated): the base checkpoint for zero-shot, plus one active checkpoint per task (2 for Pilot), plus the candidate during the smoke-test swap, plus training. That is ≈ 0.25 + 4 × 1.6 + 8.5 ≈ **15 GB**. With zero-shot disabled it is ≈ 13 GB.
- **CPU inference latency** through `laya.Agent.predict` was 282 ms p50 for one 3-option question on a ~300-token German mail (4 threads, measured). That falls inside the card's "193–464 ms (CPU)" (sourced).

## 7. Disk per kept version

**678 MB (647 MiB) per version** (measured with `du`): `model.safetensors` 643.8 MB in fp16, plus a copied tokenizer of 34.4 MB and the configs. The sourced "615 MB multilingual" in FINETUNING.md is the same weights file counted in MiB. The base checkpoint takes the same 678 MB. **Estimated:** with 2 tasks and *k* kept versions each, disk ≈ 0.68 × (1 + 2k) GB. For example, 10 versions per task is ~14 GB.

## 8. Max input tokens

(sourced)

- `laya-multilingual` ships with `max_len: 1024` and `head_max_len: 256` ([`rl_agent_config.json`](https://huggingface.co/convaiinnovations/laya-multilingual/blob/1720e3e3357cfe1e281542e223f8273b0890ca34/rl_agent_config.json)).
- The encoder has `max_position_embeddings: 8192`. The card documents `max_len=8192` at inference, but accuracy varies beyond ~4,000 tokens.
- laya-finetuning trains at `--max-len 1024 --head-max-len 256` by default.
- The SDK's `laya.common.build_sequence` (laya 0.3.6) lays out a sequence as `[CLS] <type> question [SEP] [MASK] opt0 … [SEP] state [SEP]`. The state budget is `max_len − len(prefix) − 1` **tokens**. Each option is cut at 48 tokens. **Anything over the budget is cut silently** (`st[:room]`).
- **For decider-ai** (judgement):
  - `LayaBackend.max_input(task)` can compute the state budget exactly once per task, because the question and options are fixed. It is about 768 tokens minus the question length.
  - Inputs must be checked against it in **tokens of the serialised state**, and `413 INPUT_TOO_LONG` returned before the SDK truncates.
  - `tasks.yaml` "max input length" should be specified in tokens.

## 9. What laya-finetuning contributes to `LayaBackend`

Repo [tehtommeh/laya-finetuning @ `2c39f675`](https://github.com/tehtommeh/laya-finetuning/tree/2c39f675f512ffacdd567c7541aef6ad3631cf61). The licence (none) is in §2. The table assumes that is resolved. If it is not, the same pieces have to be rebuilt from the Apache-2.0 SDK (`laya.common`: `build_model`, `build_sequence`, `collate_items`, `proper_reward`, `temp_bucket`, `ece_score`) and the official notebook.

| File / function | Use in `LayaBackend` | Changes needed |
|---|---|---|
| `train/ckpt.py`: `read_config`, `load_tokenizer`, `load_model`, `encode_case`, `save_checkpoint` | `train()`: build the model, encode `(text, question, options) → items`, write a checkpoint the SDK loads | `resolve_base`/`BASES` hard-code `/models/...` paths, so take a `ModelRef` instead. `load_tokenizer` calls the private SDK function `laya.agent._fix_tokenizer_config`, so pin the `laya` version. |
| `train/train.py`: `main()` training loop (RLCD loss, AdamW, cosine, grad checkpointing, effective batch 64) | Core of `train()` | Remove the CUDA-only exit. Run fp32 on CPU (no autocast, no GradScaler). Drop DDP. Call `progress(step/total)`. Take `seed` and `out_dir` from the port. Stop reading `/models/download.lock.json`. |
| `train/calibrate.py`: `fit`, `fit_temperature`, `metrics`, `predict_logits`, `pairs_for` | Fits per-bucket temperatures on a held-out calibration slice after training. This is needed because the base ships uncalibrated. | Already device-agnostic (autocast only on CUDA). |
| `train/data.py`: `check_question`, `option_keys`, `to_internal`, `gold_distribution`, `normalise_case` | `TaskSpec` + `Example` → Laya case format | **Not** `split_of`/`load_splits`/`subsample`. They split by hashing the id and are not group-aware. The `evaluation` module owns the frozen split. |
| `train/evaluate.py`: `answer_dist`, `score_rows` | Optional: Brier/NLL/ECE next to macro-F1 in reports | `run_model` uses `laya.Agent`. That is the predict path `LayaBackend.predict` should use too. |
| `train/validate.py` | Pattern for token-budget and label-balance checks (truncation counting via `encode_case`) | Becomes `max_input` plus a pre-train check |
| `docs/FINETUNING.md`, `docs/EXPERIMENTS.md` | Hyper-parameter defaults, data-size guidance (gains flatten at ~150 cases per question set; use 12 epochs below ~300 cases) | none |
| `api/` (FastAPI, GPU batching, CUDA graphs), `frontend/`, `scripts/`, `train/bakeoff.py`, `specialists.py`, `publish.py`, Docker files | Not applicable: GPU serving, UI, and a publish flow that decider's activation replaces | none |

`LayaBackend.predict` needs nothing from laya-finetuning. It is `laya.Agent(path, device="cpu").predict(state, {task: question})`, mapping `answers[task].probabilities` to `dict[str, float]`, using the Apache-2.0 SDK.

## Measurement method

- **Machine:** Intel Core Ultra 7 258V (8 cores: 4 performance + 4 low-power efficiency, no SMT, AVX2-VNNI, no AMX), 30 GB RAM, Linux 6.17.
- **Software:** Python 3.12, `torch 2.14.1+cpu`, `transformers 5.17.0`, `laya 0.3.6`, `safetensors 0.8.0`. These are the versions laya-finetuning pins, apart from torch.
- **Weights:** `convaiinnovations/laya-multilingual @ 1720e3e3`, loaded offline.
- **Training probe:** a scratch script that imports laya-finetuning `train/ckpt.py` and `train/data.py` at `2c39f675` and copies the `train.py` inner loop verbatim, except that it runs on the CPU device, in fp32, without GradScaler.
(Pilot detail removed)
- **Run:** a full 4-epoch run; the checkpoint was saved and measured with `du`.
- **Memory:** RSS via `psutil` and `ru_maxrss`.
- **Inference:** `laya.Agent(..., device="cpu").predict`, 8 calls, first 2 discarded.
- No real Pilot mail was used.
