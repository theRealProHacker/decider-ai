# decider-ai Phase 0 report

- Run date: 2026-10-09
- Git SHA: e00147dde0e4316f1fa573c39990cda730d6f0e5 at write time; the code ran from d60874e (later commits changed only a progress-callback signature and tests)
- Note: the laptop suspended 18:00–18:21 and 18:32–00:03 on 2026-10-08 during the CLINC runs; suspended time can only inflate Laya training time and latency
- Machine: Intel Core Ultra 7 258V, 8 threads, 30 GB RAM, Linux 6.17 (laptop) (corrected after the run; the CPU-name lookup failed under a German locale)
- Backend: laya (Laya revision 1720e3e3357cfe1e281542e223f8273b0890ca34, SDK 0.4.0)
- CPU price: 0.0256 EUR/h (retrieved 2026-10-08)
- FX: 0.86 (2026-10-08)
- Budgets 250; seeds 0, 1, 2, 3, 4
- CIs: nominal 95% paired bootstrap (2000 resamples, seeds averaged inside each resample), unadjusted; one look per dataset
- Local cost: busy CPU-hours at the hourly rate plus one retrain amortised over 30,000 decisions

## Outcome

Gate at 250 labels: **Launch**.

massive_de_scenario: at 250 labels the fine-tune scores macro-F1 0.717 vs gemini-3.5-flash-lite 0.864 (Δ gemini-3.5-flash-lite − fine-tune +0.148, 95% CI +0.123 to +0.172), costs 0.0043 EUR vs 0.0808 EUR per 1,000 decisions, p95 626.3 ms vs 804.5 ms.

clinc_domain: at 250 labels the fine-tune scores macro-F1 0.734 vs gemini-3.5-flash-lite 0.836 (Δ gemini-3.5-flash-lite − fine-tune +0.102, 95% CI +0.081 to +0.126), costs 0.0027 EUR vs 0.0766 EUR per 1,000 decisions, p95 344.6 ms vs 694.5 ms.

Zero-shot rule (zero_shot ≥ tfidf_lr at 50 on every dataset): not applicable.

| Dataset | LLM system | Cheaper | Faster p95 | Better F1 (CI > 0) | LLM wins |
|---|---|---|---|---|---|
| massive_de_scenario | gemini-3.5-flash-lite | no | no | yes | no |
| clinc_domain | gemini-3.5-flash-lite | no | no | yes | no |

## massive_de_scenario

Test set n = 1000 (18 labels). Records sha256 `2c2041a8d3417a5499a685377155685d2274a1b91290f785c6ca892ded8dee08`.

Macro-F1 with Δ vs the fine-tune at the same budget (zero-shot systems: vs the fine-tune at each budget); nominal 95% paired-bootstrap CI, unadjusted.

| System | Budget | Macro-F1 | Δ vs fine-tune | 95% CI | Invalid | p95 ms | Cost / 1,000 (EUR) |
|---|---|---|---|---|---|---|---|
| finetune | 250 | 0.717 | — | — | 0 | 626.3 | 0.0043 |
| zero_shot | zero-shot (vs 250) | 0.570 | -0.147 | -0.176 to -0.120 | 0 | 513.4 | 0.0035 |
| gemini-3.5-flash-lite | zero-shot (vs 250) | 0.864 | +0.148 | +0.123 to +0.172 | 0 | 804.5 | 0.0808 |
| majority | 250 | 0.013 | -0.703 | -0.726 to -0.676 | 0 | 0.0 | 0.0000 |
| tfidf_lr | 250 | 0.619 | -0.097 | -0.123 to -0.074 | 0 | 1.4 | 0.0000 |

Learning curve (macro-F1, mean over seeds):

| System | 250 |
|---|---|
| finetune | 0.717 |
| tfidf_lr | 0.619 |

Cost lines (EUR):

