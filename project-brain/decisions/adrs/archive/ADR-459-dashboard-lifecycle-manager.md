---
status: Implemented
date: 2026-03-20
deciders:
  - Gur Sannikov
related:
  - ADR-043
hub: null
tags:
  - daemon
  - dashboard
  - crash-loop
  - coordination
superseded_by: null
---

# ADR-459: Dashboard Lifecycle Manager

## Context

The dashboard monitor has no memory across cycles and no coordination between actors. Three failure modes recur:

1. **Crash-after-up loop** — Dashboard recovers, serves HTTP 200, monitor resets all state. 1-2 minutes later it crashes again (OOM/heap). Monitor starts from scratch with zero memory. Loops indefinitely.
2. **Concurrent actor conflict** — Multiple agents run `npm run build`, `cleanup_processes`, or `mount-plugins` simultaneously. One kills the dashboard while another is rebuilding it. The monitor can't distinguish intentional from accidental downtime.
3. **Silent downtime** — Build flock held during compilation blocks recovery. Monitor logs "skipping recovery" every 30s with no notification to user. No audit trail of who triggered what.

## Decision

Introduce a **Dashboard Lifecycle Manager** — a single coordination point for all dashboard state changes. Every actor that wants to stop/rebuild/restart the dashboard must go through this gate. It owns the event log, stability tracking, and crash-loop detection.

### Core components

**1. Event Log** — Append-only JSONL at `~/Library/Logs/Augur/dashboard_lifecycle.jsonl`. Every state change gets a record with actor, action, reason, state transition, and optional metadata (pid, uptime, recovery stage). Rotated by `auto-logs`.

**2. Lifecycle Gate** — Central coordination function `request_action(actor, action, reason, force=False) -> {"decision": "granted"|"denied", "reason": str}`. Thread/process safe via `fcntl.flock(LOCK_EX)` on a dedicated lock file.

**State machine** (7 states):
```
stopped → starting → compiling → stabilizing → healthy → stopping → stopped
                                                  ↑            |
                                                  └── crashed ──┘
```

**Gate rules:**

| Current State | Requested Action | Decision |
|---|---|---|
| `healthy` | `stop` / `rebuild` | **Granted** — actor gets exclusive ownership |
| `starting` / `compiling` / `stabilizing` | `stop` / `rebuild` | **Denied** — "dashboard is {state}, owned by {owner}" |
| `stopping` | anything | **Denied** — "shutdown in progress by {owner}" |
| `crashed` / `stopped` / `unknown` | `restart` | **Granted** to first requester, denied to others |
| any state | any action with `force=True` | **Granted** — logged as `gate_bypassed` |

**Ownership TTL:** 5-minute expiry. Dead agent protection — mirrors `LOCK_FILE_MAX_AGE_MINUTES = 5`.

**3. Stability Tracking** — After recovery succeeds, dashboard must pass 2 consecutive healthy monitor polls (60s at 30s interval) before transitioning to `healthy`. During stabilization, gate denies all `stop`/`rebuild` requests.

**4. Crash-loop detection** — Rolling window: 3 crashes in 10 minutes = crash loop. Recovery suspended. Backoff between full recovery cycles: `30 * 3^(n-1)` seconds. Resets after 5 minutes healthy (in `record_healthy_poll()`, when the state transitions to `healthy`, `recovery_backoff_seconds` is set to 0).

**Notification escalation:**

| Situation | Notification |
|---|---|
| First crash, auto-recovering | "Dashboard crashed, recovering..." |
| Crash during stabilization | "Dashboard unstable — crashed again after {N}s uptime" |
| 3rd crash in 10min (crash loop) | "CRASH LOOP: Dashboard failed 3x in 10min. Recovery suspended." |
| Recovery succeeds + 2 polls stable | "Dashboard recovered and stable" |

### Files changed

| File | Change |
|---|---|
| `.claude/skills/daemon/scripts/dashboard_lifecycle.py` | **NEW** — lifecycle gate, event log, stability tracker (~300 lines) |
| `.claude/skills/daemon/scripts/dashboard_monitor.py` | Delegate state to lifecycle module. Recovery goes through `request_action()`. |
| `.claude/skills/daemon/scripts/cleanup_processes.py` | Gate call before port kill. Remove `_create_reload_lock` / `_remove_reload_lock`. |
| `apps/dashboard/scripts/build-lock.sh` | Gate call before flock acquire (this file is Python despite .sh extension). |
| `apps/dashboard/scripts/start-dev.sh` | Log-event call on startup. |
| `CLAUDE.md` | Add Critical Rule #18 (dashboard lifecycle gate). |
| `.claude/skills/dev-build/SKILL.md` | Update to note gate is called automatically. |

