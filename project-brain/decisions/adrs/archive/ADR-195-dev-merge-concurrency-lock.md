---
status: Implemented
date: '2026-03-03'
deciders:
- Project team
related:
- ADR-054 (Cross-Tool Swarm Offloading)
- ADR-101 (Worktree Isolation)
- ADR-014 (MCP Instance Management)
hub: null
tags:
- dev
- merge
- concurrency
- lock
superseded_by: null
---

# ADR-195: Dev-Merge Concurrency Lock

## Context

The `/dev-merge` command performs critical git operations (checkout, merge, stash, push) that are not safe to run concurrently. When multiple tools (Claude Code, Cursor, Windsurf) run `/dev-merge` simultaneously on the same repository, race conditions cause:

1. **Checkout conflicts** — two processes both try to `git checkout main`
2. **Merge collisions** — concurrent `git merge --no-ff` on the same branch creates diverged histories
3. **Stash corruption** — `git stash push` in one process while another runs `git stash pop` loses changes
4. **Push rejections** — concurrent pushes to `origin main` cause non-fast-forward errors

The existing codebase has no concurrency control for dev-merge. The MCP server uses PID-based instance locks (`src/mcp/augur_mcp/instance_lock.py`), but these are per-process daemon locks, not cross-tool workflow locks.

## Decision

Add a file-based merge lock using a JSON lock file at `runtime/dev-merge.lock` (already gitignored under `runtime/`).

### 1. Lock Manager Script

**File**: `plugins/dev/skills/devops/scripts/merge_lock.py`

A CLI tool with 5 subcommands:

| Command | Purpose | Exit Code |
|---------|---------|-----------|
| `acquire --tool <name> --branch <branch> [--wait N]` | Acquire lock or wait | 0=acquired, 1=blocked |
| `release --tool <name>` | Release lock (owner-checked) | 0=released, 1=denied |
| `status` | Check lock state | 0=unlocked, 1=locked, 2=stale |
| `update --tool <name> --step <desc>` | Update progress step | 0=updated |
| `break-lock` | Force-clear stuck lock | 0=cleared |

**Lock file format** (JSON):
```json
{
  "tool": "claude-code",
  "pid": 12345,
  "ppid": 67890,
  "branch": "main",
  "step": "step-4: merge-into-main",
  "acquired_at": "2026-03-03T10:00:00+00:00"
}
```

**Design decisions**:
- **Timeout-based staleness** (30 min), not PID-based. AI agents spawn short-lived Python processes per command — the acquiring PID exits immediately while the agent continues working. PID liveness is the wrong signal for agent workflows.
- **`fcntl.flock()`** for atomic acquire — prevents two tools from acquiring simultaneously during the check-and-set window.
- **Atomic writes** via temp file + `os.rename()` — prevents partial reads if another process checks status mid-write.
- **Owner-checked release** — only the tool name that acquired the lock can release it, preventing accidental cross-tool release.
- **No queue** — if locked, the agent is instructed to inform the user and wait or abort. Queuing is unnecessary since agents are interactive and can retry.

### 2. SKILL.md Integration

**File**: `plugins/dev/skills/devops/commands/dev-merge/SKILL.md`

Added two steps:

- **Step 0: Acquire merge lock** — before any git operations, acquire the lock. If `LOCKED:`, stop and inform the user with holder details.
- **Step 10: Release merge lock** — always release, even on early failure. Added to Safety Rules as mandatory.

Progress tracking via `update --step` lets other tools see which step the current merge is on (e.g., "step-4: merge-into-main").

## Consequences

**Positive**:
- Eliminates race conditions when running `/dev-merge` from multiple IDE tools simultaneously
- Progress visibility — any tool can run `status` to see what the current merge is doing
- 30-minute auto-expire prevents permanently stuck locks from crashed sessions
- Zero external dependencies — pure Python stdlib (`fcntl`, `json`, `os`)

**Negative**:
- Agents must remember to release locks on failure paths (mitigated by explicit Step 10 instruction)
- 30-minute stale timeout means a genuinely long merge blocks others for up to 30 minutes

**Neutral**:
- Lock file lives in `runtime/` (already gitignored) — no repo pollution
- Pattern consistent with existing `instance_lock.py` for MCP and `worktree_registry.yaml` for worktrees

## Implementation Order

```
Phase 1: Lock Manager (DONE)
├── Step 1: Create merge_lock.py with 5 subcommands
├── Step 2: Test lifecycle (acquire → status → update → contention → release)
└── Step 3: Verify atomic acquire prevents simultaneous lock grants

Phase 2: SKILL.md Integration (DONE)
├── Step 4: Add Step 0 (acquire) to SKILL.md
├── Step 5: Add Step 10 (release) to SKILL.md
└── Step 6: Update Safety Rules

Phase 3: Verification (DONE)
├── Step 7: Full lifecycle test (8 scenarios, all pass)
└── Step 8: Contention test (cursor blocked while claude-code holds)
```

## Alternatives Considered

1. **PID-based liveness check** (like `instance_lock.py`): Rejected because AI agent workflows spawn short-lived Python processes — the acquiring PID exits immediately, making PID liveness always report "stale."

2. **Queue-based system** (JSONL append queue like `post_exec_queue.jsonl`): Rejected as over-engineering. Dev-merge is an interactive command — agents can inform the user and retry. A queue implies background processing which doesn't match the interactive workflow.

3. **Git's own lock mechanism** (`git lock` / `.git/index.lock`): Rejected because git locks are per-operation, not per-workflow. A dev-merge spans multiple git operations (stash, checkout, merge, push) and needs a higher-level lock.

## References

- `src/mcp/augur_mcp/instance_lock.py` — PID-based instance lock pattern (reference implementation)
- `runtime/adaptive/post_exec_queue.jsonl` — JSONL IPC pattern (considered but rejected)
- `runtime/worktree_registry.yaml` — existing gitignored runtime state file

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-195: Dev-Merge Concurrency Lock**.

Read the full ADR: `docs/decisions/ADR-195-dev-merge-concurrency-lock.md`

### Team Orchestration

This ADR is already fully implemented. No team orchestration needed.

### Execution Plan

**Status**: All phases complete. Implementation was done inline during the debugging session that identified the race condition.

#### Phase 1: Lock Manager (COMPLETE)
| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create merge_lock.py with acquire/release/status/update/break-lock commands | `plugins/dev/skills/devops/scripts/merge_lock.py` |

#### Phase 2: SKILL.md Integration (COMPLETE)
| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | low | Add Step 0 (acquire lock) and Step 10 (release lock) to SKILL.md | `plugins/dev/skills/devops/commands/dev-merge/SKILL.md` |
| 2.2 | developer | low | Update Safety Rules with lock mandate | `plugins/dev/skills/devops/commands/dev-merge/SKILL.md` |

#### Phase 3: Verification (COMPLETE)
| Step | Agent | Tier | Task |
|------|-------|------|------|
| 3.1 | validator | low | Run 8-scenario lifecycle test (all passed) |
| 3.2 | validator | low | Verify contention blocking (cursor blocked while claude-code holds) |

### Completion Criteria
- [x] Lock manager script created and tested
- [x] SKILL.md updated with Step 0 and Step 10
- [x] 8 test scenarios pass (acquire, status, update, contention, wrong-tool-release, release, re-acquire, cleanup)
- [x] ADR status set to Accepted
