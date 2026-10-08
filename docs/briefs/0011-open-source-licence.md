# Brief: open-source licence (ticket 0011)

Prepared 2026-10-08 for the live grilling of [issues/0011-open-source-licence.md](../../issues/0011-open-source-licence.md). This brief prepares the decisions. It does not make them. Nothing here is legal advice. Have a lawyer check the final choice before the first public release, because the licence will be in every published image tag.

## Context from the repo

- `docs/design.md` (APPROVED): decider-ai launches as an open-source container on GHCR plus an n8n community node on npm, released from the same repo through CI (Distribution Plan). The launch is the demand test (Premise 1). There is no named user yet.
- The later business is SaaS plus consulting for regulated German SMBs (earlier design, `~/.gstack/projects/decider-ai/rharvey-unknown-design-20261008-015741.md`, Premise 1: "later SaaS + consulting"). The SaaS and §203 hosting question is out of scope until after launch signals (map, Out of scope).
- Constraint: models and datasets must allow commercial use (design, Constraints).
- The image bundles the base checkpoint (design, Cold start).
- Model: `convaiinnovations/laya-multilingual` @ `1720e3e`, Apache-2.0, granted by the model-card metadata only; the repo has no LICENSE or NOTICE file. Base encoder `jhu-clsp/mmBERT-base` is MIT. The `laya` SDK is Apache-2.0 (`docs/research/laya-checkpoint-facts.md` §2).
- `tehtommeh/laya-finetuning` has no licence, so its code cannot be copied (same file, §2; ticket [0020](../../issues/0020-laya-finetuning-licence.md)). That is a separate ticket, but it limits this one: whatever licence decider-ai picks, no laya-finetuning code may enter the repo without a grant that is compatible with it.
- Datasets: MASSIVE 1.1 (CC BY 4.0), CLINC150 (CC BY 3.0), Banking77 optional (CC BY 4.0). None is share-alike. A MASSIVE `de-DE` fixture is the planned release-test dataset and "must include MASSIVE's licence and a NOTICE line" (`docs/research/public-benchmark-datasets.md`, Release test).

## 1. Facts

### 1.1 Licence families

| Licence | What it allows | What it costs the licensor | OSI open source |
|---|---|---|---|
| MIT | Anything, keep the copyright notice | No patent grant, no protection against a hosted competitor | Yes |
| Apache-2.0 | Anything, keep LICENSE and NOTICE, state changes; explicit patent grant and patent-retaliation clause | No protection against a hosted competitor | Yes |
| AGPL-3.0 | Anything, but anyone who modifies it and lets users reach it over a network must offer the modified source under AGPL | Many companies ban it (below); dual-licensing needs a CLA | Yes |
| ELv2 (Elastic License 2.0) | Use, modify, redistribute, except: no hosted or managed service of the software, no circumventing licence keys, keep notices | Not open source; the word "open source" can't be used | No |
| BSL 1.1 (Business Source License) | Source available; production use limited by an "Additional Use Grant"; each version converts to a named open licence after up to 4 years | Not open source; per-project parameters make it read differently everywhere | No |
| FSL (Functional Source License) | "Anything ... except undermine its producer" (no competing use); each version becomes Apache-2.0 or MIT after 2 years | Not open source for 2 years per version | No |
| n8n Sustainable Use License | Use or modify "only for your own internal business purposes or for non-commercial or personal use" | Not open source; n8n calls it "fair-code" | No |

