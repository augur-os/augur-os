# Daemon Usage (Task Scheduler)

On Windows, Augur registers the unified daemon as a per-user scheduled task. Do not run `unified_daemon.py start` as a child process of an AI client shell.

## Install / Start

Register the task through the shared service-healer entrypoint:

```powershell
python project-brain/capabilities/skills/daemon/scripts/service_healer.py install
```

After install, Windows starts the daemon at user logon. If you need to trigger it immediately, use Task Scheduler or `schtasks /run /tn "com.augur.daemon"`.

## Status

Check the scheduled-task registration and the daemon's internal runtime state:

```powershell
schtasks /query /tn "com.augur.daemon"
python project-brain/capabilities/skills/daemon/scripts/unified_daemon.py status
```

`service_healer.py status` is also safe to use when you want the shared cross-platform registration summary.

## Stop / Uninstall

Remove the scheduled task through the shared entrypoint:

```powershell
python project-brain/capabilities/skills/daemon/scripts/service_healer.py uninstall
```

If the daemon is currently running, end the active task instance from Task Scheduler or with `schtasks /end /tn "com.augur.daemon"` before uninstalling.
