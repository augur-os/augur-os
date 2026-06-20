---
title: Track 3a — Framework Split + src/ Hardcode Removal (Design)
date: 2026-04-29
status: proposed
scope: design
related:
  - 2026-04-28-cross-client-bundle-architecture-design.md
  - 2026-04-28-cross-client-bundle-migration-design.md
  - 2026-04-29-track2-vault-server-split-design.md
  - 2026-04-29-track3b-dashboard-hub-routing-design.md
---

# Track 3a — Framework Split + src/ Hardcode Removal (Design)

## Purpose

Layer 4 of the cross-client bundle architecture migration described Track 3a as splitting the `augur` monolith MCP server into `augur-core` (registry/discovery) and `augur-framework` (operational), and removing 10 known src/ vault-private hardcodes. Tools 1 and 2 already shipped:

- Track 1 extracted 5 framework libraries to `src/lib/` (extraction, knowledge, runtime, index, ai).
- Track 2 split 5 vault bundles into per-bundle MCP servers (`augur-apple`, `augur-lifestyle`, etc.) and built `aug config sync` infrastructure.

Track 3a depends on both. Track 3b (dashboard hub-routing redesign) is independent and runs in parallel.

This spec defines the augur-core/augur-framework boundary, the shared-utility package, the cleanup of dormant tools discovered during audit, the dynamic-discovery replacement for hardcoded skill enumerations, the dismantling of the existing `src/mcp/augur_mcp/` namespace, and the migration shape.

## Decisions

