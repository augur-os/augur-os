---
status: Implemented
date: 2026-03-17
deciders:
  - Gur Sannikov
related:
  - ADR-430
  - ADR-431
hub: dev
tags:
  - plugins
  - metadata
  - framework
  - migration
superseded_by: null
---

# ADR-432: Plugin Distribution — Metadata & Framework Update

> Sub-ADR of ADR-430. Phase 1 + Phase 2. Core migration work — the most complex phase.

## Context

ADR-431 cleaned up skill directories. This sub-ADR handles the two hardest steps: migrating metadata from `augur.yaml` to SKILL.md frontmatter (Phase 1), and updating all framework integration systems to discover skills from Claude Code plugin cache directories (Phase 2).

## Decision

Execute Phase 1 (metadata migration, 4 steps) and Phase 2 (framework & integration, 11 steps) from ADR-430.

**Prerequisite**: ADR-431 must be Implemented (all cleanup gates passed).

## Implementation Prompt

**Team name**: `adr-432-framework`

### Gate 0: Pre-flight
Verify ADR-431 is Implemented. Zero `.config`, `augur/data/`, `assets/prompts/` remain. ADRs in vault.

### Batch A: Metadata migration (parallel)
**Strategy**: PARALLEL via team agents

| Agent | Task | Files |
|-------|------|-------|
| `metadata` | For all 131 skills: read `augur/augur.yaml`, extract all fields, write as `x-augur-*` frontmatter into SKILL.md (x-augur-hub, x-augur-plugin, x-augur-mcp-tools, x-augur-dashboard-page, x-augur-requires-platform). Preserve existing frontmatter. Delete `augur.yaml` after migration. | `.claude/skills/*/SKILL.md`, `.claude/skills/*/augur/augur.yaml` |
| `classifier` | Classify 52 adaptive skills as "code-focused" (→ augur-adaptive) or "dashboard-focused" (→ augur-dashboard). Criterion: grep for dashboard/page/route/block refs vs code/config refs. Output classification table. Write `x-augur-plugin` value per skill. | `.claude/skills/auto-*/SKILL.md` |
| `cross-refs` | Audit all SKILL.md files for relative path references (`../`, `../../`). Convert to skill name references. Report all changes. | `.claude/skills/*/SKILL.md` |
| `unassigned` | Assign hub and plugin to `executor` and `reindex-rag` (missing augur.yaml). Create `x-augur-*` frontmatter. | `.claude/skills/executor/`, `.claude/skills/reindex-rag/` |

### Gate 1: Metadata verification
- `find .claude/skills -name 'augur.yaml' -path '*/augur/augur.yaml' | wc -l` = 0
- `grep -rL 'x-augur-plugin' .claude/skills/*/SKILL.md | wc -l` = 0 (all have plugin assignment)
- `grep -r '\.\./\.\.' .claude/skills/*/SKILL.md | wc -l` = 0 (no relative cross-refs)
- Adaptive classification table reviewed (manually or via report)

### Sequential: Paths core (dependency chain)
**Strategy**: PIPELINE (each step depends on previous)

| Step | Agent | Task | Files |
|------|-------|------|-------|
| 1 | `paths-core` | Update `src/config/paths.py`: add `get_claude_plugin_skill_dirs()`, update `get_all_client_skill_dirs()` to include plugin cache, update `_discover_skill_to_bundle_mapping()` to read `x-augur-hub` from SKILL.md frontmatter, update `get_skill_root()` for plugin cache. | `src/config/paths.py` |
| 2 | `mcp-discovery` | Update `plugin_tools.py:_collect_skill_dirs()` to scan plugin cache dirs using `get_claude_plugin_skill_dirs()` from step 1. | `src/mcp/augur_mcp/plugin_tools.py` |
| 3 | `vault-resolution` | Update `config.py`: `get_skill_data_dir()` scan plugin cache, `_resolve_client_skill_bundle()` parse SKILL.md frontmatter instead of augur.yaml. | `src/mcp/augur_mcp/config.py` |

### Gate 2: Core paths verification
- `python3 -c "from src.config.paths import get_claude_plugin_skill_dirs; print(get_claude_plugin_skill_dirs())"` returns valid paths
- `python3 -c "from src.config.paths import get_skill_bundle; print(get_skill_bundle('career'))"` returns `career` (reads from SKILL.md frontmatter)
- `augur mcp serve` starts and loads tools from `.claude/skills/`

