# XA Main Or Worktree Launch Design

**Date:** 2026-04-13  
**Status:** Proposed  
**Scope:** interactive `xa` startup choice, main-checkout sync behavior, and worktree launch handoff

## Goal

Make the `xa` shortcut ask every time whether to start Codex in the main checkout or create a fresh branch/worktree, while keeping the main checkout aligned with `origin/main` automatically.

The main-checkout path must tolerate uncommitted changes. If local `main` is behind `origin/main`, `xa` should stash the working tree, fast-forward `main`, restore the edits, and then launch Codex. The worktree path should continue to use the existing generic worktree lifecycle tool.

## Problem

The current `xa` alias is a one-line shell alias:

```sh
alias xa="cd ~/Projects/Augur/ && scripts/worktree-launch.sh create -- codex --dangerously-bypass-approvals-and-sandbox"
```

That behavior is too rigid for normal day-to-day use:

- it always creates a new worktree even when the operator wants to continue in the main checkout
- it gives no startup choice at launch time
- it does not keep the main checkout synchronized with `origin/main`
- it cannot safely handle the common case where the main checkout has uncommitted local edits but also needs to fast-forward to the remote branch tip

## Goals

- Ask on every `xa` run whether to launch in `main` or a new worktree.
- Keep the main checkout on `main` synchronized with `origin/main` automatically before launch.
- Allow uncommitted changes in the main checkout during that sync.
- Reuse `scripts/worktree-launch.sh` unchanged for the worktree path.
- Move startup behavior out of `~/.zshrc` string logic into a repo-owned script that can be tested.

## Non-Goals

- Replacing the existing worktree lifecycle contract in `scripts/worktree-launch.sh`.
- Supporting additional startup targets beyond `main` and `new worktree`.
- Auto-merging or auto-rebasing local commits on `main`.
- Preserving the existing plain alias implementation in `~/.zshrc`.

## Design Principles

1. The launcher choice belongs in a dedicated entrypoint, not inside a brittle shell alias string.
2. The worktree lifecycle tool should stay focused on worktree mechanics, not root-checkout launch choices.
3. Dirty working trees are acceptable; stale `main` is not.
4. Automatic sync may fast-forward `main`, but it must not invent merge behavior for unpublished local commits.
5. Failures should stop with explicit instructions rather than silently launching from an unsynchronized repo state.

## Recommended Model

### 1. Replace the alias with a repo-owned launcher script

`xa` should call a new script such as `scripts/xa-launch.sh`:

```sh
alias xa="cd ~/Projects/Augur/ && scripts/xa-launch.sh"
```

That script becomes the single owner of interactive `xa` startup behavior.

### 2. Prompt every time

Each run should show a simple interactive choice:

- `main`
- `new worktree`

The script should keep prompting until it gets a valid answer or the operator cancels.

### 3. Main mode behavior

If the operator selects `main`, the script should:

1. `cd` into the main repo
2. verify the target branch is `main`
3. fetch `origin/main`
4. compare local `main` with `origin/main`
5. if local `main` is behind and the working tree is dirty, stash tracked and untracked changes
6. fast-forward local `main` to `origin/main`
7. re-apply the stash if one was created
8. launch Codex from the main repo

Launch command:

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

### 4. Sync rules in main mode

The sync policy should be strict and predictable:

- If local `main` is already equal to `origin/main`, launch immediately.
- If local `main` is behind `origin/main`, fast-forward automatically.
- If the worktree is dirty, auto-stash before fast-forward and restore afterward.
- If local `main` is ahead of `origin/main` or has diverged, stop and explain that automatic sync is only supported for pure fast-forward cases.

This keeps the main checkout current without turning `xa` into a branch-integration tool.

### 5. Stash handling

The temporary stash should include untracked files so the update path behaves correctly for normal local work.

Required behavior:

- create a named temporary stash only when needed
- restore it only if this launcher created it
- if stash re-apply conflicts, stop and report the conflict clearly
- never drop or overwrite user edits silently

### 6. Worktree mode behavior

If the operator selects `new worktree`, the launcher should delegate directly to the existing generic lifecycle script:

```bash
scripts/worktree-launch.sh create -- codex --dangerously-bypass-approvals-and-sandbox
```

No main-checkout sync logic should run in this branch. Worktree startup remains owned by `scripts/worktree-launch.sh`.

### 7. Failure handling

The launcher should fail loudly in these cases:

- `origin/main` cannot be fetched
- local checkout is not on `main` when `main` mode is selected
- local `main` is ahead of or diverged from `origin/main`
- fast-forward fails
- stash restoration fails or produces conflicts

In each case, the script should explain what happened and avoid launching Codex from an ambiguous repo state.

## User-Facing Outcome

After this change, `xa` becomes a deliberate startup chooser:

- pick `main` when continuing work in the root checkout
- pick `new worktree` when starting isolated work

The main repo no longer drifts behind `origin/main`, even when it contains uncommitted changes, and the worktree path remains the existing isolated flow.

## Files To Change

### Primary

- `scripts/xa-launch.sh`
  - add the interactive choice
  - implement main-checkout sync and stash/restore logic
  - launch Codex in the selected environment

- `~/.zshrc`
  - replace the current `xa` alias with the new launcher entrypoint

### Verification

- `tests/scripts/`
  - add focused tests for prompt parsing, main-mode gating, and worktree delegation

## Testing

Focused verification should cover:

- launcher prompt accepts valid choices and rejects invalid ones
- main mode launches immediately when local `main` equals `origin/main`
- main mode stashes, fast-forwards, and restores when local edits exist and local `main` is behind
- main mode stops when local `main` is ahead or diverged
- worktree mode delegates to `scripts/worktree-launch.sh create -- ...`

## Open Decisions Resolved In This Design

- Prompt each run: yes
- Main mode allows uncommitted changes: yes
- Main mode auto-syncs to `origin/main`: yes
- Dirty main mode sync uses stash/restore: yes
- Worktree mode stays separate from main mode: yes
