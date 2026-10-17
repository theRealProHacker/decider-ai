# decider-ai Phase 0 report

- Run date: 2026-10-12
- Git SHA: d2d6981f7c582c3b1c5537c417a6c02fa9d70619
- Machine: Intel Core Ultra 7 258V, 8 threads, 30 GB RAM, Linux 6.17 (laptop)
- Backend: laya (Laya revision 1720e3e3357cfe1e281542e223f8273b0890ca34, SDK 0.4.0)
- CPU price: 0.0256 EUR/h (retrieved 2026-10-08)
- FX: n/a
- Budgets 250; seeds 0
- CIs: nominal 95% paired bootstrap (2000 resamples, seeds averaged inside each resample), unadjusted; one look per dataset
- Local cost: busy CPU-hours at the hourly rate plus one retrain amortised over 30,000 decisions

## Outcome

Gate at 250 labels: not applicable (no API system for massive_en_scenario).

Zero-shot rule (zero_shot ≥ tfidf_lr at 50 on every dataset): not applicable.

## massive_en_scenario

Test set n = 2974 (18 labels). Records sha256 `4067315d1ac17f4b85877d76157e3616b345608b07533ff4ce9d945062903aa1`.

Macro-F1 with Δ vs the fine-tune at the same budget (zero-shot systems: vs the fine-tune at each budget); nominal 95% paired-bootstrap CI, unadjusted.

| System | Budget | Macro-F1 | Δ vs fine-tune | 95% CI | Invalid | p95 ms | Cost / 1,000 (EUR) |
|---|---|---|---|---|---|---|---|
| finetune | 250 | 0.790 | — | — | 0 | 424.6 | 0.0028 |
| zero_shot | zero-shot (vs 250) | 0.635 | -0.154 | -0.172 to -0.137 | 0 | 310.4 | 0.0017 |
| majority | 250 | 0.013 | -0.777 | -0.792 to -0.761 | 0 | 0.0 | 0.0000 |
| tfidf_lr | 250 | 0.665 | -0.125 | -0.144 to -0.106 | 0 | 1.2 | 0.0000 |
| verdict-1.4 | zero-shot (vs 250) | 0.607 | -0.183 | -0.203 to -0.165 | 0 | 1725.1 | 0.0071 |
| xlmr_base | 250 | 0.461 | -0.329 | -0.349 to -0.308 | 0 | 36.9 | 0.0003 |

Learning curve (macro-F1, mean over seeds):

| System | 250 |
|---|---|
| finetune | 0.790 |
| tfidf_lr | 0.665 |

Cost lines (EUR):

- finetune (budget 250): inference 0.002003 + retrain 0.000832 per 1,000; training CPU-hours 0.975347
- zero_shot (zero-shot): inference 0.001684 + retrain 0.000000 per 1,000; training CPU-hours 0.000000
- majority (budget 250): inference 0.000000 + retrain 0.000000 per 1,000; training CPU-hours 0.000000
- tfidf_lr (budget 250): inference 0.000008 + retrain 0.000000 per 1,000; training CPU-hours 0.000352
- verdict-1.4 (zero-shot): inference 0.007106 + retrain 0.000000 per 1,000; training CPU-hours 0.000000
- xlmr_base (budget 250): inference 0.000165 + retrain 0.000096 per 1,000; training CPU-hours 0.112096

## Datasets

- massive_en_scenario: massive_en_scenario
