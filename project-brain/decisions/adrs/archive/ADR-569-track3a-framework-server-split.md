---
status: Implemented
date: 2026-04-29
deciders:
  - gsannikov
related:
  - docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md
  - docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md
  - docs/superpowers/specs/2026-04-29-track3a-framework-split-design.md
  - docs/superpowers/plans/2026-04-29-track3a-framework-split.md
  - ADR-567-bundle-architecture-phase0-cleanup.md
  - ADR-568-track3b-dashboard-hub-routing.md
hub: null
tags:
  - architecture
  - bundle-migration
  - track-3a
  - mcp
  - framework-split
superseded_by: null
---

# ADR-569: Track 3a — Framework Server Split + Cleanup + Hardcode Removal

## Status

Implemented (with deferred legacy `augur_mcp/` namespace deletion and one
remaining architecture-test allowlist entry, see Consequences).

## Context

Layer 1 of the cross-client bundle architecture migration target topology
splits the project-tier `augur` monolith into two project-tier MCP
servers: `augur-core` (lightweight, always-on coordination) and
`augur-framework` (the heavy skill/workflow surface). Layer 4 of the same
migration adds the cleanup the monolith needed before it could be split:
retiring dormant tools, replacing vault-private hardcodes with dynamic
discovery, and trimming the architecture-test allowlist that papered
over cross-skill imports.

Tracks 1 and 2 had to land first. Track 1 extracted 5 framework
libraries to `src/lib/` so the project tier no longer imported through
skill code. Track 2 split 5 vault bundles into per-bundle MCP servers
so the monolith no longer co-served vault tools. With those
prerequisites in place, the monolith was reduced to project-tier
responsibilities only and was ready to be cleaved along the
core/framework seam without colocated vault or framework-library
churn.

## Decision

Track 3a ships the project-tier server split as eight sequential PRs on
branch `track3a-framework-split`:

- **`src/mcp/augur_shared/`** — new namespace for cross-server
  utilities consumed by both `augur-core` and `augur-framework`
  (and, transitively, by per-bundle vault servers from Track 2 via
  `augur_shared.bundle_server`). PR 1 lands this additively:
  `bundle_server`, `client_surface`, `compat`, `mcp_sdk`,
  `plugin_tools`, `skill_registry`.
- **23 dormant tools retired** before the split (PR 2). The pre-track
  effective-tool count of 166 dropped to 143, removing dead surface
  area before the split codified ownership. Retirements covered
  obsolete self-update tooling, the standalone skill scorer module,
  `chains_ext`, freeze helpers, file-binary helpers, and the
  `scrape_and_save_idea` hub.
- **11 `src/` vault-private hardcodes replaced with skill_registry
  helpers** (PR 3). Project-tier code no longer hardcodes vault skill
  paths, IDs, or per-skill defaults; `augur_shared.skill_registry`
  exposes lookup helpers that resolve dynamically from the assembled
  skill registry.
- **`src/mcp/augur_core/`** — additive new server (PR 4). Registers 29
  always-on tools covering project coordination, session, and
  capabilities surfaces. Standalone `__main__.py` entry point.
- **`src/mcp/augur_framework/`** — additive new server (PR 5).
  Registers ~205 tools covering the heavy skill / workflow / browse /
  scoring surfaces. Standalone `__main__.py` entry point.
- **Atomic switchover** (PR 6) — replaces the `augur` monolith entry
  in the client manifest (`config/system/mcp_servers.yaml`) with two
  entries (`augur-core`, `augur-framework`). Removes references to
  retired tool names from `apps/dashboard/lib/server/toolFilter.ts`,
  `apps/dashboard/app/api/mcp/capabilities/route.ts`,
  `apps/dashboard/scripts/mount/tool-assembly.ts`, and
  `apps/dashboard/config/route-registry.yaml`. Dashboard build remains
  green because no UI surface was touched — only retired tool-name
  string lists.
- **Vault-tier args migrated to `augur_shared.bundle_server`** (PR 7).
  Per-bundle vault servers from Track 2 now consume their bundle-server
  scaffolding from the shared namespace rather than from `augur_mcp/`.
  This decouples the per-bundle topology from the legacy monolith
  package.
