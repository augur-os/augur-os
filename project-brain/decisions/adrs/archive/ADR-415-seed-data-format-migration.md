---
status: Implemented
date: 2026-03-15
deciders:
  - Gur Sannikov
related:
  - ADR-413
  - ADR-270
  - ADR-163
  - ADR-404
hub: null
tags:
  - seed-data
  - vault
  - data-format
  - migration
  - notion-import
superseded_by: null
---

# ADR-415: Seed Data Format Migration — Individual .md Files

## Context

ADR-413 established seed data in `assets/seed-data/` using embedded YAML arrays:

```yaml
_seeded: true
tasks:
  - id: seed-001
    title: "Review quarterly goals"
    quadrant: do-first
```

Meanwhile, the Notion import and other data ingestion tools create individual markdown files with YAML frontmatter in subdirectories:

```
~/Vault/Augur/productivity/eisenhower/tasks/
├── notion-007de891.md    # frontmatter: {title, quadrant, due, ...}
├── notion-05a48689.md
└── ... (140 files)
```

This creates a **dual source of truth** in the vault:

1. `tasks.yaml` — 4 seed items in embedded YAML format (stale after import)
2. `tasks/*.md` — 140 real items in individual frontmatter format (canonical)

### The bug

During the Apple Reminders sync implementation, the sync bridge read `tasks.yaml` (4 items) and missed the 140 real tasks in `tasks/`. Any code that reads the YAML summary file gets stale seed data instead of the actual user data.

### Scope

19 skills use the embedded-YAML seed format with list data that could conflict with imported/user data:

| Skill | Seed File | Data Type |
|-------|-----------|-----------|
| eisenhower | tasks.yaml | Task items with quadrants |
| career | index.yaml | Interview prep projects |
| content | calendar.yaml | Content calendar entries |
| growth | goals.yaml | Growth goals |
| finance | transactions.yaml | Financial transactions |
| finance/wealth | portfolio.yaml | Portfolio entries |
| health | virtual-doctor.yaml | Health records |
| lifestyle | reading-list.yaml | Reading list items |
| reading-list | reading-list.yaml | Reading list items |
| client-ai-consulting | showcase.yaml, opportunities.yaml | Client work items |
| client-smb-design | danit-design.yaml | Design projects |
| home-automation | devices.yaml | Smart home devices |
| venture-augur | index.yaml | Venture index entries |
| channels | config.yaml | Channel config (structural) |
| import | registry.yaml | Import registry (structural) |
| scraper | sources.yaml | Scraper sources |

The remaining 5 are config-only seeds (not list data) and don't need migration.

## Decision

### 1. Seed data becomes individual .md files

Seeds use the same format as imported/user data: individual markdown files with YAML frontmatter, stored in the same directory structure they'll occupy in the vault.

**Before (ADR-413 format):**
```
plugins/productivity/skills/eisenhower/assets/seed-data/
├── _seed.yaml          # manifest
└── tasks.yaml          # embedded: {tasks: [{id: seed-001, ...}]}
```

**After (new format):**
```
plugins/productivity/skills/eisenhower/assets/seed-data/
├── _seed.yaml          # manifest (updated)
└── tasks/
    ├── seed-001.md     # frontmatter: {id, title, quadrant, ...}
    ├── seed-002.md
    ├── seed-003.md
    └── seed-004.md
```

Each seed file uses the same schema that MCP tools and imports produce:
```markdown
---
id: seed-001
title: "Review quarterly goals"
quadrant: do-first
completed: false
source: seed
created_at: "2026-01-01T00:00:00Z"
---
```

The `source: seed` field marks it as seed data (replaces the `_seeded: true` marker on the container file).

### 2. `_seed.yaml` manifest updated

```yaml
data_path: ""
directories:
  - tasks/
files: []
```

The manifest now references directories of files, not single YAML files with embedded arrays. The `auto-seed-data` scanner copies entire directories to the vault.

### 3. Vault YAML summary files become generated indexes

`tasks.yaml` in the vault becomes a **generated index** (not a source of truth), rebuilt on demand by scanning `tasks/*.md`:

```yaml
# AUTO-GENERATED — do not edit. Source: tasks/*.md
_generated: true
_generated_at: "2026-03-15T10:00:00Z"
count: 144
quadrant_counts:
  do-first: 43
  schedule: 55
  delegate: 9
  eliminate: 27
  inbox: 6
```

MCP tools read from `tasks/` directory. The summary YAML is only for quick counts in dashboard overview blocks.

### 4. MCP tool read path

MCP tools like `get-eisenhower-tasks` must read from the `tasks/` directory (globbing `.md` files), NOT from `tasks.yaml`. The `SkillDataStore` helper updated to:

1. Check for data directory first (`tasks/`)
2. Glob `.md` files with frontmatter
3. Fall back to single YAML file only if directory doesn't exist (backward compat during migration)

### 5. Migration script

A one-time migration script converts existing vault data:

For each affected skill:
1. Read `{data}.yaml` embedded array
2. Create `{data}/` directory
3. Write individual `.md` files from each array item
4. Replace `{data}.yaml` with generated index
5. Update `_seed.yaml` manifest

