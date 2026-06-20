---
status: Implemented
date: 2026-05-16
deciders:
  - gsannikov
related: [ADR-601]
hub: null
tags: [brain, vault, registry, multi-brain, foundation]
superseded_by: null
spec_file: 2026-05-16-multi-brain-design.md
plan_file: 2026-05-16-adr-754-multi-brain-stage-1.md
---

# ADR-754: Multi-Brain Augur — Stage 1 (Brain Registry & Aliasing)

> **ADR-754 is an index file.** The substantive design lives in `docs/superpowers/specs/2026-05-16-multi-brain-design.md` (the umbrella spec for all three stages). The Stage 1 implementation steps live in `docs/superpowers/plans/2026-05-16-adr-754-multi-brain-stage-1.md`. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Introduce a typed brain registry at `~/.augur/brains.yaml`, auto-generated on first read from today's `vault.yaml` + detected `shared-vault/`, plus a `.augur/` mount writer that prepares each registered brain's directory for AI-client scoping — with zero data movement and zero user-visible behavior change, as the invisible-infrastructure foundation for the multi-brain model (personal / team / work / project) defined in the umbrella spec.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-16-multi-brain-design.md`](../superpowers/specs/2026-05-16-multi-brain-design.md) — umbrella design for all three stages.

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-16-adr-754-multi-brain-stage-1.md`](../superpowers/plans/2026-05-16-adr-754-multi-brain-stage-1.md) — Stage 1 only (9 tasks; registry models, YAML I/O, bootstrap, top-level accessor, `paths.py` helpers, mount writer, sync wiring, integration test, real-data smoke).

## Status notes

**Implemented (2026-05-16).** Stage 1 shipped in branch `adr-754-multi-brain-augur-stage-1-brain-registry`. The Task 9 real-data smoke passed on the user's laptop: `~/.augur/brains.yaml` was bootstrapped with `personal` pointing at `~/Projects/Au-vault` and `team-augur` pointing at `~/Projects/Augur/shared-vault`, both matching the legacy path helpers, and both roots received `.augur/BRAIN.yaml` manifests.

Stages 2 and 3 of the umbrella spec are deliberately out of scope here and will land as ADR-755 (BrainContext + propagation generalization) and ADR-756 (new brain types + federation UI), each with its own plan, once Stage 1 is stable.

## Related

- **ADR-601** — shared-vault skill ownership; established the in-repo team brain at `shared-vault/` that this ADR re-frames as the `team-augur` registry entry (bundled git arrangement, zero data movement).
- **ADR-755** (future) — Stage 2: BrainContext plumbing through MCP write tools + generalized propagation packets (`--to <brain-id>`).
- **ADR-756** (future) — Stage 3: `/brain init` for new project/work brains, `/brain clone` for additional team brains, dashboard federation with brain badges, `/dev-merge full` extension, memory shared-symlink mechanism.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "src/config/paths.py: add get_augur_state_dir, get_brain_registry_path, get_brain_dir, list_brain_ids (additive; no existing helper modified)"
  patterns_deprecated:
    - "config/system/vault.yaml as the single source of truth — becomes the auto-bootstrap input for ~/.augur/brains.yaml; kept working as a deprecated alias for one release per CLAUDE.md rule 14"
  files_affected:
    - "src/lib/brain_registry_models.py (new)"
    - "src/lib/brain_registry_io.py (new)"
    - "src/lib/brain_registry_bootstrap.py (new)"
    - "src/lib/brain_registry.py (new)"
    - "src/lib/brain_mount.py (new)"
    - "src/config/paths.py (append-only)"
    - "shared-vault/skills/ai/scripts/sync_agents.py or owning dev-sync orchestrator (additive: _ensure_brain_mounts step)"
    - "tests/unit/test_brain_registry_*.py (new, 4 files)"
    - "tests/unit/test_brain_mount.py (new)"
    - "tests/config/test_paths.py (extended)"
    - "tests/integration/test_brain_registry_stage1.py (new)"
```

## Implementation Prompt

To execute this ADR, run:

```
/adr implement ADR-754
```

This resolves the `plan_file:` frontmatter pointer above, creates an isolated worktree via `superpowers:using-git-worktrees`, and drives the plan task-by-task through `superpowers:subagent-driven-development` with the standard two-stage review between tasks. Stage 1 is fully sequential — no independent task clusters — so no Team-primitive parallelization is needed.

Completion gates per CLAUDE.md rules 28, 29, 34 apply; in particular Task 9's real-data smoke check is the value-validation gate that must pass before status flips to Implemented (mechanical green tests are necessary but not sufficient).
