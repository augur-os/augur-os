# Sync Output Classification And Worktree Bootstrap Design

**Date:** 2026-04-16
**Status:** Proposed
**Owner:** Codex + user

## Goal

Make `sync all` outputs predictable by classifying every sync-managed path into an explicit git/worktree policy, then ensure worktrees automatically regenerate the local sync outputs they need without requiring manual `sync all`.

## Problem

`python -m skills.ai.scripts.sync_agents sync all` currently produces a mix of:

- repo-local client export files
- repo-local generated directories
- machine-global client config edits
- client-owned state such as history, sessions, and cache

The current git posture is inconsistent:

- some sync outputs are intentionally tracked
- some are ignored
- many repo-local managed outputs are neither tracked nor ignored

That creates three concrete problems:

1. Fresh worktrees do not reliably contain the local sync outputs they need.
2. `git status` can show surprise untracked sync outputs with no clear policy.
3. The repo does not clearly distinguish canonical generated artifacts from local bootstrap artifacts and client state.

## Design Principles

### 1. Required In A Worktree Does Not Mean Tracked In Git

If a file is necessary for a worktree to function, that means it must be reproducibly bootstrapped. It does not mean it belongs in version control.

### 2. Client State Is Never A Repo Artifact

History, sessions, cache, transcripts, workspace storage, and similar state remain local-only. They are never committed and are never used as bootstrap inputs.

### 3. Live Client Exports Are Local Bootstrap Artifacts By Default

Most files written into repo-local client folders are environment-facing outputs, not source-of-truth files. They should be regenerated from the canonical source files instead of committed.

### 4. The Tracked Generated Set Must Stay Small

Only deterministic, reviewable, intentionally versioned generated artifacts should stay tracked. This bucket should be minimal and explicit.

## Policy Model

All sync-managed paths must fall into exactly one of these buckets:

### `tracked-generated`

Deterministic repo artifacts that are intentionally versioned and safe to review in commits.

Examples:

- repo-owned generated templates
- example config files
- intentionally versioned generated docs/manifests that are part of the product contract

### `ignored-bootstrap`

Repo-local client outputs that `sync all` can regenerate and that a worktree may need locally, but that should not be committed.

Examples:

- repo-root instruction files for local clients
- repo-local mirrored agent directories
- repo-local client config outputs
- repo-local plugin assembly outputs

### `ignored-state`

Client-owned history, sessions, cache, runtime memory, workspace storage, and similar state. These are always untracked and never treated as worktree bootstrap artifacts.

## Concrete Path Classification

The following repo-local sync-managed outputs should be treated as `ignored-bootstrap`:

- `CLAUDE.md`
- `CODEX.md`
- `AGENTS.md`
- `.claude/mcp.json`
- `.claude/agents/`
- `.claude/commands/`
- `.clinerules/augur-rules.md`
- `.cursorrules`
- `.cursor/rules/`
- `.cursor/agents/`
- `.cursor/mcp.json`
- `.cursor/memory/`
- `.windsurfrules`
- `.windsurf/rules/`
- `.windsurf/skills/`
- `.windsurf/mcp.json`
- `.gemini/GEMINI.md`
- `.gemini/skills/`
- `.gemini/settings.json`
- `.gemini/unignore`
- `.gemini/workflows/`
- `.gemini/topics/`
- `.gemini/memory/`
- `.gemini/agents/`
- `.opencode/AGENTS.md`
- `.opencode/skills/`
- `.antigravity/`
- `.codex/config.toml`
- `.codex/agents/`
- `.codex/prompts/`
- `.codex/skills/`
- `plugins/augur/`
- `.agents/plugins/marketplace.json`
- `build/cowork/`
- `build/codex/`

The following categories should be treated as `ignored-state`:

- every adapter `get_state_files()` path
- client history/session/cache/transcript/runtime-memory locations
- client-owned plugin caches and workspace storage

The `tracked-generated` bucket should stay intentionally small and separate from live client exports. Examples include:

- `.claude/mcp.json.example`
- repo-owned templates
- intentionally versioned generated reference artifacts

This design deliberately does **not** move the live repo-local client install targets listed above into the tracked set.

## Worktree Bootstrap Contract

New or reused worktrees must automatically ensure that `ignored-bootstrap` sync outputs exist locally before active development starts.

### Integration Points

Bootstrap should be enforced in the existing worktree lifecycle:

- `scripts/worktree-launch.sh`
- `scripts/worktree_preflight.py`

### Required Behavior

During worktree bootstrap/repair:

- run a sync-agent bootstrap step against the worktree root
- regenerate repo-local local-development client exports
- do not purge anything
- do not touch client-owned history/cache/session state
- do not expand scope into destructive client reset behavior
- remain idempotent and safe to run repeatedly

### Initial Command

The first implementation should favor correctness over optimization and run:

```bash
python3 -m skills.ai.scripts.sync_agents sync all
```

If startup cost becomes a problem, Augur can later introduce a narrower dedicated bootstrap mode for local managed outputs only. That optimization is deferred.

## Git Policy Changes

`.gitignore` should explicitly cover the `ignored-bootstrap` outputs so the current `untracked but not ignored` middle state disappears.

Expected result:

- each sync-managed repo-local path is either intentionally tracked or intentionally ignored
- `git status` no longer surfaces surprise untracked sync outputs after bootstrap
- local client exports stop behaving like ad hoc repo files

## Failure Handling

If worktree bootstrap cannot regenerate required sync outputs:

- surface the failure as a bootstrap/preflight incident
- report the failing sync step clearly
- do not silently accept a partially prepared worktree

This keeps worktree readiness honest and debuggable.

## Success Criteria

The design is successful when all of the following are true:

1. A fresh worktree can be created without manually running `sync all`.
2. Required repo-local sync outputs exist after worktree bootstrap.
3. `git status` in a bootstrapped worktree does not show surprise sync-managed untracked files that should have been ignored.
4. Deleting local sync outputs and re-running worktree bootstrap restores them.
5. State/history/cache files are never treated as tracked artifacts or bootstrap outputs.

## Out Of Scope

- redefining the meaning of `sync all --purge`
- redefining the meaning of `sync all --purge-state`
- changing which global client config locations are edited by sync
- redesigning adapter ownership boundaries beyond classification and bootstrap policy

## Recommended Implementation Sequence

1. Audit all repo-local `get_managed_files()` paths and classify them as tracked-generated or ignored-bootstrap.
2. Update `.gitignore` so every ignored-bootstrap path is explicitly covered.
3. Extend worktree bootstrap/preflight to run `python3 -m skills.ai.scripts.sync_agents sync all` from the worktree root.
4. Add tests for git policy assumptions where practical and for worktree bootstrap invocation/failure reporting.
5. Verify behavior in a fresh worktree and with a manual delete-and-repair cycle.