The migration is idempotent — if `{data}/` directory already exists (e.g., from Notion import), only the stale YAML file is replaced with the generated index.

### 6. `auto-seed-data` scanner updated

The scanner handles both formats during transition:
- New format: copy `tasks/` directory to vault
- Old format: still works (backward compat) but logs a warning suggesting migration

## Consequences

### Positive

- **Single source of truth**: seed data and user data in the same format, same directory
- **No stale files**: seeds become items 1-4 alongside imported items 5-144
- **Sync-safe**: any sync tool reads the directory and gets everything
- **Import-safe**: Notion import adds files to the same directory, no conflict
- **ADR-404 compliant**: all user-facing data files use markdown with YAML frontmatter

### Negative

- **One-time migration effort**: 19 skills need seed file conversion
- **`auto-seed-data` scanner**: needs update to handle directory-based seeds
- **MCP tools**: data-reading tools need update to glob `.md` files instead of loading single YAML

### Neutral

- Seed files are slightly more verbose (one file per item vs one array in YAML)
- `_seed.yaml` manifest format changes but stays in `assets/seed-data/`

## Alternatives Considered

### Alternative 1: Keep YAML format, add directory scan fallback

Have MCP tools check `tasks/` directory first, fall back to `tasks.yaml`. Rejected because it preserves the dual-source-of-truth problem — both files continue to exist and can diverge.

### Alternative 2: Convert imports to YAML format instead

Make the Notion import write to `tasks.yaml` instead of individual files. Rejected because individual `.md` files are better for git (per-item diffs), AI processing (each file fits in context), and ADR-404 compliance (markdown with frontmatter).

### Alternative 3: Delete seeds after first user data arrives

When a user imports or creates their first item, delete all seed files. Rejected because it's fragile (what counts as "first real data"?) and loses the seed data that might still be useful as examples.

## References

- ADR-413: MCP Seed Data System (established current seed format)
- ADR-270: External vault data separation
- ADR-404: Frontmatter format for user-facing files
- Memory: `feedback_vault_data_format.md` — the sync bug that triggered this ADR

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "SkillDataStore read path: now checks tasks/ directory before tasks.yaml"
  patterns_deprecated:
    - "Embedded YAML array seeds (tasks.yaml with items: [{...}])"
  files_affected:
    - "plugins/*/skills/*/assets/seed-data/*.yaml (19 skills)"
    - "~/Vault/Augur/*/tasks.yaml → ~/Vault/Augur/*/tasks/*.md"
```

## Testing

- Verify each migrated seed has matching `.md` files in `assets/seed-data/{data}/`
- Verify `_seed.yaml` manifests reference directories, not embedded YAML files
- Verify MCP tools read from `tasks/` directory, not `tasks.yaml`
- Verify `auto-seed-data` copies directory-based seeds to vault correctly
- Verify vault `tasks.yaml` is a generated index, not source of truth
- Verify Notion import and seed data coexist in same directory without conflict

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-415-seed-format-migration`

### Phase 1: Seed File Conversion
**Strategy**: PARALLEL (each skill is independent)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | converter | low | Convert eisenhower seed from YAML array to individual .md files | `plugins/productivity/skills/eisenhower/assets/seed-data/` |
| 1.2 | converter | low | Convert career seeds (index, profile, jobs) | `plugins/career/skills/*/assets/seed-data/` |
| 1.3 | converter | low | Convert finance seeds (transactions, accounts, portfolio) | `plugins/finance/skills/*/assets/seed-data/` |
| 1.4 | converter | low | Convert remaining skills (health, lifestyle, consulting, home, etc.) | `plugins/*/skills/*/assets/seed-data/` |

### Phase 2: MCP Tool Update
**Strategy**: PIPELINE (depends on Phase 1)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | backend | medium | Update SkillDataStore to check directory before YAML | `src/mcp/augur_mcp/infrastructure/` |
| 2.2 | backend | medium | Update get-eisenhower-tasks to glob tasks/*.md | `plugins/productivity/skills/eisenhower/scripts/mcp/` |
| 2.3 | backend | low | Update auto-seed-data scanner for directory-based seeds | `plugins/adaptive/skills/auto-seed-data/scripts/` |

### Phase 3: Vault Migration Script
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | backend | medium | Write vault migration script (YAML → .md files) | `plugins/adaptive/skills/auto-seed-data/scripts/migrate_seeds.py` |
| 3.2 | backend | low | Run migration on local vault, verify data integrity | `~/Vault/Augur/*/` |

### Phase 4: Tests
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | tester | medium | Update test_block_mcp_seeds.py for new seed format | `tests/nightly/test_block_mcp_seeds.py` |
| 4.2 | tester | low | Add migration idempotency test | `tests/` |

### Completion Criteria
- [ ] All 19 skills have .md-based seeds in assets/seed-data/{data}/
- [ ] All _seed.yaml manifests reference directories
- [ ] MCP tools read from data/ directories, not summary YAML
- [ ] auto-seed-data handles both formats (new + legacy fallback)
- [ ] Vault tasks.yaml replaced with generated index
- [ ] All existing tests pass
- [ ] npm run build passes
