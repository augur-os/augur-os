---
status: Implemented
date: '2026-01-21'
deciders:
- Core Team
related: []
hub: null
tags:
- monorepo
- migration
superseded_by: null
---

# ADR-016: Monorepo Migration

## Context

The Augur project was historically split across two separate Git repositories:

- **augur** (code repo): Core framework, src/lib components, build scripts, dashboard
- **augur-data** (data repo): User data, plugins, configuration, skills

This separation was established in [ADR-002 Data Separation](ADR-002-data-separation.md) to keep user data isolated from code. However, this approach introduced significant friction:

1. **Sync complexity**: Atomic changes across both repos required careful choreography
2. **Path resolution**: Two separate root paths complicated imports and symlinks
3. **Plugin development**: Skills needed files in both repos, breaking portability
4. **Build pipeline**: CI/CD had to coordinate two repos with different lifecycles
5. **Developer experience**: New contributors faced a steeper learning curve

## Decision

Consolidate both repositories into a single monorepo using the `.github/scripts/migrate_to_monorepo.py` script.

### Migration Mapping

| Source (data repo)       | Destination (code repo)   | Category |
|-------------------------|---------------------------|----------|
| `core-data/`            | `data/core/`              | data     |
| `services-data/`        | `data/services/`          | data     |
| `apps-data/`            | `plugins/`              | data     |
| `plugins/consulting/`         | `plugins/consulting/`           | plugins  |
| `plugins/orchestration/`         | `plugins/orchestration/`           | plugins  |
| `plugins/ai/`     | `plugins/ai/`       | plugins  |
| `config/`               | `config-data/`            | config   |
| `operations/`           | `operations-data/`        | data     |
| `cache/`                | `runtime/cache/`          | runtime  |
| `.agent/`               | `.agent-data/`            | data     |

### New Directory Structure

```
augur/                        # SINGLE MONOREPO
├── src/                       # Framework code (unchanged)
│   ├── dashboard/
│   ├── config/
│   ├── mcp/
│   └── scripts/
│
├── plugins/                      # All plugins consolidated
│   ├── core/
│   ├── services/
│   └── apps/
│
├── data/                         # All user data
│   ├── core/
│   ├── services/
│   └── apps/
│
├── config-data/                  # User configuration
│   └── paths.yaml
│
├── operations-data/              # Operational data
│
└── runtime/                      # Gitignored runtime files
    └── cache/
```

### Migration Script Capabilities

The migration script (`migrate_to_monorepo.py`) provides:

- **`--check`**: Dry run showing what changes would occur
- **`--migrate`**: Performs the actual migration with backup
- **`--rollback`**: Reverts to previous 2-repo state
- **`--status`**: Shows current migration status
- **`--force`**: Skips prerequisite checks

### Backup Strategy

Before migration, the script:
1. Creates a timestamped backup in `~/.augur-backup/`
2. Saves the current `paths.yaml` configuration
3. Records migration state for potential rollback

### Updated Configuration

The `paths.yaml` is updated to reflect monorepo paths:

```yaml
version: 1
paths:
  core: /path/to/augur
  data: /path/to/augur/data
  plugins: /path/to/augur/plugins
  runtime: /path/to/augur/runtime
  config: /path/to/augur/config-data
```

## Consequences

### Positive

- **Atomic commits**: Changes spanning code and data are now a single commit
- **Simplified paths**: Single root for all path resolution
- **Easier onboarding**: One repo to clone, configure, and understand
- **Better CI/CD**: Single pipeline, simpler testing and deployment
- **Plugin portability**: Copy a plugin folder and everything works

### Negative

- **Larger repository**: Combined size may exceed previous code repo
- **Migration effort**: One-time cost to migrate existing setups
- **Git history**: Data repo history not preserved (separate archive)
- **Access control**: Can't restrict access to just code or just data

### Neutral

- **Gitignore complexity**: More patterns needed to exclude runtime/cache
- **Backup strategy**: Must exclude `runtime/` from backups to avoid bloat

## Alternatives Considered

### Alternative 1: Git Submodules

Use git submodules to link data repo into code repo.

**Rejected because**:
- Submodules add complexity for contributors
- Still requires coordinating two repos
- Detached HEAD issues confuse developers

### Alternative 2: Symlinks Only

Keep two repos but use extensive symlinking.

**Rejected because**:
- Fragile across different OS/shell environments
- Doesn't solve atomic commit problem
- Adds hidden dependencies that break when repos diverge

### Alternative 3: Keep Separate Repos

Maintain the status quo with improved sync tooling.

**Rejected because**:
- Fundamental friction cannot be eliminated
- Every new feature adds to sync complexity
- Developer experience remains suboptimal

## References

- migrate_to_monorepo.py - Migration script
- [ADR-002 Data Separation](ADR-002-data-separation.md) - Original decision (superseded)
- ADR-015 Three-Tier Plugin Architecture - Plugin structure context
