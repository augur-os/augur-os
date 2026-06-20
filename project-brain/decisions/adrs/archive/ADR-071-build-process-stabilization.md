---
status: Implemented
date: '2026-02-11'
deciders:
- Augur Team
related:
- ADR-041 (Daemon Production Monitoring)
- ADR-065 (Dashboard Hardening Workflow)
hub: null
tags:
- build
- process
- stabilization
- concurrent
- build
superseded_by: null
---

# ADR-071: Build Process Stabilization — Concurrent Build Protection

## Context

The dashboard build process (`npm run build` / `npm run dev`) is unstable when multiple terminals or agents operate on the same codebase concurrently. This is a daily reality given the workspace setup:

- **mprocs** runs 8 autonomous agents + 5 manual shell slots, all sharing the same repo
- The **daemon** runs `dashboard_monitor.py` in a persistent loop, which can trigger recovery builds
- Manual `npm run build` or `npm run dev` from any terminal can conflict with the above

### The ENOENT Problem

The specific recurring failure is:

```
Error: ENOENT: no such file or directory, open '.next/static/<buildId>/_buildManifest.js.tmp.<random>'
```

**Root cause**: Two processes write to `.next/` simultaneously. Process A creates a temp file, Process B runs `rm -rf .next` (line 33 of `build.sh`), Process A tries to finalize the temp file — ENOENT. This also happens when the background manifest watcher in `build.sh` (lines 37-70) writes files that Next.js is concurrently creating/deleting.

### Current Guards (Insufficient)

| Guard | Location | Gap |
|-------|----------|-----|
| `pgrep -f "next build"` | `dashboard_monitor.py:124` | Doesn't cover prebuild steps (`mount-plugins`, `generate-registry`), dev server starts, or the `rm -rf .next` cleanup phase |
| `dashboard_rebuild.lock` | `dashboard_monitor.py:188` | Only created during daemon recovery — manual `npm run build` doesn't create it |
| Kill dev server before build | `build.sh:24-30` | Only kills dev, not other build processes |
| `rm -rf .next` before build | `build.sh:32-35` | Destructive to concurrent builds — the primary ENOENT trigger |

### No Build-Level Mutual Exclusion

There is zero coordination between:
- Terminal A running `npm run build`
- Terminal B running `npm run build`
- Terminal C running `npm run dev`
- Daemon running `stage_restart()` or `stage_full_rebuild()`
- Prebuild steps (mount-plugins, generate-registry, generate-tabs) writing to src/lib directories

## Decision

Introduce a **filesystem-level build lock** using `flock(1)` (POSIX advisory locking) that wraps the entire build lifecycle — from prebuild through Next.js build/dev — with mutual exclusion. Additionally, harden the daemon to avoid unnecessary recovery when a build is genuinely in progress.

### 1. Build Lock via `flock`

Create a src/lib lock file at `data/runtime/locks/dashboard_build.flock` used by all build entry points.

**Why flock over JSON lock files**: `fcntl.flock()` is plugins/ai/skills/ai_bridge-managed, automatically released on process death (no stale locks), and supports blocking/non-blocking modes natively. The current JSON lock files in `dashboard_monitor.py` require manual stale-lock cleanup with a 5-minute timeout — `flock` eliminates this class of bugs entirely.

**Implementation note**: The lock wrapper is implemented in Python (`#!/usr/bin/env python3`) rather than bash because macOS does not ship with the `flock(1)` CLI tool. Python's `fcntl.flock()` provides identical plugins/ai/skills/ai_bridge-level locking and works on both macOS and Linux. The script retains the `.sh` extension for backward compatibility with existing references.

#### Lock wrapper script: `src/dashboard/scripts/build-lock.sh`

