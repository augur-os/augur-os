---
status: Implemented
date: '2026-03-07'
deciders:
- Gur Sannikov
- Claude
related:
- ADR-176 (Adaptive Loop Engine)
- ADR-200 (Ops-Loops / Auto-Commands Separation)
- ADR-249 (Adaptive Incident Promotion)
- ADR-245 (Centralized Issue Inventory)
- ADR-181 (Adaptive Loops Consolidation)
hub: null
tags:
- adaptive
- loop
- heal
- command
superseded_by: null
---

# ADR-256: Adaptive Loop Heal Command

## Context

The adaptive loop engine (ADR-176) tracks failures via `consecutive_failures` and disables categories after 3 consecutive failures with exponential backoff cooldowns. However, it has no mechanism to detect or address three classes of problems:

1. **Structurally idle loops** — Loops that run but `scan()` always returns empty because the input data pipeline is broken or empty. Example: `command-evolution` has 0 trust after 7 cycles because `runtime/command-evolution/` contains no execution logs. The loop appears healthy (no failures) but is dead weight.

2. **Trust-stuck categories** — Categories running for many cycles with no trust growth. They never fail (so they aren't disabled) and never succeed (so trust stays at 0.0). The engine treats them as normal.

3. **Failed categories needing root-cause investigation** — When a category fails, the only options are: wait for cooldown re-enable (which retries blindly) or manual `/ops-loops promote` (which also retries blindly). Neither investigates *why* the category failed, leading to promote/disable infinite loops.

The existing `/ops-loops diagnose` checks state consistency (zombie enabled, uncaught disable, stale cooldowns) but does not detect stagnation or investigate root causes.

## Decision

Add `/ops-loops heal` as a new sub-command with two modes:

### 1. Detection Mode (automatic + on-demand)

Runs automatically after every nightly cycle (appends findings to daily report) and on-demand via `/ops-loops heal`.

Three detection rules:

| Class | Severity | Rule |
|-------|----------|------|
| Failed | critical | `consecutive_failures > 0` |
| Structurally idle | warning | `cycle_count >= 3` AND all categories have `success_count == 0 AND failure_count == 0 AND trust == 0.0` |
| Trust-stuck | info (warning at 10+ cycles) | `cycle_count >= 5 AND trust < 0.1 AND success_count == 0` per category |

### 2. Fix Mode (on-demand only via `--fix`)

For each finding, follows a 5-stage pipeline:

```
INVESTIGATE -> IDENTIFY ROOT CAUSE -> STRUCTURAL FIX -> VERIFY -> RE-ENABLE
```

**Stage 1: Investigate** — Read last N journal errors, check scan input data paths, dry-run `scan()` to reproduce.

**Stage 2: Identify root cause** — Match errors against known patterns:

| Error Pattern | Pattern ID | Fixable |
|---------------|-----------|---------|
| `FileNotFoundError` / `No such file` (runtime path) | `missing_path` | Yes |
| Empty input data directory | `empty_data_dir` | Report only |
| `ModuleNotFoundError` / `ImportError` | `module_error` | No |
| `timeout` / `TimeoutExpired` | `timeout` | No |
| scan() returns empty every cycle | `scan_empty` | No |

Pattern table is extensible — new patterns added as we learn from failures.

**Stage 3: Structural fix** — Create missing runtime directories, seed empty pipelines. Only for `missing_path` pattern.

**Stage 4: Verify** — Re-run dry `scan()` after fix. Must complete without exception. If same error persists, mark as unresolved (do NOT re-enable).

**Stage 5: Re-enable** — Gated by `disable_count`:
- `disable_count == 0`: Reset failure counters, re-run (one shot only)
- `disable_count >= 1`: Report only (engine disabled this before for good reason)
- `disable_count >= 1 AND --force`: Manual override — promote, reset, re-run, log as override

This prevents the infinite promote/disable loop where heal enables -> engine disables -> heal enables again.

### Post-Nightly Integration

At the end of `run_all_by_trigger("nightly")`, the engine calls `heal_detect()` and appends a "Heal Findings" section to `runtime/adaptive/reports/YYYY-MM-DD.md`. No fixes are applied automatically.

### CLI

```
/ops-loops heal                # Detection only
/ops-loops heal --fix          # Investigate + fix + verify + re-enable
/ops-loops heal --fix --force  # Same + force-promote disabled categories
```

### Implementation

New file `plugins/observability/skills/daemon/scripts/adaptive/heal.py` with:
- `HealFinding` dataclass — kind, severity, loop, category, message, last_error, context
- `InvestigationResult` dataclass — root_cause, pattern, fixable, fix_action, fix_path
- `HealFixResult` dataclass — finding, outcome (fixed/skipped/unresolved), investigation, descriptions
- `heal_detect(ledger, journal_entries)` — returns sorted list of HealFinding
- `investigate_finding(finding, entry, project_root, journal_entries)` — returns InvestigationResult
- `heal_fix(findings, ledger, registry, project_root, journal_entries, force)` — returns list of HealFixResult
- `format_heal_report(findings)` / `format_heal_fix_report(results)` — human-readable output

Engine integration: `engine.py:generate_report()` calls `heal_detect()` and appends findings.

## Consequences

### Positive

- Structurally idle loops (like command-evolution) become visible instead of silently stagnating
- Trust-stuck categories surface as findings before they become permanent dead weight
- Failed categories get root-cause investigation before re-enable, preventing blind retry loops
- Post-nightly detection runs automatically — stagnation surfaces in daily reports without user remembering to check
- `disable_count` gate prevents infinite promote/disable cycles between heal and engine

### Negative

- Adds complexity to the adaptive engine's already-deep state management
- Known fix patterns table requires ongoing maintenance as new failure modes emerge
- Post-nightly detection adds a small amount of processing time to report generation

### Neutral

- Existing `/ops-loops diagnose` remains for state consistency checks — heal is complementary, not a replacement
- Auto-fixes only target safe operational mutations (directory creation, counter resets) — structural issues still require human judgment

## Alternatives Considered

### Alternative 1: Extend `/ops-loops diagnose` with stagnation detection

Add idle/stuck detection to the existing `TrustLedger.diagnose()` method and `--fix` flag.

Rejected because: diagnose focuses on state *consistency* (data integrity), while heal focuses on operational *progress* (is the system actually doing useful work?). Mixing them creates a method that's too large and conflates two different concerns. The investigation + structural fix + verify pipeline is fundamentally different from consistency auto-repair.

### Alternative 2: Fully autonomous heal in the daemon

Run the full fix pipeline automatically after every nightly cycle, not just detection.

Rejected because: auto-fixing trust state and re-running categories without user visibility creates a feedback loop that's hard to debug. The cost of pausing to show findings and let the user choose `--fix` is low; the cost of silent autonomous re-enables that fail and re-disable is high (journal noise, wasted budget, trust state churn).

### Alternative 3: Per-category health probes

Instead of pattern-matching journal errors, add a `health_check()` method to the OpsCommand protocol that each auto-command implements to validate its prerequisites.

Rejected for now because: it requires touching all 49 auto-command modules. The pattern-matching approach covers the most common failure modes with zero changes to existing modules. Can be added later as an enhancement if pattern matching proves insufficient.

## References

- Design doc: `docs/plans/2026-03-07-ops-loops-heal-design.md`
- Implementation plan: `docs/plans/2026-03-07-ops-loops-heal-plan.md`
- Engine code: `plugins/observability/skills/daemon/scripts/adaptive/engine.py`
- Trust ledger: `plugins/observability/skills/daemon/scripts/adaptive/trust_ledger.py`
- Ops protocol: `src/lib/ops_protocol.py`

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using the implementation plan.

**Team name**: `adr-256-heal`

### Phase 1: Core Detection
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Implement HealFinding dataclass and heal_detect() with 3 detection rules | `plugins/observability/skills/daemon/scripts/adaptive/heal.py` |
| 1.2 | developer | medium | Write tests for all 3 detection rules (failed, idle, stuck) | `plugins/observability/skills/daemon/tests/test_adaptive_heal.py` |
| 1.3 | developer | low | Implement format_heal_report() | `heal.py` |

### Phase 2: Investigation and Fix Pipeline
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Implement InvestigationResult, investigate_finding() with known patterns | `heal.py` |
| 2.2 | developer | high | Implement heal_fix() with 5-stage pipeline and disable_count gate | `heal.py` |
| 2.3 | developer | medium | Write tests for investigation and fix pipeline (4 scenarios) | `test_adaptive_heal.py` |
| 2.4 | developer | low | Implement format_heal_fix_report() | `heal.py` |

### Phase 3: Integration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Integrate heal_detect() into engine.py generate_report() | `engine.py` |
| 3.2 | developer | low | Add heal sub-command to ops-loops SKILL.md | `plugins/observability/skills/ops-loops/SKILL.md` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all heal tests + existing engine/trust tests for regression |
| V.2 | validator | low | Verify heal detection on live trust_state.json |

### Completion Criteria
- [ ] heal_detect() finds failed, idle, and stuck categories from live state
- [ ] heal_fix() respects disable_count gate (skip vs force-promote)
- [ ] heal_fix() creates missing directories and verifies via dry scan
- [ ] heal_fix() marks unresolved when verify fails
- [ ] generate_report() appends heal findings to nightly report
- [ ] All existing adaptive engine tests pass (no regressions)
- [ ] SKILL.md documents heal, heal --fix, heal --fix --force
