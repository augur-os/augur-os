---
status: Implemented
date: 2026-05-31
deciders:
  - gsannikov
related:
  - ADR-770
  - ADR-771
  - ADR-781
  - ADR-788
  - ADR-791
hub: brain
tags:
  - brain
  - projection
  - agents
  - memory
  - profile
superseded_by: null
spec_file: 2026-05-31-standard-brain-workspace-files-design.md
plan_file: 2026-05-31-standard-brain-workspace-files.md
---

# ADR-794: Standard Brain Workspace Files

> **ADR-794 is an index file.** The substantive design lives in the linked spec.
> Implementation steps will live in a linked plan after review. This file
> carries pointers, status, and a one-line decision summary.

## Decision summary

Augur will align brain roots with common agent-workspace files
(`IDENTITY.md`, `SOUL.md`, `USER.md`, `AGENTS.md`, `MEMORY.md`, `TOOLS.md`,
and `HEARTBEAT.md`) while keeping `BRAIN.yaml` as the canonical Augur manifest
and preserving generated client projections.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-31-standard-brain-workspace-files-design.md`](../superpowers/specs/2026-05-31-standard-brain-workspace-files-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-31-standard-brain-workspace-files.md`](../superpowers/plans/2026-05-31-standard-brain-workspace-files.md)

## Status notes

Proposed on 2026-05-31 after reviewing GitAgent, OpenClaw-style workspace files,
and Codex `AGENTS.md` conventions against Augur's ADR-770/ADR-771
project-brain and projection architecture.

Implemented on 2026-05-31. Standard brain root files are skeleton-created,
seeded in `project-brain/`, surfaced in profile/manager snapshots, and projected
into generated client instructions through `sync_agents`.

## Related

- ADR-770: Project-Brain Physical Migration
- ADR-771: Brain Client Projections And Write Routing
- ADR-781: Harness Brain Stack Source Discovery
- ADR-788: Augur Skill Supply-Chain Guardrails
- ADR-791: Brain-Scoped Standard Skill Source

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "src/lib/brain_manifest.py: brain skeleton may add standard root files"
    - "src/lib/brain_projection.py: projection sources may include standard brain root files"
    - "src/lib/brain_profile_overlay.py: profile overlay may distinguish root prose from structured overlay files"
    - "project-brain/capabilities/skills/ai/scripts/sync_agents/: generated instructions may project standard brain files"
  patterns_deprecated:
    - "using project-brain/profile/ as the primary human-facing prose profile bucket"
    - "treating generated client instruction files as durable brain source"
  files_affected:
    - "project-brain/BRAIN.yaml"
    - "project-brain/README.md"
    - "project-brain/profile/README.md"
    - "project-brain/IDENTITY.md"
    - "project-brain/SOUL.md"
    - "project-brain/USER.md"
    - "project-brain/AGENTS.md"
    - "project-brain/MEMORY.md"
    - "project-brain/TOOLS.md"
    - "project-brain/HEARTBEAT.md"
    - "src/lib/brain_manifest.py"
    - "src/lib/brain_projection.py"
    - "src/lib/brain_profile_overlay.py"
    - "src/lib/brain_manager_snapshot.py"
    - "project-brain/capabilities/skills/ai/scripts/sync_agents/"
    - "tests/unit/"
    - "project-brain/capabilities/skills/ai/scripts/sync_agents/tests/"
```
