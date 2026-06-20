---
status: Implemented
date: 2026-03-22
deciders:
  - Gur Sannikov
related:
  - ADR-041
  - ADR-076
  - ADR-176
  - ADR-185
hub: adaptive
tags:
  - daemon
  - self-heal
  - monitoring
  - ai-client
superseded_by: null
---

# ADR-480: AI Monitor Sidecar — Daemon-Embedded Runtime Monitoring

## Context

The self-heal pipeline (ADR-076) detects runtime errors by polling logs, then spawns separate headless LLM calls to classify and fix issues. This introduces:

- **Latency**: scan interval (5min) + LLM startup per fix
- **Cost**: each fix spawns a new CLI session (context load + classification + fix attempt)
- **Indirection**: multi-step pipeline (scan → dedup → classify → route → fix) that could be short-circuited

`/dev-build --watch` proved a simpler pattern: run a process inside an AI client session so runtime errors are visible and fixable without separate LLM invocations.

The daemon already manages 9-11 child services via `SubprocessManager`. Adding an AI client as a 12th child — running a monitoring skill — enables real-time error detection and fixing with zero additional LLM spawn cost.

## Decision

### Two-Process Model

Add a new managed child service to `unified_daemon.py`: an **AI Monitor Sidecar**. The daemon spawns an AI client session (Claude Code, Codex, or Gemini — user-configurable via `llm_retry.resolve_cli()`) running `/daemon --monitor`.

The sidecar is two collaborating processes:
1. **AI client process** — runs the monitoring skill, investigates and fixes errors using tools
2. **Watcher script** (`ai_monitor_watcher.py`) — called by the AI via Bash tool, blocks on watchdog events, filters noise via `patterns.py`, returns structured JSON events

### `AISidecarManager` (not `SubprocessManager`)

A new `AISidecarManager` class manages the AI client process separately from existing children because:
- Different binary (AI CLI vs Python)
- Different invocation (`build_sidecar_cmd()` — interactive, no `--print`)
- Different failure modes (API rate limits, auth expiry, context exhaustion)
- Context pressure tracking (bytes counter → restart when threshold exceeded)
- Fix-lock awareness (never kill mid-fix)

### `build_sidecar_cmd()` in `llm_retry.py`

New function parallel to `build_headless_cmd()` that omits `--print` (output_mode), `--max-turns`, and `--no-session-persistence` — producing a long-running interactive session.

### Connection Model — File-Based, No IPC

The watcher reads child service output via watchdog filesystem events:
- `~/Library/Logs/Augur/daemon/stderr/*.stderr.log` — child service errors
- `~/Library/Application Support/Augur/state/self_heal_events.jsonl` — emit_heal_event() events
- `~/Vault/Augur/` — vault repo health (conflicts, broken frontmatter)

Zero coupling — child services don't know the sidecar exists.

### Lean Monitoring — Token Efficiency

Raw daemon output never reaches the AI. Six-layer filter pipeline in the watcher:
1. Watchdog event (file changed)
2. Read only NEW lines (byte-offset watermark)
3. `patterns.py` pre-classification (~95% noise filtered)
4. Dedup against `self_heal_registry.json`
5. Format compact JSON event (~50-100 tokens)
6. AI receives clean, structured event

Token cost per error: ~600-2,100 tokens (vs 10,000+ without filtering).

### Context Pressure Management

Watcher tracks cumulative bytes outputted to `ai_monitor_bytes.json`. Daemon reads this file; when threshold exceeded (default 500KB ~= 125k tokens), restarts the sidecar for a fresh context window. Fix lock checked before restart — never kills mid-fix.

### Graceful Fallback

When sidecar is unavailable (no AI client, API error, max restarts), existing self-heal pipeline runs as before (scan → classify via headless LLM → fix via headless LLM). No code changes to existing services.

### Dual-Fix Coordination

Both paths (sidecar and headless pipeline) share the same `FIX_LOCK_FILE`. Sidecar acquires lock via a long-lived child process (`--acquire-lock`); `_pid_alive()` in `fixers.py` correctly detects it. Registry updated after each fix to prevent re-classification.

### Vault Monitoring

The watcher also checks `~/Vault/Augur/` for:
- Git conflict markers in `data/` and `memory/` subdirectories
- Broken YAML frontmatter in `.md` files
- Uncommitted changes (auto-commit for `data/**` and `memory/**` only)

## Consequences

### Positive

- Runtime errors fixed in seconds instead of minutes (no scan interval + LLM startup)
- Eliminates classification LLM cost — the AI IS the classifier
- Vault repo health monitored continuously
- No changes to existing services — pure additive
- Falls back to today's pipeline transparently

### Negative

- Persistent AI session consumes resources when idle (mitigated by lean filtering — no tokens consumed between errors)
- Context window fills over time (mitigated by pressure-based restart)
- New dependency on AI client binary being installed

### Neutral

- Self-heal pipeline continues running alongside — registry is the coordination point
- Adaptive loop engine (ADR-176) unaffected — nightly scans still independent

## Alternatives Considered

### Alternative 1: Persistent Session (AI as top-level process)

launchd starts the AI client directly, daemon runs as its child. Rejected because AI crash kills the daemon — unacceptable for a system service. The sidecar model preserves daemon lifecycle independence.

### Alternative 2: On-Demand AI Trigger (event-driven)

Daemon runs standalone, spawns AI client per error. Rejected because it's essentially what self-heal already does — doesn't eliminate the classify → spawn → fix roundtrip.

### Alternative 3: Raw Stderr Pipe

Pipe all child stderr directly to AI's stdin. Rejected because it overwhelms the context window with noise. The watcher's six-layer filter is essential for token efficiency.

## Implementation Order

### Phase 1: Foundation (independent)
1. Create `config/system/daemon.yaml` with `ai_monitor` section
2. Add `build_sidecar_cmd()` to `src/lib/llm_retry.py`

### Phase 2: Core Watcher
3. Create `skills/daemon/scripts/ai_monitor_watcher.py` with `--wait-for-event` mode
4. Add remaining modes: `--acquire-lock`, `--release-lock`, `--record-fix`, `--vault-check`, `--status`

### Phase 3: Sidecar Manager
5. Create `skills/daemon/scripts/ai_monitor_sidecar.py` with `AISidecarManager`

### Phase 4: Integration
6. Wire `AISidecarManager` into `unified_daemon.py` as child #12
7. Document `--monitor` mode in `skills/daemon/SKILL.md`
8. End-to-end integration tests

## References

- Design spec: `docs/superpowers/specs/2026-03-22-ai-monitor-sidecar-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-22-ai-monitor-sidecar.md`
- Self-heal pipeline: ADR-076
- Production monitoring: ADR-041
- Adaptive loop engine: ADR-176, ADR-180
- Unified error patterns: ADR-185

## Files Affected

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "src/lib/llm_retry.py: added build_sidecar_cmd()"
  patterns_deprecated: []
  files_affected:
    - "config/system/daemon.yaml (created)"
    - "skills/daemon/scripts/ai_monitor_watcher.py (created)"
    - "skills/daemon/scripts/ai_monitor_sidecar.py (created)"
    - "skills/daemon/scripts/unified_daemon.py (modified)"
    - "skills/daemon/SKILL.md (modified)"
    - "src/lib/llm_retry.py (modified)"
```
