# AI Monitor Sidecar — Daemon-Embedded Runtime Monitoring

**Date:** 2026-03-22
**Status:** Draft
**Scope:** Daemon skill, self-heal pipeline, vault monitoring

## Problem

The self-heal pipeline detects runtime errors by scanning logs, then spawns separate headless LLM calls to classify and fix issues. This introduces latency (scan interval + LLM startup), cost (each fix spawns a new CLI session), and a multi-step pipeline (scan → dedup → classify → route → fix) that could be short-circuited if an LLM were already running and watching.

`/dev-build --watch` proved the pattern: running a process inside an AI client session enables real-time monitoring and fixing without separate LLM invocations.

## Solution

Add a new managed child service to `unified_daemon.py`: an **AI Monitor Sidecar**. The daemon spawns an AI client session (Claude Code, Codex, Gemini — user-configurable) running `/daemon --monitor`. The AI session calls a watcher script that uses watchdog to observe daemon stderr logs, self-heal events, and the vault repo. When actionable errors appear, the AI investigates and fixes immediately — no headless subprocess spawn needed.

## Architecture

### Two-Process Model

The sidecar is actually two collaborating processes:

```
unified_daemon.py (launchd parent)
├── ... (11 existing children, all Python scripts via PYTHON binary)
└── ai_monitor_sidecar         ← AI client process (claude/codex/gemini binary)
       │
       └── calls via Bash tool:
           python3 ai_monitor_watcher.py --wait-for-event
           (blocks until actionable error detected, outputs structured event, exits)
```

**Why two processes:** An AI client session is prompt-in/response-out — it runs tools (Read, Edit, Bash), it does not run a persistent Python event loop. The watcher script runs the watchdog loop and filtering, the AI client consumes its output and acts.

**The AI's loop:**
1. AI starts with `/daemon --monitor` prompt
2. AI calls Bash: `python3 ai_monitor_watcher.py --wait-for-event`
3. Watcher blocks until actionable error detected (watchdog + filtering)
4. Watcher outputs structured error summary (50-100 tokens) and exits
5. AI reads output, investigates, fixes using tools (Read, Edit, Bash, Grep, Glob)
6. AI updates registry: `python3 ai_monitor_watcher.py --record-fix --key <dedup_key>`
7. AI commits with `fix(self-heal):` prefix
8. AI calls watcher again → goto 3
9. Between errors, the watcher is blocking — AI is idle, no token cost

### Daemon Integration

The sidecar uses a new `AISidecarManager` class, not the existing `SubprocessManager`. They share restart/backoff logic but differ in spawn mechanics:

| Aspect | SubprocessManager (children 1-11) | AISidecarManager (child 12) |
|--------|-----------------------------------|---------------------------|
| Binary | `PYTHON` (project venv) | AI CLI binary (claude/codex/gemini) |
| Arguments | `[script.py] + args` | Client-specific flags via `build_sidecar_cmd()` (see below) |
| Failure modes | Script crash, import error | API rate limit, auth expiry, context exhaustion |
| Health check | Process alive (poll) | Process alive + context pressure byte tracking |
| Restart trigger | Crash only | Crash OR context pressure threshold |
| Stderr logging | To `stderr/{name}.stderr.log` | To `stderr/ai_monitor.stderr.log` (AI client debug output, NOT monitored by the sidecar itself to avoid feedback loop) |

`AISidecarManager` inherits: restart count tracking, consecutive failure tracking, exponential backoff, max restart limit. These are extracted from `SubprocessManager` into a shared base or mixin.

### `build_sidecar_cmd()` — Interactive Session Invocation

`build_headless_cmd()` in `llm_retry.py` injects `--print` (output_mode) which makes the CLI run as a one-shot non-interactive command. The sidecar needs a persistent interactive session where the AI can call tools in a loop.

A new `build_sidecar_cmd()` function in `llm_retry.py` builds the invocation without output_mode flags:

```python
def build_sidecar_cmd(cli_path: str, prompt: str, **kwargs) -> list[str]:
    """Build CLI command for persistent interactive sidecar session.

    Like build_headless_cmd() but omits --print/output_mode flags,
    producing a long-running interactive session.
    """
    # Uses same profile resolution but skips output_mode
    # Includes: bypass_approvals, allowed_tools, model
    # Excludes: --print, --output-format, max_turns (session runs indefinitely)
```

Per-client invocation:
- Claude Code: `claude -p "/daemon --monitor" --dangerously-skip-permissions --allowedTools Read,Edit,Bash,Grep,Glob,Write`
- Codex: `codex --full-auto --prompt "/daemon --monitor"`
- Gemini: `gemini --prompt "/daemon --monitor"` (adapter resolves flags)

