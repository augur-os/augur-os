---
status: Implemented
date: '2026-02-12'
deciders:
- Gur Sannikov
related:
- ADR-076 (Self-Heal Daemon)
- ADR-052 (Debugging Efficiency)
- ADR-060 (External Execution)
hub: null
tags:
- unix
- fail
- fast
- replace
- fallback
superseded_by: null
---

# ADR-084: Unix Fail-Fast — Replace Fallback Chains with Self-Heal Events

## Context

The codebase has accumulated **330+ fallback/backward-compatibility patterns** that violate Unix philosophy ("do one thing, fail loudly"). These patterns emerged during the dual-repo to monorepo migration and iterative refactoring cycles.

### The Problem

Scripts silently degrade instead of failing fast:

```python
# CURRENT: Silent fallback chains — masks real issues
try:
    from src.config.paths import get_user_data_base
    data_dir = get_user_data_base()
except ImportError:
    data_dir = Path.cwd() / "data"  # nobody knows this happened

# CURRENT: Path existence guessing
if os.path.exists(path_a):
    use(path_a)
elif os.path.exists(path_b):
    use(path_b)
else:
    use(path_c)  # why are we here?
```

This creates three cascading problems:

1. **Silent degradation** — issues are hidden until they cause downstream failures with no trace to root cause
2. **Dead code accumulation** — fallback branches stay even after the primary path is stable
3. **Testing blind spots** — fallback branches rarely have test coverage; bugs hide there

### Codebase Scan Results

A full scan identified these categories, ordered by priority:

| Priority | Category | Count | Risk | Example |
|----------|----------|-------|------|---------|
| P0 | **Import fallback chains** | 80+ | Module not found → silent `pass` → runtime crash later | `chain_executor.py:88-128` |
| P1 | **Path fallback chains** | 15+ | Wrong directory used silently | `offload-gate.sh:43-52`, `audit_paths.py:59-64` |
| P1 | **MCP → direct call fallbacks** | 8+ | Bypasses execution gateway | ADR-060 `fallback_to_native` |
| P2 | **Path existence guessing** | 100+ | Silent switching between paths | Widespread in `.github/scripts/` |
| P3 | **Config `.get()` with wrong defaults** | 80+ | Wrong defaults mask missing config | `augur_cli.py:190+`, `skill_registry.py:224+` |
| P4 | **Legacy function aliases** | 10+ | Old API surface never removed | `paths.py:139,207,369`, `log_retention.py:73` |
| P5 | **Cloud service fallbacks** | 5+ | Architectural — keep but instrument | ADR-021, ADR-033 |

### What We Already Have

The self-heal daemon (ADR-076) already:
- Scans `data/runtime/logs/` every 5 minutes
- Classifies issues by severity (critical/high/medium/low/transient)
- Auto-fixes critical/high issues via headless `/debug`
- Creates TODO markers for medium/low issues
- Tracks everything in `self_heal_registry.json`

**The missing piece**: code doesn't emit structured events when things fail. The daemon only sees log lines after something crashes — not when a fallback silently activates.

## Decision

### Principle: Fail Fast, Emit Event, Let Daemon Heal

Replace all fallback chains with a two-step pattern:

```python
# NEW: Fail fast + emit self-heal event
from src.logging.self_heal_event import emit_heal_event

try:
    from src.config.paths import get_user_data_base
    data_dir = get_user_data_base()
except ImportError as e:
    emit_heal_event(
        source="chain_executor",
        category="import_failure",
        severity="high",
        message=f"Cannot import get_user_data_base: {e}",
        context={"expected_module": "src.config.paths", "fallback_removed": True},
    )
    raise  # FAIL — don't silently continue
```

### Component 1: Self-Heal Event Emitter

**New file**: `src/logging/self_heal_event.py`

A zero-dependency function that writes JSONL to `data/runtime/self_heal_events.jsonl`:

```python
def emit_heal_event(
    source: str,           # Script/module name
    category: str,         # import_failure | path_missing | config_missing | mcp_failure
    severity: str,         # critical | high | medium | low
    message: str,          # Human-readable description
    context: dict = None,  # Structured metadata
) -> None:
    """Write a structured event to the self-heal event log.

    The daemon picks this up within its scan interval (default: 5 min).
    This function MUST NOT raise — it's called from error paths.
    """
```

**Event schema** (JSONL):
```json
{
  "timestamp": "2026-02-12T14:30:00.000Z",
  "source": "chain_executor",
  "category": "import_failure",
  "severity": "high",
  "message": "Cannot import get_user_data_base",
  "context": {"expected_module": "src.config.paths"},
  "host": "macbook",
  "pid": 12345
}
```

