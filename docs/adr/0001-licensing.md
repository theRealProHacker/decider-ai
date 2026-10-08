# Apache-2.0 core, MIT n8n node in its own repo, DCO, third-party assets downloaded not bundled

decider-ai's container and core code are Apache-2.0: the launch is a demand test, so the licence should give regulated buyers no reason to say no (AGPL is banned at Google and flagged by procurement checklists), it carries a patent grant, and it matches the Apache-2.0 Laya weights. There is no hosted competitor to defend against yet; closed features can later live in a separately licensed directory, as Langfuse and n8n do. The n8n community node is MIT, because n8n's verification guidelines require it, and lives in its own repository (founder, 2026-10-08), which also satisfies n8n's rule that the npm repository URL matches the GitHub repo. Contributions are accepted under a DCO (`Signed-off-by`, checked in CI), not a CLA: low friction, at the cost that a later move to a source-available licence covers only code the founder owns unless a CLA is introduced then. Model weights and benchmark datasets are not bundled in the repo or image; they are downloaded at first start or by the eval script from pinned sources, and attributed in the docs with source, revision, authors and licence.

## Considered options

- Core: MIT (no patent grant), AGPL-3.0 (procurement friction, dual-licensing needs a CLA), FSL (not open source for 2 years per version). Projects that went source-available did so after a competitor monetised them, and each move produced a fork.
- n8n node: Apache-2.0 (fails n8n verification), MIT in this repo (repo-URL rule unclear for a subdirectory).
- Contributions: CLA (keeps relicensing open, more friction), nothing (inbound = outbound under Apache §5, least provenance).
- Assets: a `THIRD_PARTY_NOTICES` file with bundled assets.

## Consequences

- The image no longer bundles the base checkpoint (changes `docs/design.md` Cold start). First start needs network access to the pinned Hugging Face revision; an offline install path (pre-download into the volume) belongs to the container ticket.
- Research: `docs/briefs/0011-open-source-licence.md`. Not legal advice; a lawyer review before the first public release is recommended.
