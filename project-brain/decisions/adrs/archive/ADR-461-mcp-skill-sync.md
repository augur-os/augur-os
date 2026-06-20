---
status: Implemented
date: 2026-03-20
deciders:
  - Gur Sannikov
related: [ADR-426, ADR-186]
hub: null
tags: [sync-agents, mcp, skills, client-native]
superseded_by: null
---

# ADR-461: MCP-Based Skill Sync

## Context

The `sync_agents` system distributes skills across 11 AI coding clients using per-client adapter classes. Each adapter implements `sync_skill()` to read a master SKILL.md, reformat it for the target client, and write an adapted copy.

Three problems:

1. **Maintenance burden**: 11 adapter classes (~1500 lines total), each with format-specific copy logic. Adding a new client means writing another 100-300 line adapter.

2. **Incomplete distribution**: Only SKILL.md gets copied. Commands, scripts, references, and modules stay in the master directory. Non-master clients can't access them.

3. **Broken cross-client access**: The MCP skill registry deduplicates by skill ID using last-scanned-wins. When an adapted copy is scanned after the master, the registry points to the adapted directory — which has no scripts/, references/, or modules/. MCP tools like `load-module`, `load-reference`, and `skill-action` silently fail.

### Research Findings

All 11 supported clients (Claude Code, Gemini CLI, Codex, Cursor, Windsurf, Cline, Copilot, Kimi, OpenCode, Antigravity, Claude Desktop) have native file-based discovery AND MCP support. No client can discover skills purely via MCP — all require local files on disk. However, the local file only needs metadata for discovery (name, description, triggers). Full content is served via MCP.

## Decision

Replace file-copy adapter `sync_skill()` methods with MCP-based stub generation:

1. **Master-aware registry deduplication** — detect adapted copies/stubs via markers (`AUGUR-ADAPTED-COPY`, `AUGUR-STUB`, `AUTO-GENERATED FILE`, `Generator:`) in the first 500 bytes of SKILL.md. Exclude them from the registry so MCP tools always resolve to master locations. Applied to three dedup sites: `filesystem_registry.py._parse_skill()`, `skills.py.list_skills_impl()`, and `skill_registry.py._is_auto_generated()`.

2. **Client format spec table** — declarative `ClientFormat` dataclass + `CLIENT_FORMATS` dict replaces per-client adapter format logic. Each entry specifies target directory, filename template, frontmatter fields, and path base (project vs home).

3. **`render-skill-file` MCP tool** — generates client-formatted stub files. Takes skill_id + client_id, returns {path, content, path_base}. Companion `render-all-skill-files` generates all stubs for a client in one call.

4. **Thin sync script** — `sync_client_skills.py` replaces adapter `sync_skill()` methods. Calls `render-all-skill-files` MCP tool, writes stubs to disk, cleans up orphans. ~130 lines replacing ~1500 lines of adapter code.

### Scope boundaries

- Global rules sync (`sync_rules()`) — CLAUDE.md, GEMINI.md, etc. — stays as-is
- MCP config sync (`generate_mcp_config()`) — stays as-is
- Memory sync (`sync_memory()`) — stays as-is
- Adapter classes retained for these responsibilities; only `sync_skill()` removed

### Client classification

| Client | Gets stubs | Format |
|--------|-----------|--------|
| Claude Code | Yes | `.claude/skills/{id}/SKILL.md` |
| Gemini | Yes | `.gemini/skills/{id}/SKILL.md` |
| Codex | Yes | `~/.codex/prompts/{id}.md` (home-based) |
| Cursor | Yes | `.cursor/rules/{id}.mdc` |
| Copilot | Yes | `.github/instructions/{id}.instructions.md` |
| Cline | No | Shares `.claude/skills/` with Claude Code |
| Claude Desktop | No | Context via CLAUDE.md only |
| Windsurf | No | `.windsurf/rules/` is for global rules only |
| Kimi | No | Context via AGENTS.md only |
| OpenCode | No | Context via AGENTS.md only |
| Antigravity | No | Context via instructions.md only |

## Consequences

### Positive

