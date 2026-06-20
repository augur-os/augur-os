---
description: Debug dashboard, MCP, or repo issues with a mandatory visibility-first protocol and regression checks.
visibility: dev
x-augur-export-command: false
---

# /dev-debug

Use when debugging any issue in the dashboard, MCP, or codebase.

## Gotchas

### 1. The 6-phase protocol is mandatory
Skipping visibility or reproduction leads to fix loops. Even trivial bugs need direct observation before changes. For dashboard and MCP failures, also use the `patterns` pack.

### 2. Never declare a fix complete without regression checks
Run relevant tests, verify related pages in the browser, and confirm the build still passes before reporting success.

### 3. Repro scripts go in `_dev/`, not the project root
Temporary repro scripts in the root trigger the root-pollution checker and will block merge work.

### 4. Dashboard data verification is stricter than page-load verification
For dashboard bugs, a page that loads but shows empty placeholders, stale model errors, disabled primary actions, or contradictory Setup/Browse/Brain status is still broken. If the user names a localhost port, test that exact port first. Record the real URL, checkout owner, useful domain data seen, blocking overlays, and remaining empty/error/stale panels before reporting success.

## Worktree Isolation

All non-trivial debugging should happen in a git worktree. Use the `using-git-worktrees` skill before starting, and merge or discard the worktree when the bug is resolved.

## Worktree Repair Policy

Worktree debugging is diagnosis-first. A worktree target may collect logs,
console errors, screenshots, MCP debug state, and lifecycle state. It must not
repair main, navigate the main browser, or send IDE update prompts.

Use `--repair` to allow target-scoped repair of the current worktree instance.
Even with `--repair`, the operation may only restart or mutate the resolved
worktree instance.

## Debugging Protocol

1. Establish visibility: confirm dev-server, MCP, and browser state are observable.
2. Assess complexity before changing code.
3. Reproduce with instrumentation and logs.
4. Form a root-cause hypothesis from observed behavior.
5. Apply the fix and rerun the reproduction path.
6. For dashboard data pages, compare related surfaces that claim the same fact, such as Setup vs `/workspace/profile`, Browse wiki vs Workspace insights, Browse memory vs Workspace memory, and Insights summaries vs underlying records.
7. Run autonomous regression checks before reporting success.

## Usage

```bash
/dev-debug
```
