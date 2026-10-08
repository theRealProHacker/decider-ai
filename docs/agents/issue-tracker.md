# Issue tracker

This repo has no remote tracker yet (and no git repo). Issues are local markdown files in `issues/`.

## Format

One file per issue: `issues/NNNN-<slug>.md`. The 4-digit number is the issue id. Frontmatter:

```yaml
---
id: 3
title: Laya checkpoint facts
labels: [wayfinder:research]
status: open          # open | closed
assignee:             # empty = unclaimed
parent: 1             # map id, for wayfinder tickets
blocked_by: []        # ids of blocking issues
---
```

## Wayfinding operations

- **Map:** the issue labelled `wayfinder:map`. Its child tickets are issues with `parent: <map id>`.
- **Claim:** set `assignee:` before any work.
- **Blocking:** `blocked_by:` in frontmatter (no native blocking exists, so this is the fallback convention). A ticket is unblocked when every listed id is `status: closed`.
- **Frontier:** children with `status: open`, empty `assignee`, and every `blocked_by` id closed:
  `grep -l '^parent: 1$' issues/*.md` then check those three fields.
- **Resolve:** append a `## Resolution` section (the resolution comment), set `status: closed`, and add a line to the map's Decisions so far.
- **Links:** refer to an issue by its title, linked to its file: `[Laya checkpoint facts](issues/0003-laya-checkpoint-facts.md)`.