```bash
#!/bin/bash
# Build lock wrapper — ensures only one build/dev process runs at a time.
# Usage: ./scripts/build-lock.sh <command> [args...]
# Example: ./scripts/build-lock.sh npx next build
#          ./scripts/build-lock.sh ./node_modules/.bin/next dev --turbopack

set -uo pipefail

LOCK_DIR="${AUGUR_DATA:-$(cd "$(dirname "$0")/../../.." && pwd)/data}/runtime/locks"
mkdir -p "$LOCK_DIR"
LOCK_FILE="$LOCK_DIR/dashboard_build.flock"

# How long to wait for the lock before giving up (seconds)
LOCK_TIMEOUT="${BUILD_LOCK_TIMEOUT:-300}"

echo "Acquiring build lock (timeout: ${LOCK_TIMEOUT}s)..."

# Open the lock file descriptor
exec 9>"$LOCK_FILE"

# Try to acquire exclusive lock with timeout
if ! flock -w "$LOCK_TIMEOUT" 9; then
  echo "ERROR: Could not acquire build lock after ${LOCK_TIMEOUT}s."
  echo "Another build process is running. Use 'lsof $LOCK_FILE' to find it."
  exit 1
fi

echo "Build lock acquired (PID: $$)"

# Write PID + metadata for observability (lock is already held)
cat > "$LOCK_FILE.meta" <<LOCKEOF
{"pid": $$, "started": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "command": "$*"}
LOCKEOF

# Clean up metadata on exit (lock auto-releases when fd 9 closes)
cleanup() {
  rm -f "$LOCK_FILE.meta"
}
trap cleanup EXIT

# Execute the actual command
exec "$@"
```

