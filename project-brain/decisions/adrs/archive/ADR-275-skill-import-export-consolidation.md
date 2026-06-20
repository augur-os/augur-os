---
status: Implemented
date: '2026-03-12'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- skill
- import
- export
- consolidation
- client
superseded_by: null
---

# ADR-275: Skill Import/Export Consolidation & Client Observability

## Context

Augur has two types of skills: (1) Augur-native skills synced across clients via sync_agents, and (2) client-native skills installed directly in a specific client (Claude Code, Codex, Gemini) that are invisible to Augur. Five overlapping skills handled import/install/export with significant duplication: `dev-import`, `install`, `notion-import`, `ops-install`, `ops-pkg`.

## Decision

1. **Consolidate 5 skills into 1 unified `import` skill** with 5 auto-detected modes: package, data-folder, notion, skill-promote, export
2. **Add client-native skill observability** via the dev-sync dashboard page with sync status and client skills inventory tabs
3. **Add skill promote pipeline** to copy client-native skills into the Augur plugin tree
4. **Add `get_client_config_dir()`** to `src/config/paths.py` for resolving client IDE config directories with env var overrides

## Consequences

### Positive

- Single entry point (`/import`) for all import/export operations
- Full visibility into client-native skills across all 3 clients from the dashboard
- Promote workflow enables cross-client skill sharing via Augur
- Net code reduction: 2,047 insertions vs 3,320 deletions

### Negative

- `/dev-import` slash command no longer exists (breaking change, no redirect)
- Old skill directories removed — any external references break

### Neutral

- Existing `install-skill`, `list-installed`, `uninstall-skill` MCP tools preserved unchanged
- Dashboard pages (Install, Registry, Catalog) preserved with updated routes

## Alternatives Considered

### Alternative 1: Keep import and export as separate skills

Rejected: Creates artificial separation since import and export are inverse operations on the same plugin system.

### Alternative 2: Add cross-client skill syncing (client A → client B without Augur)

Rejected: Too complex for first iteration. Promote-to-Augur covers the main use case.

## References

- Spec: `docs/superpowers/specs/2026-03-12-skill-import-export-observability-design.md`
- Plan: `docs/superpowers/plans/2026-03-12-skill-import-export-observability.md`

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "plugins/admin/skills/install/"
      to: "plugins/admin/skills/import/"
      scope: "plugins/admin/skills/{install,import}/**"
    - from: "/api/admin/install/"
      to: "/api/admin/import/"
      scope: "plugins/admin/skills/import/augur/**/*.ts"
  apis_changed:
    - function: get_client_config_dir
      module: src.config.paths
      breaking: false
  patterns_deprecated:
    - grep: "plugins/admin/skills/dev-import"
      replacement: "plugins/admin/skills/import (data-folder mode)"
    - grep: "plugins/admin/skills/notion-import"
      replacement: "plugins/admin/skills/import (notion mode)"
    - grep: "plugins/admin/skills/ops-install"
      replacement: "plugins/admin/skills/import (package mode)"
    - grep: "plugins/dev/skills/ops-pkg"
      replacement: "plugins/admin/skills/import (export mode)"
  files_affected:
    - glob: "plugins/admin/skills/import/**"
    - glob: "plugins/ai/skills/dev-sync/**"
    - glob: "src/config/paths.py"
```

## Testing

### Unit Tests

1. **Mode detection** (`test_modes.py`): URL→package, local dir→data-folder/notion, client path→skill-promote, "export"→export, ZIP→notion, unknown→None
2. **Promote pipeline** (`test_promote.py`): copies SKILL.md, generates augur.yaml, aborts on collision, aborts on missing SKILL.md, aborts on invalid bundle
3. **Client paths** (`test_paths_client.py`): default dirs for all 3 clients, env var override, project scope, unknown client raises ValueError
4. **Client discovery** (`test_client_discovery.py`): discovers native skills, excludes symlinked Augur skills, correct metadata shape, handles missing dirs
5. **Sync status** (`test_sync_status.py`): returns per-client status, reports missing client dir
6. **MCP tools** (`test_install_mcp.py`): dry run, install, list, uninstall, cleanup — 14 tests covering all 7 MCP tools
7. **Notion pipeline** (`test_ingest.py`, `test_classifier.py`, `test_parser.py`, `test_transformer.py`, `test_format_registry.py`): full notion import pipeline tests

### Integration Tests

8. **End-to-end promote flow**: promote a mock client skill → verify it appears in plugins tree with SKILL.md and augur.yaml
9. **Mode detection → delegation**: detect_mode returns correct mode → corresponding run_* function is callable
