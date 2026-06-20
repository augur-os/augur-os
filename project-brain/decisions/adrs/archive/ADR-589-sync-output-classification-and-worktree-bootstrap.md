---
status: Implemented
date: 2026-04-16
deciders:
  - Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-589: Sync Output Classification and Worktree Bootstrap

## Context

`python -m skills.ai.scripts.sync_agents sync all` produces a mix of repo-local client export files, repo-local generated directories, machine-global client config edits, and client-owned state (history, sessions, cache). The current git posture is inconsistent: some sync outputs are intentionally tracked, some are ignored, and many repo-local managed outputs are neither tracked nor ignored.

This creates three concrete problems: fresh worktrees do not reliably contain the local sync outputs they need, `git status` can show surprise untracked sync outputs with no clear policy, and the repo does not clearly distinguish canonical generated artifacts from local bootstrap artifacts and client state.

## Decision

Classify every sync-managed path into exactly one explicit policy bucket, ignore the bootstrap outputs in `.gitignore`, and make worktree bootstrap regenerate them automatically:

**Policy buckets:**
- `tracked-generated` — deterministic, reviewable, intentionally versioned generated artifacts (kept minimal; e.g. `.claude/mcp.json.example`, repo-owned templates).
- `ignored-bootstrap` — repo-local client outputs that `sync all` regenerates (`CLAUDE.md`, `CODEX.md`, `AGENTS.md`, `.claude/agents/`, `.claude/commands/`, `.cursor/agents/`, `.cursor/mcp.json`, `.gemini/skills/`, `.gemini/settings.json`, `.codex/agents/`, `.codex/prompts/`, `.codex/skills/`, `.opencode/skills/`, `plugins/augur/`, `.agents/plugins/marketplace.json`, `build/cowork/`, `build/codex/`, etc.). Required in worktrees but never committed.
- `ignored-state` — every adapter `get_state_files()` path: history, sessions, cache, transcripts, runtime memory, workspace storage. Always untracked, never bootstrap inputs.

**Enforcement:**
- `.gitignore` is the policy layer for `ignored-bootstrap`. A new section explicitly covers each path so the "untracked but not ignored" middle state disappears.
- `scripts/worktree_preflight.py` is the bootstrap layer. A new `_ensure_sync_outputs(project_root, repairs, incidents)` helper runs `python3 -m skills.ai.scripts.sync_agents sync all` against the worktree root during repair, idempotent and safe to run repeatedly, scoped to worktree branches only (main checkout untouched).
- Sync bootstrap failures surface as incidents (`worktree/bootstrap/missing-sync-outputs`, severity `high`) instead of silently leaving a partially prepared worktree.
- A regression test (`tests/scripts/test_sync_output_policy.py`) walks every adapter's `get_managed_files()` and asserts each repo-local path is explicitly classified by `git check-ignore`.

## Consequences

### Positive
- Fresh worktrees can be created without manually running `sync all`
- `git status` no longer surfaces surprise sync-managed untracked files in a bootstrapped worktree
- Deleting local sync outputs and re-running worktree bootstrap restores them
- Client state files are never treated as tracked artifacts or bootstrap inputs

### Negative
- Worktree bootstrap pays the cost of running full `sync all` (deferred optimization: a narrower bootstrap-only mode could come later)
- New ignore section in `.gitignore` requires care to keep tracked exceptions like `!.cursor/rules/augur.mdc` intact

### Neutral
- `sync all --purge` and `--purge-state` semantics are unchanged
- Global client config edit locations are unchanged
- Adapter ownership boundaries unchanged beyond classification

## Alternatives Considered

### Alternative 1: Track all repo-local sync outputs
Rejected: would mix live client exports with source-of-truth files and create commit noise on every sync.

### Alternative 2: Custom narrower bootstrap mode now
Rejected for v1 in favor of correctness via full `sync all`. Optimization deferred until startup cost becomes a measured problem.

### Alternative 3: Run bootstrap on main checkout too
Rejected: would auto-regenerate repo-local client exports on unrelated shell/mcp profiles, scope held to worktrees.

## References
- Plan: docs/superpowers/plans/2026-04-16-sync-output-classification-and-worktree-bootstrap.md
- Spec: docs/superpowers/specs/2026-04-16-sync-output-classification-and-worktree-bootstrap-design.md