**Design constraints**:
- Zero external dependencies (only `json`, `os`, `datetime`, `pathlib`)
- Must not import from `src.config.paths` (circular dependency risk — hardcode `data/runtime/`)
- Must not raise exceptions (it's called from error paths)
- Append-only JSONL (atomic writes via temp file + rename)
- Log rotation handled by existing `log_retention.py`

### Component 2: New Daemon Scan Target

Add to `self_heal.yaml`:

```yaml
scan_targets:
  # ... existing targets ...
  # Structured self-heal events (fail-fast emissions)
  - path: "data/runtime/self_heal_events.jsonl"
    patterns:
      - '"severity": "critical"'
      - '"severity": "high"'
      - '"severity": "medium"'
```

The daemon already processes JSONL (see `chain_telemetry.jsonl` and `offload-log.jsonl` targets). This new target integrates seamlessly.

### Component 3: Fallback Removal (Phased)

Replace fallback patterns in priority order. Each replacement follows the same template:

**Before** (fallback):
```python
try:
    result = primary_approach()
except SomeError:
    result = fallback_approach()  # silent degradation
```

**After** (fail-fast + event):
```python
try:
    result = primary_approach()
except SomeError as e:
    emit_heal_event(source=__name__, category="...", severity="...", message=str(e))
    raise
```

#### Phase 1: P0 — Import Fallback Chains (80+ instances)

Target files:
| File | Lines | Action |
|------|-------|--------|
| `plugins/orchestration/skills/executor/scripts/chain_executor.py` | 88-128 | Remove 5 import fallbacks, emit events, raise |
| `.github/scripts/audit_paths.py` | 39-64 | Remove legacy `~/Projects/augur` fallback |
| `.github/scripts/hook_runner.py` | ~99 | Remove YAML→JSON fallback |
| `plugins/observability/skills/daemon/scripts/mcp_health_check.py` | 4 instances | Remove silent `pass` on import failure |
| `plugins/observability/skills/daemon/scripts/log_monitor.py` | 3 instances | Same |
| `plugins/admin/skills/channels/lib/support_checker.py` | 3 instances | Same |
| `plugins/admin/skills/channels/lib/registry.py` | 1 instance | Same |
| `plugins/admin/skills/channels/mcp/__init__.py` | 1 instance | Same |
| `plugins/ai/skills/ai_bridge/augur/crew_parser.py` | multiple | Same |
| `plugins/ai/skills/ai_bridge/augur/chain_bridge.py` | multiple | Same |
| `plugins/ai/skills/ai_bridge/augur/codex_cli.py` | multiple | Same |
| `plugins/finance/skills/finance/mcp/__init__.py` | 16 | Remove "standalone mode" fallback |
| `plugins/ai/skills/knowledge/scripts/rag_*_cli.py` | multiple | Same |
| `plugins/ai/skills/mcp-app-factory/scripts/workflow/engine.py` | 5 instances | Same |

#### Phase 2: P1 — Path Fallback Chains (15+ instances)

| File | Lines | Action |
|------|-------|--------|
| `.claude/hooks/offload-gate.sh` | 43-52 | Remove `cwd / 'data'` fallback, emit event, exit 1 |
| `src/config/mcp_tools.py` | 26-120 | Remove `DEFAULT_TOOL_CATEGORIES` hardcoded fallback |
| `plugins/orchestration/skills/executor/scripts/chain_executor.py` | 102-128 | Remove dynamic root discovery fallback |
| `src/dashboard/lib/paths.ts` | 94, 117 | Remove monorepo runtime path fallback |
| `plugins/orchestration/skills/executor/scripts/index_manager.py` | 31 | Remove `parent / "augur"` fallback |

#### Phase 3: P2 — Path Existence Guessing (targeted — 20 highest-risk)

Focus on `.github/scripts/` where validation scripts silently skip:
| File | Action |
|------|--------|
| `.github/scripts/validate_dashboard.py` | Emit event on missing paths instead of skip |
| `.github/scripts/validate_structure.py` | Same |
| `.github/scripts/validate_file_placement.py` | Same |
| `.github/scripts/cleanup_temp_files.py` | Same |
| `.github/scripts/checkpoint_manager.py` | Same |

#### Phase 4: P3-P4 — Config Defaults and Legacy Aliases

| File | Action |
|------|--------|
| `src/config/paths.py:332-336` | Remove `get_operations_dir()` backward compat alias |
| `src/config/paths.py:139,207,369` | Remove backward compat function aliases |
| `src/config/log_retention.py:73` | Remove dict-return backward compat |
| `scripts/configure_mcp.py:332,405` | Remove v1 format backward compat |
| `plugins/ai/skills/mcp-app-factory/scripts/generate_skill_ui.py:223` | Remove backward compat analysis |

#### Phase 5: P5 — Instrument Cloud Fallbacks (keep but observe)

Cloud/service fallbacks are architectural (intentional degradation). Keep them but add event emission so the daemon tracks when fallbacks activate:

| Pattern | Action |
|---------|--------|
| ADR-060 `fallback_to_native` | Emit `mcp_failure` event before fallback |
| ADR-033 AI→static scoring | Emit `ai_bridge_unavailable` event |
| ADR-052 Chrome→Playwright | Emit `browser_tool_fallback` event |
| ADR-021 local→cloud scraping | Emit `scraper_escalation` event |

### Component 4: Shell Script Equivalent

For `.sh` files (like `offload-gate.sh`), provide a shell helper:

**New file**: `src/scripts/emit_heal_event.sh`

```bash
emit_heal_event() {
    local source="$1" category="$2" severity="$3" message="$4"
    local runtime_dir="${AUGUR_DATA:-$(pwd)/data}/runtime"
    local event_file="${runtime_dir}/self_heal_events.jsonl"
    mkdir -p "$runtime_dir"
    printf '{"timestamp":"%s","source":"%s","category":"%s","severity":"%s","message":"%s","pid":%d}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)" "$source" "$category" "$severity" "$message" $$ \
        >> "$event_file"
}
```

### Component 5: TypeScript Equivalent

For dashboard code:

**New file**: `src/dashboard/lib/self-heal-event.ts`

```typescript
export function emitHealEvent(params: {
  source: string;
  category: string;
  severity: "critical" | "high" | "medium" | "low";
  message: string;
  context?: Record<string, unknown>;
}): void {
  // POST to /api/self-heal/event endpoint
  // Fire-and-forget — never throws
}
```

**New API route**: `src/dashboard/app/api/self-heal/event/route.ts` — appends to the same JSONL file.

## Consequences

### Positive

- **Unix alignment** — each script does one thing; failures are loud and traceable
- **Self-healing loop closed** — daemon catches issues within 5 minutes instead of never
- **Dead code removal** — 100+ fallback branches eliminated
- **Debugging speed** — structured events show exactly what failed, when, and where
- **Observability** — `self_heal_events.jsonl` is a queryable audit trail of all failures
- **Test simplification** — no more testing fallback branches that shouldn't exist

### Negative

- **Temporary breakage during migration** — removing fallbacks may surface latent issues that were previously masked (this is actually the point — the daemon will catch and fix them)
- **Shell/TS emit functions add ~50 LOC** of new infra code
- **Phased rollout required** — can't remove all 330+ fallbacks at once

### Neutral

- Config `.get(key, default)` for optional config fields is fine — only wrong defaults are targeted
- Cloud fallbacks (P5) are kept — they're architectural, just instrumented
- The self-heal daemon itself keeps its own internal fallbacks (scanner has Python fallback for missing ripgrep) — this is appropriate since the healer must be maximally robust

## Alternatives Considered

### Alternative 1: Centralized Error Handler Wrapper

Wrap all functions in a decorator that catches exceptions and emits events:

```python
@self_heal_on_error(source="chain_executor", category="import")
def load_paths():
    from src.config.paths import get_user_data_base
    return get_user_data_base()
```

**Rejected**: Too magical. Hides control flow. Decorators can't easily distinguish "expected optional import" from "critical path failure". The explicit `emit_heal_event()` + `raise` pattern is clearer.

### Alternative 2: Keep Fallbacks but Add Logging

Add `logger.warning()` to every fallback branch instead of removing them:

```python
except ImportError as e:
    logger.warning("Falling back to manual path: %s", e)
    data_dir = Path.cwd() / "data"
```

**Rejected**: This is what we have today — warnings go to log files that nobody reads. The daemon already scans for ERROR/CRITICAL but not WARNING. Changing the daemon to scan WARNING would cause massive noise. The real fix is to remove the fallback, not log it.

### Alternative 3: Feature Flags per Fallback

Add a config that enables/disables each fallback individually:

```yaml
fallbacks:
  chain_executor_path_import: false
  offload_gate_cwd_data: false
```

**Rejected**: Over-engineering. 330+ config flags for code that should just work. The monorepo migration is done — the old paths are gone. Remove the fallbacks.

## References

- ADR-076: Self-Heal Daemon (scanner, classifier, fixer)
- ADR-052: Debugging Efficiency (visibility stack, full-stack vision)
- ADR-060: External Execution Mode (`fallback_to_native` pattern)
- ADR-033: RAG Search Hardening (AI→static fallback)
- `plugins/observability/skills/daemon/config/self_heal.yaml` — scan targets config
- `plugins/observability/skills/daemon/scripts/ai_self_healer.py` — daemon implementation
- `src/config/paths.py` — centralized path resolution (already no-fallback by design)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-084: Unix Fail-Fast — Replace Fallback Chains with Self-Heal Events**.

Read the full ADR: `docs/decisions/ADR-084-unix-fail-fast-self-heal.md`

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

1. **Create team**: `TeamCreate(team_name="adr-084-fail-fast", description="Implementing ADR-084: Unix Fail-Fast Self-Heal Events")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-084-fail-fast", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-084-fail-fast team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        commit your changes (git add <specific files> && git commit), then
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases → spawn all at once. PIPELINE phases → use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` → haiku, `medium` → sonnet, `high` → opus

### Execution Plan

**Team name**: `adr-084-fail-fast`

#### Phase 1: Infrastructure — Event Emitter
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create Python self-heal event emitter. Zero external deps (json, os, datetime, pathlib only). Must not import from `src.config.paths`. Atomic JSONL append. Must never raise. Include unit tests. | `src/logging/self_heal_event.py`, `tests/src/test_self_heal_event.py` |
| 1.2 | developer | low | Create shell helper `emit_heal_event()` function. Uses `$AUGUR_DATA` or `$(pwd)/data` for runtime dir. Atomic append to `self_heal_events.jsonl`. | `src/scripts/emit_heal_event.sh` |
| 1.3 | frontend | medium | Create TS `emitHealEvent()` function (fire-and-forget fetch to `/api/self-heal/event`). Create API route that appends JSONL. Never throws. | `src/dashboard/lib/self-heal-event.ts`, `plugins/observability/skills/daemon/api/self-heal/event/route.ts`, `src/dashboard/app/api/self-heal/event/route.ts` |
| 1.4 | devops | low | Add `self_heal_events.jsonl` as scan target in `self_heal.yaml`. Patterns: `"severity": "critical"`, `"severity": "high"`, `"severity": "medium"`. | `plugins/observability/skills/daemon/config/self_heal.yaml` |

#### Phase 2: P0 — Import Fallback Removal (highest priority)
**Strategy**: PARALLEL (each agent owns a disjoint set of files)
**Depends on**: Phase 1

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Remove 5 import fallback chains in chain_executor.py (lines 88-128). Replace `except ImportError: pass/fallback` with `emit_heal_event()` + `raise`. Keep the primary import. Test that imports work. | `plugins/orchestration/skills/executor/scripts/chain_executor.py` |
| 2.2 | developer | medium | Remove import fallbacks in daemon scripts (mcp_health_check.py 4 instances, log_monitor.py 3 instances). Replace with emit + raise. | `plugins/observability/skills/daemon/scripts/mcp_health_check.py`, `plugins/observability/skills/daemon/scripts/log_monitor.py` |
| 2.3 | developer | medium | Remove import fallbacks in channels (support_checker.py 3, registry.py 1, mcp/__init__.py 1) and ai_bridge (crew_parser.py, chain_bridge.py, codex_cli.py). Replace with emit + raise. | `plugins/admin/skills/channels/lib/support_checker.py`, `plugins/admin/skills/channels/lib/registry.py`, `plugins/admin/skills/channels/mcp/__init__.py`, `plugins/ai/skills/ai_bridge/augur/crew_parser.py`, `plugins/ai/skills/ai_bridge/augur/chain_bridge.py`, `plugins/ai/skills/ai_bridge/augur/codex_cli.py` |
| 2.4 | developer | medium | Remove import fallbacks in: finance/mcp/__init__.py, knowledge/scripts/rag_*_cli.py, mcp-app-factory workflow/engine.py (5 instances). Replace with emit + raise. | `plugins/finance/skills/finance/mcp/__init__.py`, `plugins/ai/skills/knowledge/scripts/rag_*_cli.py`, `plugins/ai/skills/mcp-app-factory/scripts/workflow/engine.py` |

#### Phase 3: P1 — Path Fallback Removal
**Strategy**: PARALLEL
**Depends on**: Phase 1

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | devops | medium | Fix offload-gate.sh: remove `cwd / 'data'` fallback (lines 43-52). Source `emit_heal_event.sh`. On path resolution failure, emit event and `exit 1`. | `.claude/hooks/offload-gate.sh`, `src/scripts/emit_heal_event.sh` |
| 3.2 | developer | medium | Remove `DEFAULT_TOOL_CATEGORIES` hardcoded fallback in mcp_tools.py. If YAML missing, emit event + raise. Remove the 90-line hardcoded dict. | `src/config/mcp_tools.py` |
| 3.3 | developer | low | Remove dynamic root discovery fallback in chain_executor.py path resolution (lines 102-128, the `os.path.dirname` chain). Require `src.config.paths` import to succeed. | `plugins/orchestration/skills/executor/scripts/chain_executor.py` |
| 3.4 | frontend | low | Remove monorepo runtime path fallback in `src/dashboard/lib/paths.ts` (lines 94, 117). Emit event via `emitHealEvent()` if path resolution fails. | `src/dashboard/lib/paths.ts` |
| 3.5 | developer | low | Remove `parent / "augur"` fallback in `index_manager.py:31`. Emit event + raise. | `plugins/orchestration/skills/executor/scripts/index_manager.py` |

#### Phase 4: P2 — Validation Script Hardening
**Strategy**: PARALLEL
**Depends on**: Phase 1

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Harden `.github/scripts/audit_paths.py`: remove `~/Projects/augur` legacy fallback (lines 59-64). Emit event + raise if `get_path_config()` fails. | `.github/scripts/audit_paths.py` |
| 4.2 | developer | low | Harden validation scripts: `validate_dashboard.py`, `validate_structure.py`, `validate_file_placement.py` — emit events on missing paths instead of silent skip. | `.github/scripts/validate_dashboard.py`, `.github/scripts/validate_structure.py`, `.github/scripts/validate_file_placement.py` |
| 4.3 | developer | low | Harden `hook_runner.py` (~line 99): remove YAML→JSON fallback. Emit event if YAML parse fails. | `.github/scripts/hook_runner.py` |

#### Phase 5: P3-P4 — Legacy Alias Cleanup
**Strategy**: PARALLEL
**Depends on**: Phase 2, Phase 3 (imports/paths stable first)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | medium | Remove backward compat aliases in `paths.py` (lines 139, 207, 332-336, 369). Grep codebase for callers first — update any remaining callers to use canonical names. | `src/config/paths.py` |
| 5.2 | developer | low | Remove backward compat dict return in `log_retention.py:73`. Update callers. | `src/config/log_retention.py` |
| 5.3 | devops | low | Remove v1 MCP format compat in `configure_mcp.py` (lines 332, 405). Remove `backward compat` analysis in `generate_skill_ui.py:223`. | `scripts/configure_mcp.py`, `plugins/ai/skills/mcp-app-factory/scripts/generate_skill_ui.py` |

#### Phase 6: P5 — Instrument Cloud Fallbacks (keep but observe)
**Strategy**: PARALLEL
**Depends on**: Phase 1

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 6.1 | developer | low | Add `emit_heal_event()` calls to intentional cloud/service fallbacks: ADR-060 `fallback_to_native`, RAG AI→static scoring, browser tool fallback. Keep the fallback logic — just add observability. | `plugins/orchestration/skills/executor/scripts/chain_executor.py`, `plugins/orchestration/skills/executor/scripts/offload_dispatcher.py` |

#### Final Phase: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `pytest tests/src/` — all Python tests pass |
| V.2 | validator | low | Run `npm run build` in `src/dashboard/` — build succeeds |
| V.3 | validator | low | Run `python3 .github/scripts/audit_paths.py` — no hardcoded paths |
| V.4 | validator | low | Grep for remaining `except ImportError: pass` — should be near-zero |
| V.5 | validator | low | Grep for `fallback` in `.py` files — verify only P5 (intentional) fallbacks remain |
| V.6 | validator | low | Verify `self_heal_events.jsonl` scan target works: write a test event, confirm daemon config matches |

### Completion Criteria
- [ ] `src/logging/self_heal_event.py` exists with unit tests
- [ ] `src/scripts/emit_heal_event.sh` exists
- [ ] `src/dashboard/lib/self-heal-event.ts` + API route exist
- [ ] `self_heal.yaml` includes `self_heal_events.jsonl` target
- [ ] 80+ import fallbacks replaced with emit + raise
- [ ] 15+ path fallbacks replaced with emit + raise
- [ ] Legacy aliases removed from `paths.py`, `log_retention.py`, `configure_mcp.py`
- [ ] Cloud fallbacks instrumented (kept but emit events)
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] ADR status updated to "Accepted"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-084-unix-fail-fast-self-heal.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
