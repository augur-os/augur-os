---
id: ADR-497
title: ADR-466 Architecture Review Fixes Implementation
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [architecture, paths, types, eslint, daemon, hmr]
related: [ADR-466]
---

# ADR-497: ADR-466 Architecture Review Fixes Implementation

## Context

ADR-466 identified 6 tech debt items from the Q1 2026 architecture review: path resolution duplication, type consolidation, config/state separation, ESLint enforcement for spawn/exec, platform guards for Apple daemon services, and HMR interval leaks.

## Decision

Implement 6 independent fixes:
1. **Unify path resolution** — Extract shared `path_primitives.py` module used by both `paths.py` and `augur_mcp/config.py`, eliminating 12 duplicated functions
2. **Consolidate SkillMetadata types** — Make `SkillRecord` the single canonical type, remove MCP-layer `SkillMetadata` conversion overhead
3. **Move scan targets to state dir** — Restore ADR-087 compliance by moving `discovered_scan_targets` from config YAML to runtime state
4. **ESLint spawn/exec restriction** — Block `child_process` and `node-pty` imports in API routes
5. **Platform guard** — Gate `note_watcher` and `note_ingest` behind `sys.platform == 'darwin'`
6. **HMR leak fixes** — Add `globalThis` singleton guards for reconnect/recovery timers

## Consequences

### Positive
- Path resolution is DRY across monorepo and standalone modes
- Single canonical type eliminates conversion bugs
- Config/state separation restored per ADR-087

### Negative
- Path primitives introduce a new import dependency for both consumers

## References

- Plan: `docs/superpowers/plans/2026-03-21-adr-466-architecture-fixes.md`
- Parent ADR: ADR-466 in `Au-vault/dev/adrs/`
