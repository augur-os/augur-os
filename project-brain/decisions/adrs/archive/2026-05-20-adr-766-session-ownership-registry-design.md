---
title: ADR-766 v1 — Session-Ownership Registry - Design
type: spec
status: draft
created: 2026-05-20
authors:
  - gsannikov
  - Claude (Augur agent)
implements:
  - docs/adrs/ADR-766-one-live-owner-per-session-model.md
related:
  - apps/dashboard/lib/session/SessionManager.ts
  - apps/dashboard/app/api/cli/actions.ts
  - apps/dashboard/app/api/session/open-terminal/route.ts
  - apps/dashboard/app/api/session/init/route.ts
  - scripts/ca-launch.sh
  - scripts/xa-launch.sh
  - scripts/ga-launch.sh
  - scripts/ca-launch.ps1
  - scripts/xa-launch.ps1
  - scripts/ga-launch.ps1
  - config/system/capability_exposure.yaml
  - docs/superpowers/specs/2026-05-18-native-terminal-chat-handoff-design.md
governance:
  next_step: User review, then implementation plan via writing-plans.
tags:
  - dashboard
  - session-lifecycle
  - terminal-handoff
  - mcp
  - airplane-mode
---

# ADR-766 v1 — Session-Ownership Registry

## Purpose

Enforce **at most one live process per Claude/Codex/Gemini session id, per host**, across
the dashboard embedded PTY and native-terminal handoffs. This eliminates the MCP relay
disconnect/reconnect churn (relay servers can only attach to one client process at a time)
and the concurrent-transcript-append corruption risk, and makes airplane-mode backend
switches preserve conversation history safely.

Implements ADR-766. This spec fixes the **v1 scope and the mechanisms ADR-766 left open**.

## Scope (v1)

In scope:

1. A session-ownership **registry** as the single source of truth.
2. **Claim/release** wiring across the three launch paths that resume a session id
   (dashboard `initialize`, `startCliProcess`, native-terminal launchers).
3. **Conflict resolution** by non-destructive **refuse/redirect** ("continue there").

Explicitly **out of scope for v1** (deferred):

- The opt-in **"take over here" graceful self-exit**. ADR-766 §4 describes the losing owner
  "observing the released claim via heartbeat and self-exiting", but a running native-terminal
  CLI does not poll Augur's registry, so there is no mechanism today. Implementing it requires
  a cross-OS registry-polling supervisor wrapping the CLI — significant and unnecessary because
  refuse/redirect already removes the churn and corruption risk non-destructively. Revisit only
  if users actually need cross-surface takeover.
- Any forced `kill` of an AI-client process (prohibited by the AI-client-safety rule).
- Cross-host coordination. Ownership is per machine (the user mirrors Augur across laptops);
  another host's entries never count as a local owner.

## Architecture

### Component 1 — Registry (single source of truth, exposed as MCP tools)

- **Storage:** one JSON file at `get_runtime_dir()/state/session-owners.json` (ADR-270 runtime
  state, ADR-743 file-ledger style — no DB).
- **Record shape**, keyed by `session_id`:

  ```
  {
    pid: number,
    surface: "dashboard-pty" | "native-terminal",
    host: string,            # stable machine identity
    cli_id: "claude" | "codex" | "gemini",
    started_at: ISO8601,     # when the claim was written
    proc_start_time: string, # OS process start time of `pid`, for PID-reuse detection
    last_seen: ISO8601       # refreshed on claim; informational in v1
  }
  ```

- **Implementation:** a single Python module backing **MCP tools** — `session-claim`,
  `session-release`, `session-status`. Rationale (architectural choice): the native launchers
  are shell/PowerShell and must call a CLI, while the dashboard is Node. Rather than maintain two
  parallel TS+Python implementations of the same liveness/atomicity logic (drift risk), there is
  **one** Python implementation reached two ways:
  - **launchers** → `aug session-claim|session-release|session-status …`
  - **dashboard** → the MCP bridge (`callMCPTool`), satisfying rule 11 (dashboard goes through
    MCP, never direct fs).
- **Capability exposure:** add `mcp-tool:session-claim|session-release|session-status` entries to
  `config/system/capability_exposure.yaml` with `export_to: [cli, mcp]` (cli for launchers,
  mcp for dashboard).
- **Atomicity:** every write is temp-file-then-atomic-rename, guarded by a per-file lock, so
  concurrent claims/releases from the dashboard and a launcher cannot corrupt the file.

### Component 2 — Liveness (host-scoped, PID-reuse-safe)

A registry entry is a **live local owner** iff **all** hold:

