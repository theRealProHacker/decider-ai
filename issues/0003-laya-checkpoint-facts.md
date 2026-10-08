---
id: 3
title: Laya checkpoint facts
labels: [wayfinder:research]
status: closed
assignee: rharvey
parent: 1
blocked_by: []
---

## Question

Which exact Laya checkpoint does decider-ai use (root vs multilingual), and is it fit for German legal mail? Pin: licence of the exact revision (commercial use OK?), parameter count, full fine-tune vs adapters, CPU fine-tune time per run at ~50/100/250 examples, resident memory per loaded task checkpoint, disk per kept version, max input tokens, and what the existing Laya fine-tuning project's code contributes to `LayaBackend`. Covers design open question 1 and R3-14. Output: a linked markdown summary with sources.

## Sources

- Laya fine-tuning project (founder, 2026-10-08): https://github.com/tehtommeh/laya-finetuning — the training/eval code `LayaBackend` reuses. Start here.

## Resolution

Full findings with sources: [../docs/research/laya-checkpoint-facts.md](../docs/research/laya-checkpoint-facts.md). Each fact is marked sourced, measured or estimated.

- **Checkpoint:** `convaiinnovations/laya-multilingual` at `1720e3e3357cfe1e281542e223f8273b0890ca34` (mmBERT-base, 321.9M parameters). The root checkpoint is English-only. These weights are byte-identical to `convaiinnovations/laya` subfolder `multilingual` and to the revision laya-finetuning pinned.
- **German legal mail:** German is a supported language, but nothing has been published for German specifically or for legal mail. Zero-shot is near chance (0.342 against a 0.461 majority baseline), so the Phase 0 fine-tune arm decides fitness. The checkpoint has a known position bias on `score` questions, which matters for urgency.
- **Licence:** the model is Apache-2.0 (card metadata; the repo has no LICENSE file), so commercial use is OK. The encoder is mmBERT-base, which is MIT. The laya SDK is Apache-2.0.
- **laya-finetuning has no licence at all.** Its code cannot be copied without the author's permission. The fallback is the Apache-2.0 SDK plus the official notebook.
- **Full fine-tune, no adapters.** Each version is a complete 678 MB checkpoint.
- **CPU fine-tuning works, though laya-finetuning says it doesn't** (its `train.py` refuses to run on CPU). Measured on this laptop with 4 threads, fp32, ~460-token mails and 4 epochs:
  - 50 examples: 11.8 min (measured).
  - 100 examples: ~24 min; 250 examples: ~59 min (estimated).
  - Peak RSS while training: 8.5 GB.
  - bf16 backward does not work on AVX2 CPUs.
- **Memory:** about 1.6–1.8 GB RSS per loaded checkpoint (fp32), with a 4.2 GB transient peak while loading. Inference takes ~0.3 s per question.
- **Max input:** 1,024 tokens per sequence, with up to 256 for the question and options, which leaves ~768 for the mail. The SDK silently truncates anything longer, so `LayaBackend.max_input` must check in tokens before calling the model.
- **Reusable code (once the licence is fixed):**
  - `train/ckpt.py`: load, encode and save.
  - The `train/train.py` loop, adapted for CPU.
  - `train/calibrate.py`: temperature fitting.
  - Schema helpers in `train/data.py`. Not its split: that split is hash-based, not group-aware.
  - Metrics in `train/evaluate.py`.
  - Prediction goes through `laya.Agent`.
