---
status: Implemented
date: 2026-03-13
deciders:
  - Gur Sannikov
related:
  - ADR-270
  - ADR-163
hub: null
tags:
  - blocks
  - mcp
  - seed-data
  - testing
superseded_by: null
---

# ADR-413: MCP Seed Data System

## Context

Dashboard blocks show empty or error states when no user data exists. The block rendering pipeline is: `BlockRenderer` → block type component → `useBlockData` hook → `/api/blocks/data` MCP proxy → MCP tool → `get_skill_data_dir()` → vault. When the vault is empty for a skill, MCP tools return empty results or errors, and blocks render blank.

136 blocks reference 103 unique MCP tools. Of those, 57 are core/runtime tools (Apple APIs, filesystem scanners, system health) that inherently return live data. The remaining 46 are data-bearing tools that read from the user vault and need seed data as fallback.

Prior state: 20 skills had seed data in `augur/lib/seed/`, but the auto-seed-data mechanism scanned `augur/seed/` (path mismatch). Many skills listed as "having seeds" only had prompt templates in `assets/seed-data/prompts/`, not actual data YAML. No MCP tools used `SkillDataStore` (all used `get_skill_data_dir()` directly), so the `SkillDataStore._resolve_read_path()` fallback never fired.

Additionally, 2 MCP tools (`manage-cli-agents`, `manage-tools-catalog`) had broken path resolution — resolving to `scripts/config/` instead of `augur/config/`.

## Decision

### 1. Canonical seed location: `assets/seed-data/`

All seed data files live at `plugins/{bundle}/skills/{skill}/assets/seed-data/`. The `augur/` folder is reserved for items that cannot be solved in the SKILL.md spec. Seeds are data templates — they belong in `assets/`.

Migrated all 20 pre-existing seeds from `augur/lib/seed/` to `assets/seed-data/`.

### 2. Seed file format

```yaml
_seeded: true
schema_version: 1
items:
  - id: "seed-001"
    title: "Example item"
    created_at: "2026-01-01T00:00:00Z"
```

Rules:
- `_seeded: true` marker on all seed files (UI can distinguish seed vs real data)
- Match the exact schema the MCP tool expects to read
- Realistic but clearly sample data
- Minimal — 2-5 entities per collection
- `_seed.yaml` manifest lists files for auto-seed-data to copy to vault

### 3. Auto-seed-data scanner updated

`auto-seed-data` now scans both `augur/seed/` (legacy) and `assets/seed-data/` (canonical) for seed directories.

### 4. Nightly regression test

`tests/nightly/test_block_mcp_seeds.py` — 9 tests across 4 classes:

- **TestBlockMcpToolDiscovery**: 100+ blocks exist, all use mcp_tool
- **TestMcpToolRegistration**: all block tools declared in augur.yaml mcp.tools[]
- **TestSeedDataCoverage**: all data-bearing tools have seed files, manifests valid, files parseable, manifest references exist
- **TestBlockApiRouteGuard**: no blocks use deprecated api_route pattern

### 5. Tool classification

103 tools classified into:
- **57 CORE_TOOL**: runtime/system tools (Apple APIs, Google APIs, filesystem scanners, daemon status, etc.) — no seeds needed
- **46 data-bearing**: read from user vault — all now have seeds in `assets/seed-data/`

### 6. Broken path fixes

`ai_bridge` MCP tool paths fixed: `_CATALOG_FILE` and `_CLI_AGENTS_FILE` now resolve via `Path(__file__).resolve().parents[2] / "augur" / "config"` instead of the incorrect `parent.parent / "config"`.

## Consequences

### Positive

- New users see populated blocks instead of empty/error states
- Every data-bearing MCP tool has seed data — no gaps
- Nightly test catches regressions when new blocks are added without seeds
- `api_route` guard prevents reintroduction of the deprecated dual-data pattern
- Seeds live in `assets/seed-data/` — `augur/` folder stays minimal

### Negative

- Seed data must be maintained when MCP tool schemas change
- 33 skills now have `assets/seed-data/` directories adding to repo size

### Neutral

- Auto-seed-data copies seeds to vault on first run — tools still read from vault, not directly from `assets/seed-data/`
- `SkillDataStore._resolve_read_path()` fallback to `assets/seed-data/` exists but is unused (no tools use SkillDataStore)

## Alternatives Considered

### Alternative B: Seed at block proxy layer

Intercept empty responses in `/api/blocks/data` and return hardcoded fallback per block type. Rejected: couples seed data to the dashboard, not the skill. Skills own their data schema.

### Alternative C: Seed at dashboard component layer

Each block component ships its own placeholder data. Rejected: duplicates schema knowledge across TypeScript and Python, breaks when tool schemas change.

## References

- Design spec: `docs/superpowers/specs/2026-03-13-mcp-seed-data-system-design.md`
- ADR-270: User vault separation (vault outside repo)
- ADR-163: Plugin decentralization

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "plugins/*/skills/*/augur/lib/seed/"
      to: "plugins/*/skills/*/assets/seed-data/"
  apis_changed: []
  patterns_deprecated:
    - "augur/lib/seed/ for seed data storage"
    - "api_route in block data_source declarations"
  files_affected:
    - "plugins/*/skills/*/assets/seed-data/**"
    - "plugins/adaptive/skills/auto-seed-data/scripts/seed_data_ops.py"
    - "tests/nightly/test_block_mcp_seeds.py"
    - "plugins/ai/skills/ai_bridge/scripts/mcp/__init__.py"
```

## Testing

- `pytest tests/nightly/test_block_mcp_seeds.py` — 9 tests, all pass
- Seed file parsing validation (YAML/JSON)
- Manifest reference integrity (all listed files exist)
- Block tool registration completeness
- api_route regression guard