### Public API

```python
request_action(actor, action, reason, force=False) -> dict
log_event(actor, action, reason, **extra) -> None
get_state() -> dict
```

CLI:
```bash
python3 dashboard_lifecycle.py request-action --actor X --action Y --reason Z [--force]
python3 dashboard_lifecycle.py log-event --actor X --action Y --reason Z
python3 dashboard_lifecycle.py state
```

### CLAUDE.md Critical Rule #18

> **Dashboard lifecycle gate** — Never run `npm run dev`, `npm run build`, `cleanup_processes.py --port 3000`, or kill dashboard processes directly. All dashboard state changes go through `dashboard_lifecycle.request_action()` (Python) or `dashboard_lifecycle.py request-action` (CLI) or via `/dev-build` which calls the gate internally. Direct manipulation bypasses crash-loop protection and breaks coordination between concurrent agents.

## Consequences

### Positive

- Crash loops are detected and recovery is suspended — no infinite restart cycles
- Concurrent actors are coordinated — one gate, one owner at a time
- Full audit trail via JSONL — every state change is logged with actor, reason, timestamps
- Stability window prevents premature "recovered" claims

### Negative

- Adds a coordination layer that all dashboard-touching code must call
- If lifecycle module itself crashes, falls back to direct recovery (advisory gate)
- Slightly more complex recovery path in dashboard_monitor.py

### Neutral

- State file and event log use filesystem-based storage (JSONL, JSON) — no new dependencies
- `fcntl.flock` provides kernel-managed process safety — dead processes auto-release

## Alternatives Considered

### Alternative 1: SQLite State Store

Use SQLite instead of JSON + JSONL for state and event storage. Rejected: adds dependency, JSONL is sufficient and grep-able, and the current data volume (one event per 30s cycle) doesn't justify a database.

### Alternative 2: No Gate, Advisory-Only Logging

Log all events but don't enforce coordination. Rejected: doesn't solve the concurrent actor conflict problem — the whole point is preventing actors from stepping on each other.

### Alternative 3: systemd/launchd Process Groups

Use OS-level process management to coordinate. Rejected: too platform-specific, doesn't solve the application-level state machine (crash-loop detection, stability windows).

## References

- Design spec: `~/Vault/Augur/dev/specs/2026-03-20-dashboard-lifecycle-manager-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-20-dashboard-lifecycle-manager.md`
- Related: ADR-043 (Unified IDE Registry Lifecycle)

## Implementation Prompt

**Team name**: `adr-459-lifecycle-manager`

### Phase 1: Core Module
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | backend | medium | State machine, event log, state I/O with tests | `.claude/skills/daemon/scripts/dashboard_lifecycle.py`, `.claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py` |
| 1.2 | backend | medium | Lifecycle gate (request_action) with tests | same files |
| 1.3 | backend | medium | Stability tracking, crash-loop detection with tests | same files |
| 1.4 | backend | low | CLI entry point | `.claude/skills/daemon/scripts/dashboard_lifecycle.py` |

### Phase 2: Wiring
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | backend | high | Wire dashboard_monitor.py to lifecycle module | `.claude/skills/daemon/scripts/dashboard_monitor.py` |
| 2.2 | backend | medium | Wire cleanup_processes.py, remove reload locks | `.claude/skills/daemon/scripts/cleanup_processes.py` |
| 2.3 | backend | low | Wire build-lock.sh and start-dev.sh | `apps/dashboard/scripts/build-lock.sh`, `apps/dashboard/scripts/start-dev.sh` |
| 2.4 | docs | low | CLAUDE.md rule #18, dev-build skill doc | `CLAUDE.md`, `.claude/skills/dev-build/SKILL.md` |

### Phase 3: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | test | medium | Integration tests — full lifecycle flow, crash-loop blocking | `.claude/skills/daemon/augur/tests/test_dashboard_lifecycle.py` |
| 3.2 | ops | low | Restart daemon, verify state tracking and event log | — |

### Completion Criteria
- [ ] All 9 implementation gates pass
- [ ] `dashboard_lifecycle.py state` returns valid JSON
- [ ] Event log captures health checks after daemon restart
- [ ] Crash-loop detection blocks recovery after 3 rapid crashes
- [ ] Concurrent gate requests are serialized via flock
- [ ] CLAUDE.md rule #18 is present
- [ ] ADR status updated to Implemented
