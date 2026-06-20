---
status: Implemented
date: 2026-03-19
deciders:
  - Gur Sannikov
related: []
tags: [vault, git, backup, recovery, health-checks]
---

# ADR-449: Vault Git Integration

## Context

The Augur vault (`~/Vault/Augur/`) stores skill data, memory, and config as text files. It has a git repo with a remote at `gsannikov/augur-vault`, but nothing automates commits, pushes, health checks, or recovery. Vault changes accumulate silently and are at risk of loss.

## Decision

Integrate git automation into the vault lifecycle with three layers: post-session local commits, nightly push to remote, and comprehensive health checks with recovery support.

Key design points:
- **Post-session commits**: Claude Code `Stop` hook runs `git add -u && git commit` on vault after every session (local only, cheap)
- **Nightly push**: `auto-repo-sync` learns about the vault repo, pushes at d3 in the nightly cycle; `dev-merge --push` also includes vault
- **7 health checks** in `auto-vault-hygiene`: orphan dirs, binary eviction, stale files, large file guard (>1MB), cross-reference validation, repo size monitoring, plugin alignment
- **Binary eviction**: non-text files are moved to `~/Documents/Augur/{plugin}/{skill}/` via `get_skill_documents_dir()` and the removal is committed immediately
- **Recovery**: `onboard --migrate` reads `config/system/vault.yaml` for remote URL and clones; `onboard --connect vault <url>` for linking existing vaults
- **Dashboard**: vault-status MCP tool provides git status, last sync time, push status, health score, repo size on the Command hub
- **Text-only policy**: `.gitignore` excludes `.DS_Store`, `__pycache__`, `_cache/`, `_config/`

## Consequences

### Positive

- Vault changes are automatically committed at session boundaries, creating granular undo points
- Nightly remote push protects against machine loss
- 7-category health checks catch drift before it becomes data loss
- Time travel via standard git log/diff/show on vault history

### Negative

- Post-session hook adds a few seconds to session teardown
- Binary eviction moves files to a separate directory, requiring users to know the Documents location
- `.git` directory growth needs monitoring (repo size check at >100MB)

### Neutral

- Single `main` branch -- no branching strategy needed for personal data
- Encryption at rest deferred to GitHub private repo access control
- Vault config stored in `config/system/vault.yaml` (tracked in project repo, survives machine loss)

## Alternatives Considered

### Alternative 1: Periodic Full Commits (No Session Hook)

Only commit on a schedule (e.g., hourly cron). Rejected because session-boundary commits provide more granular and meaningful history snapshots.

### Alternative 2: Minimal Health Checks (Structural Only)

Only check for orphan dirs and missing files. Rejected because binary eviction, cross-references, and repo size are critical for long-term vault health.

## References

- Design spec
