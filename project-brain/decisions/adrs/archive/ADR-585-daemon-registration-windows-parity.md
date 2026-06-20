---
status: Implemented
date: 2026-04-14
deciders:
  - Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-585: Daemon Registration Windows Parity

## Context

The Augur daemon lifecycle is effectively macOS-only. `skills/daemon/scripts/service_healer.py` only supports `sys.platform == "darwin"` for install/uninstall, `skills/daemon/commands/ops-daemon.md` describes daemon control purely in terms of `launchctl` and LaunchAgents, and the existing `skills/daemon/scripts/setup_scheduled_task.ps1` is a stale nightly-maintenance task with outdated paths and admin assumptions — not a unified-daemon registrar.

This leaves Windows without the same daemon ownership model as macOS: a per-user OS-managed background daemon that starts at login, survives AI client exits, and can be installed, healed, uninstalled, and inspected through one Augur surface. Native Windows support remains incomplete until daemon registration stops assuming LaunchAgents are the only real platform path.

## Decision

Adopt a cross-platform daemon registration model with two backends sharing one lifecycle contract:

- macOS backend: existing per-user `launchd` LaunchAgent
- Windows backend: per-user Windows `Task Scheduler` task (not a machine-wide Windows Service)

`service_healer.py` becomes the daemon registration manager rather than a plist manager, exposing `install` / `status` / `heal` / `uninstall` for both platforms. Both backends derive from one shared `DaemonRegistrationSpec` (project-derived label `com.<project>.daemon`, repo root as working directory, unified daemon entrypoint, log targets via `src.config.paths`, restart semantics). The spec renders as a LaunchAgent plist on macOS or a scheduled task XML on Windows. The Windows task triggers `AtLogOn`, runs the repo venv interpreter against `unified_daemon.py`, single-instance, restart-on-failure. `heal` compares the registered task's executable, arguments, and working directory to the current repo and re-registers if stale. The legacy `setup_scheduled_task.ps1` becomes a thin wrapper around `service_healer.py` and the old "Augur Nightly Maintenance" task is retired during cleanup.

## Consequences

### Positive
- One canonical daemon lifecycle contract across macOS and Windows
- Per-user, OS-managed daemon on Windows that survives AI client exits
- `heal` covers Windows repo-move staleness the same way it covers macOS plist staleness
- Status output reports `registrationType` / `registrationPath` instead of plist-only fields

### Negative
- Requires refactoring plist-specific assumptions out of `service_healer.py`
- A real Windows smoke (login, task trigger, status/heal/uninstall) is still required after CI

### Neutral
- `setup_scheduled_task.ps1` is retained but reduced to a wrapper
- macOS LaunchAgent model is unchanged beyond sharing structure

## Alternatives Considered

### Alternative 1: Separate Windows-only registration script
Add a dedicated Windows daemon registration flow and leave macOS lifecycle code mostly as-is. Rejected: creates two daemon control systems, encourages docs and command drift, weakens parity, makes future platform work more expensive.

### Alternative 2: Startup-only Windows registration
Register the daemon in Windows login startup and defer lifecycle parity. Rejected: does not deliver "same as macOS" — no credible `heal` / `status` / `uninstall` contract.

### Alternative 3: Machine-wide Windows Service
Rejected as a non-goal: the parity target is the macOS per-user scope, not elevated machine-wide ownership.

## References
- Plan: docs/superpowers/plans/2026-04-14-daemon-registration-windows-parity.md
- Spec: docs/superpowers/specs/2026-04-14-daemon-registration-windows-parity-design.md
