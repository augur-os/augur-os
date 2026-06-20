---
status: Implemented
date: 2026-03-22
deciders:
  - Gur Sannikov
related:
  - ADR-426
  - ADR-186
  - ADR-171
  - ADR-163
  - ADR-270
hub: null
tags: [skills, multi-client, distribution, sync, discovery]
superseded_by: null
---

# ADR-479: Multi-Client Skill Structure

## Context

Augur skills were stored across 4+ directories (`.claude/skills/`, `plugins/*/skills/`, `.gemini/skills/`, `.codex/prompts/`), managed by a 4-tier discovery engine with deduplication and shadowing (~600 lines), synced via an MCP-backed render pipeline with adapted-copy markers (~500 lines). This complexity served a simple goal: make skills available to multiple AI clients.

MiniMax-AI/skills demonstrated a radically simpler model: one `skills/` directory, per-client install instructions, no sync engine.

ADR-426 (Client-Native Skill Mastering) had Phases 3-4 pending: gradually migrate skills from `plugins/` to client dirs. This ADR supersedes that approach with a more complete solution.

## Decision

### 1. Single canonical `skills/` directory at project root

All Augur skills live in `skills/{skill-name}/` — flat, one dir per skill. No bundles, no hub grouping in directory structure. Hub assignment is a frontmatter field (`x-augur-hub`), not a directory.

### 2. Two skill tiers

- **Portable**: No `augur/` subdir. Standard frontmatter (`name`, `description`, `license`, `metadata`). Works in any SKILL.md-aware client.
- **Augur-native**: Has `augur/` subdir (`dashboard/`, `data/`, `tests/`, `seed/`). Uses `x-augur-*` frontmatter extensions. Requires Augur runtime.

### 3. Three skill sources with origin tagging

| Source | Location | Origin | Writable by Augur? |
|--------|----------|--------|-------------------|
| Augur bundled | `skills/` | `augur` | Yes |
| User-created (`/evolve`) | `skills/` | `augur` (author=`user`) | Yes |
| Client-installed | Client cache dirs | `{client-name}` | No (read-only) |

### 4. One-way stub generator replaces MCP sync

`scripts/generate_client_stubs.py` reads `skills/*/SKILL.md` and writes flat stubs to 5 client directories: `.codex/prompts/`, `.cursor/rules/`, `.github/copilot/`, `.gemini/skills/`, `.opencode/skills/`. Generated stubs are marked with `<!-- AUGUR-GENERATED -->`. No MCP dependency.

### 5. Simplified multi-source discovery

`discover_all_skills()` scans `skills/` (primary, origin=augur) + client cache dirs (read-only, origin={client}). Skips `AUGUR-GENERATED`-marked files in client dirs. Compound key: `(origin, name)`. No tiers, no dedup, no shadowing.

### 6. Deprecated fields removed

`x-augur-master`, `x-augur-sync`, `x-augur-origin`, `x-augur-plugin` — all removed. Single location = single owner.

### 7. Client plugin manifests for distribution

`.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json` enable client-native discovery. All 6 clients have INSTALL.md guides: `.codex/INSTALL.md`, `.opencode/INSTALL.md`, `.gemini/INSTALL.md`, `.cursor-plugin/INSTALL.md`, `.github/copilot/INSTALL.md`. Claude Code uses plugin.json for native discovery (no install guide needed).

## Consequences

### Positive

- Single source of truth — no more "where does this skill live?"
- ~900 lines of sync infrastructure deleted
- Skills distributable by default (git clone + symlink)
- No adapted copies, no AUGUR-ADAPTED-COPY markers
- Community contributions possible via PR to `skills/`
- Discovery under 530 lines (was 628), core scan logic ~200 lines with backward-compat wrappers
- Dashboard shows all skills from all sources with origin/author/tier/hub filters

### Negative

- 184 skills moved in one commit — large diff, hard to review
- Hub grouping only via frontmatter grep, not directory structure
- Client cache scanning adds external directory dependency
- Flat `skills/` directory with 184 entries can be noisy in IDE

### Neutral

- Vault data model unchanged (ADR-270)
- Dashboard architecture unchanged
- SKILL.md format unchanged (just fewer required fields)
- `x-augur-*` fields still work — non-Augur clients ignore them

## Alternatives Considered

### Alternative A: Hub-Grouped skills/{hub}/{name}/

Skills grouped by hub directory. Preserved filesystem discoverability of hub membership. Rejected: re-creates the bundle problem under a different name. Frontmatter is the right place for metadata.

### Alternative B: Hybrid — Root skills/ for portable, .claude/skills/ for native

Two physical directories matching the two tiers. Least migration work. Rejected: doesn't achieve the "one canonical location" goal, discovery still needs two sources.

## References

- Design spec: `docs/superpowers/specs/2026-03-22-multi-client-skill-structure-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-22-multi-client-skill-structure.md`
- Reference: [MiniMax-AI/skills](https://github.com/MiniMax-AI/skills)
- Supersedes: ADR-426 (Phase 3-4), ADR-186 (sync refactor), ADR-171 (bidirectional sync)

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - ".claude/skills/{name}/ → skills/{name}/"
    - "plugins/{bundle}/skills/{name}/ → skills/{name}/"
  apis_changed:
    - "discover_all_skills() — new origin/author fields, no master/sync_enabled"
    - "get_skill_root() — resolves from skills/ only"
    - "GET /api/skills/registry — new endpoint"
  patterns_deprecated:
    - "x-augur-master field"
    - "x-augur-sync field"
    - "x-augur-origin field"
    - "x-augur-plugin field"
    - "AUGUR-ADAPTED-COPY markers"
    - "AUGUR-STUB markers"
    - "4-tier skill discovery"
    - "MCP-backed sync pipeline"
    - "PLUGIN_BUNDLES constant"
    - "augur.yaml plugin manifests"
  files_affected:
    - "src/plugins/skill_discovery.py (rewritten)"
    - "src/config/paths.py (rewritten)"
    - "apps/dashboard/scripts/mount-plugins.ts (rewritten)"
    - "apps/dashboard/scripts/mount/discovery.ts (rewritten)"
    - "src/mcp/augur_mcp/adapters/filesystem_registry.py (simplified)"
    - "src/mcp/augur_mcp/core/skill_renderer.py (deleted)"
    - "src/mcp/augur_mcp/adapters/skill_detection.py (deleted)"
    - "src/mcp/augur_mcp/core/client_formats.py (deleted)"
```