Sources: [ELv2 text](https://www.elastic.co/licensing/elastic-license) (fetched 2026-10-08); [fsl.software](https://fsl.software/) (fetched 2026-10-08); [n8n LICENSE.md](https://raw.githubusercontent.com/n8n-io/n8n/master/LICENSE.md) (fetched 2026-10-08); [Sentry: Introducing the FSL](https://blog.sentry.io/introducing-the-functional-source-license-freedom-without-free-riding) (2023-11-20).

### 1.2 What comparable self-hosted tools chose

Licence of each repo as reported by the GitHub API on 2026-10-08 (`license.spdx_id`; "Other" means a custom or multi-licence file):

| Project | Licence today | History |
|---|---|---|
| Ollama (`ollama/ollama`) | MIT | Unchanged. |
| vLLM (`vllm-project/vllm`) | Apache-2.0 | Unchanged. |
| HF text-generation-inference | Apache-2.0 | HF moved TGI to HFOIL (source-available) in July 2023 and back to Apache-2.0 in April 2024 (from memory; not re-fetched today). |
| SetFit, Argilla, Label Studio | Apache-2.0 | Unchanged. Label Studio and Argilla sell hosted/enterprise editions on top. |
| Grafana | AGPL-3.0 | Apache-2.0 to AGPL-3.0 for Grafana, Loki and Tempo, April 2021; plugins, agents and some libraries stayed Apache-2.0; CLA updated (based on the Apache ICLA) to keep Grafana Labs' "right to relicense" ([Grafana blog, 2021-04-20](https://grafana.com/blog/2021/04/20/grafana-loki-tempo-relicensing-to-agplv3); [CEO Q&A](https://grafana.com/blog/2021/04/20/qa-with-our-ceo-on-relicensing/)). The CEO conceded AGPL "might create red tape" for companies using it internally. |
| n8n | Sustainable Use License + n8n Enterprise License for `.ee.` files | Apache-2.0 with Commons Clause until 2022-03-17, then the SUL; n8n gave the Commons Clause's ambiguity as the reason ([n8n docs: Sustainable Use License](https://docs.n8n.io/privacy-and-security/sustainable-use-license)). |
| Sentry | FSL (Other) | BSD-3 → BSL (2019) → FSL on 2023-11-20, because BSL's 4-year default was "too long" and its parameters meant different things in each project ([TechCrunch, 2023-11-20](https://techcrunch.com/2023/11/20/with-functional-source-license-sentry-wants-to-grant-developers-freedom-without-harmful-free-riding/amp); [InfoQ, 2023-12](https://www.infoq.com/news/2023/12/functional-source-license/)). |
| Terraform (HashiCorp) | BSL 1.1 (Other) | MPL-2.0 to BSL 1.1 on 2023-08-10; the OpenTF manifesto followed on 2023-08-19 and the OpenTofu fork joined the Linux Foundation in September 2023; IBM closed the acquisition 2025-02-27 without changing the licence ([OneUptime, 2026-03-20](https://oneuptime.com/blog/post/2026-03-20-mpl-vs-bsl-opentofu-terraform/markdown); [Logz.io](https://logz.io/blog/terraform-is-no-longer-open-source-is-opentofu-opentf-the-successor)). |
| Elasticsearch | AGPL-3.0 / ELv2 / SSPL (Other) | Apache-2.0 to ELv2/SSPL in 2021, which led to the AWS fork OpenSearch; AGPL added as a third option in August/September 2024 ("Elasticsearch is Open Source, Again"); client libraries stay Apache-2.0 ([DevClass, 2024-09-02](https://devclass.com/2024/09/02/elasticsearch-will-be-open-source-again-as-cto-declares-changed-landscape/)). |
| Redis | AGPL-3.0 / RSALv2 / SSPL (Other) | BSD to RSALv2/SSPL in March 2024, then the Valkey fork (BSD, Linux Foundation, backed by AWS, Google Cloud, Oracle); AGPL-3.0 added with Redis 8.0 on 2025-05-01 ([Phoronix, 2025-05-01](https://www.phoronix.com/news/Redis-8.0-Goes-AGPLv3)). |
| Langfuse | MIT outside `/ee` folders; commercial licence inside (Other) | Core MIT "without any usage limits"; enterprise modules (SCIM, audit logging, retention policies) under a commercial licence and key ([Langfuse handbook: Why is Langfuse open source?](https://langfuse.com/handbook/chapters/open-source), fetched 2026-10-08). |
| Open WebUI | BSD-3 plus a branding clause (Other) | From v0.6.6 (2025-04-19) the name and logo may not be removed above 50 users without an enterprise licence; code up to v0.6.5 stays plain BSD-3; a CLA is required for contributions from v0.6.6 ([Open WebUI licence page](https://docs.openwebui.com/license/), fetched 2026-10-08). |

Patterns:
- Inference and model tools (Ollama, vLLM, TGI, SetFit) are permissive. Adoption is their main goal.
- Tools that moved to source-available did it after they had a large user base and a competitor or cloud provider monetising them. Each move cost goodwill, and the bigger ones produced forks (OpenTofu, OpenSearch, Valkey). Two later added AGPL back (Elastic 2024, Redis 2025).
- Open core with a permissive core plus a separately licensed `/ee` directory (Langfuse, n8n's `.ee.` files) keeps the core simple and sells the extras.
- Relicensing worked where the company held the rights: a CLA (Grafana, Open WebUI), or a permissive inbound licence that already allows sublicensing (Sentry's BSD code).

### 1.3 AGPL in enterprise procurement

- Google bans AGPL code from its codebase, its products and staff laptops; the [AGPL policy page](https://opensource.google/docs/using/agpl-policy/) (fetched 2026-10-08) calls the network clause a risk that "heavily outweigh[s] the benefits".
- Grafana's CEO said AGPL "might create red tape around using our projects internally" (2021 Q&A above).
- Inference for decider-ai's buyers (judgement, no source): regulated German SMBs and their IT service providers often run licence checklists that flag AGPL. decider-ai runs as a separate container reached over HTTP, so most users would never trigger AGPL obligations unless they modify it. A procurement checklist may still stop it before anyone reads that far.

### 1.4 n8n community node

- n8n's [verification guidelines](https://docs.n8n.io/integrations/creating-nodes/build/reference/verification-guidelines/) (fetched 2026-10-08) say: "Make sure your package license is MIT." Also: no external dependencies; published from a GitHub Action with npm provenance ("From May 1st 2026 you must publish ALL community nodes using a GitHub action and include a provenance statement"); the npm repository URL must match a public GitHub repo with the same author; the node must not read environment variables or files; English only; `npx @n8n/scan-community-package` must pass.
- The official starter `n8n-io/n8n-nodes-starter` is MIT (GitHub API, 2026-10-08).
- An unverified community node can carry any licence. Verification matters because verified nodes can be installed from the n8n editor, including on n8n Cloud.
- The node runs inside n8n (Sustainable Use License). It only calls decider-ai over HTTP, so the two licences do not mix.

### 1.5 Compatibility with the model and datasets

- Apache-2.0 (laya-multilingual, laya SDK) and MIT (mmBERT-base) can be redistributed inside an image under any of the candidate licences for decider-ai's own code. The weights are a separate work in the same image (aggregation), not a derivative of decider-ai's code. Obligations under Apache-2.0 §4: ship a copy of the Apache-2.0 licence, keep copyright and attribution notices, and state changes if the weights are modified. The upstream repo has no NOTICE file, so there is no NOTICE text to carry over. Its only licence grant is the model-card metadata, so record that pinned card URL and commit in the attribution file.
- Fine-tuned checkpoints that users train are derivatives of the Apache-2.0 weights. They belong to the user, under Apache-2.0 terms for the base parts, and are never distributed by decider-ai. A SaaS that hosts customer checkpoints would only redistribute if it handed a checkpoint back.
- Apache-2.0 code can be included in AGPL-3.0 code (FSF: Apache-2.0 is compatible with GPLv3 and therefore AGPLv3), so AGPL for decider-ai is also compatible.
- CC BY 4.0 and CC BY 3.0 data: commercial use and redistribution are allowed with attribution. Creative Commons recommends title, author, source and licence ("TASL"), linked; CC BY 4.0 accepts attribution "in any reasonable manner based on the medium, means and context", and a link to a page with the details can be enough; under 3.0 the title is required ([CC: Recommended practices for attribution](https://wiki.creativecommons.org/wiki/Recommended_practices_for_attribution), fetched 2026-10-08). Neither is share-alike, so a shipped fixture does not affect decider-ai's code licence. CC licences are not meant for software, so the fixture stays under its own CC licence, not under decider-ai's code licence.
- Benchmark numbers in the README and tutorial are facts and aggregates, not copies of the dataset. Attribution is still good practice and is already planned for the eval report (`public-benchmark-datasets.md`, Report row).

### 1.6 CLA and DCO

- DCO 1.1 ([developercertificate.org](https://developercertificate.org/), fetched 2026-10-08): a `Signed-off-by` line in each commit certifies that the contributor wrote it or has the right to submit it under the project's licence. Contributions come in under the project's own licence ("inbound = outbound"). Apache-2.0 §5 does this by default even without a DCO.
- CLA: a separate agreement granting the project owner extra rights, usually including the right to relicense. Grafana updated its CLA in 2021 to keep that right when it moved to AGPL; Open WebUI added one with its 2025 licence change.
- GitLab dropped its CLA for a DCO on 2017-11-01 after Debian developers asked, saying the CLA was deterring contributors ([GitLab blog, 2017-11-01](https://about.gitlab.com/blog/2017/11/01/gitlab-switches-to-dco-license/)).
- What each allows later (judgement, from the sources in this section): with a permissive inbound licence (MIT or Apache-2.0) the owner can already ship contributors' code inside a more restrictive future release, because the permissive licence allows it; the old releases stay permissive. With AGPL inbound and only a DCO, the owner cannot sell a non-AGPL commercial licence for code that includes outside contributions. Dual licensing therefore needs a CLA.
- Today there are no outside contributors, so all code is the founder's and every option stays open until the first external PR is merged.

## 2. Decisions for the founder

Answer in this order. Each one narrows the next.

### Decision 1: licence for the container and core (this repo's server, `decider-eval`, docs)

What it settles: what users, IT service providers and possible competitors may do with the container, and what the later SaaS and consulting business can sell.

**Option A: Apache-2.0.**
- Pros: the default for self-hosted AI infrastructure (vLLM, TGI, SetFit, Label Studio, Argilla). Explicit patent grant, which regulated buyers' legal teams like. Same licence as the Laya model and SDK, so one licence text covers most of the image. Passes every procurement checklist. Contributions can later be included in a more restrictive release without a CLA.
- Cons: anyone, including a German IT service provider, can host it as a paid service or resell it with no return to the founder. The defence has to be expertise, speed and the hosted offer, not the licence.

**Option B: MIT.**
- Pros: shortest and best known (Ollama, Langfuse core). Matches the n8n node if that has to be MIT.
- Cons: same lack of protection as Apache-2.0, plus no explicit patent grant. No real gain over Apache-2.0 for a server.

**Option C: AGPL-3.0 (optionally dual-licensed commercially).**
- Pros: still OSI open source, so "open source" can be said in the launch post and SEO tutorial. A competitor that modifies and hosts it must publish changes. Enables a paid commercial licence for companies that won't accept AGPL, if paired with a CLA (Decision 3).
- Cons: banned or flagged by many enterprise policies (Google's is public). Regulated German SMBs and their IT providers are exactly the buyers who run such checklists, so it works against the adoption that is the demand test. Running an unmodified container behind HTTP mostly triggers nothing, but explaining that costs sales time. Dual licensing needs a CLA, which reduces contributions.

**Option D: source-available (FSL, ELv2 or BSL).**
- Pros: blocks a competing hosted service directly. FSL is the simplest of the three: it turns into Apache-2.0 or MIT after two years per version, and is used by Sentry.
- Cons: not open source. The launch post, README and SEO tutorial can't say "open source", and the earlier design premise is an "open-source Docker container". Communities like r/selfhosted and the n8n forum, where the design looks for its first three conversations, react to this. It protects against a threat that does not exist yet: no users, no competitor.

**Recommendation: A, Apache-2.0.** The launch is the demand test, and the test needs the fewest possible barriers for exactly the buyers named. There is nothing to protect from free-riders yet. The patent grant and matching the model licence suit regulated buyers. The precedent shows that the founder can still move later releases to a protective licence if a real free-rider appears, especially if a moat sits in a separate `/ee` directory or the hosted service, as in Langfuse and n8n. Treat that later move as costly: every comparable relicensing cost goodwill, and some produced forks.

Sub-question to settle with it: should a future enterprise directory (`/ee`, under a separate commercial licence) be reserved now? Recommendation: don't create it, just note in the ADR that the licence choice assumes that model if one is ever needed.

### Decision 2: licence for the n8n community node

What it settles: whether the node can be verified and installed from the n8n editor and on n8n Cloud.

**Option A: MIT.**
- Pros: required by n8n's verification guidelines; matches the official starter. The node is a thin HTTP client with no moat.
- Cons: a second licence in one repo. The repo needs a per-directory `LICENSE` and the right `license` field in the node's `package.json`.

**Option B: same licence as the core (Apache-2.0 if Decision 1 is A).**
- Pros: one licence for the whole repo.
- Cons: fails the "license is MIT" verification rule, so the node can only be installed manually by self-hosters. That loses the n8n Cloud audience and in-editor install, which is the reason the node exists.

**Option C: put the node in its own repo.**
- Pros: clean licence boundary; the verification rule that the npm repository URL matches a public GitHub repo with the same author is easy to satisfy.
- Cons: contradicts the Distribution Plan ("released from the same repo via CI") and doubles CI and release work for a solo founder. If chosen, it is a design change, not just a licence choice.

**Recommendation: A, MIT, in the same repo.** It is the only option that keeps verification possible without changing the Distribution Plan. Check during the node's own planning that a monorepo subdirectory passes n8n's "repository URL must match" check (npm's `repository.directory` field covers this in principle; not verified against n8n's review process today). Also note the other verification rules that bind the node's design: no runtime dependencies, no environment or file access, publishing through a GitHub Action with provenance.

### Decision 3: CLA or DCO for contributions

What it settles: whether the founder can later relicense or sell commercial licences of code that includes outside contributions.

**Option A: DCO (`Signed-off-by` on each commit, enforced by a CI check or the DCO GitHub app).**
- Pros: lightweight; used by the Linux kernel and by GitLab since 2017. Contributors keep their rights and nobody has to sign an agreement. With a permissive core (Decision 1 A or B), it still allows later releases under a more restrictive licence, because the permissive inbound licence already allows that.
- Cons: no commercial dual licensing with an AGPL core. No relicensing of contributions to a less restrictive licence, either (not relevant with a permissive core).

**Option B: CLA (for example based on the Apache ICLA, signed through a bot).**
- Pros: keeps every future option, including dual licensing and moving to AGPL or source-available, as Grafana and Open WebUI did.
- Cons: friction for contributors (GitLab dropped its CLA because it deterred them). Signing and storing CLAs is admin work for a solo founder. Signals an intent to relicense, which some communities read as a warning.

**Option C: nothing beyond the licence (inbound = outbound by Apache-2.0 §5 or MIT).**
- Pros: zero process.
- Cons: no record that a contributor had the right to submit the code. A regulated buyer's due diligence may ask for that.

**Recommendation: A, DCO, if Decision 1 is Apache-2.0 or MIT.** Permissive inbound already keeps the founder's later options open, and a DCO adds the provenance record cheaply. **If Decision 1 is AGPL-3.0 with a planned commercial licence, the answer flips to B (CLA)**, because dual licensing is impossible without it. Either way, decide before the first external PR is merged, because that is when it stops being reversible.

### Decision 4: how datasets and model weights are referenced and attributed

What it settles: how the image, the repo and the tutorial meet Apache-2.0 and CC BY obligations, and whether anything non-commercial or unlicensed can slip in.

**Option A: one `THIRD_PARTY_NOTICES.md` (or `NOTICE`) in the repo and in the image, plus per-fixture LICENSE files.**
It lists, for each third-party asset, its name, pinned source URL and commit, authors and licence with a link: laya-multilingual (Apache-2.0, card @ `1720e3e`), mmBERT-base (MIT), the laya SDK (Apache-2.0), the MASSIVE fixture (CC BY 4.0, "derived from SLURP"), and CLINC150 if shipped (CC BY 3.0, title required). Each fixture directory also carries the dataset's own licence file. The image copies the file to a fixed path (for example `/licenses/`) and the README links to it.
- Pros: one place for buyers and their auditors to look; meets Apache-2.0 §4 and CC TASL; cheap.
- Cons: someone has to keep it up to date when a dependency or dataset changes.

**Option B: Option A plus a CI check.**
CI compares the bundled assets (checkpoint revision, fixture checksums) with the notices file and fails on a mismatch or on an asset with no listed licence. Python and npm dependency licences can be checked with a standard tool in the same job.
- Pros: makes the commercial-use constraint and the laya-finetuning gap mechanically enforced, not remembered.
- Cons: more CI work, and CI is still an open map item ("CI and the GHCR release pipeline").

**Option C: don't bundle; download at first start or at build time with attribution in the README only.**
- Pros: the repo carries no third-party data or weights.
- Cons: contradicts the design (the image bundles the base checkpoint; the release test uses a shipped MASSIVE fixture). The image still redistributes the weights if they are downloaded at build time, so the obligations don't go away. Offline and air-gapped installs, common for regulated buyers, get harder.

**Recommendation: B (A plus a CI check), with the CI part done when the CI ticket is planned.** Commit the notices file now and add the check later. Also state explicitly in the ADR that dataset and model files keep their own licences and are not covered by decider-ai's code licence, and that no code from laya-finetuning enters the repo until ticket 0020 produces a grant compatible with Decision 1.

## 3. Is this ADR-worthy?

Yes. The map asks for an ADR when a choice is hard to reverse, surprising and a real trade-off.

- **Hard to reverse:** every published image tag and npm version carries its licence for good. Tightening later produces the goodwill loss and forks seen with HashiCorp, Elastic and Redis. Loosening later is easy only while the founder owns all the code, or holds a CLA.
- **Surprising:** a reader who knows the plan is a SaaS and consulting business may expect a protective licence (AGPL, FSL). Choosing a permissive one needs its reason written down: the launch is the demand test and nothing exists yet to protect. So does the second licence for the n8n node.
- **Real trade-off:** adoption by regulated buyers against protection from a hosted competitor, and contributor friction against relicensing rights.

Suggested scope: one ADR covering Decisions 1 to 3 (they depend on each other). Decision 4 is mostly an implementation convention; put it in the same ADR as a consequence section, or in the CI and release docs, but not in an ADR of its own.

## Sources

All accessed 2026-10-08 unless dated otherwise.

- GitHub REST API `repos/{owner}/{repo}` `license` field for: ollama/ollama, vllm-project/vllm, huggingface/text-generation-inference, huggingface/setfit, argilla-io/argilla, HumanSignal/label-studio, grafana/grafana, n8n-io/n8n, n8n-io/n8n-nodes-starter, getsentry/sentry, hashicorp/terraform, elastic/elasticsearch, redis/redis, langfuse/langfuse, open-webui/open-webui.
- n8n verification guidelines: https://docs.n8n.io/integrations/creating-nodes/build/reference/verification-guidelines/
- n8n LICENSE.md: https://raw.githubusercontent.com/n8n-io/n8n/master/LICENSE.md ; n8n docs, Sustainable Use License: https://docs.n8n.io/privacy-and-security/sustainable-use-license
- Functional Source License: https://fsl.software/ ; Sentry announcement (2023-11-20): https://blog.sentry.io/introducing-the-functional-source-license-freedom-without-free-riding ; TechCrunch (2023-11-20): https://techcrunch.com/2023/11/20/with-functional-source-license-sentry-wants-to-grant-developers-freedom-without-harmful-free-riding/amp ; InfoQ (2023-12): https://www.infoq.com/news/2023/12/functional-source-license/
- Elastic License 2.0: https://www.elastic.co/licensing/elastic-license ; DevClass (2024-09-02): https://devclass.com/2024/09/02/elasticsearch-will-be-open-source-again-as-cto-declares-changed-landscape/
- HashiCorp BSL and OpenTofu: https://oneuptime.com/blog/post/2026-03-20-mpl-vs-bsl-opentofu-terraform/markdown (2026-03-20); https://logz.io/blog/terraform-is-no-longer-open-source-is-opentofu-opentf-the-successor
- Redis 8 AGPL (2025-05-01): https://www.phoronix.com/news/Redis-8.0-Goes-AGPLv3
- Grafana relicensing (2021-04-20): https://grafana.com/blog/2021/04/20/grafana-loki-tempo-relicensing-to-agplv3 ; https://grafana.com/blog/2021/04/20/qa-with-our-ceo-on-relicensing/
- Langfuse open-source handbook: https://langfuse.com/handbook/chapters/open-source
- Open WebUI licence: https://docs.openwebui.com/license/
- Google AGPL policy: https://opensource.google/docs/using/agpl-policy/
- Developer Certificate of Origin 1.1: https://developercertificate.org/ ; GitLab switches to DCO (2017-11-01): https://about.gitlab.com/blog/2017/11/01/gitlab-switches-to-dco-license/
- Creative Commons attribution practice: https://wiki.creativecommons.org/wiki/Recommended_practices_for_attribution
- Repo: `docs/research/laya-checkpoint-facts.md` §2, `docs/research/public-benchmark-datasets.md` (licence table, Release test), `docs/design.md` (Constraints, Distribution Plan).
