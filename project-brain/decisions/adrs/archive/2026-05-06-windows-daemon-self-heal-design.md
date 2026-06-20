---
title: Windows Daemon Self-Heal Reliability Design
date: 2026-05-06
status: proposed
author: Codex
---

# Windows Daemon Self-Heal Reliability Design

## Goal

Make Augur daemon and self-heal behavior on Windows explicit, testable, and close enough to macOS that an operator can trust the same workflow on both platforms.

The immediate outcome is:

- the Windows daemon is registered through Task Scheduler, not inferred from an open terminal
- the daemon runs without requiring a persistent visible terminal window
- status commands report the OS registration state and the internal daemon state
- self-heal status explains whether the adaptive loop and AI monitor sidecar are active
- Windows notification delivery can be tested directly
- failure reports include exact paths and command evidence

## Current Findings

During brainstorming on 2026-05-06, this checkout showed these Windows-specific facts:

- `.\.venv\Scripts\python.exe skills\daemon\scripts\service_healer.py status` reported that `com.augur.daemon` was not registered in Task Scheduler.
- `.\.venv\Scripts\python.exe skills\daemon\scripts\unified_daemon.py status` reported no daemon status file.
- `schtasks /query /tn "com.augur.daemon" /v /fo LIST` reported that the scheduled task did not exist.
- `config/system/daemon.yaml` had `ai_monitor.enabled: false`, so the AI monitor sidecar was intentionally disabled.
- Process inspection showed Codex, dashboard, and MCP helper processes, but no `unified_daemon.py` Task Scheduler-owned daemon process.
- In sandboxed command execution, status commands failed during logger setup when creating entity log directories under `C:\Users\intel\AppData\Local\Augur\logs`, so diagnostics must not crash before printing useful status.

These findings mean the visible terminal in the screenshot is not acceptable evidence that the daemon is running. The proof must be Task Scheduler registration plus a fresh daemon status file plus healthy child service states.

## Scope

This design covers Windows daemon installation, status, healing, self-heal visibility, and notification verification.

It does not re-enable the AI monitor sidecar by default. The sidecar should stay disabled until the OS-managed daemon path is reliable and observable. Re-enabling it is a separate decision because it changes autonomous AI execution behavior.

It also does not redesign adaptive loops. The existing `auto-self-heal` scan/fix path remains the self-heal loop entrypoint; this work makes its runtime status and notification behavior visible on Windows.

## Recommended Approach

Use repair plus runtime contract hardening.

The alternatives considered were:

- Minimal repair: register and start the Windows task, then add a notification test. This is fast but leaves future drift hidden.
- Runtime contract hardening: make registration, status, logs, notifications, and self-heal activation auditable. This is the recommended path.
- Full daemon redesign: rework daemon scheduling and AI sidecar semantics across platforms. This is too broad before the Windows service path is proven.

The recommended approach fixes the current machine and adds enough diagnostics to prevent the same silent failure from returning.

## Architecture

The daemon lifecycle should keep one public control surface:

- `skills/daemon/scripts/service_healer.py` remains the OS registration entrypoint.
- `skills/daemon/scripts/unified_daemon.py` remains the long-running supervisor.
- `skills/daemon/scripts/notification_service.py` remains the cross-platform notification backend.
- A small daemon diagnostics helper should centralize status checks that are currently scattered or implicit.

The diagnostics helper owns these checks:

- Windows scheduled task exists for `com.augur.daemon`
- scheduled task command points at the repo venv Python and `skills/daemon/scripts/unified_daemon.py`
- task is running or startable
- runtime directories are writable: logs, state, locks, daemon stderr, and status
- `state/stats/daemon_status.json` exists and is fresh
- daemon PID is alive
- child service states are running, scheduled, stopped, error, or critical failure
- `config/system/daemon.yaml` reports the AI monitor sidecar state
- Windows notification self-test can send or reports the exact backend error

The key invariant is simple: a visible terminal is never proof that the daemon is healthy.

## Data Flow

On Windows, `/ops-daemon heal` should use this sequence:

1. Resolve project, runtime, log, vault, and document paths through `src.config.paths`.
2. Preflight runtime directories and report any unwritable path before starting service work.
3. Query Task Scheduler for `com.augur.daemon`.
4. If the task is missing or has stale command paths, register it with the repo venv Python and `unified_daemon.py`.
5. Start the task and wait for a fresh `state/stats/daemon_status.json`.
6. Read internal daemon status and child service states.
7. Return one status object with `healthy`, `degraded`, `not_installed`, or `error`.
8. Optionally run a notification self-test when explicitly requested.

