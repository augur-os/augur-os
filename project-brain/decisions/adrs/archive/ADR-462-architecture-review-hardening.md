---
status: Implemented
date: 2026-03-20
deciders:
  - Gur Sannikov
related:
  - ADR-430
  - ADR-163
  - ADR-270
  - ADR-460
  - ADR-020
hub: null
tags:
  - architecture
  - discovery
  - rag
  - vault
  - remote-execution
  - plugin-loading
  - hardening
superseded_by: null
---

# ADR-462: Architecture Review Hardening — Discovery, RAG, Vault, Remote Execution, Plugin Loading

## Context

A full-system architecture review of the Augur codebase identified systemic issues across 8 areas (plugin system, dashboard, MCP layer, adaptive engine, skill system, data/paths, agent infrastructure, knowledge/RAG). Two rounds of parallel fixes addressed 40+ point issues (daemon bugs, wrong-tool routes, rule violations, stale scan paths, duplicate registrations). Five larger architectural items remained that required coordinated design changes rather than point fixes.

These items shared a common root cause: the ADR-430 migration from `plugins/{bundle}/skills/` to `.claude/skills/` was ~90% complete but left debris across discovery paths, documentation, CI, and dependent systems.

## Decision

### Item 1: Discovery Consolidation (8 implementations → 1)

**Problem:** 8 independent skill discovery implementations scanned different directories, read different frontmatter fields, used different dedup logic, and produced different output types. After ADR-430, 4 of these returned empty results from dead `plugins/*/skills/` scans.

**Solution:** Create `src/plugins/skill_discovery.py` as the single canonical scanner with a `SkillRecord` frozen dataclass (14 fields covering all `x-augur-*` frontmatter). Generate `docs/generated/skill-manifest.json` for TypeScript consumers. Add 30-second TTL cache for hot-path callers. Make `skill_registry.py` a thin re-export wrapper for backward compatibility.

**Migration:** 7 consumer implementations replaced with imports from `skill_discovery`:
- `src/mcp/augur_mcp/adapters/filesystem_registry.py`
- `src/mcp/augur_mcp/registry_loader.py`
- `apps/dashboard/scripts/mount/discovery.ts` (manifest-reading fast path)
- `apps/dashboard/scripts/generate_registry.py`
- `.claude/skills/ai_bridge/augur/lib/discovery.py`
- `.claude/skills/rag/scripts/_indexer_helpers.py`
- `.claude/skills/daemon/scripts/adaptive/discovery.py`

### Item 2: Agent Tier Operationalization

Extracted to ADR-460.

### Item 3: RAG Pipeline Unification

**Problem:** Two indexing pipelines: `rag_indexer.py` (per-skill chunks, MD5 checksums) and `unified_indexer.py` (14 category pointer files). `manifest.entries` never populated, making project index search return empty.

**Solution:** Extend `unified_indexer.py` with heading-based chunking (`_chunk_skills()`) and `manifest.entries` population. Redirect nightly daemon (`rag_reindex.py`) to call `reindex_all()` instead of the per-skill indexer. Remove the `git add` staging of RAG output (ADR-270 violation — RAG artifacts live outside repo). Add word-overlap relevance scoring to `knowledge-project-index-search`. Delete `rag_indexer.py`.

### Item 4: Vault Elimination for Agent Rules

**Problem:** `sync_agents` depended on `~/Vault/Augur/ai_bridge/agent-rules.md` as the single source for all IDE config generation. Missing vault (new machine, CI) caused total failure.

**Solution:** Make `docs/agent-topics/` the only source. No vault copy, no fallback, no sync. Remove all vault path resolution from `sync_agents/constants.py`. Remove the 1000-byte minimum guard and `sync_topic_docs_shared()` from `engine.py`. Update CLAUDE.md auto-generation header. Delete vault copies interactively.

### Item 5: Wire Remote Execution Mode (ADR-020)

**Problem:** A complete remote LLM execution subsystem existed (provider registry, API proxy, UI components) but was never connected to `useActionRunner`. The dispatch pipeline had no `api` case.

**Solution:** Add `api` and `auto` dispatch cases to `useActionRunner`. `runApi()` reads provider/API key from settings, builds prompt via `resolveContext()`, POSTs to `/api/llm`. Auto mode detects IDE availability → falls back to API → falls back to chat dialog. Mount `ExecutionModeToggle` and `ProviderConfigModal` in settings page. Wire `chatStore` remote mode. Amend CLAUDE.md Rule #10 to allow the LLM proxy route when user has explicitly configured API execution mode.

### Item 6: Plugin Tool Loading Fix + Fallback Signal

**Problem:** 8 dashboard routes silently returned empty data when their plugin's MCP tool wasn't loaded. Tool load failures were logged at DEBUG and silently swallowed.

