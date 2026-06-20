---
status: Implemented
date: 2026-05-20
deciders:
  - gsannikov
  - Claude (Augur agent)
related:
  - ADR-535
  - ADR-151
hub: null
tags:
  - dashboard
  - session-lifecycle
  - terminal-handoff
  - mcp
  - airplane-mode
superseded_by: null
spec_file: 2026-05-20-adr-766-session-ownership-registry-design.md
plan_file: 2026-05-20-adr-766-session-ownership-registry.md
---

# ADR-766: One-Live-Owner-Per-Session Model for Dashboard PTY and Native Terminal Handoff

## Decision summary

Enforce **at most one live process per Claude/Codex/Gemini session id at a time** across the dashboard embedded PTY and native-terminal handoffs, via a session-ownership registry with liveness + explicit ownership transfer, eliminating the MCP relay disconnect/reconnect churn and the concurrent-transcript-append corruption risk.

## Context

### Symptom

Users report the dashboard's MCP servers — especially the single-instance relay servers `claude-in-chrome`, `computer-use`, and `context7` — **disconnecting and reconnecting "nonstop"** during a work session, and the airplane-mode toggle losing conversation history ("all memory off").

### Root cause (evidence, 2026-05-20 deep-debug)

The dashboard ↔ native-terminal handoff re-resumes the **same** session id in a **new** process on every switch, and never terminates the prior one:

- The handoff (`POST /api/session/open-terminal`) calls `SessionManager.exitForTerminalHandoff()` (kills the dashboard PTY), then opens a native Terminal running `claude --resume <lastSessionId> "<handoff prompt>"`.
- Observed live: **two handoff processes alive simultaneously** on the same session — PID 71388 (10:15, "Page: /browse") and PID 95788 (10:53, "Page: /brain"), both `claude --resume d5142902-…`. Plus Codex companions on the same and a second session id, plus an Ollama-launched local `claude` on a *fresh* session id `f0485599`.
- The single-instance relay MCP servers can only attach to one client process at a time. Each (re)launch hands the relay to the newest process and drops it from the old → the disconnect/reconnect churn observed by the harness. The churn spikes at each handoff/(re)launch, then stabilizes — it is bounded but recurs every switch.

Three code paths independently resume `lastSessionId`, so concurrent same-session ownership is reachable today:

1. `SessionManager.initialize` (prewarm / `POST /api/session/init`) — `buildResumeCmdArgs` → `--resume lastSessionId`.
2. Terminal handoff (`open-terminal` → native terminal) — `claude --resume lastSessionId`.
3. `actions.ts startCliProcess` (manual chat **Start**) — after ADR-pending Part 2 (the "memory off" fix), this path also resumes `lastSessionId`.

### Why this is a design problem, not a patch

- The pile-up of `claude --resume <id>` processes are **not leaked garbage** — they are live terminal sessions the user may still be working in (the debugging session itself was one). Auto-killing "the prior process" on handoff would terminate active user sessions, violating the AI-client-safety rule (never kill AI clients without explicit authorization).
- Two live processes resuming the same session id **append to the same Claude session transcript JSONL concurrently**, risking interleaved/corrupted history.
- There is no authoritative record of *which* surface (dashboard PTY vs which native terminal) currently owns a session, so neither side can make a safe decision.

The correct fix is an explicit ownership model spanning both surfaces, not a localized kill.

## Decision

Introduce a **session-ownership registry** (runtime state, outside the repo per ADR-270) that records, per session id, the current live owner and enforces a single owner.

### 1. Ownership registry

A registry file under `get_runtime_dir()` (e.g. `state/session-owners.json`) mapping:

```
session_id -> {
  pid: number,
  surface: "dashboard-pty" | "native-terminal",
  host: string,          # machine identity (multi-laptop mirror, ADR-754-adjacent)
  cli_id: "claude" | "codex" | "gemini",
  started_at: ISO8601,
  last_heartbeat: ISO8601 | null
}
```

- **Liveness** is determined by PID-aliveness (cheap `kill -0` / `process.kill(pid, 0)` check) plus, where available, a freshness window on `last_heartbeat`. A registry entry whose PID is dead is **stale** and reclaimable.
- The registry is host-scoped: entries from another mirrored laptop never count as a local owner.

### 2. Claim on launch

Every launch path that owns a session id (dashboard `initialize`, `startCliProcess`, terminal handoff launcher) must **claim** ownership before/at spawn:

- If no live local owner exists for the session id → claim it.
- If a live local owner **of a different surface** exists → resolve per §4 (do not silently create a second owner).
- If the claimer is the same surface relaunching (e.g. dashboard restart-to-apply-airplane after its own PTY exited) → reclaim (the prior same-surface owner is already gone).

### 3. Transfer on handoff

`exitForTerminalHandoff()` already exits the dashboard PTY before the native terminal launches. Make this an explicit **ownership transfer**: release the dashboard-PTY claim, then have the native-terminal launcher (`*-launch.{sh,ps1}`) **claim** ownership for the spawned process (writing its real `claude`/`codex`/`gemini` PID + session id into the registry) and **release** on exit. This gives the registry the native-terminal PID it currently never captures.

### 4. Conflict resolution (no killing)

When a launch would create a second live owner of an existing session id:

- **Default — refuse/redirect (non-destructive):** return a clear result ("This session is already open in <surface> (pid N) — switch to it") instead of spawning a duplicate. The dashboard surfaces this as an actionable banner. No process is killed.
- **Opt-in transfer:** the user may explicitly choose "take over here," which releases the other owner's claim and signals it to exit gracefully (the owner observes the released claim via heartbeat and self-exits) — still no forced `kill` of an AI client.

### 5. Airplane interaction (closes the Part 2 gap)