### Startup Flow

1. `unified_daemon.py` starts all 11 existing children as today
2. Attempts to resolve default AI client:
   ```python
   try:
       cli_path = resolve_cli()
   except RuntimeError:
       logger.warning("No AI client available, skipping sidecar")
       return  # Standalone mode — today's behavior
   ```
3. Builds command via `build_sidecar_cmd(cli_path, "/daemon --monitor", ...)`
4. Spawns via `AISidecarManager`
5. Periodic health check retries `resolve_cli()` if sidecar is not running (client installed later)

### Connection Model — File-Based, No IPC

The watcher script (not the AI directly) reads child service output artifacts via watchdog:

```
Child Services                    Filesystem                         ai_monitor_watcher.py
─────────────                     ──────────                         ─────────────────────
All 11 services           stderr→ ~/Library/Logs/Augur/daemon/       ←── watchdog observer
                                    stderr/{service}.stderr.log

emit_heal_event()        events→ ~/...state/self_heal_events.jsonl   ←── watchdog observer

unified_daemon.py        status→ ~/...state/stats/daemon_status.json ←── watchdog observer

get_vault_dir()/            git/fs→ (repo on disk)                     ←── watchdog observer
```

Zero coupling — child services don't know the sidecar exists.

**Feedback loop prevention:** The watcher explicitly excludes `stderr/ai_monitor.stderr.log` from its watch list. The AI client's own debug output is never monitored.

### Watchdog Setup (inside ai_monitor_watcher.py)

Uses the `watchdog` library (already used by `note_watcher.py`) with 2-second debounce:

- `~/Library/Logs/Augur/daemon/stderr/` — child service stderr logs (excluding `ai_monitor.stderr.log`)
- `~/Library/Application Support/Augur/state/` — events JSONL, registry, daemon status
- `get_vault_dir()/` — vault repo changes (`.md`, `.yaml`, `.json` only; ignores `.git/`, binaries)
- Polling fallback if watchdog unavailable

## The `ai_monitor_watcher.py` Script

A Python CLI tool the AI calls via Bash. Six modes:

### `--wait-for-event [--timeout SECONDS]`

Blocks until an actionable error is detected OR timeout expires. Outputs a structured JSON event and exits.

If `--timeout 300` is specified and no actionable error occurs within 300 seconds, exits with an empty event (`{"type": "timeout"}`). This allows the AI to periodically run `--vault-check` between waits:

```
AI loop:
  1. call --wait-for-event --timeout 300
  2. if timeout → call --vault-check → goto 1
  3. if error event → investigate, fix, record → goto 1
```

Event output format:

```json
{
  "source": "dashboard_monitor",
  "type": "daemon_stderr",
  "error": "TypeError: Cannot read property 'status' of undefined",
  "file": "src/mcp/augur_mcp/server.py:142",
  "stack_trace": "...",
  "occurrences": 3,
  "severity": "high",
  "dedup_key": "abc123"
}
```

**Internal pipeline (all happens before the AI sees anything):**
1. Watchdog event fires (file changed)
2. Read only NEW lines since byte-offset watermark
3. Run `patterns.py` pre-classification — ~95% of stderr is noise, killed here
4. Dedup against `self_heal_registry.json` — repeated/fixed errors dropped
5. If actionable → output structured event and exit
6. If not actionable → continue waiting

**Vault events** output similarly but with `"type": "vault"` and vault-specific fields.

### `--acquire-lock --key <dedup_key>`

Called by the AI before starting a fix. The watcher process stays alive as the lock holder:
```bash
python3 ai_monitor_watcher.py --acquire-lock --key <dedup_key> &
# PID of this process is written to FIX_LOCK_FILE
# Process stays alive until --release-lock is called or it's killed
```
The lock PID is this long-lived watcher process, not a short-lived subprocess. `_pid_alive()` in `fixers.py` correctly detects it as alive while the AI is working.

### `--release-lock`

Called by the AI after fixing (or aborting):
```bash
python3 ai_monitor_watcher.py --release-lock
```
Kills the lock holder process and removes `FIX_LOCK_FILE`.

### `--record-fix`

Called by the AI after fixing an issue:
```bash
python3 ai_monitor_watcher.py --record-fix --key <dedup_key> --status fixed --commit <hash>
```
Updates `self_heal_registry.json` so the scanner and watcher both know the issue is resolved.

### `--vault-check`

On-demand vault health check (called by AI every 5min via its own loop):
```bash
python3 ai_monitor_watcher.py --vault-check
```
Runs: git status, frontmatter validation on recently changed files, conflict marker scan. Outputs actionable findings or empty JSON if clean.

