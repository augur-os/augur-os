---
status: Implemented
date: '2026-02-10'
deciders:
- Gur Sannikov
related:
- ADR-005 (MCP Gateway)
- ADR-014 (Instance Management)
- ADR-038 (Unified Daemon)
- ADR-041 (Daemon Self-Healing)
- ADR-054 (Offloading)
- ADR-060 (External Execution)
hub: null
tags:
- mcp
- implementation
- hardening
superseded_by: null
---

# ADR-063: MCP Implementation Hardening

## Context

After 8 weeks of MCP-centric development, three recurring failure modes consume significant debugging time:

### Problem 1: Stalled PIDs from daemon/reload cycles

The unified daemon (`unified_daemon.py`) and `/reload` workflow both spawn MCP servers and dashboard processes. When a reload or daemon restart occurs, child processes frequently survive their parent — the PID file updates but the old process holds the port/socket. The `mcp_health_monitor.py` detects this (60s interval) but only in production mode. In dev mode (where most work happens), stalled PIDs accumulate silently until the next `cleanup_processes.py` run or manual `kill`.

**Observed**: After 3+ reload cycles in a dev session, 2-4 orphan MCP processes consuming memory, holding stdio locks, causing "address already in use" errors on restart.

### Problem 2: Offload-as-workaround pattern

ADR-054 designed offloading as a cost optimization — route cheap tasks to Kimi. In practice, offloading became a *reliability workaround*: when Claude's MCP stack is stuck (tool timeouts, context exhaustion), dispatching to Kimi via `offload-gate.sh` sidesteps the problem entirely because Kimi gets a fresh process. The fire-and-forget design (offload AND run) masks the root cause — the primary stack is degraded but work still gets done through the side channel.

**Observed**: 47 dispatches, 0 accepted verdicts until today's review loop (ADR-054 section 5 was never wired up). Offload results accumulate without review, making it impossible to distinguish cost savings from reliability workarounds.

### Problem 3: MCP stack divergence across clients

The MCP server (`augur-mcp`) runs in 5+ clients (Claude Code, Cursor, Windsurf, Kimi, Codex). Each client manages stdio/SSE transport differently. ADR-014's per-client locking works for single instances but doesn't handle the case where multiple clients connect simultaneously. The PID registry (`mcp_pids.json`) tracks server names but not which client owns them. When a client crashes, its MCP server becomes an orphan that blocks other clients from connecting.

**Observed**: "MCP stuck" in Cursor while Claude Code works fine (or vice versa). Requires `kill -9` on the orphaned process, then restart the affected client.

### Quantified impact

| Failure Mode | Frequency | Recovery Time | Root Cause |
|-------------|-----------|---------------|------------|
| Stalled PIDs after reload | 2-3x per dev session | 2-5 min (find + kill) | No graceful shutdown in reload workflow |
| Offload masking degraded stack | ~30% of offloads | 0 (masked) | Fire-and-forget hides primary failures |
| Cross-client MCP orphans | 1-2x per multi-client session | 3-5 min (identify + kill + restart) | No client-scoped PID ownership |

## Decision

### 1. Graceful shutdown protocol for daemon/reload

Add a `--graceful-stop` flag to `mcp_health_monitor.py` that:
- Reads `mcp_pids.json` and sends SIGTERM to all registered MCP servers
- Waits up to 5s per process, then SIGKILL
- Clears the PID registry
- Releases lock files (`dashboard_rebuild.lock`, `dashboard_reload.lock`)

Wire this into the reload workflow:
- `/reload` calls `--graceful-stop` BEFORE starting new processes
- `unified_daemon.py` calls `--graceful-stop` on SIGTERM/SIGINT (existing signal handler enhanced)

**Files**:
- Modify: `plugins/observability/skills/daemon/scripts/mcp_health_monitor.py` — add `--graceful-stop` CLI flag
- Modify: `plugins/observability/skills/daemon/scripts/unified_daemon.py` — call graceful stop in signal handler
- Modify: `plugins/ai/ai_bridge/agent-workflows/reload-dashboard.md` — add graceful stop as step 1

### 2. Dev-mode health checking (close the dev/prod gap)

Currently `mcp_health_monitor.py` only auto-kills stalled processes in production mode. Change behavior:
- **Dev mode**: Auto-kill stalled processes (same as prod) BUT also log to `data/runtime/mcp_issues.md` with stack trace for debugging
- **Remove the dev-mode exemption** for auto-cleanup — stalled PIDs in dev are just as harmful as in prod

