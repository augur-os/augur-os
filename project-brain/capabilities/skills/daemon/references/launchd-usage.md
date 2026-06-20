# Daemon Usage (launchd)

On macOS, manage the Augur unified daemon via launchd. The daemon MUST run as an OS-level service, never as a subprocess of Claude Code.

**CRITICAL**: Never run `python3 unified_daemon.py start` directly -- that spawns the daemon inside Claude Code's process tree, which:
- Kills the daemon when Claude Code exits
- Prevents the self-healer from spawning CLI tools (nested process error)

## 1. Status -- Check daemon health

```bash
launchctl list com.augur.daemon 2>&1; echo "---"; python3 project-brain/capabilities/skills/daemon/scripts/unified_daemon.py status
```

Report both the launchd service state and the daemon's internal status.

## 2. Start -- Launch the daemon via launchd

First check if the plist is installed. If not, install it:

```bash
# Check if plist exists
ls ~/Library/LaunchAgents/com.augur.daemon.plist 2>/dev/null || python3 project-brain/capabilities/skills/daemon/scripts/service_healer.py install
```

Then load/start the service:

```bash
launchctl load -w ~/Library/LaunchAgents/com.augur.daemon.plist
```

If already loaded, kickstart it:

```bash
launchctl kickstart -k gui/$(id -u)/com.augur.daemon
```

## 3. Stop -- Gracefully stop the daemon

```bash
launchctl unload ~/Library/LaunchAgents/com.augur.daemon.plist
```

## 4. Restart -- Stop and re-launch

```bash
launchctl unload ~/Library/LaunchAgents/com.augur.daemon.plist 2>/dev/null; sleep 1; launchctl load -w ~/Library/LaunchAgents/com.augur.daemon.plist
```

## 5. Heal -- Fix paths if project was moved

```bash
python3 project-brain/capabilities/skills/daemon/scripts/service_healer.py heal
```

## Notes

- If the user doesn't specify an action, default to **status**.
- The daemon runs via an `.app` bundle (`Augur Daemon.app`) so macOS shows "Augur" in Background Activity with a proper icon.
- If `launchctl load` fails, run `service_healer.py install` to regenerate the plist.

See [Usage (legacy)](docs/usage.md) for individual monitor commands.

For Windows Task Scheduler usage, see [windows-task-usage.md](windows-task-usage.md).

## Configuration

AI Self-Healer is configured via `config/system/self_heal.yaml`.
Defaults are at `project-brain/capabilities/skills/daemon/augur/config/self_heal.yaml`.

Key settings: `enabled`, `scan_interval_minutes`, `llm.cli`, `fix.max_files_modified`, `routing`.

## Output Files

| File | Purpose |
|------|---------|
| `~/Library/Application Support/Augur/state/daemon.pid` | Daemon PID file |
| `~/Library/Application Support/Augur/state/stats/daemon_status.json` | Service status |
| `~/Library/Application Support/Augur/state/stats/dashboard_status.json` | Dashboard health |
| `~/Library/Application Support/Augur/state/mcp_pids.json` | MCP process registry |
| `~/Library/Application Support/Augur/state/mcp_issues.md` | MCP TODO_BUG markers |
| `~/Library/Application Support/Augur/state/tech_debt.md` | External state tech debt markers |
| `~/Library/Application Support/Augur/state/self_heal_registry.json` | AI self-heal issue registry |
| `~/Library/Application Support/Augur/state/locks/` | Lock files for rebuild/fix operations |
| `config/system/self_heal.yaml` | User self-heal configuration |
