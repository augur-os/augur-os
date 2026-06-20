---
status: Implemented
date: 2026-05-17
deciders:
  - gsannikov
related:
  - ADR-727
  - ADR-755
  - ADR-758
hub: dev
tags:
  - routines
  - codex
  - claude-remote
  - browse
  - drift
  - sync
superseded_by: null
spec_file: 2026-05-17-bidirectional-routine-drift-design.md
plan_file: 2026-05-17-bidirectional-routine-drift.md
---

# ADR-763: Bidirectional Routine Drift Detection and Resolution

> **ADR-763 is an index file.** The substantive design lives in the linked spec; the implementation plan is linked below as `plan_file`.

## Decision summary

Augur projects declarative routine seeds into Codex and Claude-remote surfaces non-destructively, detects drift bidirectionally via embedded hash markers (Codex) and a per-machine cache registry (Claude remote), surfaces drift per Browse card, and resolves it through two explicit user actions — `Adopt cloud version` and `Push my version` — never silent reconciliation.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-17-bidirectional-routine-drift-design.md`](../superpowers/specs/2026-05-17-bidirectional-routine-drift-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-17-bidirectional-routine-drift.md`](../superpowers/plans/2026-05-17-bidirectional-routine-drift.md)

## Status notes

Implemented. Phases A through D of the design are now present in the current checkout: Browse scheduled-execution cards expose drift metadata plus Adopt/Push actions, MCP registers `routine-adopt-cloud` and `routine-push-local`, and daemon CLI verbs route to the same implementations. Verification coverage lives in `shared-vault/skills/daemon/augur/tests/test_routine_adopt_cloud.py`, `test_routine_push_local.py`, `test_routine_drift_cli_verbs.py`, and `test_scheduled_executions_actions.py`.

## Related

- ADR-727 — Background Routines unified discovery and Browse category (this ADR extends the Browse surface with drift metadata).
- ADR-755 — Auto-loop runner modernization (Codex automations are the runtime substrate this ADR makes safer).
- ADR-758 — Routines unification — one system, one surface (this ADR closes the bidirectional gap that one-surface unification exposed).

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - sync_codex_automations: added force=True parameter; default behavior changed from destructive to non-destructive
    - automation.toml schema: added managed_by and augur_seed_hash fields
    - Browse background-routines metadata: added managed_by and drift_status fields
    - claude-remote-routines.json cache schema: added drift_status per routine and fetched_at at top level
  patterns_deprecated:
    - Silent overwrite of user edits to ~/.codex/automations/<id>/automation.toml during sync
  files_affected:
    - src/lib/runtime/codex_automations.py
    - src/mcp/augur_framework/tools/infrastructure/browse/scheduled_sources/codex.py
    - src/mcp/augur_framework/tools/infrastructure/browse/scheduled_sources/claude_remote.py
    - src/mcp/augur_framework/tools/infrastructure/browse/scheduled_sources/claude.py
    - src/mcp/augur_framework/tools/infrastructure/browse/scheduled_sources/augur_internal.py
    - src/mcp/augur_framework/tools/infrastructure/browse/scheduled_executions.py
    - src/mcp/augur_framework/tools/infrastructure/browse/index.py
    - src/mcp/augur_framework/tools/infrastructure/browse/__init__.py
    - shared-vault/skills/daemon/scripts/mcp/__init__.py
    - apps/dashboard/lib/browse/cardModel.ts
    - apps/dashboard/components/shared/BrowseCategoryActions.tsx
```