**Solution — Layer 1 (fix root cause):** Add `_failed_plugins` tracking to `plugin_tools.py`, promote load failures to WARNING, add startup validation cross-referencing `CURATED_VISIBLE_TOOLS` against registered tools, create `get-plugin-load-status` MCP diagnostic tool, add `PLUGIN_TOOL_SOURCES` mapping (Python and TypeScript).

**Solution — Layer 2 (graceful degradation for absent plugins):** Inject `_fallback`, `_reason`, `_plugin` metadata into `gracefulFallback` responses in `createAPIRoute.ts`. Create `PluginRequiredBanner` and `ToolErrorBanner` components. Integrate into 7 consumer pages. Distinction: `plugin_not_installed` is a feature gate (not a bug per Rule #5), `tool_error` is a real failure shown in dev mode only.

## Consequences

### Positive

- Single source of truth for skill discovery — 8 implementations reduced to 1 canonical scanner
- RAG search actually returns results (manifest.entries populated, scoring added)
- CI and fresh-machine setups work without vault dependency
- Remote execution mode connects a fully-built subsystem that was never wired
- Plugin load failures are visible to users instead of silently showing empty data
- ~500 net lines removed across the consolidation

### Negative

- `skill_registry.py` re-export wrapper is a backward-compat shim (Rule #14 tension) — needed because 10+ external callers exist
- `PLUGIN_TOOL_SOURCES` is duplicated in Python and TypeScript until discovery consolidation provides the manifest
- Remote execution adds a Rule #10 exemption, expanding the attack surface for the LLM proxy route

### Risks

- Discovery TTL cache (30s) means skill additions aren't visible for up to 30 seconds in long-running processes. Mitigated by `invalidate_discovery_cache()` callable from any consumer.
- Remote execution API keys stored via `set-config` MCP tool — security depends on the MCP tool's encryption implementation.

## Alternatives Considered

### Discovery: Dual canonical implementations (Python + TypeScript)

Keep separate scanners but make them follow identical logic with a shared test suite. Rejected: two codebases to maintain, no guarantee of convergence over time. The generated JSON manifest approach gives TypeScript a static artifact without cross-language dependency.

### Vault: Repo-local fallback (keep vault as editable mirror)

Check vault first, fall back to repo copy. Rejected: two copies to keep in sync, adds complexity without benefit. The repo is version-controlled — edits are committed directly.

### Plugin loading: Remove gracefulFallback entirely (let routes 500)

Dashboard error boundaries catch and show "Plugin required." Rejected: harsher UX — error states vs. informative banners. The `_fallback` metadata approach gives components enough information to show the right message.

## Impact Manifest

```yaml
paths_renamed:
  - old: "src/plugins/skill_registry.py (primary implementation)"
    new: "src/plugins/skill_discovery.py"
  - old: "~/Vault/Augur/ai_bridge/agent-rules.md"
    new: "docs/agent-topics/agent-rules.md"

files_deleted:
  - ".claude/skills/rag/scripts/rag_indexer.py"
  - "src/mcp/augur_mcp/tools/internal/context.py"
  - "~/Vault/Augur/ai_bridge/agent-topics/"

files_created:
  - "src/plugins/skill_discovery.py"
  - "docs/generated/skill-manifest.json"
  - "scripts/generate-skill-manifest.py"
  - "src/agents/performance_ledger.py"
  - "src/config/schemas/agent-profile.schema.json"
  - "apps/dashboard/lib/mcp/plugin-tool-sources.ts"
  - "apps/dashboard/components/ui/PluginRequiredBanner.tsx"
  - "apps/dashboard/components/ui/ToolErrorBanner.tsx"

apis_changed:
  - "useActionRunner: added 'api' and 'auto' dispatch modes"
  - "CLAUDE.md Rule #10: amended to allow LLM proxy route"
  - "registry.json: schema 2.0 with tiers/safety/escalation"
  - "manifest.yaml: version 2.0 with entries list"

patterns_deprecated:
  - "plugins/*/skills/* scan paths (use discover_all_skills())"
  - "Vault-sourced agent rules (use docs/agent-topics/)"
  - "rag_indexer.py per-skill chunking (use unified_indexer.py)"
```

## References

- Design spec: `docs/superpowers/specs/2026-03-20-arch-review-remaining-items-design.md`
- Implementation plan (Phases 1-3): `docs/superpowers/plans/2026-03-20-arch-review-phases-1-3.md`
- Implementation plan (ADR-460): `docs/superpowers/plans/2026-03-20-adr-460-agent-tiers.md`
- ADR-430: Skill migration to client-native layout
- ADR-163: Plugin decentralization
- ADR-270: Data separation
- ADR-020: Local Agent Orchestration (remote execution subsystem)
- ADR-460: Agent Tier Operationalization