**Key properties**:
- **Automatic release**: If the process dies (kill, crash, OOM), the plugins/ai/skills/ai_bridge releases the flock
- **No stale locks**: Unlike JSON lock files, there's no 5-minute timeout to manage
- **Blocking with timeout**: Concurrent builds queue up and wait (up to 5 min), rather than silently failing
- **Observable**: `.flock.meta` file shows who holds the lock (but isn't the lock itself)
- **`exec` at the end**: The locked command replaces the shell, so the lock is held for exactly the command's lifetime

### 2. Updated `build.sh`

Wrap the entire build (including `rm -rf .next` and the manifest watcher) inside the lock:

```bash
#!/bin/bash
# Build wrapper for Next.js 16 — runs under build lock.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DASHBOARD_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
NEXT_DIR="$DASHBOARD_DIR/.next"
SERVER_DIR="$NEXT_DIR/server"

cd "$DASHBOARD_DIR"

# Kill any running dev server to avoid ENOTEMPTY on .next/server
DEV_PIDS=$(pgrep -f "next dev.*--turbopack" 2>/dev/null || true)
if [ -n "$DEV_PIDS" ]; then
  echo "Stopping running dev server (PIDs: $DEV_PIDS)..."
  echo "$DEV_PIDS" | xargs kill 2>/dev/null || true
  sleep 1
fi

# Clean .next directory (safe — we hold the lock)
if [ -d "$NEXT_DIR" ]; then
  rm -rf "$NEXT_DIR"
fi

# Background watcher: pre-create missing manifests for Turbopack
# [existing watcher logic unchanged]
(
  while true; do
    if [ -d "$SERVER_DIR" ] && [ ! -f "$SERVER_DIR/pages-manifest.json" ]; then
      echo '{}' > "$SERVER_DIR/pages-manifest.json"
    fi
    if [ -d "$SERVER_DIR" ] && [ ! -f "$SERVER_DIR/app-paths-manifest.json" ]; then
      echo '{}' > "$SERVER_DIR/app-paths-manifest.json"
    fi
    if [ -d "$NEXT_DIR" ] && [ ! -f "$NEXT_DIR/build-manifest.json" ]; then
      echo '{"pages":{}}' > "$NEXT_DIR/build-manifest.json"
    fi
    if [ -d "$NEXT_DIR" ] && [ ! -f "$NEXT_DIR/required-server-files.json" ]; then
      echo '{"version":1,"config":{},"appDir":true,"files":[],"ignore":[]}' > "$NEXT_DIR/required-server-files.json"
    fi
    if [ -d "$NEXT_DIR/static" ]; then
      for chunk_dir in $(find "$NEXT_DIR/static" -maxdepth 1 -mindepth 1 -type d 2>/dev/null); do
        if [ ! -f "$chunk_dir/_buildManifest.js" ]; then
          echo 'self.__BUILD_MANIFEST={};self.__BUILD_MANIFEST_CB&&self.__BUILD_MANIFEST_CB()' > "$chunk_dir/_buildManifest.js"
        fi
        if [ ! -f "$chunk_dir/_ssgManifest.js" ]; then
          echo 'self.__SSG_MANIFEST=new Set;self.__SSG_MANIFEST_CB&&self.__SSG_MANIFEST_CB()' > "$chunk_dir/_ssgManifest.js"
        fi
      done
    fi
    sleep 0.1
  done
) &
WATCHER_PID=$!

cleanup() {
  kill $WATCHER_PID 2>/dev/null
  wait $WATCHER_PID 2>/dev/null
}
trap cleanup EXIT

npx next build
```

**Change**: The `npm run build` script in `package.json` becomes:
```json
"build": "./scripts/build-lock.sh ./scripts/build.sh"
```

The prebuild step already runs sequentially before build, and because `npm run build` calls prebuild first then build, the lock wraps the actual Next.js build. However, prebuild output (mounted plugins, generated registries) is also a src/lib resource.

### 3. Prebuild Lock

The prebuild pipeline (`mount-plugins`, `generate-registry`, `generate-tabs`) writes to src/lib directories (`src/dashboard/app/`, `src/dashboard/lib/tabs/`). These must also be locked.

Update `package.json`:
```json
"prebuild": "npm run build:scripts && ./scripts/build-lock.sh sh -c 'npm run setup-mcp && npm run generate-registry && npm run mount-plugins && npm run generate-tabs'",
"build": "./scripts/build.sh"
```

Wait — this won't work because npm runs prebuild then build as separate processes. Instead, wrap the entire `npm run build` invocation:

**External callers** (agents, daemon, manual) should use:
```bash
./scripts/build-lock.sh npm run build
```

This locks the entire lifecycle: prebuild → build → exit.

Update `package.json` for the common case:
```json
"build": "./scripts/build.sh",
"build:safe": "./scripts/build-lock.sh npm run build"
```

### 4. Dev Server Lock

`start-dev.sh` also needs the lock, but with different semantics — the dev server runs indefinitely, so it should hold the lock only during startup (prebuild + initial compilation), then release.

Updated `start-dev.sh`:
```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Run prebuild under lock (prevents concurrent prebuild races)
"$SCRIPT_DIR/build-lock.sh" sh -c '
  node scripts/build-scripts.mjs
  node scripts/dist/setup-mcp.mjs
  python3 scripts/generate_registry.py
  node scripts/dist/mount-plugins.mjs
  node scripts/dist/generate-tab-registry.mjs
'

# Dev server runs unlocked (long-lived, HMR handles file changes)
if [ ! -f "./node_modules/.bin/next" ]; then
    echo "Error: next binary not found. Run: npm install"
    exit 1
fi

echo "Starting Next.js..."
./node_modules/.bin/next dev --turbopack
```

### 5. Daemon Recovery Hardening

Update `dashboard_monitor.py` to:

1. **Check the flock before recovery** — if the lock is held, another process is already building
2. **Use the flock for its own recovery builds** — acquire lock before running recovery stages
3. **Remove redundant JSON lock management** — flock replaces the manual lock protocol for build coordination

```python
def is_build_lock_held() -> bool:
    """Check if another process holds the build flock."""
    lock_file = get_locks_dir() / "dashboard_build.flock"
    if not lock_file.exists():
        return False
    try:
        import fcntl
        fd = os.open(str(lock_file), os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Got the lock — nobody else has it
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        except (IOError, OSError):
            # Lock is held by another process
            return True
        finally:
            os.close(fd)
    except FileNotFoundError:
        return False
```

Update `is_rebuild_in_progress()` to add flock as Layer 0 (before process detection):

```python
def is_rebuild_in_progress() -> bool:
    # Layer 0: Build flock — plugins/ai/skills/ai_bridge-managed, never stale
    if is_build_lock_held():
        logger.info("Build flock held by another process")
        return True

    # Layer 1: Process detection (existing)
    if is_build_process_running():
        return True

    # Layer 2: JSON lock files (existing, for non-build operations)
    # ... existing lock file logic ...
```

Update recovery stages to acquire the flock:

```python
def run_recovery(max_attempts=None):
    """Run recovery under build lock."""
    dashboard_dir = get_dashboard_dir()
    lock_script = dashboard_dir / "scripts" / "build-lock.sh"

    # If lock script exists, use it; otherwise fall back to direct execution
    if lock_script.exists():
        # Recovery commands run through the lock wrapper
        # e.g., stage_restart spawns: build-lock.sh npm run dev
        ...
```

### 6. Observability

The `.flock.meta` sidecar file enables monitoring:

```python
def get_build_lock_info() -> dict | None:
    """Read build lock metadata (who holds it, since when)."""
    meta_file = get_locks_dir() / "dashboard_build.flock.meta"
    if meta_file.exists():
        try:
            return json.loads(meta_file.read_text())
        except Exception:
            return None
    return None
```

The daemon status output (`dashboard_status.json`) gains a `build_lock` field:

```json
{
  "running": true,
  "pids": [12345],
  "rebuild_in_progress": false,
  "build_lock": {"pid": 67890, "started": "2026-02-11T10:30:00Z", "command": "npm run build"},
  "checked_at": "2026-02-11T10:31:00Z",
  "mode": "production"
}
```

## Consequences

### Positive

- **Eliminates ENOENT race conditions** — only one build touches `.next/` at a time
- **Automatic stale lock cleanup** — plugins/ai/skills/ai_bridge releases flock on process death, no 5-minute timeout hacks
- **Queue semantics** — concurrent builds wait instead of failing or corrupting each other
- **Daemon stops false-positive recovery** — flock check prevents recovery during active builds
- **Backward compatible** — `npm run build` still works (just without protection); `npm run build:safe` or direct `build-lock.sh` adds protection
- **Observable** — `.flock.meta` sidecar shows who holds the lock

### Negative

- **macOS/Linux only** — `flock(1)` is POSIX; not available on Windows (acceptable — Augur is macOS-first per ADR-049)
- **5-minute timeout** — if a build legitimately takes >5 min, queued builds may fail (configurable via `BUILD_LOCK_TIMEOUT`)
- **Adds shell wrapper** — one more indirection layer in the build chain

### Neutral

- Existing JSON lock files in `dashboard_monitor.py` remain for non-build operations (reload, recovery signaling)
- `prebuild` npm script unchanged — the lock is applied at the outer invocation level
- The manifest watcher in `build.sh` is unchanged — it runs safely under the lock

## Implementation Order

```
Phase 1: Build Lock Infrastructure
├── Step 1: Create build-lock.sh wrapper script
├── Step 2: Update build.sh to remove redundant dev-kill logic when lock is held
└── Step 3: Add build:safe script to package.json

Phase 2: Entry Point Integration
├── Step 4: Update start-dev.sh to lock prebuild phase
├── Step 5: Update daemon recovery stages to use flock
└── Step 6: Add is_build_lock_held() to dashboard_monitor.py

Phase 3: Observability
├── Step 7: Add build_lock field to dashboard_status.json output
└── Step 8: Add lock info to daemon /api/services status endpoint

Phase 4: Verification
├── Step 9: Test concurrent builds (two terminals, both run npm run build:safe)
├── Step 10: Test daemon recovery doesn't trigger during active build
└── Step 11: Test stale lock auto-release (kill -9 build process, verify lock freed)
```

## Alternatives Considered

### Alternative 1: PID File with Stale Detection

**Approach**: Write PID to a file, check if PID is alive before building.
**Rejected**: This is what the current JSON lock files do, with a 5-minute stale timeout. It's fragile — process can die without cleanup, and timeout-based stale detection is a source of bugs. `flock` eliminates all of this.

### Alternative 2: npm Concurrency Plugin (`npm-run-all --serial`)

**Approach**: Use npm scripts to serialize builds.
**Rejected**: Only works within a single `npm run` invocation. Doesn't protect against multiple terminals running `npm run build` independently.

### Alternative 3: Port-Based Detection (Broader `pgrep`)

**Approach**: Expand `pgrep` patterns to catch prebuild processes too.
**Rejected**: Brittle — process names change across Node versions and tools. `flock` is a positive lock (held = locked) rather than a heuristic detection (matching process names).

### Alternative 4: `.next/lock` File (Next.js Internal)

**Approach**: Check for `.next/dev/lock` which Next.js creates during dev.
**Rejected**: Only exists during dev server, not during `next build`. Doesn't cover prebuild steps. Internal implementation detail that may change.

## References

- ADR-041: Daemon Production Monitoring & Self-Healing
- ADR-049: Zero-Technical Onboarding (macOS first — justifies POSIX-only `flock`)
- ADR-065: Dashboard Hardening Workflow
- `flock(1)` man page: Advisory file locking via file descriptors
- `src/dashboard/scripts/build.sh` — current build wrapper
- `plugins/observability/skills/daemon/scripts/dashboard_monitor.py` — current recovery logic

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-071: Build Process Stabilization — Concurrent Build Protection**.

Read the full ADR: `docs/decisions/ADR-071-build-process-stabilization.md`

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
   - Accept (diff is correct): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict accept`
   - Fix (you patched the output): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict fix`
   - Escalate (offload failed, you did it yourself): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict escalate`
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself as normal

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-071-build-lock", description="Implementing ADR-071: Build Process Stabilization")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-071-build-lock", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-071-build-lock team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-071-build-lock`

#### Phase 1: Build Lock Infrastructure
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create `build-lock.sh` — flock-based lock wrapper with timeout, metadata sidecar, and cleanup trap | `src/dashboard/scripts/build-lock.sh` |
| 1.2 | developer | low | Update `build.sh` — remove the `rm -rf .next` guard (lock guarantees exclusion), keep manifest watcher | `src/dashboard/scripts/build.sh` |
| 1.3 | developer | low | Add `build:safe` script to `package.json` pointing to `./scripts/build-lock.sh npm run build` | `src/dashboard/package.json` |

#### Phase 2: Entry Point Integration (depends on Phase 1)
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Update `start-dev.sh` — wrap prebuild steps in `build-lock.sh`, leave dev server unlocked | `src/dashboard/scripts/start-dev.sh` |
| 2.2 | developer | medium | Add `is_build_lock_held()` to `dashboard_monitor.py`, update `is_rebuild_in_progress()` to check flock as Layer 0, update recovery stages to acquire lock | `plugins/observability/skills/daemon/scripts/dashboard_monitor.py` |

#### Phase 3: Observability (depends on Phase 2)
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | low | Add `build_lock` field to `get_dashboard_status()` and `write_status()` in `dashboard_monitor.py` | `plugins/observability/skills/daemon/scripts/dashboard_monitor.py` |
| 3.2 | devops | low | Update daemon services API to include build lock status in `/api/services` response | `plugins/observability/skills/daemon/dashboard/api/route.ts` |

#### Phase 4: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | validator | low | Run existing tests: `pytest tests/src/` and `cd src/dashboard && npm run build` — verify no regressions |  |
| 4.2 | validator | low | Test concurrent builds: run `npm run build:safe` in two parallel shells, verify second waits then succeeds |  |
| 4.3 | architect | low | Verify ADR-071 intent matches implementation — review all changed files against ADR sections |  |

### Completion Criteria
- [ ] `build-lock.sh` exists and is executable
- [ ] `npm run build:safe` acquires lock, runs prebuild + build, releases on exit
- [ ] Two concurrent `npm run build:safe` serialize correctly (second waits)
- [ ] `dashboard_monitor.py` checks flock before triggering recovery
- [ ] `kill -9` of locked build process releases the lock (plugins/ai/skills/ai_bridge guarantee)
- [ ] `npm run build` still works without lock (backward compatible)
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] ADR status updated to "Accepted"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-071-build-process-stabilization.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
