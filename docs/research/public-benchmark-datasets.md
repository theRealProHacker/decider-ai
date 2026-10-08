# Public benchmark datasets

Ticket: [Public benchmark datasets](../../issues/0015-public-benchmark-datasets.md). Researched 2026-10-08.

This benchmark gives decider-ai reproducible, publishable numbers while Pilot data is pending. **It does not replace the Phase 0 Pilot gate.** The action gate and urgency gate in `docs/design.md` (steps 5–8) are decided only on blind, rule-unmatched Pilot mail. Public-set numbers never set the tutorial headline and never feed `action_gate` or `urgency_gate`.

## Recommendation

| # | Dataset | Language | decider-ai task | Labels | "ignore" class | Ordinal 2nd label |
|---|---|---|---|---|---|---|
| 1 | MASSIVE 1.1, locale `de-DE`, scenario level | German | `massive_de_scenario` | 18 | `general` | none |
| 2 | CLINC150 `oos_plus`, domain level + out-of-scope | English | `clinc_domain` | 11 (10 domains + `out_of_scope`) | `out_of_scope` | none |
| 3 | Banking77 (optional, many-label stress test) | English | `banking77` | 77 | none | none |

Sets 1 and 2 are the core benchmark. Set 1 covers German; set 2 is the only commercially usable set with a real out-of-scope class, which plays "ignore" the way Pilot's `ignore` action does. Set 3 runs only if the Laya checkpoint can take 77 options in one input (see [Laya checkpoint facts](../../issues/0003-laya-checkpoint-facts.md)). Without that, the benchmark is sets 1 and 2.

