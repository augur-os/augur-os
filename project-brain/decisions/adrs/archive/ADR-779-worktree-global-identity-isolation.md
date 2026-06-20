---
status: Implemented
date: 2026-05-24
deciders:
  - gsannikov
related: [778, 759]
hub: null
tags: [worktrees, cli, mcp, isolation, runtime, tooling]
superseded_by: null
spec_file: 2026-05-24-worktree-global-identity-isolation-design.md
plan_file: 2026-05-24-worktree-global-identity-isolation.md
---

# ADR-779: Worktree Global Identity Isolation

## Context

Parallel Augur sessions can run from multiple git worktrees at the same time.
Before this ADR, a worktree could run install or sync commands that rewrote
shared runtime identity to itself. Shared `.venv` editable installs, `.pth`
files, global `aug`, persistent MCP configs, and global client config could then
resolve to a stale or unrelated worktree.

ADR-778 fixed module identity isolation inside the Python test process. This ADR
protects the developer runtime so local shared identity cannot reintroduce stale
worktree packages or MCP launch roots.

## Decision

The main checkout is the installation authority for shared/global identity.
Worktree identity is process-local only.

Shared editable installs, `.pth` files, global CLI links, persistent MCP config,
and global client config must point to the main checkout. Worktree execution
uses explicit process overlays such as `AUGUR_PROJECT_ROOT`, `AUGUR_ROOT`, and
scoped `PYTHONPATH` only for that process or generated session-local config.

Global identity mutations are guarded by a shared filesystem lock. Worktree
global mutations are blocked unless the command is an explicitly allowed repair
or sync path that delegates to the main authority root.

## Consequences

- Parallel sessions can work from different worktrees without stealing `aug` or
  MCP runtime identity from each other.
- Persistent client config points to main, while session-local worktree config
  remains allowed.
- Drift becomes diagnosable by a single audit command.
- Repair rewrites shared identity to main and reports the changed surfaces.
- Commands that previously relied on a worktree mutating global install state
  must switch to process-local overlays.

## Status Notes

Implemented (2026-05-24). The implementation added a runtime identity layer,
global mutation lock, drift doctor, guarded persistent MCP/client config sync,
Codex launcher root ordering, staged/CI guardrails, and a two-worktree
regression test. Live audit after repair reported shared Augur identity rooted
at main with no editable install, `.pth`, import-spec, CLI, or persistent MCP
config drift.

## Acceptance Gate

- Unit tests prove authority-root detection, mutation guard behavior, lock
  serialization, overlay generation, and drift scanning.
- A two-worktree integration simulation proves concurrent install-like and
  sync-like operations cannot stamp shared identity with worktree paths.
- A live audit proves shared editable installs, `.pth`, import specs, global
  `aug`, and persistent MCP configs do not point at `augur-wt-*`.
- Persistent global client configs point to main after sync.
- Worktree-local MCP and CLI execution still runs worktree code through overlays.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "src.config.runtime_identity.resolve_runtime_identity"
    - "src.config.runtime_identity.GlobalMutationGuard"
    - "src.config.global_identity_drift.scan_global_identity_drift"
  patterns_deprecated:
    - "worktree process mutating shared editable installs"
    - "persistent global client config pointing at linked worktrees"
    - "Codex MCP launcher selecting cwd before explicit overlay/configured roots"
  files_affected:
    - src/config/runtime_identity.py
    - src/config/worktrees.py
    - src/config/global_identity_drift.py
    - scripts/check_global_identity_drift.py
    - scripts/configure_mcp.py
    - scripts/augur-codex-mcp
    - scripts/augur-codex-mcp.ps1
    - project-brain/capabilities/skills/ai/scripts/sync_agents/
    - .githooks/pre-commit
    - .github/workflows/ci-tests.yml
```