1. `host == ` this host (other-host entries are ignored for conflict purposes), AND
2. `pid` is alive — `os.kill(pid, 0)` / `process.kill(pid, 0)`, AND
3. the OS process start time of `pid` matches the recorded `proc_start_time` (defeats PID reuse —
   a dead CLI's PID re-assigned to an unrelated process will not match).

`proc_start_time` is read via `psutil` (cross-platform: macOS + Windows for the `.ps1` launchers).
Any entry failing the check is **stale** and reclaimable.

### Component 3 — Claim / release wiring

- **Dashboard `SessionManager.initialize` and `actions.ts startCliProcess`:** after the PTY is
  spawned (real PID known), `session-claim(session_id, surface="dashboard-pty", pid, cli_id,
  host)`. On `markCliStopped` / `terminate`, `session-release(session_id, surface="dashboard-pty")`.
- **Handoff `exitForTerminalHandoff`:** release the dashboard claim *before* the native terminal
  launches (the PTY is already exited here). The native launcher (`{ca,xa,ga}-launch.{sh,ps1}`)
  then `aug session-claim … --surface native-terminal --pid <spawned-cli-pid>` and, via
  `trap`/`finally`, `aug session-release …` on exit (best-effort; abnormal exits are reclaimed by
  liveness).

### Component 4 — Conflict resolution (refuse/redirect, "continue there")

- `session-claim` returns `{ok:true, ...}` on success, or
  `{ok:false, conflict:{surface, pid, host}}` when a **live local owner of a different surface**
  already holds the session id. (A same-surface relaunch after the prior owner died is a normal
  **reclaim**, not a conflict.)
- The dashboard launch routes (`open-terminal`, `/api/cli` start, `/api/session/init`) translate a
  conflict into a redirect payload. The dashboard shows a **non-blocking banner**:
  *"This conversation is live in &lt;Terminal / dashboard&gt; (pid N) — continue there."*
  No process is spawned and none is killed. (Chosen UX: inform + "continue there"; no
  "start fresh here" button in v1.)

### Component 5 — Airplane interaction (closes the "memory off" gap safely)

The committed Part-2 fix (`ee8f9449e`) makes a dashboard restart resume `lastSessionId` so an
airplane backend switch keeps history. Under this registry that is safe:

- Dashboard airplane restart → `startCliProcess` → `session-claim`.
- If a **live native terminal** owns the session → conflict → "continue in Terminal" banner
  (the switch is performed in the owning surface). No second process appends to the transcript.
- If the **dashboard's own** PTY exited (its claim released) → **reclaim**, resume, apply the
  local backend → history preserved, single owner.

## Data flow (claim on dashboard start)

```
start chat / restart-to-apply-airplane
  └─ actions.ts startCliProcess: spawn PTY (pid)
       └─ callMCPTool("session-claim", {session_id, surface:"dashboard-pty", pid, cli_id, host})
            ├─ ok:true   → proceed (record owner)
            └─ ok:false  → route returns redirect payload → dashboard banner "continue there"
```

## Error handling

- **session-claim during a write race:** the per-file lock serializes writers; the loser re-reads
  and re-evaluates (claim is idempotent for the same surface+pid).
- **Launcher fails to release (crash/SIGKILL):** the stale entry remains until the next liveness
  check reclaims it (dead PID or start-time mismatch). No leak persists across a real conflict.
- **psutil unavailable:** fall back to PID-alive only (degraded PID-reuse safety) and log once;
  do not hard-fail. (psutil is already an Augur dependency; this is a defensive path.)
- **Registry file missing/corrupt:** treat as empty (no owners) and rewrite atomically on next
  claim — never block a launch on a malformed registry.

## Testing

- **Python unit tests** (`tests/packages/augur-mcp/tools/test_session_owners.py`, matching the
  existing `test_airplane_mode.py` / `test_connectivity.py` convention): claim → status; same-surface
  reclaim after dead PID; cross-surface conflict; PID-reuse via start-time mismatch → reclaim;
  host-scoping (other-host entry ignored); concurrent atomic writes (no corruption).
- **Dashboard tests:** a conflict from `session-claim` produces the redirect payload from
  `open-terminal` / `/api/cli` start; claim and release are called on start and stop.
- **Integration (no runaway agents):** a **scripted** two-claim simulation — first claims, second
  (different surface) is refused — asserted by inspecting the registry and the claim result.
  Per session memory, the live dashboard chat is **not** driven via browser automation for
  verification (it spawns real autonomous agents); verification is via the registry/API and the
  scripted sim.

## Impact

```yaml
new:
  - src/mcp/augur_framework/tools/infrastructure/session_owners.py  # registry + MCP tools: session-claim, session-release, session-status
  - tests/packages/augur-mcp/tools/test_session_owners.py
  - state/session-owners.json (runtime state, get_runtime_dir)
modified:
  - apps/dashboard/lib/session/SessionManager.ts        # claim/release in initialize, terminate, markCliStopped, exitForTerminalHandoff
  - apps/dashboard/app/api/cli/actions.ts               # claim after startCliProcess; conflict → redirect
  - apps/dashboard/app/api/session/open-terminal/route.ts  # conflict → redirect payload
  - apps/dashboard/app/api/session/init/route.ts        # conflict → redirect payload
  - scripts/{ca,xa,ga}-launch.sh / .ps1                 # claim with spawned PID; release on exit
  - config/system/capability_exposure.yaml              # session-claim/release/status exposure
  - dashboard chat UI                                   # non-blocking "continue there" banner
deferred:
  - "take over here" graceful self-exit (needs cross-OS registry-polling supervisor)
```

## Open questions

None blocking. The registry lives in `src/mcp/augur_framework/tools/infrastructure/` (framework
infra, alongside `local_backends.py` / `connectivity.py` / `client_resolver.py`), not a vault
skill. Remaining mechanical choices (banner placement, host-identity source) are settled during
planning/implementation.