**Files**:
- Modify: `plugins/observability/skills/daemon/scripts/mcp_health_monitor.py` — remove dev-mode skip for auto-cleanup, add stack trace logging

### 3. Client-scoped PID ownership

Extend `mcp_pids.json` schema to track which client started each server:

```json
{
  "servers": {
    "augur-mcp-claude-code": {
      "pid": 12345,
      "client": "claude-code",
      "transport": "stdio",
      "started_at": "2026-02-10T17:00:00",
      "port": null
    },
    "augur-mcp-cursor": {
      "pid": 12346,
      "client": "cursor",
      "transport": "stdio",
      "started_at": "2026-02-10T17:05:00",
      "port": null
    }
  }
}
```

When a client starts an MCP server, it registers with `client` field. Health monitor can then:
- Detect orphans: PID alive but parent client process dead
- Clean up per-client: restart only the affected client's MCP server
- Prevent collisions: warn when two clients try to share a server

**Files**:
- Modify: `plugins/observability/skills/daemon/scripts/mcp_health_monitor.py` — extend registry schema, add client-aware cleanup
- Modify: `data/runtime/mcp_pids.json` — schema migration (backward-compatible)

### 4. Offload health signal (distinguish cost savings from workarounds)

Add a `trigger_reason` field to offload log entries to distinguish intentional offloads from workaround offloads:

| Trigger | Meaning |
|---------|---------|
| `cost_optimization` | Normal ADR-054 flow — task is low-tier, cheap CLI handles it |
| `stack_degraded` | Primary stack timed out or errored, offload is a fallback |
| `manual` | User explicitly requested offload |

The `offload-gate.sh` hook can detect `stack_degraded` by checking if the Task tool has failed recently (read last N lines of offload-log for error patterns).

Add a `--health-report` flag to `offload_dispatcher.py` that outputs:
- Total dispatches by trigger reason
- Accept rate by trigger reason
- If `stack_degraded` > 30% of dispatches: flag MCP health issue

**Files**:
- Modify: `.claude/hooks/offload-gate.sh` — add `trigger_reason` to log entries
- Modify: `plugins/orchestration/skills/executor/scripts/offload_dispatcher.py` — add `--health-report` flag

### 5. Startup health gate

Add a pre-flight check to the MCP server startup that:
- Scans for orphan PIDs from previous sessions
- Kills orphans before starting
- Validates port availability
- Writes clean PID registry entry

This runs automatically when the MCP server initializes, eliminating the 60s window where stalled PIDs can cause issues.

**Files**:
- Modify: `plugins/observability/skills/daemon/scripts/mcp_health_monitor.py` — add `--preflight` flag
- Wire into MCP server startup sequence

## Consequences

### Positive

- Reload cycles become reliable — no more manual PID hunting
- Dev sessions match prod behavior — same auto-healing in both modes
- Multi-client usage becomes safe — client-scoped ownership prevents cross-contamination
- Offload metrics distinguish cost savings from reliability workarounds
- Startup is self-healing — orphans cleaned before new server starts

### Negative

- Dev-mode auto-kill loses the "preserve for debugging" benefit — mitigated by stack trace logging
- Client field in PID registry requires all client integrations to pass their identity
- Graceful shutdown adds 0-5s to reload cycles

### Neutral

- Existing `mcp_health_monitor.py` 60s loop continues as backup — preflight handles startup, loop handles runtime
- Fire-and-forget offload design unchanged — just better instrumentation

## Alternatives Considered

### Alternative 1: Watchdog process per MCP server

Run a dedicated watchdog for each MCP server that auto-restarts on crash. Rejected because:
- Adds process overhead (N watchdogs for N servers)
- Doesn't solve the root cause (unclean shutdown)
- Complicates the unified daemon which already manages health

### Alternative 2: Shared MCP server across all clients (SSE transport only)

Run a single MCP server on a fixed port, all clients connect via SSE. Rejected because:
- ADR-014 chose stdio for privacy and simplicity
- SSE requires network stack, adds attack surface
- Some clients (Kimi, Codex) only support stdio

### Alternative 3: Container-based isolation