The "memory off" fix (manual Start resumes `lastSessionId`) is correct, but only safe under this model: with one-owner enforcement, a dashboard restart-to-apply-airplane resumes the conversation **without** colliding with a still-open terminal on the same id (the conflict is detected and resolved per §4) — so resuming preserves history without risking concurrent transcript appends.

## Consequences

### Positive
- Eliminates the MCP relay disconnect/reconnect churn (one owner ⇒ no relay tug-of-war).
- Removes the concurrent-transcript-append corruption risk.
- Makes airplane-mode backend switches preserve conversation history safely.
- Gives an authoritative, inspectable record of session ownership (debuggability).

### Negative
- New runtime state + lifecycle code (claim/heartbeat/release) across three launch paths and the native-terminal launchers.
- The native-terminal launchers must be taught to register/deregister, including on abnormal exit (best-effort cleanup; stale entries reclaimed by PID-liveness).

### Neutral
- Host-scoping is required for the mirrored multi-laptop setup; ownership is per machine.
- Refuse/redirect changes handoff UX (a second handoff of a live session is redirected, not duplicated) — intended behavior.

## Implementation Notes

v1 shipped on 2026-05-20 with the runtime ownership registry, MCP/CLI tools, native-terminal handoff claim/release, dashboard PTY claim/release, conflict refusal payloads, and the dashboard conflict banner.

The deferred explicit transfer shipped on 2026-05-21: the conflict banner now offers switch and take-over actions, dashboard start requests can explicitly release the current owner claim and retry the dashboard claim, and native-terminal handoff clients watch their claim so they exit gracefully after another surface takes over. The take-over path releases registry ownership; it does not force-kill an AI client.

## Implementation Order

1. **Registry module** — claim/reclaim/release/isOwnerLive + PID-liveness + host scoping, under `get_runtime_dir()`. Unit-tested in isolation.
2. **Dashboard launch paths** — wire claim/release into `SessionManager.initialize`, `startCliProcess`, and `markCliStopped`/`terminate`.
3. **Handoff transfer** — release dashboard claim in `exitForTerminalHandoff`; teach `*-launch.{sh,ps1}` to claim with the real spawned PID and release on exit (trap/finally).
4. **Conflict resolution UX** — refuse/redirect response from `open-terminal` and `startCliProcess`; dashboard banner with "switch to it" / "take over here."
5. **Validation** — multi-process simulation test (two claims, second is refused); real-browser verification that toggling airplane mid-conversation preserves history and does not spawn a duplicate owner.

## Alternatives Considered

1. **Auto-kill the prior `claude --resume <id>` process on handoff.** Rejected: the prior process is frequently an active user terminal; killing it is destructive and violates AI-client-safety. It also can't distinguish the user's current terminal from a stale one.
2. **Give every surface a distinct session id and never resume across surfaces.** Rejected: defeats the whole point of handoff (continuity) and re-introduces "memory off" — switching surfaces would always start an empty conversation.
3. **Fork the transcript per surface (copy-on-launch).** Rejected for now: avoids concurrent writes but produces diverging conversation copies that must later be reconciled; heavier and more confusing than single-owner with transfer.
4. **Do nothing (document only).** Rejected by decision: the churn is bounded but recurs constantly in normal use, and the Part 2 resume fix elevates the concurrent-append risk enough to warrant a real model.

## References

- ADR-535 — dashboard chat / terminal session lifecycle
- ADR-151 — remote-user CLI/PTY restrictions (handoff is local-only)
- `apps/dashboard/lib/session/SessionManager.ts` — `initialize`, `buildResumeCmdArgs`, `exitForTerminalHandoff`, `getTerminalHandoffSnapshot`, session-id lifecycle
- `apps/dashboard/app/api/session/open-terminal/route.ts` — handoff route
- `apps/dashboard/app/api/cli/actions.ts` — `startCliProcess`, `cmdWithResumableSessionId` (Part 2 resume)
- `scripts/{ca,xa,ga}-launch.{sh,ps1}` — native-terminal launchers
- Deep-debug evidence (2026-05-20): concurrent `claude --resume d5142902` PIDs 71388/95788; Ollama local session `f0485599`; relay servers `claude-in-chrome`/`computer-use`/`context7` cycling at each handoff.

## Impact Manifest

```yaml
paths_renamed: []
apis_changed:
  - "POST /api/session/open-terminal: may return a conflict/redirect payload when session already owned"
  - "POST /api/cli (start): may return a conflict/redirect payload when session already owned by a native terminal"
patterns_deprecated:
  - "Unbounded re-resume of lastSessionId in a new process without an ownership check"
files_affected:
  - apps/dashboard/lib/session/SessionManager.ts
  - apps/dashboard/lib/session/sessionOwners.ts
  - apps/dashboard/app/api/session/open-terminal/route.ts
  - apps/dashboard/app/api/cli/actions.ts
  - apps/dashboard/app/api/cli/cli-config.ts
  - apps/dashboard/features/hooks/useCliChat.ts
  - apps/dashboard/features/components/FloatingChat.tsx
  - apps/dashboard/features/components/chat/ChatHeader.tsx
  - apps/dashboard/features/components/chat/ChatLayout.tsx
  - src/scripts/agent_launch.py
  - scripts/ca-launch.sh
  - scripts/xa-launch.sh
  - scripts/ga-launch.sh
  - scripts/ca-launch.ps1
  - scripts/xa-launch.ps1
  - scripts/ga-launch.ps1
  - tests/dashboard/api/cli-actions.test.ts
  - tests/dashboard/hooks/useCliChat.test.tsx
  - tests/dashboard/components/ChatHeader-airplane-chip.test.tsx
  - tests/scripts/test_agent_launch_core.py
```
