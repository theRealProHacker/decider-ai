# decider-ai Phase 0 report

- Run date: 2026-10-11
- Git SHA: d2d6981f7c582c3b1c5537c417a6c02fa9d70619
- Machine: Intel Core Ultra 7 258V, 8 threads, 30 GB RAM, Linux 6.17 (laptop)
- Backend: laya (Laya revision 1720e3e3357cfe1e281542e223f8273b0890ca34, SDK 0.4.0)
- CPU price: 0.0256 EUR/h (retrieved 2026-10-08)
- FX: 0.86 (2026-10-08)
- Budgets 1000; seeds 0
- CIs: nominal 95% paired bootstrap (2000 resamples, seeds averaged inside each resample), unadjusted; one look per dataset
- Local cost: busy CPU-hours at the hourly rate plus one retrain amortised over 30,000 decisions

## Outcome

Gate at 250 labels: not applicable (budget 250 not run).

Zero-shot rule (zero_shot ≥ tfidf_lr at 50 on every dataset): not applicable.

## massive_de_scenario

Test set n = 2974 (18 labels). Records sha256 `d617edbb51a609d846581c4c83561daab9f58a10b35f4c14182be00d611b22bd`.

Macro-F1 with Δ vs the fine-tune at the same budget (zero-shot systems: vs the fine-tune at each budget); nominal 95% paired-bootstrap CI, unadjusted.

| System | Budget | Macro-F1 | Δ vs fine-tune | 95% CI | Invalid | p95 ms | Cost / 1,000 (EUR) |
|---|---|---|---|---|---|---|---|
| finetune | 1000 | 0.789 | — | — | 0 | 851.2 | 0.0050 |
| zero_shot | zero-shot (vs 1000) | 0.566 | -0.223 | -0.241 to -0.204 | 0 | 477.1 | 0.0027 |
| gemini-3.5-flash-lite | zero-shot (vs 1000) | 0.872 | +0.083 | +0.068 to +0.100 | 0 | 804.5 | 0.0808 |
| majority | 1000 | 0.013 | -0.776 | -0.790 to -0.759 | 0 | 0.0 | 0.0000 |
| tfidf_lr | 1000 | 0.792 | +0.002 | -0.013 to +0.020 | 0 | 1.4 | 0.0000 |
| verdict-1.4 | zero-shot (vs 1000) | 0.300 | -0.489 | -0.511 to -0.468 | 0 | 844.3 | 0.0050 |

Learning curve (macro-F1, mean over seeds):

| System | 1000 |
|---|---|
| finetune | 0.789 |
| tfidf_lr | 0.792 |

Cost lines (EUR):

- finetune (budget 1000): inference 0.003299 + retrain 0.001661 per 1,000; training CPU-hours 1.945914
- zero_shot (zero-shot): inference 0.002714 + retrain 0.000000 per 1,000; training CPU-hours 0.000000
- gemini-3.5-flash-lite (zero-shot): 0.0808 per 1,000 at list price (±30% tokens: 0.0565 to 0.1050); mean tokens 304.3 in / 1.1 out
- majority (budget 1000): inference 0.000000 + retrain 0.000000 per 1,000; training CPU-hours 0.000000
- tfidf_lr (budget 1000): inference 0.000008 + retrain 0.000001 per 1,000; training CPU-hours 0.000681
- verdict-1.4 (zero-shot): inference 0.005024 + retrain 0.000000 per 1,000; training CPU-hours 0.000000
- gemini-3.5-flash-lite: model gemini-3.5-flash-lite, settings {"output": "enum restricted to the task's labels", "shots": 0, "temperature": 0.0, "thinking_level": "MINIMAL"}, prices {"price_input_per_million_usd": 0.3, "price_output_per_million_usd": 2.5} (retrieved 2026-10-08)

## massive_en_scenario

Test set n = 2974 (18 labels). Records sha256 `4067315d1ac17f4b85877d76157e3616b345608b07533ff4ce9d945062903aa1`.

Macro-F1 with Δ vs the fine-tune at the same budget (zero-shot systems: vs the fine-tune at each budget); nominal 95% paired-bootstrap CI, unadjusted.

| System | Budget | Macro-F1 | Δ vs fine-tune | 95% CI | Invalid | p95 ms | Cost / 1,000 (EUR) |
|---|---|---|---|---|---|---|---|
| finetune | 1000 | 0.809 | — | — | 0 | 350.9 | 0.0032 |
| zero_shot | zero-shot (vs 1000) | 0.635 | -0.174 | -0.192 to -0.156 | 0 | 372.6 | 0.0022 |
| majority | 1000 | 0.013 | -0.796 | -0.811 to -0.780 | 0 | 0.0 | 0.0000 |
| tfidf_lr | 1000 | 0.812 | +0.003 | -0.014 to +0.020 | 0 | 1.6 | 0.0000 |
| verdict-1.4 | zero-shot (vs 1000) | 0.607 | -0.202 | -0.221 to -0.186 | 0 | 1725.1 | 0.0071 |

Learning curve (macro-F1, mean over seeds):

| System | 1000 |
|---|---|
| finetune | 0.809 |
| tfidf_lr | 0.812 |

Cost lines (EUR):

- finetune (budget 1000): inference 0.002053 + retrain 0.001115 per 1,000; training CPU-hours 1.306085
- zero_shot (zero-shot): inference 0.002168 + retrain 0.000000 per 1,000; training CPU-hours 0.000000
- majority (budget 1000): inference 0.000000 + retrain 0.000000 per 1,000; training CPU-hours 0.000000
- tfidf_lr (budget 1000): inference 0.000008 + retrain 0.000000 per 1,000; training CPU-hours 0.000531
- verdict-1.4 (zero-shot): inference 0.007106 + retrain 0.000000 per 1,000; training CPU-hours 0.000000

## Datasets

- massive_de_scenario: MASSIVE 1.1, locale de-DE, scenario level; FitzGerald et al., Amazon (2022); derived from SLURP; licence CC BY 4.0; https://github.com/alexa/massive; pin amazon-massive-dataset-1.1.tar.gz (alexa/massive @ f966f21846043aabef9b0f974fa7970027f43738); sha256 amazon-massive-dataset-1.1.tar.gz `4cba5faa11c71437928e17cb1b9b3d8b8e727e7ea363a3a9a8045e19c0491577`, 1.1/data/de-DE.jsonl `5e09cc550b38d37faf002e0ff42103acd330906e23032689e8f071e1cf3ff621`
- massive_en_scenario: massive_en_scenario
