# Brief: non-functional targets

Preparation for grilling [issue 0012](../../issues/0012-non-functional-targets.md). It decides nothing. It collects the facts and lists the decisions in the order to take them. Every decision has options and a recommendation. Prepared 2026-10-08.

Labels used:

- **sourced**: stated in a linked source.
- **measured**: run for this brief or for [Laya checkpoint facts](../research/laya-checkpoint-facts.md) (0003). The method is under [Measurement method](#measurement-method).
- **estimated**: derived from sourced or measured numbers, with the derivation shown.

## 1. Facts

### 1.1 Measurement machine

Every measured number is from one machine:

- Intel Core Ultra 7 258V laptop: 8 cores (4 performance, 4 low-power efficiency), no SMT, AVX2 and AVX-VNNI, no AVX-512, no AMX. 30 GB RAM. Linux 6.17, platform profile `performance`, on AC power.
- Software: Python 3.12, `torch 2.14.1+cpu`, `transformers 5.17.0`, `laya 0.3.6`.
- **Contention caveat.** During the runs for this brief, four unrelated `stockfish` processes each used about 80% of a core, so the load average was 6–9. To size the effect, I re-ran the exact 0003 latency probe: it gave **444 ms p50**, where 0003 measured **282 ms** on an idle machine. That is a factor of about 1.6. So treat this brief's latency numbers as **pessimistic upper bounds**. An idle run is the first thing to repeat before targets are fixed.

### 1.2 Single-decision CPU latency (measured, new)

Setup: `laya.Agent.predict`, batch 1, one 10-option `choice` question in German ("In welche Warteschlange gehört diese Nachricht?"). 10 warm-up calls are discarded.

- "Short" means 200 synthetic German support messages of 15 tokens mean (20 max).
- "Long" means 40 messages of 451 tokens mean (457 max). That is about 60% of the ~768-token state budget.
- The model is the base checkpoint `laya-multilingual @ 1720e3e3`, plus a precision check on the 0003 fine-tuned n50 checkpoint.

| Input | Threads | Precision | p50 | p95 | p99 | Basis |
|---|---|---|---|---|---|---|
| short | 1 | fp32 | 410 ms | 426 ms | 441 ms | measured, contended |
| short | 2 | fp32 | 222 ms | 231 ms | 245 ms | measured, contended |
| short | 4 | fp32 | 164–170 ms | 191–251 ms | 223–346 ms | measured, contended (two runs) |
| short | 4 | bf16 weights | 139–144 ms | 175–203 ms | 218–307 ms | measured, contended (base + fine-tuned) |
| short | 4 | dynamic int8 (encoder Linear) | 129–132 ms | 159–168 ms | 184–246 ms | measured, contended (base + fine-tuned) |
| long | 2 | fp32 | 1,421 ms | 1,477 ms | 1,520 ms | measured, contended |
| long | 4 | fp32 | 1,035 ms | 1,189 ms | 1,282 ms | measured, contended |
| long | 4 | bf16 weights | 1,030 ms | 1,252 ms | 1,406 ms | measured, contended |
| long | 4 | dynamic int8 | 951 ms | 1,062 ms | 1,081 ms | measured, contended |
| ~300-token mail, 3 options | 4 | fp32 | 282 ms | n/a | n/a | measured idle in 0003 (8 calls) |

What the numbers show:

- **The floor is not zero.** A 15-token message still costs ~165 ms. The question and 10 options are encoded with every call, so the sequence is never short. The cost per decision grows with the number of labels, not only with text length. (measured + judgement)
- **Threads help with diminishing returns.** Going from 1 to 4 threads is 2.5× faster on short inputs. Going from 2 to 4 threads is only 1.4× on long inputs. (measured)
- **Estimated idle numbers.** Scaling by the 0.64 contention factor from §1.1 gives about 105 ms p50 for short inputs and about 0.65–0.75 s p50 for long inputs on this laptop at 4 threads. (estimated)
- **Server CPUs are unmeasured.** Hetzner shared vCPUs are hyperthreads of EPYC or Xeon cores. They will not match a 4.8 GHz laptop performance core, and nothing here measures them. (judgement)

### 1.3 Precision fidelity (measured, new)

Top-1 agreement with fp32 is measured on the same 200 short texts. This is a numerical-fidelity check, not task accuracy.

| Checkpoint | bf16 weights | dynamic int8 |
|---|---|---|
| base | 199/200, max \|Δp\| 0.146, mean \|Δp\| 0.0012 | **160/200**, max \|Δp\| 0.970, mean \|Δp\| 0.037 |
| fine-tuned n50 (0003) | 198/200, max \|Δp\| 0.111, mean \|Δp\| 0.0010 | **167/200**, max \|Δp\| 0.976, mean \|Δp\| 0.037 |

- **Naive dynamic int8 breaks the model.** It flips 16–20% of top-1 answers. Fixing that would need calibrated static quantization or ONNX, and design.md already defers "ONNX/INT8" under decision 18271c16. These measurements support that deferral. (measured + judgement)
- **bf16 weights are nearly lossless and halve the weight memory.**
  - The SDK has no switch for bf16. It needs `agent.model.to(torch.bfloat16)` plus keeping `act_head` in fp32, because `forward()` feeds it fp32 features. The SDK's own `autocast` is disabled on CPU and overrides an outer one. (measured)
  - This CPU lacks native bf16 arithmetic, so it gains little speed. The value of bf16 here is memory. (measured)
  - bf16 *training* still fails on AVX2 (0003).

### 1.4 Memory

| Item | Value | Basis |
|---|---|---|
| Python + torch + laya, no model | 0.23 GB | measured (0003) |
| One loaded checkpoint, fp32 | 1.81 GB process, so ~1.6 GB per checkpoint | measured (0003, reconfirmed here) |
| Transient peak while loading (fp16 file → fp32) | 4.18 GB | measured (0003, reconfirmed in every run here) |
| Training peak, 4 threads, batch 8 | 8.47 GB | measured (0003) |
| Weights by precision: fp32 / bf16 / int8-encoder-linear | 1.29 / 0.64 / ~0.96 GB | estimated: 321.9M params, of which 196.6M token embeddings, 110.3M encoder Linear, 15.0M other (counted from the safetensors header) |
| Process RSS after converting fp32 → bf16 in place | 1.42 GB | measured. This overstates a direct bf16 load, because the allocator keeps freed fp32 pages. |
| One bf16 checkpoint if loaded directly | ~0.8 GB per checkpoint | estimated: 0.64 GB weights + buffers |
| Token embeddings' share of the model | 61% (196.6M / 321.9M) | measured |

**Peak memory formula** (estimated). With *L* loaded checkpoints and *m* GB each:

`peak ≈ 0.25 + m·L + 8.3 (a training job) + 2.4 (if an activate loads a candidate during training)`

| Loaded checkpoints *L* | fp32 (*m* = 1.6) | bf16 (*m* ≈ 0.8) |
|---|---|---|
| 1 | 10.2 / 12.6 GB | 9.4 / 11.8 GB |
| 2 | 11.8 / 14.2 GB | 10.2 / 12.6 GB |
| 3 | 13.4 / 15.8 GB | 11.0 / 13.4 GB |
| 4 | 15.0 / 17.4 GB | 11.8 / 14.2 GB |

The first number is without and the second with an activate during training. All base-checkpoint (zero-shot) tasks share one loaded base. Add 0.5–1 GB for the OS and Docker.

### 1.5 Load time

Loading a checkpoint took **17–23 s** (measured, contended; 0003 measured ~15–45 s together with calibration). An `activate` or a lazily loaded task therefore takes tens of seconds, not milliseconds.

### 1.6 Training wall-clock

All from 0003, at 4 threads, fp32, ~456-token mails:

- **4 epochs** (measured, estimated): 50 examples take 11.8 min (measured), 100 take ~24 min, and 250 take ~59 min.
- **12 epochs** (estimated): FINETUNING.md recommends 12 epochs below ~300 cases. At 250 examples that is 3,000 sequences × 3.5 s ≈ **2.9 h**. Which epoch count applies is [Training procedure](../../issues/0019-training-procedure.md)'s call.
- **Fewer threads are slower** (estimated). The design caps training at "half the CPUs". On a 4-vCPU host that is 2 threads. The serving measurements show 2 threads are 1.4× slower than 4 on long inputs, so a 250-example, 4-epoch run would take ~1.4 h and a 12-epoch run ~4 h.
- **Long mails cost ~2.2× per sequence** (estimated, 0003).

### 1.7 Disk

- **Per version** (measured, 0003): 678 MB, fp16 weights plus a copied tokenizer.
- **Total** (estimated): with *T* tasks and *k* kept versions per task, disk ≈ 0.68 × (1 + T·k) GB. The 1 is the bundled base checkpoint.
- **Examples:** T = 2, k = 3 gives 4.8 GB. T = 2, k = 10 gives 14.3 GB. T = 5, k = 5 gives 17.7 GB.
- **Tokenizer copies:** the copied tokenizer is 34 MB of each version and could be shared, which saves 5%. (measured + estimated)

### 1.8 Image size

| Part | Size | Basis |
|---|---|---|
| `torch 2.14.1+cpu` wheel, x86_64 / aarch64 | 196 MB / 159 MB compressed | sourced: `download.pytorch.org/whl/cpu` Content-Length |
| `torch` installed | 738 MB | measured (`du`) |
| `transformers` + `tokenizers` + `numpy` + `safetensors` + `laya` installed | ~107 MB | measured (`du`) |
| Base checkpoint | 678 MB | measured |
| `python:3.12-slim` base layer | ~120–150 MB | estimated, not pulled |
| **Total uncompressed** | **~1.65–1.7 GB** | estimated |
| **Pull size** | **~1.0–1.1 GB** | estimated: fp16 weights barely compress |

Note: the default PyPI `torch` wheel for linux x86_64 is 555 MB and pulls the CUDA libraries. A CPU image must install from the CPU index (sourced: PyPI JSON for `torch 2.14.1`).

### 1.9 arm64

- **PyTorch builds exist.** PyTorch publishes `torch-2.14.1+cpu-cp312-…-manylinux_2_28_aarch64.whl` (sourced, CPU index). A multi-arch image is buildable.
- **Laya on arm64 is unmeasured,** for both speed and correctness.
- **Some arm64 hardware is common:** Hetzner CAX (Ampere Altra), Apple Silicon Macs running Docker Desktop, and Raspberry Pi 5.

### 1.10 Typical small hosts and prices

**Hetzner Cloud**, Germany/Finland, monthly, excl. VAT and IPv4, new orders since 15 June 2026 (sourced: [Hetzner price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/); specs from [cost-optimized](https://www.hetzner.com/cloud/cost-optimized/), [regular performance](https://www.hetzner.com/cloud/regular-performance/), [general purpose](https://www.hetzner.com/cloud/general-purpose/)):

| Plan | vCPU | RAM | Disk | CPU | €/month | Fits |
|---|---|---|---|---|---|---|
| CX23 | 2 shared | 4 GB | 40 GB | Intel/AMD | 5.49 | nothing below (cannot hold a checkpoint plus its load peak) |
| CX33 | 4 shared | 8 GB | 80 GB | Intel/AMD | 8.49 | serving only, no training |
| CAX21 | 4 shared | 8 GB | 80 GB | Ampere arm64 | 10.49 | serving only, arm64 |
| **CX43** | 8 shared | **16 GB** | 160 GB | Intel/AMD | **15.99** | training + 2 fp32 tasks |
| CAX31 | 8 shared | 16 GB | 160 GB | Ampere arm64 | 20.99 | as CX43, arm64 |
| CPX32 | 4 shared | 8 GB | 160 GB | AMD | 35.49 | serving only |
| CPX42 | 8 shared | 16 GB | 320 GB | AMD | 69.49 | training + 2 fp32 tasks |
| CX53 | 16 shared | 32 GB | 320 GB | Intel/AMD | 29.49 | generous |
| CCX13 | 2 dedicated | 8 GB | 80 GB | AMD | 42.99 | serving only |
| CCX23 | 4 dedicated | 16 GB | 160 GB | AMD | 85.99 | training + 2 fp32 tasks |

- On 2026-10-08, Hetzner's cost-optimized page marked every CX and CAX plan "currently unavailable" (sourced). Availability changes often.
- An aggregator that read Hetzner's price API on 2026-10-02 lists the same plans €0.50 higher, which matches the IPv4 fee ([AgentDeals](https://agentdeals.dev/hetzner-pricing-2026); judgement).
- **Netcup G12 VPS** (sourced via a third-party review, [Valebyte](https://valebyte.com/en/blog/netcup-review-2026-the-price-performance-king-and-its-fine-print/), unverified on netcup.com): VPS 1000 G12 (4 vCores, 8 GB) is €10.37/month incl. VAT. VPS 2000 G12 (16 GB, by the review's table) is €19.25. The review notes fair-use throttling of sustained 100% CPU, which matters for hour-long training.
- **What self-hosters of n8n run** (sourced, vendor guides; n8n does not publish official sizing): 2 vCPU / 4 GB is the common production start. 8 GB is "comfortable" for n8n + Postgres + Redis on one box ([Cherry Servers](https://www.cherryservers.com/blog/n8n-self-hosting-requirements), [Hostinger](https://www.hostinger.com/tutorials/n8n-vps-requirements)).
- **Judgement:** decider-ai's audience typically has a **4–8 GB box that already runs n8n**. decider-ai with in-container training does not fit on it.

## 2. Decisions for the founder, in order

Each decision feeds the next. RAM sets the task count. The task count and precision set the memory formula. Latency and training budgets are then stated on the hardware chosen in decision 1.

### 2.1 Minimum supported host (RAM, cores, CPU features)

Context:

- The 8.5 GB training peak is the dominant term.
- A 4–8 GB n8n box cannot train.
- Training at "half the CPUs" on 4 vCPU means 2 threads.

| Option | Pros | Cons |
|---|---|---|
| **A. 16 GB, 4 vCPU, x86-64 with AVX2** (reference: Hetzner CX43, €15.99) | Training fits with 2 fp32 tasks. Cheap reference box. Matches all measurements. | Not the 4–8 GB box most n8n users have. They need a second or larger host. |
| B. 8 GB serve-only floor, 16 GB to train (two documented profiles) | Fits the n8n box for decisions, so a wider entry. | Training needs a different host. That contradicts "one container that learns from corrections" unless the user exports and imports models, which the design does not have. A second support matrix. |
| C. 32 GB, 8 vCPU | Comfortable: 4+ tasks, activate during training, headroom for long mails. | Prices out the self-hoster. The demand test would hit only bigger teams. |
| D. 16 GB, 8 vCPU | Training and serving don't fight for the same cores. 4 training threads at nice keep the 0003 timing. | 8 shared vCPUs are what CX43 offers anyway. On dedicated-core hosts it doubles the price (CCX33 €138). |

**Recommendation: A**, with D's 8 vCPU as "recommended" rather than "minimum".

- 16 GB is the smallest step at which the product, including retrain, works at all.
- CX43 already gives 8 vCPU at that price.
- B is attractive for reach, but it needs a model-transfer path the design does not have. Raise it again if launch conversations show people won't add a 16 GB box.

### 2.2 Maximum loaded tasks

Context:

- Each trained task holds a full checkpoint: 1.6 GB fp32, or ~0.8 GB bf16 (estimated).
- All zero-shot tasks share one base checkpoint.
- Loading takes ~20 s and has a 4.2 GB transient peak.

| Option | Pros | Cons |
|---|---|---|
| **A. Eager load of all tasks, documented cap, startup check.** The cap is 2 trained-task checkpoints (+ the base if any task is zero-shot) on the 16 GB minimum. Startup refuses with `ConfigError` if the formula exceeds the container memory limit. | Predictable latency: no cold loads. Fails loudly at start, not by OOM mid-training. | A hard ceiling on a 16 GB host. Users with more tasks need more RAM. |
| B. Lazy LRU loading with a configurable cap | Any number of tasks on fixed RAM. | The first decision on an evicted task takes ~20 s plus a 4.2 GB spike. That hurts the p95 claim. More code: eviction, load locks. |
| C. No cap, publish the formula | Least code. | The OOM-killer picks the moment, likely during training. That kills serving too. |
| D. One multi-question checkpoint for all tasks | ~1.6 GB total regardless of task count. Laya natively answers several questions per forward pass. | Couples tasks: retraining one task changes the model serving all of them. That breaks per-task versioning, verdicts and activation as designed. A design change, not a target. |

**Recommendation: A.**

- It keeps the design's per-task versioning and gives a fail-fast guarantee.
- A cap of 2 also matches Phase 1's real need: no named user, and the release test exercises one task.
- If more tasks are needed later, decision 2.3 (bf16) raises the cap to ~4 on the same host before B or D are worth their cost.

### 2.3 Serving precision

| Option | Pros | Cons |
|---|---|---|
| **A. fp32** (SDK default) | What the SDK, 0003 and Phase 0 measure. Served accuracy equals evaluated accuracy. No SDK workaround. | 1.6 GB per task. |
| B. bf16 weights | Measured 198–199/200 top-1 agreement. Halves weight memory, so ~2 more tasks fit in 16 GB. ~15% faster on short inputs. | Needs a non-API tweak of `agent.model`, which may break on SDK upgrades. Verdicts and Phase 0 numbers must then be computed in bf16 too, or served ≠ evaluated. No speed gain on long inputs on AVX2 CPUs. |
| C. Dynamic int8 | ~20% faster on short inputs. | **Measured 80–84% top-1 agreement: it breaks predictions.** Also deferred under 18271c16. |

**Recommendation: A for launch, with B as the named lever once a user needs more than 2 tasks.**

- fp32 keeps "the evaluated model is the served model" trivially true.
- The cap from 2.2 already fits the launch.
- C should be ruled out on measurement, not only deferred.

### 2.4 Decision latency target (p50 / p95)

Context:

- Measured on the laptop under contention: 164/191 ms for short inputs and 1,035/1,189 ms for ~450-token inputs (4 threads, 10 options).
- The gate (design Premise 4) compares p95 against the LLM baseline, so the target is also a marketing number.
- Training runs at nice on the same CPUs.

| Option | Pros | Cons |
|---|---|---|
| **A. Two-tier target on the reference host, idle: inputs ≤128 tokens p50 ≤ 300 ms, p95 ≤ 500 ms; max-length inputs p95 ≤ 2 s. During training: reported, no target.** | Honest about the length dependence. Headroom over the contended laptop numbers for slower shared vCPUs. | Two numbers to explain. Unverified on the CX43 class until measured there. |
| B. One target: p95 ≤ 1 s for any allowed input | Simple. | Long inputs on 2–4 shared vCPUs probably miss it (1.2 s contended on a fast laptop). It would force a lower token limit. |
| C. Targets that also hold during training | The strongest claim. | Needs CPU pinning or partitioning (serving cores vs training cores), which the design lacks. On 4 vCPU it likely fails. |
| D. No target, report measurements only | No risk of missing a promise. | The release test has no latency check, and regressions go unnoticed. |

**Recommendation: A.** Define it with the label count stated (the sequence includes the options), and measure it on the actual reference host before release. If the reference host misses it, lower the max-length tier rather than the short tier. Short messages are the routing case.

### 2.5 Training wall-clock budget

Context:

- 250 examples take ~1 h at 4 epochs and 4 threads.
- At 12 epochs, the FINETUNING.md advice below 300 cases, it is ~2.9 h.
- With 2 threads (half of a 4-vCPU host) it is ~1.4 h or ~4 h.

| Option | Pros | Cons |
|---|---|---|
| A. ≤ 1 h for 250 examples on the reference host | Fits a lunch break. A tutorial can show a full retrain. | Forces 4 epochs and ≥4 training threads, and may cap the max input tokens. Ties 0019's hands. |
| **B. ≤ 3 h for 250 examples of ≤512 tokens on the reference host at the default thread cap, with an ETA shown in job progress** | Leaves room for 12 epochs or for 2 threads. The ETA makes long runs bearable. | Not "watch it finish" in a demo, so the tutorial needs a smaller demo run (50 examples ≈ 12 min). |
| C. Overnight (≤ 8 h) | Never a constraint on 0019. | Feels broken to a first-time user. Fair-use throttling on cheap VPSs (netcup) makes it worse. |
| D. No budget, ETA only | Simplest. | No regression check on training speed. |

**Recommendation: B.**

- It is the loosest budget that still makes "retrain on request" a same-day action.
- It does not pre-empt [Training procedure](../../issues/0019-training-procedure.md)'s epoch choice.
- Decide the reference thread count together with 2.1: on 8 vCPU, half the CPUs is 4 threads.

### 2.6 Disk and version retention

Context:

- 678 MB per version.
- The design has no delete-version API.
- `forget` reports versions trained on erased data ([Data lifecycle and erasure](../../issues/0009-data-lifecycle-erasure.md)).

| Option | Pros | Cons |
|---|---|---|
| A. Keep every version until the user deletes it (needs a `DELETE /v1/models/{version}`) | No data the user didn't choose to drop is lost, in line with the no-automatic-action rule. | Disk grows without bound: ~0.7 GB per retrain. A new endpoint. |
| **B. Keep the active, the previously active, and the newest *k* candidates per task (default *k* = 3, configurable). Older non-active versions are pruned when a new job finishes.** | Bounded disk: ≈ 0.68 × (1 + 5T) GB, 7.5 GB at T = 2. Rollback to the last good model always works. | Auto-deletion is a background action. It is not retrain or activate, so it doesn't break decision 83b5e76c, but the founder should confirm it is in the spirit of the rule. |
| C. A disk budget in GB, oldest non-active pruned first | Users think in disk. | Version count varies, so harder to explain. |
| D. Keep only active + previous | Smallest: ≈ 0.68 × (1 + 2T) GB. | The user can't compare or return to an older candidate. A `not_recommended` candidate evicts a useful one. |

**Recommendation: B, with *k* = 3.** It gives bounded disk and a guaranteed rollback target. It also helps erasure, because old versions trained on deleted data age out. Recommended host disk: ≥ 20 GB free. CX43 has 160 GB.

### 2.7 Image size budget

Estimated ~1.65–1.7 GB uncompressed and ~1.0–1.1 GB to pull, with the base bundled as the design says. Whether to bundle is [Container image and runtime](../../issues/0013-container-image-runtime.md)'s call. This decision is the budget CI enforces.

| Option | Pros | Cons |
|---|---|---|
| **A. ≤ 2.0 GB uncompressed, base bundled; CI fails above it** | ~15% headroom for dependency drift. Catches an accidental CUDA torch (+GBs) at once. | Large next to n8n's image, but unavoidable with bundled weights. |
| B. ≤ 1.0 GB uncompressed, base fetched on first start | Small pull. | Contradicts the approved design ("the image bundles the base checkpoint"). First start needs network and HF availability. The pin moves out of the image. |
| C. No budget | Nothing to maintain. | The CUDA-wheel mistake ships silently. |

**Recommendation: A.** The budget exists mainly to catch the CPU-vs-CUDA torch mistake and stray dev dependencies. The fetch-or-bundle question stays with 0013.

### 2.8 arm64 support

| Option | Pros | Cons |
|---|---|---|
| A. x86-64 only at launch | One platform to test. All measurements are x86. | Apple Silicon users get an emulated amd64 image (slow, and torch under emulation is unverified). CAX and Pi users are excluded. |
| **B. Multi-arch image. arm64 passes the functional release test (decide/retrain-50/activate) on a GitHub arm64 runner; latency and training targets are stated for x86-64 only.** | Mac users can try it natively. Cheap: the aarch64 CPU wheel exists, and buildx makes it one CI matrix line. | A second CI leg. arm64 numbers are unknown until measured. |
| C. Full arm64 parity (targets on CAX31 as well) | A fully supported second platform. | Doubles the performance work before any user. Unmeasured, so the targets might not hold. |

**Recommendation: B.**

- Trying it on a Mac is likely the first contact for the developer audience, which is the launch demand test.
- B buys that for one CI leg without promising arm64 performance.
- Measure Laya on CAX31 once before launch to see if B can become C.

## 3. Facts that change the ticket's question or the design

1. **Memory, not CPU, binds, and training dominates.**
   - 8.5 GB for training, against 1.6 GB per served task.
   - "Drop it next to your n8n on the box you have" does not hold for most self-hosters' 4–8 GB boxes while training stays in-container.
   - The design's "single container that learns" implies a ≥16 GB host. The launch copy and tutorial should say so up front.
2. **In-process training threads may not hand memory back.**
   - The design trains in a background *thread* of the serving process (`ThreadRunner`).
   - The glibc allocator usually keeps freed pages after a multi-GB burst. The serving process could sit near ~10 GB RSS after the first retrain, and an OOM during training kills serving too. (estimated, not measured)
   - A subprocess per training job returns its memory on exit and isolates the OOM. It would be a third `Runner` adapter, so the port already allows it.
   - Worth a measurement, and an input to 0019 and 0013.
3. **One checkpoint per task is expensive, and Laya allows alternatives.** These are training-procedure questions (0019), but they decide this ticket's task cap.
   - **One multi-question checkpoint for all tasks** (Laya answers several questions in one pass) cuts RAM to ~1.6 GB total. It couples task versions, which conflicts with per-task activation and verdicts.
   - **Freezing the token embeddings** (61% of the parameters) during fine-tuning would let tasks share them. It would also cut the training peak by roughly 2.4 GB (196.6M × 12 bytes of gradients and AdamW moments).
   - Both are estimates. The second needs a custom loader.
4. **Latency depends on the label count.**
   - The options are in every sequence, so a 15-token message costs ~165 ms with 10 options.
   - A latency target is only meaningful with the label count stated.
   - The `tasks.yaml` input limit (0003) already depends on question and option length.
5. **"Half the CPUs" on a 4-vCPU host doubles training time.**
   - The thread-cap default and the minimum core count have to be decided together (2.1 and 2.5).
   - Serving and training share cores, so there is no latency guarantee during training unless cores are partitioned.
6. **Activation and lazy loading take ~20 s and spike memory by ~2.4 GB.**
   - An `activate` during a training run is the worst case for peak memory (1.4).
   - The 0003 container estimate (13–15 GB) assumed the base plus 2 tasks plus the candidate plus training. That stands as the peak only if `activate` is allowed during training.
7. **Dynamic int8 is ruled out by measurement, not only deferred** (1.3). bf16 is the only cheap precision lever, and it changes what Phase 0 must measure if adopted.
8. **Reference-machine pricing has moved.** Hetzner raised prices sharply on 15 June 2026 (CPX and CCX more than doubled), and the CX/CAX lines were unavailable on 2026-10-08.
   - The design's open question on "which reference machine prices local CPU time" should pin a plan, a date and a price.
   - Rough estimate: CX43 at €15.99/month is €0.022/h. At ~0.17 s per short decision (laptop, 4 threads) that is ~21k decisions/h, so **~€0.001 per 1,000 decisions** before training. Unverified until measured on the actual host.

## Measurement method

- **Scripts** are outside the repo, under `/tmp/claude-1000/nft-0012/`:
  - `bench.py` (latency, RSS, probabilities)
  - `agree.py` (top-1 agreement and |Δp| against fp32)
  - `runall.sh` and `runft.sh` (run order)
- **Environment:** the venv and weights from 0003 (`/tmp/claude-1000/laya-research/`), loaded offline.
- **Each configuration is a fresh process,** so RSS is per configuration. Runs were sequential, never in parallel with each other.
- **Latency:** `time.perf_counter()` around `agent.predict`. p95 is the nearest-rank value on the sorted list.
- **bf16:** `agent.model.to(torch.bfloat16)`, then `agent.model.act_head.float()`.
- **int8:** `torch.ao.quantization.quantize_dynamic(agent.model.encoder, {nn.Linear}, qint8)`. Quantizing the whole model crashes in the `nn.TransformerEncoder` head's fast path. This API prints a deprecation warning in torch 2.14.
- **Data:** synthetic German support messages built from templates, with seed 12. No real user text.
- **Contention:** load average 6–9 throughout. The rerun of the 0003 probe gave 444 ms against 282 ms idle (§1.1).
- **Not measured:** server or VPS CPUs, arm64, training at 2 threads, RSS after in-process training, direct bf16 loading.
