---
status: Implemented
date: 2026-04-13
deciders:
  - Gur Sannikov
related: []
hub: null
tags:
  - worktree
  - infrastructure
  - dev-merge
  - clients
superseded_by: null
---

# ADR-583: Generic Worktree Lifecycle

## Context

Augur worktree infrastructure was split across two mismatched surfaces. `scripts/worktree-launch.sh` was infrastructure by name but Claude-specific in its shell mode, with task-shaped verbs like `implement-adr` and `harden` baked into the launcher contract. User aliases (e.g. `xa`) sometimes bypassed worktree creation entirely and started AI clients in the root checkout, inheriting whatever feature branch was already checked out. `/dev-merge` already documented a no-leftovers contract, but post-merge cleanup was not anchored to one shared lifecycle entry point, so merged worktrees and side branches survived past successful merges unless the operator remembered to clean them manually.

These produced three concrete failures: starting Codex from the repo root inherited a feature branch instead of branching from `main`; the launcher contract encoded one client's task names rather than generic worktree semantics; and successful `/dev-merge` runs left leftover worktrees and branches behind.

ADR-101 worktree isolation mechanics (registry allocation, marker file, bootstrap, per-worktree MCP config generation) work correctly and should be preserved. The fix is in the launcher's interface and the merge command's terminal cleanup, not in the underlying isolation model.

## Decision

Make `scripts/worktree-launch.sh` a client-neutral worktree lifecycle tool with generic verbs, and align `/dev-merge` with automatic post-merge cleanup.

**Launcher contract:**

- Verbs: `create`, `list`, `cleanup`.
- Auto-generated names when `--name` is omitted: `wt-YYYYMMDD-HHMMSS` (worktree, branch, and `../augur-<name>` directory share the same identifier).
- Base branch resolution order: explicit `--into`/`--base`, then `refs/remotes/origin/HEAD`, then local `main`. Fail loudly if none resolve. Never silently branch from the current root checkout.
- Generic passthrough: arguments after `--` are `exec`'d inside the new worktree with `AUGUR_ROOT`/`AUGUR_CORE`/`AUGUR_REPO` exported to the worktree path. Examples: `create -- codex --dangerously-bypass-approvals-and-sandbox`, `create -- gemini --approval-mode yolo`, `create -- zsh`.
- Without arguments, `create` prints the worktree path and exits successfully (`--json` for machine-readable output).
- Comments and help text use generic wording ("AI client", "agent") instead of naming one client.

**`/dev-merge` terminal cleanup:** after a successful verified merge into the target branch, the originating worktree and branch are removed. The successful path is: detect worktree session → complete merge and verification → prove target branch contains intended result → remove worktree → delete branch → unregister registry entry → remove launchd/marker leftovers → report what was deleted. Cleanup is intentionally skipped only when verification or salvage proof fails. Cleanup logic delegates to `scripts/worktree-launch.sh cleanup ...` so branch deletion, registry unregistration, and worktree removal stay consistent.

**User alias update:** `xa` calls the generic launcher and passes `codex` after `--`.

## Consequences

### Positive
- New worktrees branch from the merge target consistently, never inheriting whatever the root checkout happens to be on.
- Any AI client (or plain shell) can be launched through one passthrough interface; infrastructure stops naming clients.
- Successful `/dev-merge` leaves no leftover branch or worktree; cleanup is deterministic, not an operator reminder.
- Single shared cleanup entry point keeps branch-deletion, registry, and launchd-cleanup rules consistent.
- ADR-101 isolation mechanics preserved unchanged.

### Negative
- Old task-named launcher invocations (`implement-adr`, `harden`) stop working; user-side aliases must be updated.
- Auto-generated timestamp names (`wt-20260413-154500`) are less semantically meaningful than task-named branches.
- If `origin/HEAD` is unset and `main` is missing, creation fails loudly rather than silently — the strictness can surprise operators on misconfigured remotes.

### Neutral
- `generate-worktree-mcp.py` already multi-client; this slice does not touch it.
- Per-worktree MCP config generation, port allocation, and `.augur-worktree.yaml` marker behavior unchanged.
- JSON/setup mode preserved for agent automation.

## Alternatives Considered

### Alternative 1: Keep client-specific launch behavior in the infrastructure script
Bake `claude` invocation into the launcher, add Codex/Gemini as parallel verbs. Rejected because every new client requires another launcher branch; passthrough generalizes once.

### Alternative 2: Preserve old task-based verbs alongside generic ones for backward compatibility
Ship `implement-adr` and `harden` as deprecated aliases. Rejected because compatibility shims violate the canonical-cleanup rule (CLAUDE.md rule 14) and the mental model stays muddy.

### Alternative 3: Make `/dev-merge` only suggest cleanup after success
Print a hint, leave the worktree intact. Rejected because operator-reminder cleanup is what the bug already was; successful verified merge is the right cleanup trigger.

### Alternative 4: Fall back to current checkout branch when target resolution fails
Silent fallback so creation always succeeds. Rejected — that is the original bug; loud failure is correct here.

## References
- Plan: docs/superpowers/plans/2026-04-13-generic-worktree-lifecycle.md
- Spec: docs/superpowers/specs/2026-04-13-generic-worktree-lifecycle-design.md
