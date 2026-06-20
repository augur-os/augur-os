---
title: Worktree Global Identity Isolation
date: 2026-05-24
status: design
topic: worktrees
---

# Worktree Global Identity Isolation - Design

## Problem

Parallel Augur development sessions can currently repoint shared runtime identity
to whichever worktree ran the most recent install or sync command. The visible
symptom is that the global `aug` CLI, shared editable installs, MCP runtime, or
Python import paths can start resolving to `<active worktree>` instead of the
main checkout at `<main checkout>`.

This is a real product bug, not a local cleanup annoyance. Once one session
poisons shared identity, another session can run code from the wrong checkout,
import stale compatibility shims, or send MCP requests through an unexpected
runtime. ADR-778 removed one module-identity root cause from the test suite; this
design prevents the local runtime from reintroducing stale worktree identity into
shared CLI and MCP surfaces.

## Goal

Make this invariant true:

**Global identity belongs to main. Worktree identity is process-local only.**

Concretely:

- Shared `.venv`, editable installs, global `aug`, pipx-style CLI links, and
  persistent client MCP configs point to the main checkout.
- Worktrees can run as themselves only through scoped environment overlays for
  that process or child process.
- A worktree cannot silently install, sync, or export itself into shared global
  identity.
- Drift is detected early with an actionable diagnostic and repaired only through
  the main authority path.

## Non-goals

- Do not require one full virtualenv per worktree as the default model.
- Do not remove editable installs everywhere as part of this change.
- Do not rewrite client-specific sync adapters beyond the identity guard needed
  to stop path drift.
- Do not break production MCP runtime requirements that intentionally need both
  the project root and `src/mcp` in process-local `PYTHONPATH`.

## Chosen Approach

Use a main-owned global identity model with worktree-local runtime overlays.

The main checkout is the installation authority. Worktrees may request scoped
runtime behavior, but they do not mutate shared site-packages, global CLI links,
or persistent client config to point at themselves.

Compared with per-worktree virtualenvs, this preserves fast worktree creation and
keeps the existing local developer ergonomics. Compared with a no-editable-install
policy, it fixes the immediate cross-session bug without requiring a packaging
redesign first.

## Architecture

The implementation should introduce a small identity-control layer used by
bootstrap, sync, CLI, MCP config, and dev/worktree workflows.

### RuntimeIdentity

`RuntimeIdentity` resolves the current execution context:

- main root
- current repository root
- current worktree root, when applicable
- authority root
- branch and session identity, when available
- whether the current process may mutate shared global identity

It must not assume the current working directory is main. It should use git
metadata and the existing worktree registry where available, with conservative
fallbacks that fail closed for global mutations.

### GlobalMutationGuard

`GlobalMutationGuard` wraps operations that can repoint shared identity:

- editable installs
- `.pth` writes
- global `aug` CLI repoints
- pipx-style command surfaces
- client MCP config sync
- generated client exports that embed project paths

The default rule is:

- allowed when the target root is the authority root
- blocked when a worktree attempts to target shared global identity
- delegated only for explicitly allowed repair or sync commands that operate
  through the authority root

### WorktreeOverlay

`WorktreeOverlay` produces process-local environment for worktree execution:

- `AUGUR_PROJECT_ROOT=/path/to/worktree`
- scoped `PYTHONPATH`
- scoped MCP server environment
- optional temporary config path for the child process

The overlay is never persisted into shared `.venv`, `.pth`, global CLI links, or
long-lived client config unless the target is the main authority root.

### DriftDoctor

`DriftDoctor` audits real local state for identity drift:

- `pip list --editable`
- editable `.pth` files in site-packages
- `importlib.util.find_spec(...)` for Augur packages
- global `aug` executable resolution
- generated MCP config paths for supported clients

It reports the exact drifted surface, the unexpected path, and the expected main
authority root. Repair holds the global identity lock and rewrites shared state
back to main.

### GlobalIdentityLock

`GlobalIdentityLock` serializes shared identity mutations across parallel
sessions. It should be a filesystem lock in the runtime state directory so
separate clients and shells coordinate through the same lock.

Short sync/repair operations may wait briefly. Interactive commands that should
not mutate global identity should fail fast if they somehow try to take the lock.

## Data Flow

### Main checkout global operation

1. A command asks to mutate global identity.
2. `RuntimeIdentity` resolves `<main checkout>` as the authority root.
3. `GlobalMutationGuard` verifies the target is the authority root.
4. The command takes `GlobalIdentityLock`.
5. Editable installs, CLI links, and persistent client configs are written with
   main-root paths.
6. Drift checks confirm that shared state resolves to main.

### Worktree execution