### Batch B: Integration consumers (all parallel, depend on paths-core)
**Strategy**: PARALLEL via team agents

| Agent | Task | Files |
|-------|------|-------|
| `rag` | Update RAG: (1) `_indexer_helpers.py:_discover_skill_dirs()` use updated paths. (2) `rag_indexer.py:resolve_rag_output_root()` handle plugin cache. (3) `rag_tools.py:_resolve_scope_paths()` resolve plugin skills. (4) `rag_reindex.py` scan plugin cache. (5) `scripts/bulk_index.py` include plugin cache. | `.claude/skills/rag/scripts/`, `scripts/bulk_index.py` |
| `daemon` | Update daemon: (1) `service_healer.py` replace hardcoded paths with `get_skill_root("daemon")`. (2) Plist templates use `__SKILL_ROOT__` placeholder. (3) Add `AUGUR_SKILL_ROOT` + `PYTHONPATH` env vars to plist. Test LaunchAgent generation. | `.claude/skills/daemon/scripts/`, `.claude/skills/daemon/assets/plists/` |
| `mount` | Update `mount-plugins` to scan Claude Code plugin install dirs for `augur/dashboard/` and `augur/api/`. | `scripts/mount-plugins.*` |
| `seeds` | Update auto-seed-data and `/import`: seed discovery scans plugin cache dirs for `assets/seeds/`. | `.claude/skills/import/scripts/`, `.claude/skills/auto-seed-data/` |
| `cross-paths` | Audit all `Path(__file__).parent` patterns that navigate outside skill directory. Convert to `get_skill_root()`. | `.claude/skills/*/scripts/**/*.py` |
| `sync` | Update sync engine: (1) `constants.py` add plugin cache. (2) `engine.py` scan plugin cache for masters, fix cleanup/freshness. (3) `auto_tag_master()` infer claude-code for plugin cache. (4) `discovery.py` include plugin cache. (5) `mount/discovery.ts` scan plugin cache. | `.claude/skills/ai_bridge/scripts/sync_agents/`, `apps/dashboard/scripts/mount/discovery.ts` |
| `adr-consumers` | Update ADR consumers: (1) `unified_indexer.py:index_adrs()` read vault. (2) `browse.py:list_adr_impl()` read vault. (3) `orphan_plans.py` scan vault. (4) `auto-doc-freshness` scan vault. (5) dev-adr MCP tools read/write vault. | `.claude/skills/rag/scripts/`, `src/mcp/augur_mcp/infrastructure/browse.py`, `.claude/skills/dev-adr/scripts/mcp/` |
| `browse` | Update Browse: (1) `skill_registry.py` add tier 3 for plugin cache, add source/plugin fields. (2) `list-skills` MCP tool include source/plugin. (3) `transforms.ts` map to badges. (4) `BrowseToolbar.tsx` add plugin filter. (5) `BrowseCard.tsx` render source badge. | `src/plugins/skill_registry.py`, `apps/dashboard/lib/browse/`, `apps/dashboard/components/shared/BrowseCard.tsx` |

### Gate 3: Full integration verification
- `augur mcp serve` loads tools from both `.claude/skills/` and a test plugin dir
- `get_skill_data_dir("career")` resolves for both local and plugin-installed
- RAG reindex discovers skills from plugin cache
- `/ask "what is ADR-430"` returns content from vault
- `/adr query 430` reads from vault
- Daemon plist generates with dynamic `__SKILL_ROOT__`
- `mount-plugins` finds resources from plugin cache
- `sync_agents --all` discovers masters in plugin cache, generates adapted copies
- Browse shows `source` badges and plugin name filter works
- `npm run build` passes
- `pytest` passes

### Completion Criteria
- [ ] Zero `augur.yaml` files remain
- [ ] All 131 SKILL.md have `x-augur-plugin` frontmatter
- [ ] `paths.py` includes plugin cache scanning
- [ ] `plugin_tools.py` discovers MCP tools from plugin cache
- [ ] Vault resolution works for plugin-installed skills
- [ ] RAG indexes plugin-installed skills
- [ ] Daemon uses `get_skill_root()` (no hardcoded paths)
- [ ] mount-plugins scans plugin cache
- [ ] Sync engine handles plugin cache masters
- [ ] Browse shows source/plugin metadata
- [ ] ADR consumers read from vault
- [ ] All cross-skill `Path(__file__)` patterns fixed
- [ ] ADR-432 status → Implemented