- **Two project-tier servers** — `augur-core` (~29 registry/discovery tools) and `augur-framework` (~114 operational tools). The 166 tools currently exposed by the monolith get cleaned + redistributed: 23 retire, 143 migrate.
- **Shared utilities live in a new package `src/mcp/augur_shared/`** — bundle launcher, skill registry helpers, MCP-SDK pinning, interceptor, metrics, client surface, plugin loader. The existing `src/mcp/augur_mcp/` namespace is fully dismantled by the end of Track 3a.
- **Browse-family classification: 13 listing tools to augur-core; 4 operational tools to augur-framework.** Browsing is a registry surface (lists ADRs, agents, scripts, tests, etc.); only `open-file`, `reveal-in-finder`, `cli-install`, `cli-status` are operational.
- **`valid_bundles` and similar hardcoded skill lists in src/ replaced with dynamic registry lookups.** Calling `list_skills()` (already augur-core's tool) — same mechanism used by `_collect_skill_dirs()` in Track 2 — is the canonical source of valid bundle/skill names.
- **23 dormant tools retired before migration** — see Cleanup section. Saves carrying junk forward.
- **All 3 architecture-test allowlist entries retire** — `("ingest", "ai")`, `("ingest", "rag")`, `("knowledge", "rag")`. This is the verification gate for Track 3a per the migration spec.
- **Monolith atomic switchover** — at the moment the project-tier servers split, all client configs flip from `augur` to `augur-core` + `augur-framework` in a single PR. No incremental dual-stack on the protocol layer.
- **Hardcode removal coupled in same track** — the 10 (now 11, including `browse/cli.py:308`) src/ vault-private hardcodes get fixed alongside the server split, since dynamic discovery (the replacement mechanism) only works once augur-core is the registry source-of-truth.
- **8 PRs** — see Migration Shape.
- **Layer 1 spec inconsistency resolved** — fat-framework interpretation (114 tools, not 25). Layer 1's "~25 tools" sentences were drafted before the inventory was done; the 50 figure was the more recent estimate; the 114 reality reflects retirement-first triage.

## Architecture

### Server topology after Track 3a

| Tier | Server | Tool count | Hosts |
|---|---|---|---|
| Project | `augur-core` | ~29 | Registry/discovery: `list-skills`, `find-skill`, `cross-skill`, `unified-search`, `browse-index`, `list-adrs`, `list-agents`, `list-api-routes`, etc. |
| Project | `augur-framework` | ~114 | Operational: file ops, plugins, jobs, IDE control, MCP management, settings, system, performance, workflow, templates, widgets, paths, backend/clients, actions, src/lib/* tools |
| Vault | `augur-apple` | 38 | apple's tools (Track 2) |
| Vault | `augur-lifestyle` | 14 | lifestyle's tools (Track 2) |
| Vault | `augur-file-manager` | 15 | file-manager's tools (Track 2) |
| Vault | `augur-obsidian` | 7 | obsidian's tools (Track 2) |
| Vault | `augur-ingest` | 42 | ingest's tools (Track 2) |

The legacy `augur` monolith is dismantled. After Track 3a, `aug config sync` writes 7 server entries (2 project-tier + 5 vault-tier) to user-tier client configs.

### Source-tree layout after Track 3a

```
src/
├── mcp/
│   ├── augur_core/          # NEW: registry/discovery server
│   │   ├── __init__.py
│   │   ├── __main__.py      # python -m augur_core
│   │   └── tools/           # Registry tools (28-29 of them)
│   ├── augur_framework/     # NEW: operational server
│   │   ├── __init__.py
│   │   ├── __main__.py      # python -m augur_framework
│   │   └── tools/           # Operational tools (~114)
│   ├── augur_shared/        # NEW: cross-server utilities
│   │   ├── __init__.py
│   │   ├── bundle_server.py # MOVED from augur_mcp/ (used by Track 2 vault-tier)
│   │   ├── plugin_tools.py  # MOVED — _load_bundle_mcp_module + _collect_skill_dirs
│   │   ├── interceptor.py   # MOVED — mcp_tool_interceptor
│   │   ├── metrics.py       # MOVED — metrics tracker
│   │   ├── client_surface.py # MOVED — visibility/exposure utilities
│   │   ├── mcp_sdk.py       # MOVED — _pin_mcp_sdk_package + FastMCP setup
│   │   └── compat.py        # MOVED — backward-compat helpers
│   └── augur_mcp/            # DELETED at end of Track 3a — no remaining files
└── ...
```

`bundle_server.py` continues to support per-bundle vault-tier servers (Track 2 invariant). After Track 3a, vault-tier servers launch via `python -m augur_shared.bundle_server <bundle>` — the import path updates as part of the move.

### Shared utility migration

Files moving from `src/mcp/augur_mcp/` to `src/mcp/augur_shared/`:

| Source path | Destination | Used by |
|---|---|---|
| `augur_mcp/bundle_server.py` | `augur_shared/bundle_server.py` | Track 2's per-bundle vault-tier servers |
| `augur_mcp/plugin_tools.py` | `augur_shared/plugin_tools.py` | augur-core (skill scan), bundle-server (resolution) |
| `augur_mcp/server.py` (parts) | split: `augur_shared/mcp_sdk.py` (SDK pinning, FastMCP wiring) + tool definitions absorbed into core/framework | both servers |
| `augur_mcp/compat.py` | `augur_shared/compat.py` | both servers (legacy compat helpers) |
| `augur_mcp/client_surface.py` | `augur_shared/client_surface.py` | both servers (visibility filter — to be deleted in Track 4) |

Files NOT moving (their tool definitions migrate into augur-core or augur-framework):
- `augur_mcp/core/__init__.py` — 29 tool registrations → augur-core
- `augur_mcp/domain/cowork.py`, `domain/ide.py`, `domain/plugins.py` → augur-framework
- `augur_mcp/infrastructure/*` (29 files) → augur-framework (mostly)
- `augur_mcp/tools/hubs/*` → augur-framework (after deleting `scrape_and_save_idea.py`)
- `augur_mcp/tools/internal/*` → augur-framework
- `augur_mcp/self_update/__init__.py` → DELETE entirely (cluster retired in cleanup)

### Cleanup — 23 tools retired before migration

#### Confirmed dead (6) — zero callers anywhere

`freeze-overview`, `get-augur-mode`, `set-augur-mode`, `enhance-dashboard`, `create-dashboard-wizard`, `switch-mcp-tool-groups`

#### Self-update suite (9) — entire `src/mcp/augur_mcp/self_update/` package retired

`apply-patch`, `diff-module`, `update-module`, `rollback-module`, `list-backups`, `learn-pattern`, `list-patterns`, `mark-pattern-applied`, `propose-update`. All 9 declared in registry/capabilities/tool-filter but zero real callers. Experimental "self-modifying code" surface that was scaffolded but never wired up.

#### Heavy-docs-no-caller (3) — plans documented but wiring never landed

`vault-file-read`, `vault-file-write`, `skill-score`. Replacement: `file-read` and `file-write` cover vault operations; skill scoring exists in the skill-quality skill independently. The `skills/auto-skill-quality/SKILL.md` reference to `skill-score` is updated to remove the dangling tool name.

#### Declaration-only (4) — only in visibility/filter lists

`get-batch-presets`, `record-voice` (Au-vault note explicitly says "Returns not implemented"), `run-intelligence-prompt`, `match-content-to-skill`.

#### Hardcoded-to-lifestyle module (1) — entire file deleted

`scrape-and-save-idea-overview` in `src/mcp/augur_mcp/tools/hubs/scrape_and_save_idea.py`. The module is one of the 11 src/ hardcodes (the entire file is keyed to `lifestyle`). Deleted; the lifestyle vault server can implement scraping internally if needed.

### Hardcode removal — 11 sites

10 from migration spec + 1 new from research:

| File | Line | Pattern | Replacement |
|---|---|---|---|
| `src/config/mcp_tools.py` | 386-387 | `vertical_skills = {"career", "lifestyle", ...}` | Dynamic registry lookup via `list_skills()`; filter by `x-augur-type` |
| `src/mcp/augur_mcp/infrastructure/mcp_management.py` | 289 | `"lifestyle"` heuristic | Generalize to skill-type lookup |
| `src/mcp/augur_mcp/infrastructure/config.py` | 730-742 | `valid_bundles = [...11 names...]` | Dynamic registry lookup |
| `src/mcp/augur_mcp/infrastructure/config.py` | 736 | `"lifestyle"` literal | Same as above |
| `src/mcp/augur_mcp/domain/plugins.py` | 218 | `bundle: str = "lifestyle"` default param | Remove default; require explicit bundle |
| `src/mcp/augur_mcp/tools/hubs/capabilities.py` | 24 | hardcoded `"apple"` capability description | Move to skill-declared `x-augur-mcp-tools` metadata |
| `src/mcp/augur_mcp/tools/hubs/scrape_and_save_idea.py` | 17, 22, 53 | entire module hardcoded to `lifestyle` | DELETE module entirely (cleanup) |
| `src/mcp/augur_mcp/infrastructure/browse/dev.py` | 98 | `"lifestyle"` literal in list | Dynamic discovery |
| `src/mcp/augur_mcp/infrastructure/mcp_management.py` | 318 | `lifestyle` in category-description string | Generalize description |
| `src/mcp/augur_mcp/infrastructure/browse/cli.py` | 308 | `if integration_type == "vault" and skill == "obsidian":` | Replace with `is_vault_skill(skill)` registry check |

After Track 3a, the parallel architecture-rule test `tests/architecture/test_no_vault_skill_refs.py` passes with no allowlist exceptions for `src/`.

### Migration shape (8 PRs)

#### PR 1 — `src/mcp/augur_shared/` setup (additive)

Move shared infrastructure files from `augur_mcp/` to `augur_shared/`. Update `augur_mcp/` files to re-export from the new location (compat layer). All existing imports continue to work; tests pass unchanged.

Files moved: `bundle_server.py`, `plugin_tools.py`, `compat.py`, `client_surface.py`, plus extracted parts of `server.py` (`mcp_sdk.py`).

Track 2's `augur_mcp.bundle_server` import path stays valid via the re-export shim — the `aug config sync` manifest's vault-tier `args: [-m, augur_mcp.bundle_server, <bundle>]` continues working.

Verification: full test cascade passes; existing per-bundle servers still launch.

#### PR 2 — Cleanup (retire 23 dormant tools)

Delete:
- `src/mcp/augur_mcp/self_update/` (entire directory; 9 tools)
- `src/mcp/augur_mcp/tools/hubs/scrape_and_save_idea.py` (1 tool)
- 6 confirmed-dead tool registrations: `freeze-overview` (delete `freeze.py`), `get-augur-mode`/`set-augur-mode` registrations in `config.py`, `enhance-dashboard`/`create-dashboard-wizard` registrations in `workflow.py`, `switch-mcp-tool-groups` registration in `mcp_management.py`
- 4 declaration-only tools: `get-batch-presets`, `record-voice`, `run-intelligence-prompt`, `match-content-to-skill`
- 3 heavy-doc-no-caller tools: `vault-file-read`, `vault-file-write` from `core/__init__.py`; `skill-score` from `skill_scorer.py`
- Update `apps/dashboard/lib/server/toolFilter.ts` and capabilities/route.ts to remove deleted tool names
- Update `config/dashboard/mcp_tools.yaml` to remove deleted tool category
- Update `skills/auto-skill-quality/SKILL.md` to remove `skill-score` reference

Verification: full test cascade; dashboard build clean; no remaining references to deleted tool names anywhere.

#### PR 3 — Hardcode removal (10 sites + 1 module-delete)

Replace hardcoded skill names with dynamic registry lookups in the 10 sites listed above. The 11th (`scrape_and_save_idea.py`) was already deleted in PR 2.

Each site gets a targeted fix:
- `valid_bundles` lists → `is_known_skill(name)` helper backed by registry
- `bundle: str = "lifestyle"` defaults → required parameters with explicit error
- Hardcoded vault checks → `is_vault_skill(name)` registry check

The shared `is_vault_skill()` helper lives in `augur_shared/skill_registry.py` (new file).

Verification: new test `tests/architecture/test_no_vault_skill_refs.py` passes (scope: `src/`).

#### PR 4 — `src/mcp/augur_core/` setup (additive)

Create `augur_core/` with all 29 registry/discovery tools. Tools are imported from their existing definitions in `augur_mcp/` (so the move is just a new server entrypoint, not a code copy). The `augur` monolith continues to register the same tools alongside augur-core during this PR.

Files created:
- `src/mcp/augur_core/__init__.py`
- `src/mcp/augur_core/__main__.py` — `python -m augur_core` stdio entrypoint
- `src/mcp/augur_core/tools/__init__.py` — pulls in the 29 registry tools

Manifest update: add `augur-core` to `config/system/mcp_servers.yaml` `project_tier`. Don't add to `monolith_exclusions` yet — augur monolith still serves these tools redundantly during PR 4.

Verification: `python -m augur_core` starts; `tools/list` returns 29 tools.

#### PR 5 — `src/mcp/augur_framework/` setup (additive)

Same shape as PR 4, for ~114 operational tools.

Verification: `python -m augur_framework` starts; `tools/list` returns ~114 tools.

#### PR 6 — Atomic switchover

The single critical PR. In one commit:
- Manifest: replace `augur` entry in `project_tier` with `augur-core` + `augur-framework`
- Manifest: do NOT add anything to `monolith_exclusions` (augur is gone)
- Delete `src/mcp/augur_mcp/server.py` and any monolith entrypoint
- Update `pyproject.toml` `[project.scripts]` if it references the monolith
- Update Track 1's plan documentation that mentions `augur_mcp` runtime
- Update `aug config sync`'s adapter logic to handle entries with `id == "augur"` removal (the sync diff will show `- augur` once)

After this PR, the user runs `aug config sync` and the user-tier configs replace `augur` with `augur-core` + `augur-framework`.

Verification: `aug config sync --dry-run` shows the expected diff; manual reload confirms each new server is reachable.

#### PR 7 — Dismantle `src/mcp/augur_mcp/` namespace

After PR 6 cuts over, no code should import from `augur_mcp.*` anymore. Audit grep:

```bash
grep -rn "from augur_mcp\|import augur_mcp" --include="*.py" .
grep -rn "from src\.mcp\.augur_mcp\|src\.mcp\.augur_mcp" --include="*.py" .
```

Any remaining references get migrated to `augur_core`, `augur_framework`, or `augur_shared`. Then delete `src/mcp/augur_mcp/` entirely.

Manifest update: ensure `augur-core` and `augur-framework` arg paths reference `augur_core` and `augur_framework`, not `augur_mcp`.

Verification: full test cascade; dashboard build clean; all 5 vault-tier per-bundle servers still launch (their `bundle_server` reference now points at `augur_shared.bundle_server`).

#### PR 8 — Architecture allowlist retirement + ADR

Retire 3 entries from `tests/architecture/test_no_cross_skill_imports.py`:
- `("ingest", "ai")` — sync_agents extraction follow-up
- `("ingest", "rag")` — rag bundle MCP consolidation in framework
- `("knowledge", "rag")` — same

These retire because:
1. ingest is now a vault-tier per-bundle server (Track 2)
2. ai is a `src/lib/ai/` library (Track 1)
3. rag's bundle MCP wrappers consume `src/lib/index/` (Track 1)
4. knowledge consumes `src/lib/index/` directly (Track 1)
5. cross-skill imports of `skills/<X>/scripts/` library code are no longer possible (libraries moved out)

Run the architecture test: should pass with empty allowlist.

Write ADR `track3a-framework-split.md` recording:
- The augur-core/augur-framework boundary (29 / 114 tool counts)
- The augur_shared package
- The 23-tool retirement list
- The 11 hardcode fixes
- The 8-PR shape and dates

Verification: `tests/architecture/test_no_cross_skill_imports.py` passes with empty `ALLOWED_CROSS_SKILL_IMPORTS` frozenset; ADR committed.

### Validation gates

| PR | Gate |
|---|---|
| 1 | full test cascade; existing per-bundle servers still launch |
| 2 | full test cascade; dashboard build clean; zero references to deleted tool names |
| 3 | new `test_no_vault_skill_refs.py` passes for `src/`; existing tests pass |
| 4 | `python -m augur_core` exposes 29 tools |
| 5 | `python -m augur_framework` exposes ~114 tools |
| 6 | `aug config sync --dry-run` shows expected `- augur, + augur-core, + augur-framework`; manual reload confirms each new server reachable |
| 7 | full test cascade; dashboard build clean; all 5 vault-tier servers still launch |
| 8 | `test_no_cross_skill_imports.py` passes with empty allowlist; ADR written |

### Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| PR 6 atomic switchover misconfigures clients; user loses MCP access mid-session | Medium | `aug config sync` creates timestamped backups; rollback is `cp <bak> <config> && reload`. Document the recovery path in commit body. |
| PR 7 misses an `augur_mcp` import; deletes namespace breaks production code | Medium | Audit grep before deletion; CI lint check forbids `from augur_mcp.` going forward. |
| Track 2's vault-tier servers break when `bundle_server.py` moves to `augur_shared` | Medium | PR 1 keeps a re-export shim in `augur_mcp.bundle_server`; manifest's `args: [-m, augur_mcp.bundle_server, <bundle>]` still works through PR 6. PR 7 updates manifest entries to `augur_shared.bundle_server` and removes the shim. |
| 23 tool retirements break a caller the audit missed | Low | The audit covered TS, slash, tests, config, registries, docs, SKILL.md, action YAML, Au-vault. PR 2 runs full test cascade + dashboard build; any missed caller surfaces. |
| Architecture test fails after allowlist retirement | Medium | PR 8 runs test BEFORE removing entries; if violations surface, they're real cross-skill imports needing migration first. |
| `valid_bundles` dynamic discovery is slower than the hardcoded list | Low | Skill registry is already cached; `is_known_skill()` is O(1) lookup. |

### Allowlist retirement table (Done criterion #5)

After PR 8, `tests/architecture/test_no_cross_skill_imports.py:ALLOWED_CROSS_SKILL_IMPORTS` is the empty frozenset:

```python
ALLOWED_CROSS_SKILL_IMPORTS: frozenset[tuple[str, str]] = frozenset()
```

### Coordination with Track 3b

Tracks 3a and 3b are independent per Layer 4 spec. They can execute in either order or in parallel. Both touch `apps/dashboard/scripts/skill-scripts/` files — Track 3b's PR 3 (scanner templates) overlaps with Track 3a's PR 3 (hardcode removal in src/) only at the boundary. The `apps/dashboard/scripts/skill-scripts/` files are Track 3b's territory; the `src/mcp/augur_mcp/` files are Track 3a's. No collision.

If both tracks execute simultaneously: merge sequence doesn't matter because the file-paths are disjoint.

## Done criteria

1. ✅ `src/mcp/augur_core/` package exists; `python -m augur_core` exposes 29 registry/discovery tools
2. ✅ `src/mcp/augur_framework/` package exists; `python -m augur_framework` exposes ~114 operational tools
3. ✅ `src/mcp/augur_shared/` package exists; cross-server utilities live there
4. ✅ `src/mcp/augur_mcp/` directory deleted; no code imports from it
5. ✅ Architecture-test allowlist `ALLOWED_CROSS_SKILL_IMPORTS` is empty
6. ✅ 23 dormant tools retired and zero references in production code
7. ✅ 11 src/ vault-private hardcodes replaced with dynamic discovery
8. ✅ `tests/architecture/test_no_vault_skill_refs.py` passes for `src/` with no allowlist exceptions
9. ✅ `aug config sync` writes 2 project-tier servers (augur-core + augur-framework) instead of 1 (augur) — 5 vault-tier entries unchanged
10. ✅ Dashboard builds successfully and renders normally in browser
11. ✅ All 5 vault-tier per-bundle servers still launch (Track 2 invariant preserved)
12. ✅ ADR `track3a-framework-split.md` written
13. ✅ All 8 PRs merged to `main`

## Track 4 follow-up

Track 4 (visibility filter removal) ships immediately after Track 3a. With the monolith split into 2 servers (29 + 114 tools) plus 5 per-bundle vault servers, no server registers more than ~114 tools — the filter is no longer the bandage hiding the 200-tool problem. Single-PR delete of `CURATED_VISIBLE_TOOLS`, `COWORK_VISIBLE_TOOLS`, and `filter_tools_for_client` curation branches in `client_surface.py` (which now lives in `augur_shared`).
