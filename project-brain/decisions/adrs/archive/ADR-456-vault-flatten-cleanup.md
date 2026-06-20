---
status: Implemented
date: 2026-03-19
deciders:
  - Gur Sannikov
related:
  - ADR-451
  - ADR-452
  - ADR-453
  - ADR-416
  - ADR-143
  - ADR-270
hub: null
tags:
  - vault
  - architecture
  - data-separation
superseded_by: null
---

# ADR-456: Vault Flatten & Cleanup

## Context

The vault (`~/Vault/Augur/`) accumulated 3,714 files across 7 bundle directories with 3-4 levels of nesting. 82% of files were exact duplicates of plugin source — action prompts, seed data, prompt templates, chain definitions, schemas, and technical markers (`._seeded`) were copied to vault even though the runtime code could read them from plugin source via fallback.

The structure mirrored internal plugin organization (`augur-{bundle}/{skill}/`) rather than serving user needs. Users opening their vault saw technical clutter mixed with their actual data.

This work builds on ADRs 451-453 which decoupled the dashboard from direct vault access, making this cleanup safe.

### Audit findings

| Category | Files | Status |
|----------|------:|--------|
| Actions | 139 | 120 exact duplicates, 3 stale paths, 16 orphaned |
| Prompts | 81 | 46 exact duplicates, 25 user-authored (source had TODOs), 10 orphaned |
| Seeds (example-*) | 84 | 100% exact duplicates |
| ._seeded markers | 111 | Technical overhead, zero user value |
| Chains | 21 | 100% dead per ADR-143 |
| Schemas | 5 | 100% orphaned |
| _config/ dirs | 11 | 10 orphaned, 1 used with fallback |
| .gitkeep | 10 | Placeholder files |
| Hardening | 10 | Belongs in runtime per ADR-416 |
| augur-adaptive tree | 104 | No user data, all technical files |

## Decision

Flatten the vault from `augur-{bundle}/{skill}/` to `{skill}/` at root. Remove all technical files. Apply the same flattening to `~/Documents/Augur/` and RAG index directories.

### Rules

1. **No bundle grouping** — skill dirs sit directly under vault root
2. **Max 1 entity subdir** — `vault/{skill}/{entity-type}/{file}` — max depth of 4
3. **User data only** — no actions, prompts, chains, seeds, markers, schemas, hardening
4. **No empty dirs** — vault dirs created on-demand when first writing user data
5. **Actions read from plugin source** — `_collect_skill_action_files()` scans plugin source only
6. **Seeds read via fallback** — `SkillDataStore._resolve_read_path()` falls back to `assets/seeds/`
7. **No adaptive skill dirs** — auto-command skills have no user data, no vault presence
8. **Reserved root names** — `config/`, `dev/`, `memory/` rejected by `get_skill_vault_dir()`

### Target state

```
~/Vault/Augur/
  career/              # skill dirs at root
    companies/          # max 1 entity subdir level
    jobs/
    notes/
  finance/
  venture-augur/
  ...
  config/              # cross-skill (kept as-is)
  dev/                 # ADRs, plans, specs (kept as-is)
  memory/              # agent memory (kept as-is)
```

## Consequences

### Positive

- Vault is user-readable — only user data, flat structure
- Vault file count reduced from 3,714 to 3,248 (~466 files removed)
- Directory depth reduced from 10-13 levels to max 4
- Single source of truth — actions, prompts, seeds read from plugin source only
- Path functions simplified — `get_skill_vault_dir()` is now a one-liner, no bundle lookup needed
- MCP config path functions simplified — removed 80 lines of bundle-scanning code
- Hardening bug fixed — career hardening was writing to vault instead of runtime state

### Negative

- RAG indexes must be rebuilt after migration
- Any external scripts that hardcoded `augur-{bundle}/` vault paths will break

### Neutral

- `SkillDataStore._resolve_read_path()` fallback pattern unchanged — works the same, just fewer vault copies to find
- Plugin source structure unchanged — bundles still exist in `plugins/` and `.claude/skills/`

## Alternatives Considered

### Alternative 1: Phased migration with backward compat

Split into 3 sub-ADRs with transitional compatibility shims. Rejected because ADR-453 already decoupled vault access, making a clean cut safe. CLAUDE.md rule 14 (no backward-compat shims) also applies.

