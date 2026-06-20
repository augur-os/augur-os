---
status: Implemented
date: 2026-03-22
deciders:
  - Gur Sannikov
related: []
hub: command
tags:
  - vault
  - git
  - backup
  - auto-commit
superseded_by: null
---

# ADR-474: Vault Git Integration

## Context

The vault (`~/Vault/Augur/`) contains personal data (memory, skill configs, notes) but has no automated git backup. Changes can be lost if not manually committed and pushed. Binary files accumulate in the vault, bloating the git repo. There is no health monitoring for vault state.

## Decision

Automate vault git commits, pushes, health checks, binary eviction, and recovery:

1. **Config**: Add `config/system/vault.yaml` with remote URL and vault path
2. **Auto-commit hook**: Add a Claude Code `Stop` hook that auto-commits tracked vault changes with timestamped messages
3. **Repo sync extension**: Extend `auto-repo-sync` to scan vault for uncommitted/unpushed changes (d0=scan, d3=push)
4. **Vault hygiene expansion**: Add 7 health checks to `auto-vault-hygiene` -- binary detection, orphan dirs, stale files, large file guard, cross-references, plugin alignment, repo size monitoring
5. **Binary eviction**: At d2+, move binary files (`.m4a`, `.xlsx`, `.png`, etc.) from vault to `~/Documents/Augur/` and commit the removal
6. **MCP tool**: Add `vault-status` tool returning git state, sync status, repo size, and recent commits
7. **Onboard recovery**: Add vault clone/connect to the onboard flow for machine migration
8. **Dev-merge integration**: Include vault repo in the `--push` multi-repo cycle

## Consequences

### Positive
- Vault is always backed up with automated commits and pushes
- Binary files are evicted to Documents, keeping vault text-only and git-efficient
- Health monitoring catches orphan dirs, stale files, and repo bloat

### Negative
- Auto-commit on every session stop adds git history noise
- Binary eviction changes file locations, requiring consumers to update paths

### Neutral
- `.gitignore` policy: `.DS_Store`, `__pycache__`, `._*`, `_cache/`, `_config/`
- Vault recovery via onboard depends on GitHub auth being configured

## Alternatives Considered

### Alternative 1: Rsync-based backup instead of git
Use rsync to a remote destination. Rejected because git provides versioning, diffing, and conflict resolution that rsync lacks.

## References
- Plan: `docs/superpowers/plans/2026-03-19-vault-git-integration.md`
- Spec: `docs/superpowers/specs/2026-03-19-vault-git-integration-design.md`