- Cross-client resource access works — MCP tools resolve to master directories with scripts, references, modules
- Adding a new client = adding one row to `CLIENT_FORMATS` dict, not a 200-line adapter class
- ~1500 lines of adapter `sync_skill()` code deleted
- Single source of truth for format specifications (declarative table vs 11 imperative classes)
- Stubs are cheap to regenerate — no freshness tracking needed

### Negative

- `importlib.util` file-loading workaround needed in `sync_client_skills.py` due to `mcp/` directory shadowing
- `CLIENT_SKILL_DIRS` in engine.py and `CLIENT_FORMATS` in client_formats.py are two parallel dicts that can diverge

### Neutral

- Stub files are minimal (frontmatter + `<!-- AUGUR-STUB -->` comment) vs full SKILL.md copies — clients still discover skills natively
- Engine wiring uses `_LocalMcpShim` to bridge direct function calls with the MCP call interface

## Alternatives Considered

### Alternative A: Thin Stubs + MCP On-Demand (no MCP tool)

Keep local stubs but reduce to frontmatter-only, with body loaded via `get-skill` MCP call when triggered. Rejected because it adds an MCP round-trip on every skill activation and doesn't centralize format transformation.

### Alternative C: Full File Sync, Better Engine

Refactor sync_agents with declarative config but keep full file copies. Rejected because it doesn't leverage MCP, maintains N copies on disk with staleness risk, and doesn't fix the cross-client resource access bug.

## References

- Spec: `docs/superpowers/specs/2026-03-20-mcp-skill-sync-design.md`
- Plan: `docs/superpowers/plans/2026-03-20-mcp-skill-sync.md`
- ADR-426: Client-Native Skills
- ADR-186: Agent Source Discovery

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "render-skill-file MCP tool added"
    - "render-all-skill-files MCP tool added"
    - "BaseAdapter.sync_skill() removed"
  patterns_deprecated:
    - "Per-adapter sync_skill() overrides — use render-skill-file MCP tool instead"
    - "_fix_adapted_copy_freshness() — stubs are cheap to regenerate"
    - "sync_single_skill() — replaced by sync_all_clients()"
  files_affected:
    - "src/mcp/augur_mcp/adapters/filesystem_registry.py"
    - "src/mcp/augur_mcp/core/skills.py"
    - "src/mcp/augur_mcp/core/__init__.py"
    - "src/plugins/skill_registry.py"
    - "dist/plugins/augur-knowledge/skills/ai_bridge/scripts/sync_agents/engine.py"
    - "dist/plugins/augur-knowledge/skills/ai_bridge/scripts/sync_agents/adapters/*.py"
```

## Implementation Prompt

**Team name**: `adr-461-mcp-skill-sync`

### Phase 1: Foundation
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | skill-detection | low | Create `is_adapted_copy()` helper with marker detection | `src/mcp/augur_mcp/adapters/skill_detection.py` |
| 1.2 | client-formats | low | Create `ClientFormat` dataclass and `CLIENT_FORMATS` dict | `src/mcp/augur_mcp/core/client_formats.py` |

### Phase 2: Core Implementation
**Strategy**: PARALLEL (depends on Phase 1)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | registry-fix | medium | Fix dedup in filesystem_registry to skip adapted copies | `src/mcp/augur_mcp/adapters/filesystem_registry.py` |
| 2.2 | skills-fix | medium | Fix dedup in skills.py + add AUGUR-STUB to skill_registry.py | `src/mcp/augur_mcp/core/skills.py`, `src/plugins/skill_registry.py` |
| 2.3 | renderer | low | Create render_skill_file() and render_all_skill_files() | `src/mcp/augur_mcp/core/skill_renderer.py` |

### Phase 3: Integration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | mcp-tools | medium | Register render-skill-file MCP tools | `src/mcp/augur_mcp/core/__init__.py` |
| 3.2 | sync-script | medium | Create thin sync script | `.claude/skills/ai_bridge/scripts/sync_agents/sync_client_skills.py` |
| 3.3 | engine-wiring | high | Wire sync script into engine, remove old sync_skill() | `engine.py`, `adapters/*.py` |

### Completion Criteria
- [ ] All phases executed
- [ ] All 36 tests pass (10 detection, 15 renderer/formats, 11 sync)
- [ ] MCP registry resolves 157 skills to master locations
- [ ] Cross-client resource access verified (scripts accessible from non-master clients)
- [ ] ADR status updated to Implemented
