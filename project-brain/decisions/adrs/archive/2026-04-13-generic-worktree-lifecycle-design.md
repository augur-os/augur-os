# Generic Worktree Lifecycle Design

**Date:** 2026-04-13  
**Status:** Proposed  
**Scope:** generic worktree creation/launch, auto-generated branch naming, and `/dev-merge` terminal cleanup

## Goal

Make Augur worktree infrastructure client-neutral.

Starting a new AI session from this repo should create a fresh isolated worktree and branch from the target branch, not inherit whatever branch the main checkout happens to be on. The infrastructure layer should not assume Claude, Codex, Gemini, or any other client.

The same lifecycle must also terminate cleanly: once `/dev-merge` has safely merged verified repo work into the target branch, it should remove the temporary branch and worktree instead of leaving leftovers behind.

## Problem

The current setup is split across two mismatched surfaces:

1. `scripts/worktree-launch.sh` is infrastructure by name, but its shell mode is Claude-specific.
2. User launch aliases can bypass worktree creation entirely and start the client in the root checkout.
3. `/dev-merge` already documents a no-leftovers contract, but cleanup is not anchored to one shared worktree lifecycle entry point.

This creates three concrete failures:

- starting Codex from the repo root inherits the current branch instead of creating a new one from `main`
- the launcher contract encodes task names like `implement-adr` and `harden` instead of generic worktree semantics
- merged worktrees and side branches can survive past successful merge unless the operator remembers to clean them manually

## Goals

- Make `scripts/worktree-launch.sh` generic and client-neutral.
- Generate a new worktree name and branch automatically when none is provided.
- Base new worktrees on the merge target branch instead of the current root checkout branch.
- Allow any AI client or shell command to be launched inside the new worktree through one generic passthrough interface.
- Keep ADR-101 worktree isolation behavior: registry allocation, marker file, bootstrap, and per-worktree MCP config generation.
- Make `/dev-merge` remove the merged worktree and branch after successful verification.

## Non-Goals

- Replacing the worktree registry or port-allocation model.
- Replacing `generate-worktree-mcp.py` in this slice. It is already multi-client even if the launcher around it is not.
- Preserving the old `implement-adr` / `harden` launcher interface for backward compatibility.
- Making worktree cleanup happen before merge verification is complete.

## Design Principles

1. Infrastructure verbs should describe worktree lifecycle, not one client’s workflow.
2. The current branch in the main checkout must never decide the base of a new worktree by accident.
3. Successful merge is the terminal point of a worktree unless safety checks fail.
4. Cleanup should be shared and deterministic, not reimplemented differently in multiple places.
5. Client-specific behavior belongs in shell aliases or caller commands, not in repo infrastructure scripts.

## Recommended Model

### 1. Generic launcher contract

`scripts/worktree-launch.sh` becomes a canonical worktree lifecycle tool with neutral verbs:

- `create`
- `list`
- `cleanup`

Canonical examples:

```bash
scripts/worktree-launch.sh create
scripts/worktree-launch.sh create --name ask-native-ux
scripts/worktree-launch.sh create --json
scripts/worktree-launch.sh create -- codex --dangerously-bypass-approvals-and-sandbox
scripts/worktree-launch.sh cleanup wt-20260413-154500
scripts/worktree-launch.sh list
```

If no explicit name is passed, `create` generates one automatically.

### 2. Auto-generated names

Default generated identifiers should be neutral and sortable:

- worktree name: `wt-YYYYMMDD-HHMMSS`
- branch name: same as worktree name unless explicitly overridden
- directory: sibling checkout `../augur-<worktree-name>`

Example:

- worktree name: `wt-20260413-154500`
- branch: `wt-20260413-154500`
- directory: `../augur-wt-20260413-154500`

This keeps branch naming generic and avoids encoding one client name into infrastructure.

### 3. Base branch resolution

New worktrees must branch from the merge target branch, not the current root checkout branch.

Resolution order:

1. explicit `--into <branch>` or `--base <ref>`
2. remote default branch from `refs/remotes/origin/HEAD`
3. local `main`

If none of those refs exist, creation should fail loudly instead of silently branching from the current checkout.

This is the critical behavior change that prevents Codex startup from inheriting a feature branch already checked out in the root repo.

### 4. Generic launch passthrough

Shell mode should no longer hardcode `claude`.

If arguments appear after `--`, the launcher should:

1. create or reuse the worktree
2. export `AUGUR_ROOT`, `AUGUR_CORE`, and `AUGUR_REPO` to the worktree path
3. `cd` into the worktree
4. `exec` the provided command

Examples:

```bash
scripts/worktree-launch.sh create -- codex --dangerously-bypass-approvals-and-sandbox
scripts/worktree-launch.sh create -- gemini --approval-mode yolo
scripts/worktree-launch.sh create -- zsh
```

If no command is provided, the script should print the created worktree path and exit successfully.

### 5. JSON/setup mode