### Alternative 2: Code-first, data-last

Change code to stop using vault files, leave dead files sitting, cleanup later. Rejected — leaves vault messy until cleanup pass, two-pass overhead with no benefit over single clean cut.

## References

- Design spec: `docs/superpowers/specs/2026-03-19-vault-flatten-cleanup-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-19-vault-flatten-cleanup.md`
- Migration script: `src/scripts/migrate_vault_flatten.py`

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - "~/Vault/Augur/augur-{bundle}/{skill}/ -> ~/Vault/Augur/{skill}/"
    - "~/Documents/Augur/augur-{bundle}/{skill}/ -> ~/Documents/Augur/{skill}/"
  apis_changed:
    - "get_skill_vault_dir() — no longer requires bundle lookup, returns vault/{skill}"
    - "get_skill_documents_dir() — same change"
    - "get_skill_rag_dir() — same change"
    - "get_bundle_rag_dir() — removed entirely"
  patterns_deprecated:
    - "Seed copy-to-vault (_seed.yaml manifests, ._seeded markers)"
    - "Vault action scanning (_collect_skill_action_files vault source)"
    - "Bundle-based vault path construction (vault / bundle / skill)"
  files_affected:
    - "src/config/paths.py"
    - "src/mcp/augur_mcp/config.py"
    - "src/mcp/augur_mcp/infrastructure/actions.py"
    - "src/mcp/augur_mcp/infrastructure/browse.py"
    - ".claude/skills/auto-seed-data/scripts/seed_data_ops.py"
    - ".claude/skills/auto-vault-hygiene/scripts/vault_hygiene_ops.py"
    - ".claude/skills/rag/scripts/_scanners_structural.py"
    - ".claude/skills/rag/scripts/binary_extractor.py"
    - ".claude/skills/rag/scripts/mcp/rag_tools.py"
    - ".claude/skills/knowledge/scripts/mcp/rag_search.py"
    - ".claude/skills/knowledge/scripts/mcp/rag_knowledge.py"
    - ".claude/skills/file-manager/scripts/mcp/__init__.py"
    - ".claude/skills/apple/scripts/sync/source_sync.py"
    - ".claude/skills/attention/scripts/sync_reminders.py"
    - ".claude/skills/channels/augur/lib/registry.py"
    - ".claude/skills/page-builder/scripts/mcp/__init__.py"
    - ".claude/skills/import/scripts/mcp/__init__.py"
    - ".claude/skills/career/scripts/hardening_helpers.py"
```

## Implementation Prompt

> Already implemented. See branch `adr-454-vault-flatten` in `.worktrees/`.

**Team name**: `adr-456-vault-flatten`

### Phase 1: Core Path Changes
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Flatten vault/documents/RAG path functions | `src/config/paths.py` |
| 1.2 | developer | medium | Rewrite MCP config path functions | `src/mcp/augur_mcp/config.py` |

### Phase 2: Remove Vault Dependencies
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | low | Remove vault from action loading | `infrastructure/actions.py` |
| 2.2 | developer | low | Remove seed copy mechanism | `auto-seed-data/scripts/seed_data_ops.py` |
| 2.3 | developer | medium | Rewrite vault hygiene scanner | `auto-vault-hygiene/scripts/vault_hygiene_ops.py` |

### Phase 3: Fix Path Extraction
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | high | Fix parts[0] hub extraction across 11+ files | RAG, knowledge, browse, file-manager, apple |
| 3.2 | developer | low | Hardening writer audit | Career hardening_helpers.py |

### Phase 4: Migration & Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | low | Remount plugins | `src/scripts/mount-plugins.py` |
| 4.2 | developer | medium | Run vault flatten migration | `src/scripts/migrate_vault_flatten.py` |
| 4.3 | developer | low | RAG re-index + verification | `unified_indexer.py` |
| 4.4 | developer | low | Gap scan + _seed.yaml cleanup | Codebase-wide grep |

### Completion Criteria
- [x] All phases executed
- [x] All 8 verification tests pass
- [x] MCP server starts and responds
- [x] RAG re-indexed (6,297 entries)
- [x] Vault file count: 3,248 (down from 3,714)
- [x] Zero bundle dirs, zero technical files in vault
