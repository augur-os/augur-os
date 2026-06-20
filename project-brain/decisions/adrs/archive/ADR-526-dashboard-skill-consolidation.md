---
status: Implemented
date: 2026-04-02
deciders:
  - gsannikov
related:
  - ADR-490
hub: dev
tags:
  - architecture
  - performance
  - dashboard
superseded_by: null
---

# ADR-526: Dashboard Skill Consolidation — Eliminate @skill/ Alias

## Context

The dashboard had a split architecture where framework code lived in `apps/dashboard/` and feature code (components, hooks, pages) lived in `skills/dashboard/`. A TypeScript `@skill/` path alias with `baseUrl: "../.."` bridged the two directories.

This forced `turbopack.root` to the monorepo root so Turbopack could resolve cross-directory imports. The consequence: Turbopack watched the entire 1.2GB repo tree — Python code, docs, config, daemon logs, skill scripts — causing the dev server to consume ~2GB RAM instead of the expected ~800MB-1GB for a dashboard of this size (21 pages, 41 API routes, ~290 feature files).

The `skills/dashboard/` "skill" was anomalous: unlike other skills which are self-contained domain modules, it was a monolithic bucket containing ALL dashboard feature code. It contributed no skill-specific metadata, commands, or data — it was effectively the application itself, split across two directories for historical reasons (the original plugin decentralization architecture, ADR-490).

## Decision

Consolidate all `skills/dashboard/` content into `apps/dashboard/` and delete the skill entirely.

### 1. Move UI code into `apps/dashboard/features/`

- `skills/dashboard/components/` (111 files) → `apps/dashboard/features/components/`
- `skills/dashboard/hooks/` (21 files) → `apps/dashboard/features/hooks/`
- `skills/dashboard/pages/` (142 files) → `apps/dashboard/features/pages/`

### 2. Replace `@skill/` alias with `@/features/`

- 118 import statements across 60+ files updated: `@skill/` → `@/features/`
- `tsconfig.json`: `baseUrl` changed from `../..` to `.`, removed `@skill/*` path mapping
- `jest.config.js`: removed `@skill/` moduleNameMapper

### 3. Scope Turbopack root to dashboard directory

- `next.config.ts`: removed `turbopack.root: repoRoot` override (auto-detects to project dir)
- Removed `experimental.externalDir: true` (no longer importing outside project)
- Cleaned dead `outputFileTracingExcludes` patterns for dirs outside project scope
- Removed backward-compatibility redirects/rewrites (rule 14)

### 4. Extract shared build utilities

- Created `scripts/lib/path-utils.ts` with shared `getDashboardRoot()` and `FEATURES_DIR` constant
- Eliminated 3x duplication of `getDashboardRoot()` across build scripts
- Unified duplicate `registerComponent()` logic in `block-registry-gen.ts`
- Removed dead `pageValidationErrors` code in `mount-plugins.ts`

### 5. Move non-UI files

- Python scripts (134 files) → `apps/dashboard/scripts/skill-scripts/`
- Tests (112 files) → `tests/dashboard/python/`
- Commands, references, assets, modules → `apps/dashboard/docs/`
- `config.yaml` → `apps/dashboard/contributions.yaml`

### 6. Update all external references

- 13 Python files with hardcoded `skills/dashboard` paths
- Pre-commit hook page storage enforcement rules
- CLAUDE.md, agent instruction files across 6 IDE integrations
- Active docs in `docs/agent-topics/`, `docs/references/`

## Consequences

### Positive

- **~50% memory reduction**: Dev server drops from ~2GB to ~800MB-1GB (Turbopack watches only dashboard source, not entire repo)
- **Simpler architecture**: Single `@/` alias, no cross-directory imports, standard Next.js project structure
- **Faster HMR**: Turbopack invalidation scope narrowed from 1.2GB to ~7MB of source
- **Eliminated anomaly**: No more fake "skill" that was really the application itself

### Negative

- **6 CLI commands lost**: `create-plugin`, `audit-plugin`, `import-skill`, `migrate-skill`, `new-page`, `test-ui` were declared in `skills/dashboard/commands/`. Can be re-created as standalone skills if needed.
- **ADR-490 partially superseded**: The dual-alias `@/` + `@skill/` architecture is now single-alias. The ADR's dependency rule (`@/` never imports `@skill/`) is obsolete.

### Neutral

- Build scripts and registries continue to work — `mount-plugins`, `generate-registry`, `block-registry-gen` updated to use new paths
- Git history preserved via `git mv`

## Implementation Order

Executed in a single session, 8 phases:

1. Move UI files (git mv)
2. Replace all `@skill/` imports (sed)
3. Update config files (tsconfig, next.config, jest)
4. Update build scripts (mount-plugins, block-registry-gen, generate-registry)
5. Move non-UI files (scripts, tests, docs, assets)
6. Update external references (Python, pre-commit, docs, agent instructions)
7. Delete `skills/dashboard/`
8. Code quality fixes (shared utils, dead code, deduplication)
9. Tab registry: add `features/pages/` discovery to `generate-tab-registry.ts` with dedup against `skills/*/augur/dashboard/`
10. Hub overview: surface `blocks` as navigable app pages with assembled-hubs label/icon lookup
11. Icon regression fix: index block icons from skill contributions for tab metadata
12. Stale reference cleanup: page-discovery.ts, context.py, pluginFallback.ts, client_surface.py, skill-manifest.json

## Alternatives Considered

### A. pnpm workspace package

Make `skills/dashboard/` a workspace package importable via `node_modules`. Rejected: Turbopack auto-detects root via lockfile location — workspace puts lockfile at repo root, same as current state.

### B. Drop Turbopack, use webpack

Webpack respects `watchOptions.ignored` patterns already configured. Rejected: HMR regression from <1s to 3-5s.

### C. Keep split, cap heap with `--max-old-space-size`

Already in place (`start-dev.sh` sets 4GB cap). Rejected: treats symptom not cause, V8 still grows to fill available space.

## Impact Manifest

```yaml
paths_renamed:
  - old: skills/dashboard/components/
    new: apps/dashboard/features/components/
  - old: skills/dashboard/hooks/
    new: apps/dashboard/features/hooks/
  - old: skills/dashboard/pages/
    new: apps/dashboard/features/pages/
  - old: skills/dashboard/scripts/
    new: apps/dashboard/scripts/skill-scripts/
  - old: skills/dashboard/augur/tests/
    new: tests/dashboard/python/
apis_changed: []
patterns_deprecated:
  - pattern: "@skill/ import alias"
    replacement: "@/features/"
  - pattern: "turbopack.root: repoRoot"
    replacement: "auto-detected (project dir)"
  - pattern: "baseUrl: ../.."
    replacement: "baseUrl: ."
files_affected: 115
```

## References

- ADR-490: Framework Migration — Dual-Alias Architecture (partially superseded)
- CLAUDE.md rule #14: Break compatibility, do cleanup
- CLAUDE.md rule #23: Exhaustive path migration on renames/moves
