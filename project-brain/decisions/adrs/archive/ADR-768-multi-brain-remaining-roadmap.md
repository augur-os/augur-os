---
status: Implemented
date: 2026-05-21
deciders:
  - gsannikov
related: [ADR-754, ADR-601]
hub: brain
tags: [brain, multi-brain, roadmap, project-brain]
superseded_by: null
spec_file: 2026-05-21-multi-brain-remaining-roadmap-design.md
plan_file: 2026-05-21-multi-brain-remaining-roadmap.md
---

# ADR-768: Multi-Brain Remaining Roadmap

> **ADR-768 is an index file.** The substantive design and implementation
> order live in the linked spec + plan. This file carries pointers, status, and
> a one-line decision summary.

## Decision summary

Finish multi-brain through one roadmap ADR plus one implementation ADR per
phase, keeping phase boundaries narrow enough for concrete `/adr implement`
sessions such as `/adr implement ADR-770`.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-21-multi-brain-remaining-roadmap-design.md`](../superpowers/specs/2026-05-21-multi-brain-remaining-roadmap-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-21-multi-brain-remaining-roadmap.md`](../superpowers/plans/2026-05-21-multi-brain-remaining-roadmap.md)

## Status notes

Accepted 2026-05-21. This ADR formalizes the remaining phase map and delegates
implementation to ADR-769 through ADR-772.

Implemented 2026-05-21. The roadmap's full delegated scope is complete: all four
phase ADRs (769 foundation, 770 physical migration, 771 client projections +
write routing, 772 UI federation + memory review) are Implemented and archived.
The roadmap is functionally discharged and itself archivable.

## Related

- ADR-754: Stage 1 registry foundation.
- ADR-769: Project-brain foundation and `aug init`.
- ADR-770: Physical migration from `shared-vault/` to `project-brain/`.
- ADR-771: AI-client projections and write routing.
- ADR-772: UI federation and memory review.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated:
    - "single large multi-brain ADRs; remaining work is split by phase"
  files_affected:
    - "docs/adrs/ADR-768-multi-brain-remaining-roadmap.md"
```

## Implementation Prompt

To execute the remaining roadmap, implement the phase ADRs in order:

```text
/adr implement ADR-770
/adr implement ADR-771
/adr implement ADR-772
```

ADR-769 records work already implemented by the project-brain foundation merge.
