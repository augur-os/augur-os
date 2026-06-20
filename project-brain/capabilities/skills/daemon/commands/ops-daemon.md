---
description: "Manage the Augur daemon: start, stop, restart, status"
visibility: ops
x-augur-export-command: false
---

# /daemon

Manage the Augur unified daemon as an OS-level background service. macOS uses `launchd`. Windows uses `Task Scheduler`. `service_healer.py` is the install / heal / uninstall entrypoint on both platforms.

**CRITICAL**: Never run `python project-brain/capabilities/skills/daemon/scripts/unified_daemon.py start` directly — that spawns the daemon inside Claude Code's process tree, which:
- Kills the daemon when Claude Code exits
- Prevents the self-healer from spawning CLI tools (nested process error)

## Actions

### 1. Status — Check daemon health

```bash
python project-brain/capabilities/skills/daemon/scripts/service_healer.py status
python project-brain/capabilities/skills/daemon/scripts/unified_daemon.py status
```

Report both the OS service registration state and the daemon's internal status.

### 2. Install / Start — Register the background service

```bash
python project-brain/capabilities/skills/daemon/scripts/service_healer.py install
```

On Windows, the same install command runs under the repo venv Python and registers a per-user scheduled task rather than a LaunchAgent.

### 3. Stop / Restart / Uninstall — Use the platform service manager

- macOS `launchd` commands live in [references/launchd-usage.md](../references/launchd-usage.md).
- Windows Task Scheduler commands live in [references/windows-task-usage.md](../references/windows-task-usage.md).
- Use `python project-brain/capabilities/skills/daemon/scripts/service_healer.py uninstall` when you need to remove the registration from the current platform.

### 4. Heal — Fix paths if the project moved

```bash
python project-brain/capabilities/skills/daemon/scripts/service_healer.py heal
```

Re-run install after a heal if you want the current platform manager to refresh the daemon immediately.

## Notes

- If the user doesn't specify an action, default to **status**.
- The daemon manages child services: log monitor, continuous executor, nightly maintainer, dashboard monitor, MCP health monitor, runtime marker scanner, AI self-healer, and insight scanner.
- The daemon runs via an `.app` bundle (`Augur Daemon.app`) on macOS so Background Activity shows a proper icon.
- Use the platform-specific references for native manager commands; keep the shared operational entrypoint as `service_healer.py`.