- finetune (budget 250): inference 0.003017 + retrain 0.001254 per 1,000; training CPU-hours 1.469708
- zero_shot (zero-shot): inference 0.003516 + retrain 0.000000 per 1,000; training CPU-hours 0.000000
- gemini-3.5-flash-lite (zero-shot): 0.0808 per 1,000 at list price (±30% tokens: 0.0565 to 0.1050); mean tokens 304.3 in / 1.1 out
- majority (budget 250): inference 0.000000 + retrain 0.000000 per 1,000; training CPU-hours 0.000000
- tfidf_lr (budget 250): inference 0.000009 + retrain 0.000000 per 1,000; training CPU-hours 0.000434
- gemini-3.5-flash-lite: model gemini-3.5-flash-lite, settings {"output": "enum restricted to the task's labels", "shots": 0, "temperature": 0.0, "thinking_level": "MINIMAL"}, prices {"price_input_per_million_usd": 0.3, "price_output_per_million_usd": 2.5} (retrieved 2026-10-08)

## clinc_domain

Test set n = 1000 (11 labels). Records sha256 `78d2ad8030f85e9cf0e383131ce8fe584af4c00735843613ce1e2dec822d428a`.

Macro-F1 with Δ vs the fine-tune at the same budget (zero-shot systems: vs the fine-tune at each budget); nominal 95% paired-bootstrap CI, unadjusted.

| System | Budget | Macro-F1 | Δ vs fine-tune | 95% CI | Invalid | p95 ms | Cost / 1,000 (EUR) |
|---|---|---|---|---|---|---|---|
| finetune | 250 | 0.734 | — | — | 0 | 344.6 | 0.0027 |
| zero_shot | zero-shot (vs 250) | 0.456 | -0.278 | -0.311 to -0.247 | 0 | 264.1 | 0.0017 |
| gemini-3.5-flash-lite | zero-shot (vs 250) | 0.836 | +0.102 | +0.081 to +0.126 | 0 | 694.5 | 0.0766 |
| majority | 250 | 0.014 | -0.720 | -0.739 to -0.699 | 0 | 0.0 | 0.0000 |
| tfidf_lr | 250 | 0.588 | -0.146 | -0.165 to -0.126 | 0 | 1.5 | 0.0000 |

Learning curve (macro-F1, mean over seeds):

| System | 250 |
|---|---|
| finetune | 0.734 |
| tfidf_lr | 0.588 |

Cost lines (EUR):

- finetune (budget 250): inference 0.001889 + retrain 0.000824 per 1,000; training CPU-hours 0.965515
- zero_shot (zero-shot): inference 0.001731 + retrain 0.000000 per 1,000; training CPU-hours 0.000000
- gemini-3.5-flash-lite (zero-shot): 0.0766 per 1,000 at list price (±30% tokens: 0.0536 to 0.0996); mean tokens 276.2 in / 2.5 out
- majority (budget 250): inference 0.000000 + retrain 0.000000 per 1,000; training CPU-hours 0.000000
- tfidf_lr (budget 250): inference 0.000009 + retrain 0.000000 per 1,000; training CPU-hours 0.000408
- gemini-3.5-flash-lite: model gemini-3.5-flash-lite, settings {"output": "enum restricted to the task's labels", "shots": 0, "temperature": 0.0, "thinking_level": "MINIMAL"}, prices {"price_input_per_million_usd": 0.3, "price_output_per_million_usd": 2.5} (retrieved 2026-10-08)

## Datasets

- massive_de_scenario: MASSIVE 1.1, locale de-DE, scenario level; FitzGerald et al., Amazon (2022); derived from SLURP; licence CC BY 4.0; https://github.com/alexa/massive; pin amazon-massive-dataset-1.1.tar.gz (alexa/massive @ f966f21846043aabef9b0f974fa7970027f43738); sha256 amazon-massive-dataset-1.1.tar.gz `4cba5faa11c71437928e17cb1b9b3d8b8e727e7ea363a3a9a8045e19c0491577`, 1.1/data/de-DE.jsonl `5e09cc550b38d37faf002e0ff42103acd330906e23032689e8f071e1cf3ff621`
- clinc_domain: CLINC150 oos_plus, domain level + out_of_scope; Larson et al., EMNLP 2019; licence CC BY 3.0; https://github.com/clinc/oos-eval; pin clinc/oos-eval @ 828f8093932c8fe6ca7936c3d2e52903b1c523de; sha256 data_oos_plus.json `bfcca9ae515623541dc1983c94c4ed7cae9d26b42ae47d74b972e51bb6f7a21f`, domains.json `b947b579d3b8e74b06f93b01083d8efaff2888b43a3e362533bd88a6e1211b3a`