- **Architecture-test allowlist trimmed from 3 to 1 entry** (PR 8).
  `tests/architecture/test_no_cross_skill_imports.py` previously
  allowed three known cross-skill import sites. Track 3a's hardcode
  removal eliminates two of them; the third remaining entry is the
  `("knowledge", "rag")` pair gated on `unified_rag_search` extraction
  and is retained pending follow-up work.

## Deferred (with reasons)

- **Full `src/mcp/augur_mcp/` namespace deletion** — `augur-core` and
  `augur-framework` still call `register_*` functions that live in
  `augur_mcp/` (notably under `tools/hubs/`, `infrastructure/`,
  `domain/plugins.py`). Relocating these ~50 modules into the new
  namespaces is a multi-PR effort with non-trivial test re-routing
  and is not required for the migration's correctness gates. The
  monolith package now functions as a registration-source library
  rather than a server, and its `server.py` / `__main__.py` are
  stripped of coordinator and bundle responsibilities. The full move
  is tracked as follow-up work.
- **`("knowledge", "rag")` allowlist entry** — the last remaining
  architecture-test allowlist entry. Retires when
  `unified_rag_search` extracts to `src/lib/index/`. Out of scope for
  Track 3a because the extraction touches the index pipeline, not the
  framework split.

## Consequences

- Track 4 (visibility filter removal) is unblocked. With no server
  exposing more than ~205 tools per-server, the
  `filter_tools_for_client` mechanism that was needed when the
  monolith registered ~200 tools is dead code; ADR-570 removes it.
- Per-bundle vault servers from Track 2 keep working without churn.
  Their bundle-server scaffolding now imports from
  `augur_shared.bundle_server` (PR 7), and the per-bundle test suites
  (`test_bundle_server_apple.py`, `_file_manager.py`, `_ingest.py`,
  `_lifestyle.py`, `_obsidian.py`) pass against the new namespace.
- The architecture-test allowlist is now a meaningful gate. Two
  known-bad cross-skill import sites are gone; only one allowlist
  entry remains, scoped to the `unified_rag_search` follow-up. New
  cross-skill imports outside the allowlist fail CI.
- The dashboard build stays clean across the switchover. PR 6 only
  removed retired tool-name string references from
  toolFilter / capabilities / tool-assembly / route-registry; no UI
  files changed semantics.
- `augur_mcp/` continues to host registration code consumed by both
  new servers. Treat it as a transitional library, not a server. The
  full namespace migration is captured as deferred work.

## Verification

- `tests/cli/test_augur_core_server.py` — new server smoke (29 tools
  registered, schema valid).
- `tests/cli/test_augur_framework_server.py` — new server smoke
  (~205 tools registered, schema valid, tool-count bound 100-300).
- `tests/architecture/test_no_cross_skill_imports.py` — allowlist
  trimmed to 1 entry, all other cross-skill imports rejected.
- `tests/architecture/test_no_vault_skill_refs.py` — new test guards
  the `src/` hardcode-removal work; project-tier code must not
  reference vault skill paths or IDs directly.
- `tests/cli/test_bundle_server*.py` — per-bundle vault servers pass
  after vault-tier arg migration to `augur_shared.bundle_server`.
- `tests/cli/test_manifest.py` — manifest split into `augur-core` +
  `augur-framework` validates cleanly.
- Dashboard build (`pnpm --filter dashboard build`) clean per PR 6
  commit body.

## Commits

Eight PRs landed sequentially on branch `track3a-framework-split`,
merged via `67cb4a1ad`:

1. **PR 1** — `04910ef24` `feat(track3a): add src/mcp/augur_shared/ (additive)`
2. **PR 2** — `b07b2c1cb` `refactor(track3a): retire 23 dormant tools`
3. **PR 3** — `b091b4ad6` `refactor(track3a): replace 11 src/ vault-private hardcodes with dynamic discovery`
4. **PR 4** — `c9f5d08be` `feat(track3a): add src/mcp/augur_core/ (additive)`
5. **PR 5** — `ff1e20bff` `feat(track3a): add src/mcp/augur_framework/ (additive)`
6. **PR 6** — `2c45a9148` `feat(track3a): atomic switchover — augur monolith → core + framework`
7. **PR 7** — `e4c0555a7` `refactor(track3a): migrate vault-tier args to augur_shared.bundle_server`
8. **PR 8** — `337bf88e6` `refactor(track3a): retire 2 of 3 architecture-test allowlist entries`
