---
title: dashboard-monitor-lifecycle-gate-stuck-kill-the-daemon
name: dashboard-monitor-lifecycle-gate-stuck-kill-the-daemon
description: When dashboard restart hangs at "Lifecycle gate denied; dashboard is
  starting, owned by dashboard_monitor" for >2 min, kill dashboard_monitor PID and
  launchctl will respawn it cleanly; the dashboard process itself may already be healthy,
  only the gate's owner field is stale
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_dashboard_monitor_stuck_gate_fix.md
source_hash: ea9b8e3799c387f4
---


**Symptom:** after `cleanup_processes.py` or any path that flips the dashboard lifecycle into `state: starting, owner: dashboard_monitor`, the lifecycle gate stays stuck. Every launchctl restart attempt fails with `Lifecycle gate denied: dashboard is starting, owned by dashboard_monitor`. TTL is 300 s but the dashboard's own `dashboard_monitor.py --loop` keeps refreshing `owner_since` or never releases ownership, so the gate never expires.

**Why:** `dashboard_monitor.py --loop` acquires the "starting" lock when it sees a crash, attempts a relaunch, and on failure it does not clear the owner. launchctl's KeepAlive backs off after repeated failures. Result: dashboard process can actually be healthy (HTTP 200 from curl), but the gate machinery insists otherwise and blocks any new build/restart cycle.

**Fix (verified 2026-05-17):**
```bash
ps aux | grep dashboard_monitor | grep -v grep         # find PID
kill <PID>                                              # SIGTERM, not -9
sleep 2
cat "$HOME/Library/Application Support/Augur/state/daemon/dashboard/main/state.json"
# expect: state="crashed", owner=null  ← lock released
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/
# expect: 200 (immediately, no restart needed if dashboard process was already healthy)
```
launchctl auto-respawns dashboard_monitor on its KeepAlive cycle (com.augur.daemon), so the daemon is back within seconds and now reads fresh state. No data loss; the next state-transition will be honest.

**How to apply:** if you're in the middle of a Monitor poll loop waiting on the dashboard and it's been >180 s without recovery, stop the monitor and kill the daemon instead of waiting on TTL. The user gave explicit blessing for this (2026-05-17): "kill the daemon to unstick it." Don't preemptively kill it on every restart — only when stuck. The lifecycle gate is supposed to be the right path; this is recovery from a known bug in the gate's owner-release logic.

**Durable fix landed 2026-05-18 — commit a917fa017:** added
`TRANSIENT_STATE_TTL_SECONDS = 60` for `{starting, compiling, stopping}`
in `shared-vault/skills/daemon/scripts/dashboard_lifecycle.py:87-94`.
`_check_ownership_ttl` now picks the right TTL by current_state — fast-
fail in 60 s for transient states, full 300 s for everything else.

When a daemon dies mid-start or gets SIGKILLed in a transient state,
the next `request_action` call clears the stale owner after 60 s and
grants the new actor. launchctl's KeepAlive loop self-recovers in
60-90 s without needing the manual `kill <PID>` + `state.json` edit.

If you ever see this stuck-gate symptom AGAIN with that fix in place,
check whether dashboard_monitor is refreshing owner_since on every loop
iteration (it should only set owner_since once per acquisition). Then
the manual SIGTERM recipe below stays as the emergency escape hatch.

Related: [[feedback_long_session_drift]] (mechanical gates beat behavioral rules — but only when the mechanical gate itself doesn't get stuck).
