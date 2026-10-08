# Brief: Phase 0 report scope (ticket 0005)

Prepared 2026-10-08 for a live grilling session on [Phase 0 report scope](../../issues/0005-phase-0-report-scope.md). This brief decides nothing. It collects the facts, lists the decisions in the order to ask them, and gives a recommendation for each.

Inputs read: the ticket, the [map](../../issues/0001-map-decider-ai-engineering.md), [design.md](../design.md) (APPROVED; Premises 3–4, Track 1), [architecture.md](../architecture.md) (`evaluation`, `decider-eval`), [public-benchmark-datasets.md](../research/public-benchmark-datasets.md), [laya-checkpoint-facts.md](../research/laya-checkpoint-facts.md), and the original R3-6 / R3-9 text in `~/.gstack/projects/decider-ai/rharvey-unknown-design-20261008-015741.md`.

## 1. Facts

Each fact is **sourced** (linked, with retrieval date), **measured** (run for this brief) or **estimated** (derivation shown).

### 1.1 LLM list prices (USD per 1M tokens, standard synchronous tier)

All retrieved 2026-10-08. Batch tiers are 50% cheaper at all three providers, but batch calls have no usable latency.

| Provider | Model ID | Input | Output | Notes | Source |
|---|---|---|---|---|---|
| Google | `gemini-3.5-flash-lite` | 0.30 | 2.50 | Thinking on by default at `minimal`; levels minimal/low/medium/high | [pricing](https://ai.google.dev/gemini-api/docs/pricing) (page "Last updated 2026-10-07 UTC"), [thinking](https://ai.google.dev/gemini-api/docs/thinking) |
| Google | `gemini-3.1-flash-lite` | 0.25 | 1.50 | Older Flash-Lite generation | same |
| Google | `gemini-2.5-flash-lite` | 0.10 | 0.40 | Thinking off by default; oldest still listed | same |
| Google | `gemini-3.8-flash` | 0.75 → **1.50 from 2027-01-01** | 3.75 → **7.50 from 2027-01-01** | Thinking cannot go below `low` on 3.7/3.8 Flash | same |
| OpenAI | `gpt-6-luna` | 0.10 | 0.50 | Cheapest current-generation tier | [pricing](https://developers.openai.com/api/docs/pricing) |
| OpenAI | `gpt-5.4-nano` / `gpt-5.4-mini` | 0.20 / 0.75 | 1.25 / 4.50 | | same |
| OpenAI | `gpt-5-mini` / `gpt-5-nano` | 0.25 / 0.05 | 2.00 / 0.40 | Older generation | same |
| Anthropic | Claude Haiku 5.5 (prompts ≤100k tokens) | 0.10 | 0.50 | Claude 4.7+ tokenizer counts ~30% more tokens for the same text | [pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| Anthropic | Claude Haiku 4.5 | 1.00 | 5.00 | | same |

- **Thinking tokens are billed as output.** Google: "response pricing is the sum of output tokens and thinking tokens" ([thinking](https://ai.google.dev/gemini-api/docs/thinking), 2026-10-08). A classification answer is ~7 output tokens, so any thinking budget dominates the output bill and the latency.
- **Prices are scheduled to change.** The Gemini 3.6–3.8 Flash prices double on 2027-01-01 (pricing page, 2026-10-08). "Provider list price at run date" (design Track 1 step 4) therefore makes the gate depend on when the eval runs.

### 1.2 Tokens per classification call

**Measured** with `tiktoken` 0.14.0, `o200k_base` (OpenAI's tokenizer; Gemini and Claude tokenizers differ, Claude 4.7+ counts ~30% more). Prompt: a two-sentence instruction ("choose exactly one label, reply with JSON `{"label": …}`"), the task question, and every label with its one-line description from `public-benchmark-datasets.md`, then the message.

| Task | Labels | Fixed part (instruction + question + labels) | Typical message | Total input | Output (`{"label": "calendar"}`) |
|---|---|---|---|---|---|
| `massive_de_scenario` | 18, German descriptions | 326 | ~10 (median text is 37 characters) | **~336** | **6–7** |
| `clinc_domain` | 11, English descriptions | 187 | ~11 | **~198** | **6–7** |

Structured-output / JSON-schema modes add a provider-side overhead that is not shown here. Thinking adds output tokens on top.

### 1.3 LLM cost per 1,000 decisions (estimated)

From 1.1 × 1.2, MASSIVE prompt (336 in / 7 out), no thinking tokens, standard tier. CLINC costs ~60% of these.

| Model | Cost per 1,000 decisions | +100 thinking tokens per call |
|---|---|---|
| `gemini-2.5-flash-lite` | $0.036 | +$0.04 |
| `gpt-6-luna` | $0.037 | +$0.05 |
| Claude Haiku 5.5 (×1.3 tokens) | $0.048 | +$0.05 |
| `gpt-5.4-nano` | $0.076 | +$0.13 |
| `gemini-3.1-flash-lite` | $0.095 | +$0.15 |
| `gemini-3.5-flash-lite` | $0.118 | +$0.25 |
| `gemini-3.8-flash` (thinking ≥ low, so the right column applies) | $0.278 | +$0.38 |

A full LLM run over both official test sets (2,974 + 5,500 = 8,474 calls) costs about **$0.30–$5** per model. Money is not a constraint on how many LLMs to run.

### 1.4 LLM latency

- **No provider publishes a p95 for short prompts.** The only public tracker found, Artificial Analysis, reports **medians (P50) over 72 hours on a 10,000-token input workload**, including thinking time. For `gemini-3.5-flash-lite` it shows 8.62 s to first answer token and 10.07 s end-to-end for 500 output tokens ([providers page](https://artificialanalysis.ai/models/gemini-3-5-flash-lite/providers), 2026-10-08). That workload is ~30× larger than a classification prompt, so these numbers are not usable for the gate. (sourced)
- **Conclusion (judgement):** p95 for (b) has to be measured by the eval run itself, with synchronous calls, and it depends on the thinking setting, the client location and the time of day. A batch run gives no latency at all.

### 1.5 Local latency and training time (from laya-checkpoint-facts.md)

- Inference: **282 ms p50** for one 3-option question on a ~300-token German mail, 4 threads, laptop (Intel Core Ultra 7 258V). The model card gives 193–464 ms on CPU. (measured / sourced there)
- Training: 11.8 min at 50 examples (measured), ~59 min at 250 (estimated), for ~456-token mails, fp32, 4 threads. MASSIVE and CLINC texts are ~10–15 tokens, so sequences are shorter and training should be faster. That is not measured.
- bf16 training needs AMX or AVX-512-BF16. The laptop has neither. Server CPUs were not measured.

### 1.6 Reference machine prices

**Hetzner Cloud**, Germany/Finland, EUR excluding VAT and IPv4 (+€0.50/month for IPv4). These prices apply to new orders and rescales since **2026-06-15 08:00 CEST**. Source: [Hetzner price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/), 2026-10-08.

| Plan | vCPU | RAM | Hourly | Monthly | Notes |
|---|---|---|---|---|---|
| CX33 | 4 shared | 8 GB | 0.0136 | 8.49 | Too small: the training peak is 8.5 GB RSS |
| **CX43** | 8 shared | 16 GB | **0.0256** | **15.99** | Shared vCPU, so latency is noisier |
| CAX31 | 8 Arm | 16 GB | 0.0336 | 20.99 | Arm. Laya on Arm is unmeasured |
| CPX42 | 8 shared AMD | 16 GB | 0.1114 | 69.49 | Was 25.49 before June 2026 |
| **CCX23** | 4 dedicated AMD | 16 GB | **0.1378** | **85.99** | Was 31.49. The product page showed "currently unavailable" on 2026-10-08 ([general-purpose](https://www.hetzner.com/cloud/general-purpose/)) |
| CCX33 | 8 dedicated AMD | 32 GB | 0.2219 | 138.49 | |

**AWS EC2**, on-demand Linux, USD per hour, from the AWS price feed behind the EC2 pricing page (publication date 2026-10-07T16:54Z, retrieved 2026-10-08; [ec2-ondemand feed, Frankfurt](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/EU%20(Frankfurt)/Linux/index.json)). The us-east-1 figure matches [Vantage](https://instances.vantage.sh/aws/ec2/m7i.xlarge) ($0.2016).

| Instance | vCPU | RAM | eu-central-1 (Frankfurt) | us-east-1 | ×730 h, Frankfurt |
|---|---|---|---|---|---|
| c7i.xlarge | 4 | 8 GiB | 0.2037 | 0.1785 | 148.70 (too small for training) |
| **m7i.xlarge** | 4 | 16 GiB | **0.2415** | 0.2016 | **176.30** |
| m8i.xlarge | 4 | 16 GiB | 0.2536 | 0.2117 | 185.10 |
| c7i.2xlarge | 8 | 16 GiB | 0.4074 | 0.3570 | 297.40 |
| m7i.2xlarge | 8 | 32 GiB | 0.4830 | 0.4032 | 352.60 |

AWS vCPUs are hyperthreads, so 4 vCPU means 2 physical cores. m7i is Sapphire Rapids, which has AMX. That would allow bf16 training (a known property of the CPU family, not tested on the instance).

### 1.7 Local cost per 1,000 decisions under two cost models (estimated)

Assumptions: 0.3 s machine time per decision (1.5); one 250-label retrain taking ~1 h of machine time, amortised over 30,000 decisions (design Track 1 step 4); 10,000 decisions per month.

| Reference machine | **Busy machine-hours** (design's wording: "inference CPU-hours … plus training cost") | **Provisioned machine** (the whole monthly bill ÷ 10,000 decisions) |
|---|---|---|
| Hetzner CX43 | €0.0021 inference + €0.0009 training ≈ **€0.003** | €15.99 / 10 = **€1.60** |
| Hetzner CCX23 | €0.0115 + €0.0046 ≈ **€0.016** | **€8.60** |
| AWS m7i.xlarge (Frankfurt) | $0.020 + $0.008 ≈ **$0.028** | **$17.63** |

Compare with 1.3: LLMs cost **$0.04–$0.28** per 1,000. Under the busy-hours model, local is 10–100× cheaper on every machine. Under the provisioned model at the reference volume, every LLM is 5–500× cheaper. **The choice of cost model decides the gate's cost axis. The machine price does not.** (Decision 4.)

### 1.8 Status of the ticket's original sub-questions

- **R3-6 ((d) as a fourth system): settled by the approved design.** Premise 3 and Track 1 list (b), (c), (d), majority and TF-IDF+LR, and the Success Criteria say "for every system". (sourced, design.md)
- **R3-9 (repeated looks, 98.75%): obsolete as stated.** It was about re-checking the Pilot CI every 100 mails, up to four times. The public-set design has one look per dataset (ticket Notes). A different multiplicity remains (2 datasets × several systems × 4 budgets); see Decision 7.

## 2. Decisions, in the order to ask them

### Decision 1 — Which LLM is baseline (b)?

The gate (Premise 4) re-scopes only if (b) dominates (c) on cost, p95 and macro-F1 on every dataset. The choice of LLM moves all three axes.

| Option | Pros | Cons |
|---|---|---|
| A. One Gemini model: `gemini-3.5-flash-lite` (current cheap Gemini; thinking `minimal` by default) | Matches the founder's own framing ("if gemini is cheaper…"). One client, one price row. | Not the cheapest model on the market (1.3), so a reader can call the cost comparison soft. A single vendor. |
| B. The most capable Flash: `gemini-3.8-flash` | Strongest F1 among Gemini's mass-market tier; a hard F1 bar. | Thinking cannot be switched off, so it is slow and pricier. Its price doubles on 2027-01-01. It makes the gate easy on cost and latency. |
| C. A panel of the cheapest current model per vendor: `gemini-3.5-flash-lite`, `gpt-6-luna`, Claude Haiku 5.5. The gate fires if **any** of them dominates (c) on every dataset. | No straw man on any axis. Costs ~$10 in total. The headline can name the strongest rival per axis. | Three API keys and three adapters (two of them can go through OpenAI-compatible endpoints). More report rows. The gate wording changes from "the LLM" to "any LLM". |
| D. The cheapest model listed: `gemini-2.5-flash-lite` or `gpt-5-nano` | Hardest cost bar. | An older generation is a weak F1 rival. "What people use today" is doubtful. |

**Recommendation: C.** The gate exists to catch the case where switching makes no sense. Testing only one vendor's mid-priced model leaves an easy rebuttal ("Haiku 5.5 or gpt-6-luna is 3× cheaper"), and the panel costs ~$10. If the founder wants a single model, A is the fallback, with the cheaper rivals listed as a stated limitation.

### Decision 2 — How is (b) called (prompt, shots, thinking, output)?

| Option | Pros | Cons |
|---|---|---|
| A. Zero-shot. Same question and label descriptions as `tasks.yaml`. Lowest thinking setting the model allows. Temperature 0. Structured output constrained to the label enum. Sync calls. One run. | This is the status quo call ("one LLM API call returning JSON"). Gives the LLM the same information Laya gets. Cheapest and fastest LLM setting. | It is not the LLM's best possible F1. One run does not show LLM run-to-run variance. |
| B. A, plus k labelled examples per label (few-shot) from the same 50/100/250 budget | A fair "the LLM gets your labels too" comparison at each budget. A learning curve for (b). | Prompt grows ~10–40×, so cost and latency rise. Three LLM runs per dataset. Few-shot is not what most current users do. |
| C. Provider defaults (default thinking, free-text answer parsed afterwards) | "As people actually call it." | Defaults change silently between model versions. Parsing failures need a rule. Results are harder to reproduce. |

**Recommendation: A**, with the prompt template, the model ID, the thinking level and the run date written into the report. Add B later as a named secondary system only if the A result is close. The gate compares (c) at 250 labels with the call people use today, and that call is zero-shot. A also needs one rule for an invalid or failed answer: count it as wrong, and report the count.

### Decision 3 — Where does the LLM call run?

There is a conflict in the documents (see 3.2): the map says "decider-ai never calls Gemini", the architecture says baselines "arrive as exported predictions", and the design says "(b) an LLM baseline the eval script runs offline on public data only".

| Option | Pros | Cons |
|---|---|---|
| A. A separate script outside `src/decider` (e.g. `bench/llm_baseline.py`) writes a predictions JSONL with per-call latency, token usage, model ID and timestamp. `decider-eval` reads it as one more named system. | Keeps every LLM client out of the package and the image, which honours the standing rule as written. Matches the architecture's "baselines arrive as predictions" seam and the dataset doc's named prediction columns. The LLM run is decoupled and cached, so it is not re-paid on every eval. | Needs a prediction-file format with latency and cost fields (Decision 8). Two commands to run. |
| B. `decider-eval` calls the LLM directly, behind an optional extra (`pip install decider-ai[bench]`) | One command. | An LLM client in the repo package. The standing rule needs rewording. Re-runs re-pay and re-measure. |
| C. A, plus a recorded run committed to the repo (aggregates and predictions only) so anyone can reproduce the report without API keys | Reproducible results for the tutorial. | Licence attribution for the shipped predictions. Repo size grows by a few MB. |

**Recommendation: A** (C is a cheap follow-on, see Decision 8). It needs no change to any standing rule, and it fits the existing seam.

### Decision 4 — Local cost model: busy CPU-hours or a provisioned machine?

Per 1.7, this decision alone settles the cost axis.

| Option | Pros | Cons |
|---|---|---|
| A. Busy machine-hours only (the design's current wording) | Scales with volume. Fair when the box is shared with other work. | It flatters (c) by 10–100×. A reader who rents a VM for this alone pays the whole month. |
| B. Provisioned machine at the reference volume (monthly bill ÷ 30,000 decisions over 3 months) | It is what a solo self-hoster pays. | At 10,000 per month it hands the cost axis to every LLM. It hides that the same box serves 10× the volume for the same price. |
| C. Report both, plus the **break-even volume** (decisions per month where the provisioned local cost equals the LLM cost). The gate uses A; the headline states the break-even. | Honest, and gives the reader the number they actually need. Keeps the gate rule as approved. | One more line in the report. The gate uses the model that favours (c), which a reviewer may challenge. |
| D. Report both, and the gate's cost axis counts as "LLM cheaper" if it is cheaper under **either** model | Most conservative for (c). | In practice it hands the cost axis to the LLM, so the gate turns on latency and F1 alone. |

**Recommendation: C.** It keeps the approved gate text (CPU-hours) and adds the one number that makes it honest. Estimated break-even on CX43 against `gemini-3.5-flash-lite`: €15.99 ÷ ~$0.12 per 1,000 ≈ 130,000 decisions per month (state FX at run date).

### Decision 5 — Which reference machine, and where are latency and training timed?

| Option | Pros | Cons |
|---|---|---|
| A. Hetzner CX43 (8 shared vCPU, 16 GB, €0.0256/h, €15.99/month). Rent it for the eval run and measure latency and training there. | The cheapest machine that fits the 8.5 GB training peak. A plausible self-hoster box. The EU location matches the German audience. | Shared vCPUs make p95 noisy (neighbours). Prices rose in 2026 and may rise again. |
| B. Hetzner CCX23 (4 dedicated vCPU, 16 GB, €0.1378/h) | Dedicated cores give a stable p95. | 5× the price of CX43 after June 2026. Showed "currently unavailable" on 2026-10-08. |
| C. AWS m7i.xlarge, Frankfurt ($0.2415/h) | The best-known benchmark machine. AMX allows bf16 training. Readers can rescale to their own AWS bill. | ~10× Hetzner's busy cost. 4 vCPU = 2 physical cores. |
| D. Time on the founder's laptop and price as if on A or C | No rental. | Timings do not belong to the priced machine. Thermal throttling (laptop-facts §5). Readers cannot reproduce it. |

**Recommendation: A**, with (c)'s latency and training measured on the rented CX43 itself, and C's price shown as a second cost line (cost only, no second timing run). Under Decision 4C the gate's cost axis does not depend on the machine (1.7), so pick the box a self-hoster would actually rent. Report in USD at the ECB rate on the run date, so the currency matches the LLM prices.

### Decision 6 — What does "p95 latency per decision" mean, for both sides?

| Option | Pros | Cons |
|---|---|---|
| A. Sequential single requests, warm model, end-to-end wall clock from the caller (LLM: from the reference machine to the API, sync, no streaming; local: `Backend.predict` on one text), over the whole test set, p95 with a bootstrap 95% CI | Same definition on both sides. Matches "replace one call". Cheap. | LLM latency varies by hour. One run captures one afternoon. |
| B. A, split into 3 sessions on different days/times, p95 pooled | More robust LLM p95. | Three times the wall-clock time, still only ~$15. |
| C. Local measured through the HTTP container instead of `Backend.predict` | Includes FastAPI and serialisation overhead, so a truer product latency. | Needs Track 2 before Phase 0 can report. Couples the tracks. |

**Recommendation: B with A's definition.** The gate requires (b) to have "lower p95". A single afternoon's LLM tail is the weakest number in the gate. C waits until Track 2 ships the container.

### Decision 7 — How is uncertainty stated?

| Option | Pros | Cons |
|---|---|---|
| A. Nominal 95% paired-bootstrap CIs (2,000 resamples, seeds averaged inside each resample) on every macro-F1 difference vs (c). The report says plainly that CIs are per comparison and not adjusted. The gate needs no correction. | Simple. The gate is an intersection-union test: it fires only if **every** dataset rejects, and that is already conservative at the nominal level. | Many CIs in one report (2 datasets × ~5 systems × 4 budgets); a reader may cherry-pick. |
| B. Bonferroni-adjusted CIs for the gate comparisons only (e.g. 97.5% for 2 datasets) | Defends against a "you peeked twice" reading. | Statistically unnecessary for a conjunctive rule. Makes re-scoping harder to trigger, which favours launch. |
| C. A, plus CIs on p95 (bootstrap) and a sensitivity line on cost (±30% tokens for tokenizer differences, both cost models) | Every gate axis carries its uncertainty, not only F1. | More numbers. |

**Recommendation: C.** It answers R3-9 in its new form (nominal, stated, no correction needed for an all-datasets rule). It also stops the cost and latency axes from looking more certain than F1.

### Decision 8 — Test-set size

| Option | Pros | Cons |
|---|---|---|
| A. Full official test partitions (2,974 MASSIVE, 5,500 CLINC) | Comparable with published work; tightest CIs. | (c) inference: 8,474 × 0.3 s ≈ 42 min per seed × budget, so ~14 h for 5 seeds × 4 budgets, plus training. |
| B. A fixed, seeded, stratified 1,000 per set, id list committed (the dataset doc's fallback) | ~5 h of inference. | Wider CIs. Not comparable with published numbers. |
| C. Full for the gate cell (250 labels) and for (b)/(d)/majority/TF-IDF; 1,000 subsample for the other budgets | Tight CIs where the gate decides, cheaper elsewhere. | Two test sets in one report; the learning curve mixes sizes. |

**Recommendation: A** if the CX43 run fits in a day (it should: ~14 h of inference plus 20 training runs is about €1 of CX43 time), otherwise C. The gate cell should never be the noisy one.

### Decision 9 — Report files and sections

| Option | Pros | Cons |
|---|---|---|
| A. `report.json` (machine-readable, schema-versioned) + `report.md` rendered from it, one pair per run in `reports/<run-id>/`, plus `predictions/<system>.jsonl` kept outside the repo | One source of truth; Markdown cannot drift from the numbers. | A renderer to write. |
| B. A, plus the prediction files committed (see Decision 3C) | Anyone can recompute everything without API keys or 14 h of CPU. | Attribution files for MASSIVE (CC BY 4.0) and CLINC (CC BY 3.0). A few MB in the repo. |
| C. Markdown only | Least work. | The tutorial and any later re-run have nothing to diff against. |

Proposed `report.md` sections for A/B (all numbers aggregate, no message text):

1. Run header: date, git SHA, dataset pins and checksums, Laya revision, LLM model IDs, prompt hash, thinking level, reference machine, prices with retrieval date, FX rate.
2. Gate outcome per dataset: the three axes for (b) vs (c) at 250 labels, each with its CI, and a verdict (re-scope / launch), then the headline sentence.
3. Macro-F1 table: every system × budget, with Δ vs (c) and its 95% CI; n test.
4. Learning curve for (c) and TF-IDF+LR at 50/100/250/all.
5. Latency: p50/p95 with CI, per system, and the measurement protocol.
6. Cost per 1,000 decisions: both cost models, the break-even volume, training CPU-hours as their own line, labelling cost excluded (R2-7).
7. Per-label precision/recall and recall on the "ignore" class (`general`, `out_of_scope`); confusion matrices in JSON only.
8. Limitations and attribution: CIs are nominal; invalid LLM answers counted as wrong (count shown); dataset licences.

**Recommendation: B.** The approved design already says JSON + Markdown. Committing predictions turns the tutorial's "run it yourself" into a check anyone can run in seconds, at the price of an attribution file.

## 3. Facts that change the ticket's question

1. **Two of the ticket's three questions are already answered.** (d) is in the report (design Premise 3, Success Criteria), and the repeated-looks correction no longer applies (one look per dataset). What remains is Decisions 1–9 above. The ticket's Question text predates the approved design and could be rewritten to match its Notes.
2. **The cost axis turns on the cost model, not on the reference machine's price** (1.7). The ticket asks for "the reference machine and CPU-hour price". The more consequential question is busy hours versus a provisioned machine (Decision 4).
3. **Conflict: the "never calls Gemini" rule.** The map's standing rule says "decider-ai never calls Gemini"; architecture.md says baselines "arrive as exported predictions" and no LLM client ships; design.md says the eval script runs (b) offline. Decision 3 resolves which wording holds. This brief edits none of them.
4. **architecture.md is Pilot-era in the parts this ticket touches.** `decider-eval` "reads the Pilot JSONL export" with "(a) rules and (b) Gemini", and `evaluation` exposes `action_gate(cmp, n_test, per_class) -> Proceed | ReScope | LabelMore` and `urgency_gate`. The approved gate is a three-axis cost-benefit rule that needs cost and latency inputs, and there is no urgency gate. public-benchmark-datasets.md still says the gate is "not called" on public sets and that "public-set numbers never set the tutorial headline", which design.md has since reversed. These need updating once this ticket resolves (not done here).
5. **"List price at run date" moves with the calendar.** Gemini 3.6–3.8 Flash prices double on 2027-01-01. The report must state the price retrieval date, and the gate verdict belongs to that date.
6. **Thinking is a hidden cost and latency setting.** It is billed as output, and some current models cannot switch it off (3.7/3.8 Flash). The (b) settings (Decision 2) are part of the baseline's identity, not a detail.
7. **Possible Laya input-budget issue (for ticket 0003/0017, not this one).** Laya gives question and options a 256-token head budget and cuts each option at 48 tokens (laya-facts §8). MASSIVE's question plus 18 German label descriptions is roughly 270 tokens in `o200k_base`. mmBERT's count will differ, but if it is over 256 the options are silently cut. Then (c)/(d) and (b) would not see the same label descriptions. Worth a check with the mmBERT tokenizer before the eval runs.
8. **Hetzner's dedicated plans more than doubled in June 2026,** and CCX showed "currently unavailable" on 2026-10-08. A dedicated Hetzner box is now neither cheap nor reliably orderable, which shifts the realistic self-host reference to shared CX plans.

## Sources

- Google, Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing (page last updated 2026-10-07; retrieved 2026-10-08)
- Google, Gemini thinking: https://ai.google.dev/gemini-api/docs/thinking (retrieved 2026-10-08)
- OpenAI, API pricing: https://developers.openai.com/api/docs/pricing (retrieved 2026-10-08)
- Anthropic, Claude pricing: https://platform.claude.com/docs/en/about-claude/pricing (retrieved 2026-10-08)
- Artificial Analysis, Gemini 3.5 Flash-Lite providers: https://artificialanalysis.ai/models/gemini-3-5-flash-lite/providers (retrieved 2026-10-08)
- Hetzner, price adjustment of 15 June 2026: https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/ (retrieved 2026-10-08)
- Hetzner, General Purpose / Regular Performance plan pages (specs, availability): https://www.hetzner.com/cloud/general-purpose/, https://www.hetzner.com/cloud/regular-performance/ (retrieved 2026-10-08)
- AWS EC2 on-demand price feed (Frankfurt and N. Virginia, Linux), publication 2026-10-07T16:54Z: https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/EU%20(Frankfurt)/Linux/index.json (retrieved 2026-10-08)
- Vantage, m7i.xlarge / m7i.2xlarge (cross-check, CPU family): https://instances.vantage.sh/aws/ec2/m7i.xlarge (updated 2026-10-08)
- Token counts: `tiktoken` 0.14.0, `o200k_base`, run 2026-10-08 on the prompts described in 1.2.
