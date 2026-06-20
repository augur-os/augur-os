---
status: Implemented
date: 2026-04-29
deciders:
  - Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-597: Track 1 Daemon Runtime Extraction

## Context

The cross-client bundle architecture migration (Track 1) is moving heavily-imported skill code into a properly-importable framework library at `src/lib/`. After Library 1 (document-extractor → `src/lib/extraction/`) and Library 2 (knowledge memory → `src/lib/knowledge/`), the third library targets daemon's runtime helpers.

The daemon skill's `augur/lib/` directory contains two library files — `performance_ledger.py` (TaskRecord dataclass and ADR-460 telemetry helpers) and `behavior_thresholds.py` (autonomy/learning thresholds shared by dashboard and orchestrator) — that are imported externally by `src/mcp/augur_mcp/infrastructure/settings/system.py`, internally by `skills/daemon/scripts/nightly_maintainer.py`, and by two daemon importability tests.

The Layer 4 spec predicted "11 importers" for daemon, but real surface verified at planning time was 4 sites total: 1 external Python import + 1 internal lazy import + 2 importability tests. The daemon process subsystem (adaptive loop engine, monitors, ops, self-heal) stays in the skill bundle — only the library/telemetry helpers move.

## Decision

Use rename-via-overlap across three sequential PRs to relocate the two library files from `skills/daemon/augur/lib/` to `src/lib/runtime/`:

- PR 1 (additive): copy both files verbatim to `src/lib/runtime/`, write an `__init__.py` re-exporting the public API (`TaskRecord`, `record_task`, `get_aggregates`, `compact`, `AUTONOMY_THRESHOLDS`, `LEARNING_THRESHOLDS`, `AUTONOMY_LEVELS`, `LEARNING_LEVELS`, `get_action_required_level`, `get_learning_behavior_at_level`, `is_behavior_enabled`), and add smoke tests at `tests/lib/runtime/`. Both old and new paths work.
- PR 2: migrate all 4 consumer sites (`system.py:20`, `nightly_maintainer.py:258`, `test_performance_ledger.py:19`, `test_behavior_thresholds.py:19`) to import from `src.lib.runtime`.
- PR 3: delete `skills/daemon/augur/lib/` (rename-via-overlap completes).

The daemon bundle keeps `SKILL.md`, `config.yaml`, all 42 scripts and 5 subdirectories under `scripts/`, plus tests, actions, evals, and assets.

## Consequences

### Positive
- External consumers import telemetry helpers via a clean Python path, no skill cross-imports.
- The daemon bundle is purely a process subsystem (adaptive loop engine, monitors, ops, self-heal), not a library host.
- Public API is documented and smoke-tested at the new canonical location.

### Negative
- Requires 3 sequential commits with consumer migration in lockstep; intermediate states exist where both paths resolve.

### Neutral
- No allowlist entries get retired — daemon was never in `ALLOWED_CROSS_SKILL_IMPORTS` (its imports went via `augur/lib/` which the architecture test's regex doesn't catch).

## Alternatives Considered

### Alternative 1: Move-and-redirect with compatibility shim
Rejected. Compatibility shims violate Critical Rule 14 (prefer canonical cleanup). Rename-via-overlap completes the migration without leaving redirects.

### Alternative 2: Leave runtime helpers in the daemon skill
Rejected. External consumers (`src/mcp/...`) should not depend on skill-bundled library code; the architecture treats skills as bundles, not framework libraries.

## References
- Plan: docs/superpowers/plans/2026-04-29-track1-daemon-runtime-extraction.md
- Spec (Layer 1): docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md
- Spec (Layer 4 / Track 1): docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md