Run each MCP server in a lightweight container. Rejected because:
- Massive overhead for a local-first tool
- Violates ADR-006 (local-first, minimal dependencies)
- Docker/OrbStack dependency unacceptable for onboarding simplicity

## References

- ADR-005: MCP as Execution Gateway
- ADR-014: MCP Instance Management and Transport Strategy
- ADR-038: Unified Daemon Process
- ADR-041: Daemon Production Monitoring & Self-Healing
- ADR-054: Cross-Tool Swarm Offloading
- ADR-060: External Execution Mode

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-063: MCP Implementation Hardening**.

Read the full ADR: `docs/decisions/ADR-063-mcp-implementation-hardening.md`

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` → look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output — check `success`, `files_changed`, and `diff` fields
4. Record the verdict:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict-for "<output_file>" "<verdict>"
   ```
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-063-mcp-hardening", description="Implementing ADR-063: MCP Implementation Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-063-mcp-hardening", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-063 team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-063-mcp-hardening`

#### Phase 1: Graceful Shutdown Protocol
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Add `--graceful-stop` flag to mcp_health_monitor.py: read mcp_pids.json, SIGTERM all servers, wait 5s, SIGKILL survivors, clear registry and lock files | `plugins/observability/skills/daemon/scripts/mcp_health_monitor.py` |
| 1.2 | developer | medium | Enhance unified_daemon.py signal handler to call graceful stop on SIGTERM/SIGINT before exit | `plugins/observability/skills/daemon/scripts/unified_daemon.py` |
| 1.3 | developer | low | Update reload-dashboard.md workflow to call `--graceful-stop` as first step before any restart | `plugins/ai/ai_bridge/agent-workflows/reload-dashboard.md` |

#### Phase 2: Dev-Mode Health + Client-Scoped PIDs
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Remove dev-mode exemption for auto-cleanup in mcp_health_monitor.py. Both modes auto-kill stalled PIDs, dev mode additionally logs stack trace to `data/runtime/mcp_issues.md` | `plugins/observability/skills/daemon/scripts/mcp_health_monitor.py` |
| 2.2 | developer | medium | Extend mcp_pids.json schema with `client` field. Update `load_mcp_pids`/`save_mcp_pids` to handle new schema (backward-compatible). Add client-aware orphan detection: PID alive but parent client process dead | `plugins/observability/skills/daemon/scripts/mcp_health_monitor.py` |

#### Phase 3: Offload Health Signal + Startup Gate
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Add `trigger_reason` field to offload-gate.sh log entries (cost_optimization, stack_degraded, manual). Detect stack_degraded by checking recent offload-log for error patterns | `.claude/hooks/offload-gate.sh` |
| 3.2 | developer | medium | Add `--health-report` flag to offload_dispatcher.py: output dispatches by trigger reason, accept rate by reason, flag if stack_degraded > 30% | `plugins/orchestration/skills/executor/scripts/offload_dispatcher.py` |
| 3.3 | developer | medium | Add `--preflight` flag to mcp_health_monitor.py: scan for orphan PIDs, kill orphans, validate port availability, write clean registry entry. Designed to run at MCP server startup | `plugins/observability/skills/daemon/scripts/mcp_health_monitor.py` |

#### Phase 4: Sync & Regenerate
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | devops | low | Run `python3 plugins/ai/skills/ai_bridge/scripts/sync_agents.py` to regenerate slash commands including updated `/reload` | `.claude/commands/reload.md` |

#### Final Phase: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `pytest tests/` — verify no regressions |
| V.2 | validator | low | Run `python3 plugins/observability/skills/daemon/scripts/mcp_health_monitor.py --check` — verify health check still works |
| V.3 | validator | low | Run `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --health` — verify offload system works |
| V.4 | architect | low | Read ADR-063, review all changed files, verify implementation matches intent |

### Completion Criteria
- [ ] `--graceful-stop` stops all MCP servers cleanly
- [ ] `/reload` workflow no longer leaves orphan PIDs
- [ ] Dev mode auto-kills stalled PIDs (same as prod)
- [ ] `mcp_pids.json` tracks client ownership
- [ ] `--preflight` cleans orphans at startup
- [ ] `--health-report` distinguishes cost offloads from workaround offloads
- [ ] All tests pass (`pytest tests/`, `npm run build` in `src/dashboard/`)
- [ ] ADR-063 status updated to Accepted
