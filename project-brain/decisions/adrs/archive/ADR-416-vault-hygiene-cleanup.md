---
status: Implemented
date: 2026-03-15
deciders:
  - Gur Sannikov
related:
  - ADR-270
  - ADR-415
  - ADR-413
hub: null
tags:
  - vault
  - data-separation
  - hygiene
  - sync
superseded_by: null
---

# ADR-416: Vault Hygiene Cleanup — Separate Runtime, Config, and User Data

## Context

A vault-wide scan for Apple sync readiness revealed 3 structural bugs affecting every skill's vault data. These bugs make automated sync unreliable — the sync engine cannot distinguish user data (sync-worthy) from generated reports, config files, and duplicate folders.

### Bug 1: Duplicate folders (20 instances)

Same folder name appears at multiple levels, causing ambiguity for MCP tools and sync:

| Vault Path | Issue |
|---|---|
| `career/career/companies` | Exists both at `career/career/companies/` (1 file) and `career/career/job-analyzer/companies/` (54 files) |
| `career/career/profile` | Exists both at `career/career/profile/` (3 files) and `career/career/job-analyzer/profile/` (6 files) |
| `career/career/reports` | At `career/career/` and `career/career/job-analyzer/reports/` |
| `admin/channels/reviews/reviews` | Nested duplicate — `reviews/reviews/` |
| `dev/mcp-app-factory/mcp-app-factory` | Nested self-duplicate |
| 15 more across health, lifestyle, consulting, dev, professional |

### Bug 2: Config files mixed with user data (8 instances)

Config YAML files sit alongside user `.md` files in the same directory. Any tool globbing `*.yaml` or `*` gets config mixed with data:

| File | Problem |
|---|---|
| `career/career/job-analyzer/jobs/config.yaml` | Config alongside 186 job `.md` files |
| `observability/daemon/inbox/config.yaml` | Config alongside notification items |
| `observability/daemon/insights/config.yaml` | Config alongside insight items |
| `observability/daemon/notifications/config.yaml` | Config alongside notification items |
| `productivity/organizer/platform/config.yaml` | Config alongside organizer data |
| `dev/devops/setup/config.yaml` | Config alongside setup data |
| `professional/venture-augur/brand/config.yaml` | Config alongside brand data |
| `productivity/organizer/platform/list-manager/config.yaml` | Nested config |

### Bug 3: Runtime/generated data in user vault (92 instances, 870+ files)

Auto-generated data lives in `~/Vault/Augur/` (user data per ADR-270) instead of `~/Library/Application Support/Augur/state/` (runtime state) or `~/Library/Logs/Augur/` (logs):

| Pattern | Count | Should Be |
|---|---|---|
| `hardening-reports/` | Every skill (40+ dirs, 870+ files) | `~/Library/Application Support/Augur/state/hardening/` |
| `mcp-hygiene-*.md` | In hardening-reports across all skills | Runtime state |
| `audit-*.md` | In channels/reviews | Runtime logs |
| `scan-*.md` | In advisor/analytics | Runtime state |
| `complexity-reports/` | In advisor | Runtime state |

This violates ADR-270's data separation rule: user-editable content in vault, runtime state in platform directories.

## Decision

### 1. Move `hardening-reports/` to runtime state directory

All `hardening-reports/` directories move from vault to `~/Library/Application Support/Augur/state/hardening/{hub}/{skill}/`. The daemon writes there instead of the vault.

**Migration**: A script scans all vault skills for `hardening-reports/`, moves contents to the state directory, and removes the empty vault directories.

**Daemon update**: All hardening report writers (`auto-code-review`, `auto-plugin-lint`, `mcp-hygiene`, etc.) updated to use `get_runtime_dir() / "hardening"` instead of `get_skill_vault_dir() / "hardening-reports"`.

### 2. Move config files to a `_config/` subdirectory

Config files that sit alongside user data move into a `_config/` subdirectory (underscore prefix = machine-managed, not user data):

```
Before: career/career/job-analyzer/jobs/config.yaml  (alongside 186 .md files)
After:  career/career/job-analyzer/jobs/_config/config.yaml
```

Any tool globbing `*.md` in a data directory naturally excludes `_config/`. MCP tools updated to read config from `_config/config.yaml`.

### 3. Deduplicate folders

For each duplicate, determine the canonical location and merge:

| Duplicate | Resolution |
|---|---|
| `career/companies` vs `job-analyzer/companies` | Keep `job-analyzer/companies/` (54 files), delete empty root `companies/` |
| `career/profile` vs `job-analyzer/profile` | Keep both — different purposes (career profile vs job profile) but rename root to `career-profile/` |
| `channels/reviews/reviews` | Flatten to `channels/reviews/` |
| `mcp-app-factory/mcp-app-factory` | Flatten to `mcp-app-factory/` |
| Others | Case-by-case: merge if same data, rename if different purposes |

