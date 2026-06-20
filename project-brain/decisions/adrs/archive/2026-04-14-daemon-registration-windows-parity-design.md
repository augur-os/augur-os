# Daemon Registration Windows Parity Design

## Goal

Make daemon registration cross-platform so Windows matches the current macOS behavior: a per-user OS-managed background daemon that starts automatically at login, survives AI client exits, and can be installed, healed, uninstalled, and checked through the same Augur daemon management surface.

## Problem

Today the daemon lifecycle is effectively macOS-only.

- skills/daemon/scripts/service_healer.py only supports `sys.platform == "darwin"` for install/uninstall.
- skills/daemon/commands/ops-daemon.md describes daemon control only in terms of `launchctl` and LaunchAgents.
- The existing Windows script skills/daemon/scripts/setup_scheduled_task.ps1 is not a unified-daemon registrar. It is a stale nightly-maintenance task with outdated paths, admin assumptions, and no parity with the unified daemon lifecycle.

This leaves Windows without the same daemon ownership model as macOS. Native Windows support remains incomplete until daemon registration stops assuming LaunchAgents are the only real platform path.

## Decision

Adopt a cross-platform daemon registration model with two backends:

- macOS backend: existing per-user `launchd` LaunchAgent model
- Windows backend: per-user `Task Scheduler` model

Windows will explicitly **not** use a machine-wide Windows Service. The intended parity target is the current macOS scope: per-user, OS-managed, auto-start at login, limited privileges, and recoverable through the same `install` / `status` / `heal` / `uninstall` surface.

## Approach Options

### Option A: Cross-platform registrar layer

Keep one daemon management surface and split registration into platform backends.

Pros:
- preserves one canonical daemon lifecycle contract
- keeps `/daemon` and `service_healer.py` as the only public lifecycle entrypoints
- supports real platform parity instead of adding Windows as a one-off exception

Cons:
- requires refactoring plist-specific assumptions out of `service_healer.py`

### Option B: Separate Windows-only registration script

Add a dedicated Windows daemon registration flow and leave macOS lifecycle code mostly as-is.

Pros:
- smaller immediate patch

Cons:
- creates two daemon control systems
- encourages docs and command drift
- weakens parity and makes future platform work more expensive

### Option C: Startup-only Windows registration

Register the daemon in Windows login startup and defer lifecycle parity.

Pros:
- smallest scope

Cons:
- does not deliver “same as macOS”
- no credible `heal` / `status` / `uninstall` contract

## Recommended Architecture

Use Option A.

`service_healer.py` becomes the daemon registration manager rather than a plist manager. It remains the single public lifecycle entrypoint, but delegates registration work to platform-specific backends.

### Shared registration contract

Both platforms derive from one shared daemon registration spec:

- project-derived daemon label, consistent with the current macOS naming pattern `com.<project>.daemon`
- repo root as working directory
- unified daemon entrypoint and arguments as the managed command contract
- platform-native stdout/stderr log targets under paths resolved by `src.config.paths`
- keep-alive / restart semantics

The spec should describe the daemon command abstractly enough that each backend can render it appropriately:

- macOS may keep the existing `.app` wrapper so Background Activity continues to show a proper Augur app entry
- Windows should launch the repo venv Python against `skills/daemon/scripts/unified_daemon.py`

This removes the current assumption that “the service definition is a plist.” Instead, the service definition becomes a Python-side registration spec that can be rendered as:

- a LaunchAgent plist on macOS
- a scheduled task definition on Windows

## Windows Backend Design

### Registration primitive

Windows uses `Task Scheduler` as the native equivalent of the current LaunchAgent model.

Why this backend:

- per-user scope is supported
- login trigger is supported
- restart-on-failure behavior is available
- task state can be queried and managed without introducing a machine-wide service
- it is materially closer to `launchd` than a `Run` key or Startup folder entry

### Scope and privileges

- run as the current user
- no administrator-only Windows Service install
- limited privileges
- start at user logon

### Task behavior

The Windows daemon task should:

- trigger `AtLogOn` for the current user
- launch the repo venv interpreter
- pass the unified daemon script path as the command target
- use the repo root as working directory
- prefer single-instance semantics
- restart on failure with bounded retry behavior

### Heal semantics

`heal` on Windows means:

- inspect the registered task definition
- compare executable, arguments, working directory, and task identity to the current Augur repo root and venv
- if stale or missing, regenerate and re-register the task

This mirrors the current macOS “project moved, plist paths stale” healing behavior.

### Status semantics

`status` on Windows should report both:

- Task Scheduler registration/runtime state
- `unified_daemon.py status`

That matches the current macOS pattern of reporting both OS service state and daemon-internal state.

### Uninstall semantics

`uninstall` on Windows removes or disables the registered task and leaves the daemon no longer auto-managed by the OS.

### Migration semantics

Any pre-existing Windows task that represents the old nightly-maintenance scheduling path must not remain a parallel daemon owner.

The current setup_scheduled_task.ps1 should either:

- be absorbed into the new unified Windows daemon registration flow, or
- be retired if the unified daemon fully takes over its responsibilities

It must not remain a separate scheduling system once unified daemon parity exists.

## Code Structure

### `service_healer.py`

Refactor into:

- shared daemon registration spec builder
- platform backend selector
- macOS backend functions
- Windows backend functions

The existing macOS plist functions can stay, but they should no longer be the structural center of the module.

### Path and naming helpers

Keep shared naming and path resolution in Python using `src.config.paths`.

The daemon label identity should remain project-derived so multiple Augur projects on one machine can stay disambiguated.

### Command and doc surface

Update:

- skills/daemon/commands/ops-daemon.md
- skills/daemon/SKILL.md
- related daemon references

These should become platform-neutral at the top level:

- macOS examples remain `launchctl`-based
- Windows examples become `schtasks` / PowerShell-based
- the rule remains the same on both platforms: never run the unified daemon as a subprocess of the AI client process tree

## Verification Strategy

### Automated

- unit tests for backend selection by platform
- unit tests for shared registration spec generation
- macOS regression tests to ensure plist rendering and existing labels do not drift
- Windows tests for:
  - task name / label derivation
  - user-logon trigger
  - repo venv interpreter path
  - unified daemon script path
  - working directory
  - restart-on-failure settings

### CI

Add a Windows-oriented smoke that validates task-definition generation or registration logic in a CI-safe way, without requiring a machine-wide service install.

### Manual

One real Windows smoke is still required after implementation:

- install daemon registration
- log out / log in or manually trigger the task
- verify daemon survives outside the launching shell
- verify `status`, `heal`, and `uninstall`

## Non-Goals

- converting Augur into a machine-wide Windows Service
- redesigning the unified daemon internals
- changing daemon child-service ownership model
- changing the macOS LaunchAgent model beyond what is needed to share structure with Windows

## Risks

### Platform drift

The biggest risk is implementing Windows as an exception path while leaving docs and commands macOS-shaped. This is avoided by keeping one shared lifecycle contract and one public management surface.

### Duplicate scheduler ownership

Leaving the existing nightly scheduled task alive alongside the new Windows daemon task would create split ownership and unpredictable behavior. Migration or retirement is mandatory.

### Repo-move staleness

Windows task definitions can go stale after repo moves just like plist paths do on macOS. `heal` must explicitly cover this.

## Outcome

After this change, daemon registration becomes genuinely cross-platform:

- macOS: per-user LaunchAgent
- Windows: per-user Task Scheduler task

Both are treated as the same Augur daemon lifecycle, with the same install/heal/status/uninstall contract and the same rule that the daemon must be OS-managed rather than child-managed by the active AI client session.
