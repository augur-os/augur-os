---
status: Implemented
date: '2026-02-28'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- adaptive
- loops
- consolidation
superseded_by: null
---

# ADR-181: Adaptive Loops Consolidation

## Context

The daemon ran 13 child services, three of which (`ai_self_healer`, `nightly_maintainer`, `runtime_marker_scanner`) duplicated functionality already modeled as adaptive loop categories. The `SelfHealLoop` was registered without a healer instance (placeholder that never executed). The `command-evolution` loop had `trigger: post-execution` but the engine only dispatched `nightly` and `continuous` triggers, so it never fired. There was no structural hardening loop to catch plugin misconfigurations.

## Decision

### 1. Absorb 3 services into the adaptive loop engine (13 → 10 services)

| Removed Service | Absorbed Into | New Category |
|---|---|---|
| `ai_self_healer` | `SelfHealLoop` | existing import-fixes/config-fixes/logic-fixes |
| `nightly_maintainer` (log compression) | `CodeQualityLoop` | `log-maintenance` (tier 0) |
| `nightly_maintainer` (analytics) | `KnowledgeEnrichmentLoop` | `analytics-generation` (tier 0) |
| `runtime_marker_scanner` | `CodeQualityLoop` | `scan-markers` (tier 0, continuous trigger) |

### 2. Wire SelfHealLoop with healer instance

The executor imports `AISelfHealer`, instantiates at startup, and passes to `SelfHealLoop(project_root, healer_module=healer)`. Every fix now goes through trust gate, budget, journal, and regression guard.

### 3. Mixed trigger support

`CodeQualityLoop` changed from `trigger: nightly` to `trigger: mixed`. Each category declares its own trigger (`continuous` or `nightly`). The engine's `run_all_by_trigger()` filters actions by per-category trigger using `_category_matches_trigger()`.

### 4. Post-execution trigger and JSONL queue

`ide_bridge.py` appends events to `runtime/adaptive/post_exec_queue.jsonl`. The executor's main loop drains this queue and runs `command-evolution` cycles per event. File-based IPC chosen because daemon and Claude Code run in separate process trees.

### 5. New HardeningLoop with 6 tiered categories

| Category | Tier | Trigger | Action |
|---|---|---|---|
| `augur-yaml-lint` | 0 | nightly | Report: validate all augur.yaml parse correctly |
| `page-mount-check` | 1 | nightly | Report: verify contributions.pages have source files |
| `api-route-health` | 2 (locked) | nightly | Report + TODO_BUG marker |
| `dependency-audit` | 3 (locked) | nightly | Report + TODO_BUG marker |
| `plugin-template-lint` | 4 (locked) | nightly | Headless Claude fix |
| `stale-path-scan` | 5 (locked) | nightly | Headless Claude fix |

Reports written to `runtime/adaptive/reports/hardening-{date}.md`.

### 6. Explicit tier field in config

Trust ledger reads `tier` from config YAML (`cat_cfg.get("tier", idx)`) instead of inferring from dict enumeration order.

## Consequences

### Positive

- 3 fewer daemon services to manage (13 → 10)
- Every self-heal fix goes through trust gate and regression guard
- Mixed triggers allow continuous + nightly categories in one loop
- Post-execution queue enables command-evolution to fire on slash command completion
- Structural hardening catches plugin misconfigurations nightly
- Tier ordering is explicit and stable regardless of YAML key ordering

### Negative

- Optional imports with try/except for `nightly_maintainer`, `runtime_marker_scanner`, `ai_self_healer` add module-level complexity
- JSONL file-based IPC requires periodic drain (checked every 60s in main loop)

### Neutral

- Core logic of absorbed services unchanged — only invocation paths moved
- `NightlyScheduler` class removed from unified_daemon.py (adaptive engine handles its own scheduling)

## References

- [ADR-176: Adaptive Loop Engine](ADR-176-adaptive-loop-engine.md) — original engine design
- [Design doc](../plans/2026-02-28-adaptive-loops-consolidation-design.md) — full consolidation design
- [Implementation plan](../plans/2026-02-28-adaptive-loops-consolidation-plan.md) — 12-task TDD plan

## Impact Manifest

```yaml
impact:
  apis_changed:
    - function: run_cycle
      module: adaptive.engine
      breaking: false  # Added optional trigger_filter parameter
    - function: run_all_by_trigger
      module: adaptive.engine
      breaking: false  # Now handles "mixed" trigger loops
    - function: drain_post_exec_queue
      module: adaptive.engine
      breaking: false  # New method
    - function: _emit_post_exec_event
      module: ide_bridge
      breaking: false  # New function
  patterns_deprecated:
    - grep: "CHILD_SERVICES.*nightly_maintainer"
      replacement: "Absorbed into adaptive engine code-quality/knowledge-enrichment loops"
    - grep: "CHILD_SERVICES.*runtime_marker_scanner"
      replacement: "Absorbed into adaptive engine code-quality scan-markers category"
    - grep: "CHILD_SERVICES.*ai_self_healer"
      replacement: "Absorbed into adaptive engine self-heal loop with healer instance"
    - grep: "NightlyScheduler"
      replacement: "Adaptive engine handles nightly scheduling internally"
  files_affected:
    - glob: "config/system/adaptive_loops.yaml"
    - glob: "plugins/observability/skills/daemon/scripts/adaptive_loop_executor.py"
    - glob: "plugins/observability/skills/daemon/scripts/unified_daemon.py"
    - glob: "plugins/ai/skills/ai_bridge/scripts/ide_bridge.py"
    - glob: "plugins/observability/skills/daemon/scripts/adaptive/loops/*.py"
```