On Windows, `/ops-daemon status` should not mutate registration. It should read the same facts and print an operator-readable summary:

- Task Scheduler: installed, missing, disabled, running, or stopped
- Daemon status file: missing, stale, fresh, unreadable, or malformed
- Daemon PID: alive or stale
- Child services: counts and failed service names
- Self-heal loop: latest adaptive self-heal report path and summary when present
- AI monitor sidecar: enabled, disabled, unavailable, or failed
- Notifications: configured, last sent, or self-test required

## Self-Heal Visibility Contract

Self-heal has two separate runtime surfaces and status must not conflate them.

`auto-self-heal` is the adaptive loop scan/fix path. Its status should be derived from adaptive reports, trust state, and self-heal registry data.

`ai_monitor_sidecar` is the daemon-embedded AI monitor. Its status should be derived from `config/system/daemon.yaml` and daemon status. When disabled, status must say it is intentionally disabled and point to the config file.

Notification delivery is a third independent surface. A lack of notifications does not prove self-heal is idle; it may mean notification delivery failed or quiet-hours/preferences blocked delivery.

## Notification Contract

Windows notifications should be bounded.

Send notifications for:

- daemon installed or started by an explicit heal/install action
- daemon service recovered after failure
- daemon child service entered critical failure
- self-heal found a high or critical finding
- self-heal fixed, escalated, or failed to fix an issue
- manual notification self-test

Do not send notifications for:

- routine polling
- every healthy status check
- repeated identical failures inside a cooldown window
- expected disabled states, such as `ai_monitor.enabled: false`

The notification self-test must report which backend was tried and why it failed or succeeded. On Windows that may include `plyer`, BurntToast, or the WinRT fallback.

## Error Handling

Status and heal flows must fail loudly and specifically.

- Missing scheduled task: report `not_installed`.
- Disabled scheduled task: report `disabled`.
- Task starts but status file does not become fresh: report `task_started_but_daemon_not_reporting` and include stdout/stderr paths.
- Log or state path is unwritable: report the exact path and exception, and still print status where possible.
- Task action path mismatch: report the current command, expected command, and working directory.
- Stale PID file: report stale PID and do not claim the daemon is running.
- Notification failure: report backend and exact exception.
- AI monitor sidecar disabled: report intentional disabled state and config path.
- Child service repeated crash: keep the critical item behavior and emit one bounded notification.

The logger must not be a single point of failure for status commands. If file logging cannot initialize, commands should still print diagnostics to stdout or stderr.

## Testing

Use focused tests before any broad integration run.

Unit tests:

- Windows scheduled task missing, disabled, running, and command path mismatch
- status survives log directory creation failure and still returns diagnostics
- AI monitor disabled state is visible in daemon status
- notification self-test returns backend success or backend-specific failure
- fresh versus stale `daemon_status.json`
- child service critical failure produces a bounded notification request

Live Windows smoke:

1. Run service status and confirm missing or installed state is reported without crashing.
2. Run heal/install and confirm Task Scheduler has `com.augur.daemon`.
3. Confirm `unified_daemon.py status` reports a fresh status file.
4. Confirm child services are present in the status file.
5. Run a notification self-test and inspect the exact backend result.

Do not claim Windows parity from unit tests alone. At least one live Task Scheduler smoke is required because the failure mode is OS integration.

## Acceptance Criteria

The work is complete when:

- `service_healer.py status` reports useful Windows diagnostics without crashing on logging setup failure
- `service_healer.py heal` can install/start the Windows scheduled task or report exact blockers
- `unified_daemon.py status` distinguishes missing, stale, and fresh daemon state
- `com.augur.daemon` registration uses the repo venv Python and the current repo path
- no persistent visible terminal is required for normal daemon operation
- self-heal status distinguishes adaptive loop status from AI monitor sidecar status
- Windows notification self-test has an explicit pass/fail result
- focused tests and one live Windows smoke have been run and recorded

## Implementation Notes

Prefer small, testable changes:

- Extract diagnostics functions before changing command behavior.
- Keep Windows Task Scheduler code behind platform checks.
- Do not introduce a Windows Service unless a future ADR changes the lifecycle target.
- Do not re-enable the AI monitor sidecar as part of this work.
- Keep operator output terse but evidence-rich: exact task name, exact path, exact state, exact exception.

## Review

This spec intentionally limits the first implementation to reliability and observability. It gives Windows the same operator confidence macOS has without expanding autonomous AI behavior before the daemon is actually proven to be managed by the OS.