### `--status`

Returns current monitoring state for the AI to bootstrap after a fresh start or restart:
```bash
python3 ai_monitor_watcher.py --status
```
Outputs JSON with: daemon service health (from `daemon_status.json`), pending issues in registry, recent fix history, current watermark positions. The AI calls this once on startup before entering the monitoring loop.

## The `/daemon --monitor` Skill

New mode added to the existing daemon skill. The skill prompt instructs the AI to:

1. Read initial state: `python3 ai_monitor_watcher.py --status` (current registry, daemon health)
2. Enter monitoring loop:
   ```
   loop:
     event = call --wait-for-event --timeout 300
     if event.type == "timeout":
       vault_issues = call --vault-check
       if vault_issues: fix in get_vault_dir()/, commit with "fix(vault):" prefix
       goto loop
     if event.type == "daemon_stderr" or "heal_event":
       call --acquire-lock --key <dedup_key>     # long-lived lock holder
       investigate source files, fix
       commit with "fix(self-heal):" prefix
       call --record-fix --key <dedup_key> --status fixed --commit <hash>
       call --release-lock
       goto loop
   ```
3. Track fix count — after N fixes, estimate context usage and decide whether to continue or exit cleanly for restart

### What the skill does NOT do:

- Does not replace the adaptive loop engine (nightly scans still run independently)
- Does not replace dashboard_monitor (health checks/auto-restart still via launchd)
- Does not run classification LLM calls — it IS the LLM

## Lean Monitoring — Token Efficiency

Raw daemon output never reaches the AI. The watcher script handles all filtering:

```
Layer 1: watchdog event fires (file changed)              ← watcher
Layer 2: Read only NEW lines (byte-offset watermark)      ← watcher
Layer 3: patterns.py pre-classification (~95% noise)      ← watcher
Layer 4: Dedup against registry                           ← watcher
Layer 5: Format COMPACT JSON event (~50-100 tokens)       ← watcher
Layer 6: AI receives clean, structured event              ← AI client
```

**Token cost per error:** ~600-2,100 tokens (50-100 delivery + 500-2,000 investigation/fix).
**Without lean filtering:** 10,000+ tokens just to deliver the same error.

### Context Pressure Management

The `AISidecarManager` in the daemon tracks context pressure by monitoring the AI client process lifetime and fix count:

```python
# In AISidecarManager
PRESSURE_THRESHOLD = 500_000  # ~125k tokens

def _check_context_pressure(self):
    """Estimate context usage from sidecar's activity."""
    state = self._read_sidecar_state()  # reads from state file
    if state.get("bytes_outputted", 0) >= PRESSURE_THRESHOLD:
        if not self._fix_lock_held():  # never kill mid-fix
            self._restart_sidecar()
```

The watcher script tracks cumulative bytes it has outputted across invocations in a state file (`~/...state/ai_monitor_bytes.json`), written atomically (write-to-temp-then-rename) to prevent partial reads. The daemon reads this file to estimate context pressure.

**Why restart instead of `/clear`:** `/clear` is client-specific (Claude Code supports it, Codex/Gemini may not). Process restart is client-agnostic and guaranteed clean.

