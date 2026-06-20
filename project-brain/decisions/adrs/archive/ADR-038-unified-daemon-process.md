---
status: Implemented
date: ''
deciders: []
related: []
hub: null
tags:
- unified
- daemon
- process
superseded_by: null
---

# ADR-038: Unified Daemon Process

**Date:** 2026-02-04
**Author:** Augur Team

## Context

After implementing the autonomous execution pipeline (ADR-037), Augur had 3 separate
LaunchAgent plists running as background services:

- `com.augur.logmonitor` — log_monitor.py (24/7, error detection)
- `com.augur.continuous` — continuous_executor.py (24/7, task polling)
- `com.augur.nightly` — nightly_maintainer.py (scheduled, 3 AM)

Each appeared in macOS System Settings > Background Activity as a separate
"python3 (unidentified developer)" entry, making the system look unprofessional
and cluttered. Users had no way to identify which "python3" belonged to Augur.

## Decision

Unify all background services into a single process managed through a lightweight
macOS `.app` bundle (`Augur Daemon.app`).

### Architecture

```
~/Library/LaunchAgents/com.augur.daemon.plist
    ↓
Augur Daemon.app/Contents/MacOS/augur-daemon  (shell script)
    ↓
unified_daemon.py  (process manager)
    ├── log_monitor.py        (subprocess, persistent)
    ├── continuous_executor.py (subprocess, persistent)
    └── nightly_maintainer.py  (subprocess, scheduled 3 AM)
```

### Key Design Choices

**Lightweight .app bundle over Tauri:** The Tauri desktop app (`plugins/augur-desktop/`)
is a full GUI application with Rust compilation. A minimal `.app` bundle with just
Info.plist, icon, and shell script achieves the same macOS identity (name + icon in
Background Activity) with zero compilation and instant deployment.

**Subprocesses over threads:** The 3 services have different lifecycles.
`continuous_executor.py` already uses `ProcessPoolExecutor` internally. Subprocesses
provide crash isolation, independent restart, and avoid nested concurrency complexity.

**Internal scheduling over StartCalendarInterval:** With a single LaunchAgent plist
(KeepAlive), the nightly schedule is handled by the unified daemon via a simple
time check, eliminating the need for a separate scheduled plist.

### Components

| Component | Purpose |
|-----------|---------|
| `Augur Daemon.app` | Identity wrapper (CFBundleName="Augur", icon) |
| `unified_daemon.py` | Subprocess manager with health monitoring |
| `NightlyScheduler` | Time-based scheduling for nightly maintainer |
| `SubprocessManager` | Per-service health check, restart with circuit breaker |
| `service_healer.py` | Plist generation, install/uninstall/heal/migrate |

### Migration Path

`service_healer.py migrate` or `cleanup_legacy_plists.py`:
1. Unload and remove legacy plists
2. Install unified `com.augur.daemon.plist`
3. Reset macOS Background Activity cache (`sfltool resetbtm`)

## Consequences

### Positive

- Single "Augur" entry with icon in macOS Background Activity
- Centralized process management with health monitoring
- Circuit breaker prevents restart storms
- Status reporting via `runtime/stats/daemon_status.json`
- Simplified service_healer (one service instead of three)

### Negative

- If unified daemon crashes, all services stop until launchd restarts it
- Slightly more complex architecture (parent process managing children)
- Shell script wrapper adds one more layer of indirection

### Neutral

- Dashboard plist (`com.augur.dashboard`) remains separate (different runtime: Node.js)
- Individual service scripts unchanged — can still run standalone for debugging