1. A session starts in `<active worktree>`.
2. `RuntimeIdentity` resolves the current root as a worktree and authority root
   as main.
3. Commands that need worktree-local behavior receive `WorktreeOverlay`.
4. The child process runs with scoped env pointing at the worktree.
5. Shared `.venv`, `.pth`, global `aug`, and persistent client config remain
   pointed at main.

### Drift repair

1. `DriftDoctor` detects any shared surface pointing at a worktree.
2. It reports the bad surface and the expected authority root.
3. Repair reruns through the authority root under `GlobalIdentityLock`.
4. It rewrites shared install and config identity back to main.
5. It rechecks CLI resolution, editable locations, `.pth`, and imports.

### Parallel sessions

Two worktrees can execute process-local commands at the same time. Only one
global identity mutation can run at a time, and worktrees cannot become the
global owner by racing an install or sync command.

## Failure Handling

- If a worktree tries to install itself into shared `.venv`, fail with a message
  naming the worktree root, authority root, and attempted mutation.
- If existing drift is detected, fail early before running with mixed identity.
- If repair cannot find a valid main checkout, do not fall back to the current
  worktree; report the missing authority root.
- If the lock is held, wait briefly only for commands whose contract includes
  global repair or sync. Other commands should fail fast.
- If a client config is intentionally process-local, the guard should classify it
  separately from persistent global client config so valid overlays are not
  blocked.

## Testing And Verification

Automated tests should cover the identity layer before any command wiring:

- root and authority detection for main, linked worktree, nested cwd, and missing
  registry cases
- mutation guard behavior for main-allowed, worktree-blocked, and delegated
  repair paths
- overlay generation, proving worktree paths appear only in child-process env
- drift-doctor parsing for editable installs, `.pth`, import specs, CLI links,
  and MCP config paths

Integration tests should simulate two concurrent worktree sessions:

- create or fixture two worktree roots
- run install-like and sync-like operations concurrently
- assert shared editable locations and `.pth` files still point to main
- assert persistent client config paths still point to main
- assert each worktree can still run repo-local code through its overlay

Real-data verification must inspect the live developer environment:

- `pip list --editable` contains no `augur-wt-*` locations for shared Augur
  packages
- editable `.pth` files do not contain `augur-wt-*`
- `find_spec` for Augur runtime packages resolves to the expected main-owned
  runtime or the process-local overlay for the command being tested
- `aug` resolves to the main-owned command surface
- generated persistent MCP configs point to main unless the file is explicitly a
  session-local overlay

## User Value

After this merge, parallel Codex, Claude, Gemini, and shell sessions stop
stealing Augur runtime identity from each other. A worktree can test its own code
without repointing the global CLI or MCP runtime for every other session.

The user gets:

- fewer "this session is using the wrong checkout" failures
- safer parallel work on multiple ADRs or branches
- reliable `aug` and MCP behavior across active sessions
- a single diagnostic for local identity drift
- a controlled repair path that puts shared identity back on main
- operational protection for ADR-778's module identity cleanup

## Implementation Planning Defaults

These defaults should carry into the ADR and implementation plan unless a code
inventory proves one is unsafe.

1. Authority-root discovery:
   use git worktree metadata to find the common repository, prefer the checkout
   whose branch is `main`, and cross-check against the existing worktree
   registry. A missing or ambiguous main checkout blocks global mutation.
2. Delegation:
   only repair and explicit client-sync commands may delegate through the main
   authority root. Install and bootstrap commands invoked from a worktree fail
   unless they are operating on a process-local overlay.
3. DriftDoctor surfaces:
   add a direct CLI/audit command first, then wire it into `/dev-debug` and setup
   status. `/dev-clean` may offer repair, but it must not silently rewrite global
   identity without reporting the changed surfaces.
4. Client config classification:
   persistent files in home/client config locations are global and must point to
   main. Files under a session temp directory or explicitly generated worktree
   overlay path are process-local and may point to the worktree.
5. Governing artifact:
   because this changes cross-session CLI, MCP, and worktree behavior, the design
   should be promoted into an ADR before implementation. The ADR should cite this
   spec as the brainstorming source and define the final acceptance gate.

## Acceptance Criteria

- A worktree cannot mutate shared editable installs or `.pth` identity to itself.
- Persistent global MCP/client config is main-rooted after sync.
- Process-local worktree overlays still allow testing and MCP launches from a
  worktree.
- A two-worktree concurrent simulation cannot produce shared identity drift.
- The live developer environment audit reports no shared Augur identity pointing
  at `augur-wt-*`.
- Drift repair, when needed, rewrites shared identity to main and verifies the
  result.