**Restart safety:** Before killing the sidecar, the daemon checks `FIX_LOCK_FILE`. If the lock is held (AI is mid-fix), the restart is deferred. The daemon polls the lock every 10s until released, with a hard timeout of 5 minutes (after which it force-kills — the lock's 10-minute staleness check in `fixers.py` will clean it up).

**What survives restart:** Registry, watermarks, daemon status, git history, byte counter (reset to 0).
**What's lost:** Conversational flow (recovered by reading state files on startup via `--status`).

## Fallback Behavior

When the sidecar is unavailable, the system works identically to today:

| Scenario | Behavior |
|----------|----------|
| AI client not installed | `resolve_cli()` raises RuntimeError. Caught, logged. Sidecar never starts. |
| API key expired / rate limited | Sidecar process exits. `AISidecarManager` restarts with backoff. |
| Sidecar crashes | `AISidecarManager` restarts. Max restarts exhausted → standalone mode. |
| `ai_monitor.enabled: false` | Sidecar never starts. |

**Fallback means:** Self-heal pipeline runs as today (scan → classify via headless LLM → fix via headless LLM). Zero code changes to existing services.

### No Dual-Fix Conflicts

Both paths use the same `FIX_LOCK_FILE`:
- AI sidecar acquires lock via `--acquire-lock` (long-lived watcher process holds the lock, PID is alive) → AI fixes → `--release-lock`
- `fixers.py` tries concurrently → lock held, PID alive → skips
- Sidecar down → `fixers.py` acquires lock normally → headless fix as today
- Sidecar restarted mid-fix → lock holder process is killed → `_pid_alive()` detects dead PID → `fixers.py` cleans up stale lock

Sidecar also updates `self_heal_registry.json` via `--record-fix`, preventing re-classification by the scanner.

### Scanner/Classifier Interaction

The scanner (`scanner.py`) continues running and populating the registry regardless of sidecar state. When the sidecar IS running:
- Scanner finds an error → adds to registry with status `detected`
- Watcher sees the same error via watchdog → checks registry → already `detected` → presents to AI
- AI fixes → records as `fixed` in registry via `--record-fix`
- Scanner's next pass sees `fixed` status → skips

When the sidecar is NOT running:
- Scanner finds error → adds to registry → pipeline classifies and fixes as today

No modification to `scanner.py` needed. The registry is the coordination point.

## Relationship to Existing Self-Heal Pipeline

| Component | With sidecar running | Without sidecar (fallback) |
|-----------|---------------------|---------------------------|
| `scanner.py` | Still runs, populates registry | Still runs, populates registry |
| `patterns.py` | Used by watcher for pre-filtering | Used by scanner for classification |
| `classifier.py` | Skipped — AI classifies directly | Runs, spawns headless LLM |
| `fixers.py` | Skipped — AI fixes directly | Runs, spawns headless LLM |
| `registry.py` | Updated by watcher's `--record-fix` | Updated by pipeline after fix |
| `emit_heal_event()` | Watcher reads events via watchdog | Pipeline reads events via scan |

## Vault Monitoring Details

### Checks

| Check | Trigger | Action |
|-------|---------|--------|
| Git conflicts | Watchdog: file with conflict markers (`<<<<<<<`) | Resolve conflicts, commit |
| Broken frontmatter | Watchdog: `.md` file changed | Validate YAML frontmatter, fix if malformed |
| Stale refs | Every 5min via `--vault-check` | Check recently changed files (last 5min only) reference valid paths |
| Uncommitted changes | Every 5min via `--vault-check` | `git status` — only auto-commit files matching `data/**`, `memory/**` patterns |
| Large untracked files | Every 5min via `--vault-check` | Flag files >1MB via notification, do not auto-commit |

### Guard Rails

- **Auto-commit scope:** Only `data/` and `memory/` subdirectories. User-edited files (ADRs, notes) are never auto-committed.
- **Commit message format:** `fix(vault): auto-save <N> changed files in <subdirs>` with file list in commit body.
- **Respects `.gitignore`:** Untracked files not in `.gitignore` are flagged, not committed.
- **Opt-out:** Set `vault_auto_commit: false` in config to disable auto-commits.
- **Stale ref check bound:** Only checks files modified in the last 5 minutes, not full vault scan.

## Configuration

```yaml
# config/system/daemon.yaml (NEW FILE — must be created)
ai_monitor:
  enabled: true
  context_pressure_bytes: 500000   # ~125k tokens, trigger restart
  debounce_seconds: 2
  vault_check_interval: 300        # vault checks every 5min
  vault_auto_commit: true          # auto-commit data/memory changes
  vault_auto_commit_paths:         # only these vault subdirs
    - "data/**"
    - "memory/**"
```

## Platform Notes

The spec references macOS paths (`~/Library/Logs/`, `~/Library/Application Support/`). These are resolved via `src.config.paths` at runtime. On non-macOS platforms, equivalent XDG paths are used. The child service count is 11 on macOS (includes `note_watcher`, `note_ingest`) and 9 on other platforms.

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `skills/daemon/scripts/ai_monitor_watcher.py` | Create | Watcher script (watchdog, filtering, event output, registry updates) |
| `skills/daemon/scripts/ai_monitor_sidecar.py` | Create | `AISidecarManager` class (spawn AI client, context pressure tracking) |
| `skills/daemon/scripts/unified_daemon.py` | Modify | Import and start `AISidecarManager` as child #12 |
| `skills/daemon/SKILL.md` | Modify | Add `--monitor` mode documentation |
| `config/system/daemon.yaml` | Create | New config file for `ai_monitor` settings |
| `src/lib/llm_retry.py` | Modify | Add `build_sidecar_cmd()` function for interactive session invocation |
| `skills/daemon/scripts/self_heal/patterns.py` | No change | Imported by watcher for pre-filtering |
| `skills/daemon/scripts/self_heal/fixers.py` | No change | Fix lock mechanism reused as-is |
| `skills/daemon/scripts/self_heal/scanner.py` | No change | Registry coordination, no code changes |
