---
status: Implemented
date: 2026-05-21
deciders:
  - gsannikov
related: [ADR-754, ADR-768]
hub: brain
tags: [brain, project-brain, init, registry]
superseded_by: null
spec_file: 2026-05-20-multi-brain-project-brain-design.md
plan_file: 2026-05-20-multi-brain-project-brain-foundation.md
---

# ADR-769: Project-Brain Foundation And `augur init`

> **ADR-769 is an index file.** The substantive design and implementation steps
> live in the linked spec + plan. This file records the phase-2 foundation work
> that already landed in code.

## Decision summary

Replace the old Stage-1-only model with a project-brain foundation: three brain
types, root `BRAIN.yaml`, `project-brain/` discovery, active brain context, and
idempotent `augur init`.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-20-multi-brain-project-brain-design.md`](../superpowers/specs/2026-05-20-multi-brain-project-brain-design.md)

## Plan (canonical)

- [`docs/superpowers/plans/2026-05-20-multi-brain-project-brain-foundation.md`](../superpowers/plans/2026-05-20-multi-brain-project-brain-foundation.md)

## Status notes

Implemented before this ADR was formalized. Current code includes:

- `src/lib/brain_manifest.py`
- `src/lib/brain_context.py`
- `src/lib/brain_init.py`
- `src/lib/brain_registry_bootstrap.py` project-brain bootstrap behavior
- `src/cli.py` `init` handling
- tests for brain manifest, context, init, paths, and CLI behavior

This ADR is post-facto documentation so future work can depend on a real ADR
number instead of an orphan spec/plan pair.

## Related

- ADR-754: Original registry foundation.
- ADR-768: Remaining multi-brain roadmap.
- ADR-770: Physical content migration that depends on this foundation.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "src/cli.py: built-in init command"
    - "src/config/paths.py: project-brain and active-context helpers"
  patterns_deprecated:
    - "work brain as a first-class v1 type"
    - "shared-vault auto-registration as team-augur"
  files_affected:
    - "src/lib/brain_manifest.py"
    - "src/lib/brain_context.py"
    - "src/lib/brain_init.py"
    - "src/lib/brain_registry_models.py"
    - "src/lib/brain_registry_bootstrap.py"
    - "src/cli.py"
```

## Implementation Prompt

Do not reimplement this ADR. If needed, run:

```text
/adr gaps ADR-769
```

Then archive it only after the gap check is clean.