### 4. Vault directory conventions (new rule)

| Directory | Purpose | Sync-eligible |
|---|---|---|
| `tasks/`, `notes/`, `items/`, etc. | User data (`.md` files) | Yes |
| `_config/` | Machine config for this skill | No |
| `_cache/` | Generated indexes, caches | No |
| `prompts/` | AI prompt templates | No |
| `actions/` | Action definitions | No |

**Rule**: directories starting with `_` are machine-managed and excluded from sync. User data directories contain only `.md` files with frontmatter.

## Consequences

### Positive

- **Sync-safe vault**: sync engine can glob `*/` directories and trust everything is user data
- **ADR-270 compliant**: runtime state out of user vault
- **No duplicates**: every piece of data has one canonical location
- **Clean separation**: `_config/` convention makes config discoverable but not syncable

### Negative

- **Daemon update required**: all hardening report writers need path changes
- **One-time migration**: move ~870 files from vault to state directory
- **MCP tool updates**: config reading paths change for 8 tools

### Neutral

- Vault size decreases significantly (870+ generated files removed)
- Hardening reports still accessible via state directory path resolution

## Alternatives Considered

### Alternative 1: Add sync exclusion patterns

Add `exclude_patterns: ["hardening-reports", "config.yaml"]` to the sync engine. Rejected because it treats the symptom (sync picks up wrong files) not the root cause (wrong files in wrong location).

### Alternative 2: Use `.syncignore` file per skill

Like `.gitignore` but for sync. Rejected because every skill would need one, and the real fix is putting files in the right place per ADR-270.

## References

- ADR-270: External vault data separation
- ADR-415: Seed data format migration (discovered these bugs)
- CLAUDE.md Rule 4: Data separation

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - "~/Vault/Augur/*/hardening-reports/ → ~/Library/Application Support/Augur/state/hardening/"
    - "*/config.yaml (in data dirs) → */_config/config.yaml"
  apis_changed:
    - "Hardening report write path: get_skill_vault_dir → get_runtime_dir/hardening"
    - "Config read path in data dirs: config.yaml → _config/config.yaml"
  patterns_deprecated:
    - "Writing hardening-reports/ to vault"
    - "Placing config.yaml alongside user .md files"
  files_affected:
    - "~/Vault/Augur/*/*/hardening-reports/**"
    - "plugins/*/skills/*/scripts/**  (hardening report writers)"
    - "plugins/adaptive/skills/*/scripts/**  (auto-command reporters)"
```

## Testing

- Verify zero `hardening-reports/` directories remain in vault after migration
- Verify all hardening reports accessible at new state directory path
- Verify zero `config.yaml` files sit alongside `.md` user data files
- Verify zero nested duplicate folder names (e.g., `reviews/reviews/`)
- Verify daemon writes new hardening reports to state directory
- Verify MCP tools read config from `_config/` subdirectory
- Verify sync engine skips `_` prefixed directories

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-416-vault-hygiene`

### Phase 1: Move hardening-reports to state directory
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | backend | low | Write migration script: scan vault for hardening-reports/, move to state dir | `scripts/migrate_hardening_reports.py` |
| 1.2 | backend | low | Run migration script on vault | `~/Vault/Augur/` |
| 1.3 | backend | medium | Update all hardening report writers to use state dir path | `plugins/*/skills/*/scripts/` |

### Phase 2: Move config files to _config/
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | backend | low | Write script to move config.yaml into _config/ subdirs | `scripts/migrate_vault_config.py` |
| 2.2 | backend | low | Run on vault | `~/Vault/Augur/` |
| 2.3 | backend | medium | Update MCP tools that read config from data directories | `plugins/*/skills/*/scripts/mcp/` |

### Phase 3: Deduplicate folders
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | backend | medium | Analyze each duplicate, determine canonical location, merge/rename | `~/Vault/Augur/` |
| 3.2 | backend | low | Run deduplication | `~/Vault/Augur/` |

### Phase 4: Tests and validation
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | tester | medium | Write vault hygiene test suite | `tests/nightly/test_vault_hygiene_adr416.py` |
| 4.2 | tester | low | Run full test suite to verify no regressions | all tests |

### Completion Criteria
- [ ] Zero hardening-reports/ directories in vault
- [ ] Zero config.yaml alongside user .md files in data directories
- [ ] Zero nested duplicate folders
- [ ] All hardening reports accessible at state directory
- [ ] Daemon writes to state directory
- [ ] Sync engine skips _-prefixed directories
- [ ] All existing tests pass