The launcher still needs a machine-readable mode for agent automation, but it should be described generically.

Preferred canonical form:

```bash
scripts/worktree-launch.sh create --json
```

The JSON payload should continue to include:

- `worktree_path`
- `worktree_name`
- `branch`
- `main_repo`
- `dashboard_port`
- `mcp_port`
- exported env values

This preserves the existing automation affordance without carrying client-specific shell behavior.

### 6. Shared bootstrap remains

The launcher should keep the current ADR-101 isolation steps:

- git worktree creation
- registry registration and port allocation
- `.augur-worktree.yaml`
- worktree bootstrap/preflight
- per-worktree MCP config generation for supported clients

This design changes the interface and lifecycle orchestration, not the underlying isolation model.

### 7. `/dev-merge` becomes the terminal cleanup point

After `/dev-merge` completes a successful verified merge into the target branch, it should treat the originating worktree as disposable infrastructure and remove it.

Required successful path:

1. determine whether the current session is running in a worktree
2. complete the merge and any required verification
3. prove the target branch contains the intended result
4. remove the originating worktree
5. delete the originating branch
6. unregister the worktree and remove marker/launchd leftovers
7. report what was deleted

This applies to:

- normal `fast` merge from a clean worktree
- `full` mode merge after inspected dirty-state handling
- mixed leftover salvage after merge-worthy work has been proven present in the target

If verification or salvage proof fails, `/dev-merge` must escalate and leave the worktree intact for inspection.

### 8. Shared cleanup entry point

Cleanup logic should not live only inside merge prose.

`/dev-merge` should call one shared cleanup path, preferably through `scripts/worktree-launch.sh cleanup ...`, so that:

- branch deletion rules remain consistent
- registry unregistration remains consistent
- worktree removal fallback behavior remains consistent
- launchd/plist cleanup hooks remain attached to the same lifecycle event

The launcher owns lifecycle mechanics; `/dev-merge` owns when cleanup is allowed.

### 9. Client-neutral wording and comments

Repo-owned infrastructure text should stop naming one client unless the file is explicitly that client’s adapter.

This slice should update:

- `scripts/worktree-launch.sh` help text and comments
- `worktreeinclude` comments that currently mention Claude creation semantics
- `/dev-merge` command docs where needed so terminal cleanup is explicit and unconditional after successful verified merge

## User-Facing Outcome

After this change:

- starting Codex through the launcher opens a fresh worktree and branch automatically
- the root repo can stay on any branch without affecting the new worktree’s base
- the same launcher can open Codex, Claude, Gemini, or a plain shell
- a successful `/dev-merge` leaves no leftover branch or worktree behind

## Files To Change

### Primary

- `scripts/worktree-launch.sh`
  - replace task-specific Claude-first interface with generic lifecycle verbs
  - add automatic name generation
  - add generic `--` passthrough launch mode
  - resolve base branch explicitly from target branch

- `skills/platform-admin/commands/dev-merge.md`
  - make terminal cleanup explicit after successful verified merge
  - define shared cleanup handoff to the launcher lifecycle

- `docs/agent-topics/WORKFLOWS.md`
  - align `/dev-merge` workflow guidance with terminal cleanup
  - align worktree launcher examples with the new generic interface

- `worktreeinclude`
  - remove client-specific wording from comments

### Optional / out-of-repo consumer updates

- user shell aliases such as `xa`
  - should call the generic launcher and pass `codex` after `--`

## Failure Handling

### Worktree creation

Fail creation if:

- no valid base branch can be resolved
- git worktree creation fails
- registry allocation fails in a way that leaves the worktree unusable

Do not silently fall back to the current branch.

### Merge cleanup

Do not remove the worktree if:

- merge verification has not completed
- salvage cannot prove equivalence
- the target branch tip is not confirmed

In those cases `/dev-merge` should stop and report that cleanup was intentionally skipped for safety.

## Test Strategy

### Documentation / contract

- update existing `/dev-merge` contract tests to assert successful verified merges remove the branch/worktree
- add documentation assertions for the generic launcher wording if coverage exists for command docs

### Script behavior

- create mode generates a timestamped worktree name when no name is passed
- create mode resolves the base branch from target branch rules, not current checkout
- create mode launches an arbitrary command after `--`
- cleanup removes the worktree, unregisters it, and deletes the branch

### Manual verification

1. run the launcher from a root checkout currently on a feature branch
2. confirm the new worktree branch is based on `main` or the resolved target branch
3. launch Codex through the passthrough interface
4. merge back via `/dev-merge`
5. confirm the worktree directory and branch are gone afterward

## Open Questions Resolved In This Design

- Should infrastructure keep client-specific launch behavior?
  - No. Launch behavior becomes command passthrough.

- Should the old task-based launcher contract be preserved?
  - No. Canonical lifecycle verbs replace it.

- Should `/dev-merge` merely suggest cleanup after success?
  - No. Successful verified merge is the cleanup trigger.