None of the commercially usable sets has an urgency-like ordinal label, so the public benchmark cannot exercise the urgency gate (MAE). See [Gaps](#gaps-and-follow-ups).

## Pinned sources

Pin the canonical upstream files, not Hugging Face mirrors. MASSIVE and Banking77 on Hugging Face are loader scripts that download the same upstream files at run time.

| Dataset | Canonical source (pin) | File checksums (sha256) | Licence |
|---|---|---|---|
| MASSIVE 1.1 | `https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz`, referenced by [alexa/massive @ `f966f21846043aabef9b0f974fa7970027f43738`](https://github.com/alexa/massive/blob/f966f21846043aabef9b0f974fa7970027f43738/README.md) | tarball `4cba5faa11c71437928e17cb1b9b3d8b8e727e7ea363a3a9a8045e19c0491577`; `1.1/data/de-DE.jsonl` `5e09cc550b38d37faf002e0ff42103acd330906e23032689e8f071e1cf3ff621` | CC BY 4.0: `1.1/LICENSE` inside the tarball ("Attribution 4.0 International"); [NOTICE.md @ f966f21](https://github.com/alexa/massive/blob/f966f21846043aabef9b0f974fa7970027f43738/NOTICE.md): "The MASSIVE dataset is licensed under CC BY 4.0". Derived from SLURP, also CC BY 4.0 (same NOTICE). HF mirror: [`AmazonScience/massive` @ `ff6bd8e4b27c3543e4f8fe2108f32bb95a6f8740`](https://huggingface.co/datasets/AmazonScience/massive/tree/ff6bd8e4b27c3543e4f8fe2108f32bb95a6f8740), card `license: cc-by-4.0`, loader `massive.py` downloads the same S3 tarball. |
| CLINC150 | [clinc/oos-eval @ `828f8093932c8fe6ca7936c3d2e52903b1c523de`](https://github.com/clinc/oos-eval/tree/828f8093932c8fe6ca7936c3d2e52903b1c523de) `data/data_oos_plus.json` and `data/domains.json` | `data_oos_plus.json` `bfcca9ae515623541dc1983c94c4ed7cae9d26b42ae47d74b972e51bb6f7a21f` | CC BY 3.0: [LICENSE @ 828f809](https://github.com/clinc/oos-eval/blob/828f8093932c8fe6ca7936c3d2e52903b1c523de/LICENSE) ("Attribution 3.0 Unported"). HF mirror: [`clinc/clinc_oos` @ `155b9c710419136e17307b80d0a13e68cd46b4ec`](https://huggingface.co/datasets/clinc/clinc_oos/tree/155b9c710419136e17307b80d0a13e68cd46b4ec), config `plus`, `license: cc-by-3.0`, same split sizes. |
| Banking77 | [PolyAI-LDN/task-specific-datasets @ `57ec275d8078af65b7731c2a98be812d844a6d6b`](https://github.com/PolyAI-LDN/task-specific-datasets/tree/57ec275d8078af65b7731c2a98be812d844a6d6b/banking_data) `banking_data/train.csv`, `test.csv` | `train.csv` `b06e26ac675513959a63135f11b94ea7786ed02da65db93a5650d8838cbc664b`; `test.csv` `d12d6e3bc4c3103966ae786dc435913c0c563dfa328f5a3646d0e62cfeeb474d` | CC BY 4.0: [LICENSE @ 57ec275](https://github.com/PolyAI-LDN/task-specific-datasets/blob/57ec275d8078af65b7731c2a98be812d844a6d6b/LICENSE) (GitHub detects `CC-BY-4.0`). HF mirror: [`PolyAI/banking77` @ `90d4e2ee5521c04fc1488f065b8b083658768c57`](https://huggingface.co/datasets/PolyAI/banking77/tree/90d4e2ee5521c04fc1488f065b8b083658768c57), `license: cc-by-4.0`, loader downloads the same GitHub `master` CSVs (so pin the commit, not `master`). |

All three allow commercial use. Their only obligation is attribution: name the dataset, authors and licence, and link it. None is share-alike, so a fixture subset shipped in the repo carries no copyleft obligation.

Counts below come from the pinned files above (downloaded 2026-10-08, counted with a throwaway script).

## 1. MASSIVE `de-DE`, scenario level (German)

Human-localised German translations of SLURP voice-assistant commands. Text is lower-cased and unpunctuated (median 37 characters, max 393). Each record has `id`, `partition`, `scenario` (18), `intent` (60) and `utt`.

Splits (official `partition` field): train 11,514 · dev 2,033 · test 2,974.

Class balance, scenario (train / dev / test):

| scenario | train | dev | test |
|---|---|---|---|
| calendar | 1688 | 280 | 402 |
| play | 1377 | 260 | 387 |
| qa | 1183 | 214 | 288 |
| email | 953 | 157 | 271 |
| iot | 769 | 118 | 220 |
| general | 652 | 122 | 189 |
| weather | 573 | 126 | 156 |
| transport | 571 | 110 | 124 |
| lists | 539 | 112 | 142 |
| news | 503 | 82 | 124 |
| recommendation | 433 | 69 | 94 |
| datetime | 402 | 73 | 103 |
| social | 391 | 68 | 106 |
| alarm | 390 | 64 | 96 |
| music | 332 | 56 | 81 |
| audio | 290 | 35 | 62 |
| takeaway | 257 | 44 | 57 |
| cooking | 211 | 43 | 72 |

Majority class `calendar` is 13.5% of test. Use the scenario level, not the 60 intents: intents are much less balanced (train min `cooking_query` 4, test min `general_greet` 1), and 60 options inflate the input the same way Banking77 does.

Task mapping (`tasks.yaml` sketch; the question is in German because the set is German):

- **question:** "Worum geht es in dieser Anfrage an einen Sprachassistenten?"
- **labels** (one-line descriptions, derived from the intents each scenario contains):
  - `alarm`: Wecker stellen, abfragen oder löschen
  - `audio`: Lautstärke ändern oder stummschalten
  - `calendar`: Termine und Erinnerungen anlegen, abfragen oder löschen
  - `cooking`: Rezepte und Kochfragen
  - `datetime`: Uhrzeit oder Datum abfragen, Zeitzonen umrechnen
  - `email`: E-Mails lesen oder senden, Kontakte verwalten
  - `general`: Smalltalk, Witze, Begrüßungen und Äußerungen ohne klaren Auftrag
  - `iot`: Smart-Home-Geräte steuern (Licht, Steckdosen, Staubsauger, Kaffeemaschine)
  - `lists`: Listen anlegen, ergänzen, abfragen oder löschen
  - `music`: Musikgeschmack mitteilen, laufenden Titel erfragen, Musikeinstellungen
  - `news`: Nachrichten abfragen
  - `play`: Musik, Radio, Podcasts, Hörbücher oder Spiele starten
  - `qa`: Wissensfragen, Definitionen, Rechnen, Währungen, Aktienkurse
  - `recommendation`: Empfehlungen für Veranstaltungen, Orte oder Filme
  - `social`: In sozialen Medien posten oder dort nachsehen, Beschwerden an Firmen
  - `takeaway`: Essen bestellen oder Bestellstatus abfragen
  - `transport`: Tickets, Taxi, Verkehrslage, Fahrpläne
  - `weather`: Wetter abfragen
- **"ignore" role:** `general` (intents `general_quirky` 555/105/169, `general_joke` 72/15/19, `general_greet` 25/2/1 in train/dev/test). It is a catch-all with no actionable request, the closest analogue to Pilot's `ignore`. Caveat: `general_quirky` is noisy and contains some device-status requests (e.g. "überprüfe ob mein laptop funktioniert"), a known SLURP property. Read per-label recall on `general` with that in mind.
- **Ordinal second label:** none.

## 2. CLINC150 `oos_plus`, domain level + out-of-scope (English)

Crowd-sourced English assistant queries, 150 intents grouped into 10 domains of 15 intents each (`domains.json`), plus an out-of-scope (`oos`) set. The `oos_plus` variant has the larger out-of-scope training set.

Splits (from `data_oos_plus.json`; in-scope + oos): train 15,000 + 250 = 15,250 · val 3,000 + 100 = 3,100 · test 4,500 + 1,000 = 5,500. In-scope intents are exactly balanced: 100 / 20 / 30 per intent.

Class balance at domain level:

| label | train | val | test |
|---|---|---|---|
| each of the 10 domains | 1,500 | 300 | 450 |
| `out_of_scope` | 250 | 100 | 1,000 |

`out_of_scope` is the smallest class in train but the largest in test (18.2%). That mirrors Pilot, where unactionable mail is under-represented in what operators correct but common in traffic. The 10 domains tie for majority in train. The majority baseline breaks the tie by first label in sorted order (`auto_and_commute`); the reference run below used `travel`, which scores the same macro-F1.

Task mapping:

- **question:** "Which area does this request to a virtual assistant belong to?"
- **labels:** `banking` (accounts, transfers, bills, fraud), `credit_cards` (card limits, rewards, applications, declines), `kitchen_and_dining` (recipes, restaurants, nutrition), `home` (lists, reminders, smart home), `auto_and_commute` (car, fuel, traffic, commute), `travel` (flights, bookings, visas, travel alerts), `utility` (time, weather, calculator, alarms), `work` (meetings, PTO, payroll, schedules), `small_talk` (greetings, jokes, chit-chat), `meta` (settings of the assistant itself: name, language, repeat), `out_of_scope` (a request none of these areas covers). Write the final one-line descriptions from the 15 intent names per domain in `domains.json`.
- **"ignore" role:** `out_of_scope`. This is the cleanest public analogue of Pilot's `ignore`: a real "none of the above" class collected separately from in-scope queries.
- **Ordinal second label:** none.

The 150-intent level is the standard CLINC benchmark, but 151 options are impractical for a question-plus-options model. Use the domain level.

## 3. Banking77 (English, optional)

13,083 English online-banking customer queries, 77 fine-grained intents. There is no validation split (carve one from train if needed).

Splits: train 10,003 · test 3,080. Balance: test is exactly 40 per label. Train is imbalanced: max `card_payment_fee_charged` 187, min `contactless_not_working` 35.

Task mapping:

- **question:** "What does this bank customer need?"
- **labels:** the 77 categories, with one-line descriptions written from the label names (e.g. `card_arrival`: "asks when or whether their new card will arrive").
- **"ignore" role:** none. Every query is in scope. Report macro-F1 only, no ignore recall.
- **Ordinal second label:** none.

Why keep it: it is the closest public set to support routing (real customer phrasing, a single domain, many near-duplicate labels), and the standard few-shot intent benchmark. Why it is optional: 77 options with descriptions may exceed the Laya input limit, which the [Laya checkpoint facts](../../issues/0003-laya-checkpoint-facts.md) ticket must pin. Its training budgets are per class (5 and 10 shots, i.e. 385 and 770 examples), because a 50-example budget cannot cover 77 labels.

## Candidates rejected or not chosen

| Candidate | Verdict | Reason (source) |
|---|---|---|
| `Tobi-Bueck/customer-support-tickets` @ `ddf1c81a5475992c4fa6752bf1e8b4e31f07bbeb` | **Rejected: non-commercial** | Card `license: cc-by-nc-4.0` ([README @ ddf1c81](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/blob/ddf1c81a5475992c4fa6752bf1e8b4e31f07bbeb/README.md)). The licence is NC at every revision checked, back to the initial commit `299eafd9edd8`. It is also synthetic (the card advertises the author's synthetic ticket generator). It would otherwise fit well (DE/EN, queue + Low/Medium/Critical priority). The HF search for German ticket sets returned only NC copies and derivatives of it (`ale-dp/*`, `Eklavya73/*`, `Prady06/*`, `vasu1111/*` …, all `cc-by-nc-4.0`). |
| GermEval 2017 (Deutsche Bahn customer feedback) | **Rejected until the licence is clarified** | Structurally the best German fit: `Relevance` true/false is an ignore class, and document `Sentiment` neg/neu/pos is a second, roughly ordinal label. Counts at [`uhhlt/GermEval2017` @ `99da66e994364c565ff980960c83fc9039f81266`](https://huggingface.co/datasets/uhhlt/GermEval2017/tree/99da66e994364c565ff980960c83fc9039f81266): train 19,432 (relevant 16,201 / irrelevant 3,231), dev 2,369, test_syn 2,555 (irrelevant 460), test_dia 1,842. The licence sources conflict, though. The organisers' download page ([ltdata1.informatik.uni-hamburg.de/germeval2017](https://ltdata1.informatik.uni-hamburg.de/germeval2017/)) says "licensed under the CC-BY terms", while the same lab's HF card says "creative commons by nc (4.0)". The texts are also scraped social-media posts (Twitter, Facebook, Q&A sites), which carry their own platform terms. Under the commercial-use constraint, the stricter reading wins. |
| 10kGNAD | Rejected: non-commercial | Excluded by the ticket (CC BY-NC-SA). |
| IT support tickets (Zenodo [10.5281/zenodo.7648117](https://doi.org/10.5281/zenodo.7648117); HF mirror `tasksource/it-support-tickets` @ `e0bbdcb96c84feaa394aaae9c48f8ba4b818451b`) | Not chosen; noted as interesting | Real, PII-masked IT tickets, CC BY 4.0 (Zenodo metadata `cc-by-4.0`). 7 categories; train 1,572 / test 657 (test: Support general 221, Fileservice 138, O365 92, Software 58, EOL 58, Active Directory 49, Computer-Services 41). Its `[NAME]`/`[COMPANY]` placeholders resemble Pilot's pseudonymised text, which makes it a good stress test for that format. Not chosen because it is mostly English: a stopword heuristic flagged only ~24 train / ~18 test tickets as German. It has no ignore class and no priority label. |
| MTOP German (`tasksource/mtop`, CC BY-SA 4.0) | Not chosen | Commercial use is allowed, but share-alike binds any shipped subset. It is the same assistant-command genre as MASSIVE with no added coverage. |
| `deutsche-telekom/NLU-Evaluation-Data-en-de` (CC BY 4.0) | Not chosen | A German translation of the same SLURP-family assistant commands MASSIVE already covers. |
| Bitext customer-support sets | Not chosen | English only, synthetic, CDLA-Sharing-1.0. |
| Amazon Reviews Multi | Not chosen | Its licence restricts use to non-commercial research. |

## Baselines

Every system is scored on the same official test partition with macro-F1 (primary, as in the action gate), plus accuracy, per-label precision/recall and a confusion matrix.

1. **Majority class.** Predict the most frequent label in the training budget used (ties broken by sorted label name) for every test example. It is deterministic and needs no seeds. It is the floor the design's first-model rule and zero-shot rule refer to. Its macro-F1 is ≈ (2p/(1+p))/K, where p is that label's test share and K the label count. The value is tiny on these sets (≤ 0.014), which confirms R3-7: it is too low a bar on its own.
2. **TF-IDF + logistic regression.** This is the cheap supervised comparator. On public sets it stands in for (b), because no Gemini predictions exist. Spec: union of word 1–2-gram TF-IDF and `char_wb` 2–5-gram TF-IDF (both `sublinear_tf=True`), then `LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000)`. It is not tuned on test. It is trained on the same training subsets and the same 5 seeds as (c), so the learning curves line up.
3. **(d) base zero-shot.** The bundled base checkpoint answers the task's question + options with no training (`Backend.predict` on the base `ModelRef`). It is deterministic, so a single run. This is the number that tells the [Zero-shot policy](../../issues/0007-zero-shot-policy.md) ticket whether zero-shot clears a meaningful bar on tasks other than Pilot's.
4. **(c) fine-tuned Laya.** `Backend.train` on each training budget × 5 seeds, scored by `Backend.predict`.

Training budgets: 50 / 100 / 250 examples, sampled from the official train partition (one example per label first, then random fill, seed = run seed). These match Pilot's realistic label volume (design step 5: ~250). "All" (the full train partition) is reported for TF-IDF + LR only, unless the CPU cost of a full Laya fine-tune proves acceptable (depends on [Laya checkpoint facts](../../issues/0003-laya-checkpoint-facts.md) and [Non-functional targets](../../issues/0012-non-functional-targets.md)). For Banking77, the budgets are 5 and 10 per class.

Reference numbers from the research run (scikit-learn 1.5.2, pinned files above; macro-F1 on the full official test set, mean over 5 seeds):

| Set | Majority | TF-IDF+LR @50 | @100 | @250 | @all |
|---|---|---|---|---|---|
| MASSIVE de-DE scenario | 0.013 | 0.338 (sd 0.018) | 0.484 (0.021) | 0.638 (0.021) | 0.874 |
| CLINC150 domain + oos | 0.014 | 0.341 (0.028) | 0.468 (0.012) | 0.594 (0.012) | 0.876 |
| Banking77 | 0.000 | @385: 0.569 (0.011) | @770: 0.694 (0.003) | — | 0.907 |

These are sanity numbers that show the sets are neither trivial nor hopeless at Pilot-scale budgets. They are not the published benchmark; the published run uses the `decider-eval` pipeline described next.

## How `decider-eval` and `evaluation` run on a public set

There are no rules (a) and no Gemini system (b). Each Pilot-specific input is replaced as follows:

| Pilot Phase 0 input | Public benchmark replacement |
|---|---|
| JSONL export from Pilot's confirmation queue | A conversion step (data prep, outside the container) writes each pinned set into the same record format (`external_id`, `input.text`, `labels`, `group_id`, `provenance`). The record format itself is pinned by [Pilot contract](../../issues/0004-pilot-contract.md). |
| (a) rules predictions | Absent. Every example counts as "rule-unmatched", so the rule-matched filter is a no-op. |
| (b) Gemini predictions | Absent; decider-ai never calls Gemini. The comparator in the paired bootstrap is TF-IDF + LR (and, secondarily, majority and (d)). The conversion step writes these as named external prediction columns, in the same place the Pilot export carries (a) and (b). That keeps scikit-learn out of the container image and out of `src/decider`. |
| `group_id` (mail thread) | Public sets have no threads. Set `group_id = external_id`, which makes every example its own group, so group-aware resampling reduces to per-example resampling. For MASSIVE, use `external_id = "massive-de-DE-" + id`. If a later run mixes locales, set `group_id = id`, because MASSIVE `id`s are shared across translations of one SLURP utterance and would otherwise leak across splits. For CLINC and Banking77: `"<set>-<split>-<row index>"`. |
| `label_mode` (blind / assisted) | The official test partition is the blind test set: its labels were produced without seeing any decider-ai or Gemini prediction, which is what `blind` asserts. Import test records as `label_mode: blind` and train-partition records as `assisted` (eligible for training only). Do **not** re-split with `evaluation.split`: use the official partitions, so numbers stay comparable with published work. |
| Blind test set size and the ≥15-per-class minimum | The full official test partition (2,974 / 5,500 / 3,080). Every class is far above 15. If CPU inference over 5 seeds × budgets is too slow, use a fixed, seeded, stratified test subsample (e.g. 1,000), with its id list committed. |
| `evaluation.compare` | Unchanged: `compare(gold, a=<tfidf_lr predictions>, b_by_seed=<(c) per seed>, groups=<group_id>, metric="macro_f1", resamples=2000)`. Run it again with `a` = majority and `a` = (d). Report Δ and its 95% CI per budget. |
| `action_gate`, `urgency_gate` | **Not called.** They encode the Pilot decision (5-point margin against Gemini, label-more branch). A public-set report states Δ with CIs and the learning curve, with no gate verdict. |
| Learning curve (design step 8) | Unchanged definition, on budgets 50 / 100 / 250. |
| Per-label precision/recall, confusion matrix | Unchanged. Additionally, call out recall on the "ignore" class (`general`, `out_of_scope`). |
| Report | Unchanged format (JSON + Markdown, aggregates only). It names the dataset, the pinned revision and checksum, and the licence attribution. |

"Unchanged" holds for `evaluation`: it is pure and takes arrays. For `decider-eval` it holds only if the adapter treats external systems generically (named prediction columns, any of them optional) and applies the gate only on request. That is a refinement of `docs/architecture.md`; see [Conflicts](#conflicts-with-the-design-docs).

## Secondary: release-test data and tutorial dataset

- **Release test (design Success Criteria, Phase 1).** A MASSIVE `de-DE` scenario subset is the best fixture. It is German, CC BY 4.0 (no share-alike, so it can ship with an attribution file), short texts, and 18 labels with ≥10 per label available. For example, 400 examples (≥10 per label for the 100-example split, the rest for training) exercise every step: import, the `unverified` state below 150, split freezing at ≥150, and `recommended`/`not_recommended`. The fixture must include MASSIVE's licence and a NOTICE line. CLINC (CC BY 3.0) also works, if an English or out-of-scope fixture is wanted.
- **Tutorial dataset.** None of these replaces the synthetic German dataset in `docs/design.md`. None looks like mail, and none has an urgency label. Public-set numbers can appear in the tutorial as a reproducible appendix ("run it yourself on MASSIVE de-DE"). They never form the headline, which the Pilot gate outcome sets.

## Conflicts with the design docs

1. `docs/architecture.md`, `decider-eval` adapter: "reads the Pilot JSONL export. Systems (a) rules and (b) Gemini come as predictions inside the export." To run unchanged on public sets, the adapter has to accept an export without (a)/(b), with other named external systems (majority, TF-IDF + LR), and with the gate applied only when requested. This is a refinement, not a reversal: the "baselines arrive as exported predictions" seam already fits.
2. `docs/design.md` Phase 0 step 4 lists only (a)–(c). The benchmark adds (d) plus two reference systems; whether (d) joins the Pilot report is [Phase 0 report scope](../../issues/0005-phase-0-report-scope.md) (R3-6).
3. No conflict with the licence constraint. All three recommended sets allow commercial use; the NC candidates are excluded above.

## Gaps and follow-ups

- **No commercially usable public set carries an urgency-like ordinal label.** The only candidates with one are NC (`Tobi-Bueck` priority) or licence-ambiguous (GermEval 2017 sentiment). `urgency_gate` and the MAE path can therefore be exercised only on literal arrays in tests or on the synthetic German dataset. Decide whether that dataset should carry an urgency 1–5 label for exactly this reason.
- **GermEval 2017 licence:** an email to the UHH LT group asking which licence (CC BY vs CC BY-NC 4.0) governs the 2017-09-15 release could unlock the best German customer-feedback set. This is a founder action, not research.
- **Option count:** Banking77 (77 options) and MASSIVE at intent level (60) depend on the Laya input limit and on any `tasks.yaml` maximum label count. Neither is pinned yet.
- **CPU budget:** thousands of test predictions × 5 seeds × 3 budgets × 2–3 sets. Size it once Laya's CPU latency is known.

## Sources

- MASSIVE: [github.com/alexa/massive @ f966f21](https://github.com/alexa/massive/tree/f966f21846043aabef9b0f974fa7970027f43738) (README, NOTICE.md, LICENSE.txt); S3 tarball v1.1 (sha256 above, `1.1/LICENSE`); [HF `AmazonScience/massive` @ ff6bd8e](https://huggingface.co/datasets/AmazonScience/massive/tree/ff6bd8e4b27c3543e4f8fe2108f32bb95a6f8740); paper [arXiv:2204.08582](https://arxiv.org/abs/2204.08582).
- CLINC150: [github.com/clinc/oos-eval @ 828f809](https://github.com/clinc/oos-eval/tree/828f8093932c8fe6ca7936c3d2e52903b1c523de) (LICENSE, `data/data_oos_plus.json`, `data/domains.json`); [HF `clinc/clinc_oos` @ 155b9c7](https://huggingface.co/datasets/clinc/clinc_oos/tree/155b9c710419136e17307b80d0a13e68cd46b4ec); paper Larson et al., EMNLP 2019 ([aclanthology D19-1131](https://aclanthology.org/D19-1131/)).
- Banking77: [github.com/PolyAI-LDN/task-specific-datasets @ 57ec275](https://github.com/PolyAI-LDN/task-specific-datasets/tree/57ec275d8078af65b7731c2a98be812d844a6d6b) (LICENSE, `banking_data/*.csv`); [HF `PolyAI/banking77` @ 90d4e2e](https://huggingface.co/datasets/PolyAI/banking77/tree/90d4e2ee5521c04fc1488f065b8b083658768c57); paper [arXiv:2003.04807](https://arxiv.org/abs/2003.04807).
- Tobi-Bueck: [HF card @ ddf1c81](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/blob/ddf1c81a5475992c4fa6752bf1e8b4e31f07bbeb/README.md); commit history via `https://huggingface.co/api/datasets/Tobi-Bueck/customer-support-tickets/commits/main`.
- GermEval 2017: [organisers' data page](https://ltdata1.informatik.uni-hamburg.de/germeval2017/); [HF `uhhlt/GermEval2017` @ 99da66e](https://huggingface.co/datasets/uhhlt/GermEval2017/tree/99da66e994364c565ff980960c83fc9039f81266); [proceedings](https://www.inf.uni-hamburg.de/en/inst/ab/lt/publications/2017-wojatzkietal-germeval2017-proceedings.pdf).
- IT support tickets: [Zenodo record 7648117](https://zenodo.org/records/7648117); [HF `tasksource/it-support-tickets` @ e0bbdcb](https://huggingface.co/datasets/tasksource/it-support-tickets/tree/e0bbdcb96c84feaa394aaae9c48f8ba4b818451b).
- Discovery: HF API search `datasets?search=ticket|support&filter=language:de`, `datasets?filter=language:de&filter=task_ids:intent-classification`, `datasets?author=bitext`, `datasets?search=germeval|mtop`.
