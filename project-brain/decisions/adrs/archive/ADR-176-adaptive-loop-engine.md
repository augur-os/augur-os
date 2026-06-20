---
status: Implemented
date: '2026-02-28'
deciders:
- Augur Team
related:
- ADR-076 (Self-Heal)
- ADR-041 (Daemon Monitoring)
- ADR-102 (Adaptive Slash Commands)
- ADR-167 (Browser Error Telemetry)
hub: null
tags:
- adaptive
- loop
- engine
superseded_by: null
---

# ADR-176: Adaptive Loop Engine

## Context

Augur has several autonomous systems — self-heal (ADR-076), nightly daemon (ADR-041), adaptive command evolution (ADR-102), and the `/harden` command — but they operate independently with no unified trust model, budget control, or cross-loop learning.

Current state:
- **Self-heal** is the only actively running loop (181 issues tracked, 40 fixed autonomously, 22% success rate)
- **ADR-102 adaptive infrastructure** is fully built (classes, storage, analysis engine) but no commands are wrapped to use it
- **Nightly daemon** runs maintenance tasks but doesn't perform autonomous code improvement
- **No unified trust model** — each system has its own ad-hoc safety constraints
- **No budget control** — no limits on how much autonomous change can happen per cycle
- **No cross-loop learning** — self-heal patterns don't inform command evolution or vice versa

The goal is to make Augur continuously self-improve across three axes — healthier code, smarter commands, and richer knowledge — without human intervention, while ensuring safety through graduated trust.

## Decision

Build a **Unified Adaptive Loop Engine** that runs as a single child service inside `unified_daemon.py`. All loops register with the engine, share a trust ledger and budget system, and log to a common execution journal. A new `/ops-loops` command provides full lifecycle management.

### 1. Core Architecture

```
unified_daemon.py
  └── adaptive_loop_executor.py     ← Single child service
        ├── engine.py                ← Orchestrates all loops
        ├── trust_ledger.py          ← Trust scores + budget + promotion/demotion
        ├── journal.py               ← Append-only JSONL action log
        └── loops/
            ├── base_loop.py         ← Abstract interface
            ├── self_heal.py         ← Wraps existing ai_self_healer.py
            ├── code_quality.py      ← Lint, format, TODO resolution
            ├── command_evolution.py  ← Wraps ADR-102 infrastructure
            └── knowledge_enrichment.py ← RAG reindex, data gaps
```

All new code lives in `plugins/observability/skills/daemon/scripts/adaptive/`.

### 2. Four Loops

| Loop | Trigger | Purpose | Output |
|------|---------|---------|--------|
| **self-heal** | Continuous (5min) | Scan errors, classify, auto-fix | Commits, TODOs |
| **code-quality** | Nightly | Lint, fix style, reduce debt | Commits, reports |
| **command-evolution** | Post-execution | Track commands, extract patterns, rewrite skills | SKILL.md updates |
| **knowledge-enrichment** | Nightly | Rebuild RAG, fill data gaps, import content | Index updates |

Each loop implements `BaseLoop` with two methods: `scan()` returns actionable items, `execute_action()` performs a single fix.

### 3. Trust Ledger

Each loop has tiered **categories** that unlock progressively:

**Self-heal categories:**
| Tier | Category | Starting Trust |
|------|----------|---------------|
| 0 | import-fixes | 0.9 (proven) |
| 1 | config-fixes | 0.6 |
| 2 | logic-fixes | 0.3 |
| 3 | refactor-fixes | 0.0 (locked) |

**Code-quality categories:**
| Tier | Category | Starting Trust |
|------|----------|---------------|
| 0 | format | 0.0 (always safe) |
| 1 | lint-autofix | 0.0 |
| 2 | todo-cleanup | 0.0 (locked) |
| 3 | type-errors | 0.0 (locked) |
| 4 | todo-outdated | 0.0 (locked) |

**Command-evolution categories:**
| Tier | Category | Starting Trust |
|------|----------|---------------|
| 0 | timeout-hints | 0.0 |
| 1 | cache-keys | 0.0 |
| 2 | missing-steps | 0.0 (locked) |
| 3 | reorder-phases | 0.0 (locked) |
| 4 | remove-steps | 0.0 (locked) |

**Knowledge-enrichment categories:**
| Tier | Category | Starting Trust |
|------|----------|---------------|
| 0 | rag-reindex | 0.0 |
| 1 | index-new-files | 0.0 |
| 2 | fix-broken-indices | 0.0 (locked) |
| 3 | generate-descriptions | 0.0 (locked) |
| 4 | create-data-files | 0.0 (locked) |

**Promotion mechanics:**
- After each success: `trust += (1.0 - trust) * 0.1` (diminishing returns)
- After 10+ successes AND trust > 0.8: next tier category auto-enables
- After 10 consecutive successes: budget increases by `budget_growth_rate`

**Demotion mechanics:**
- After each failure: `trust -= 0.2` (steep penalty), budget decrements
- After 3 consecutive failures: category auto-disables
- Budget hits 1: loop enters probation (only tier 0 allowed)

### 4. Execution Journal

Append-only JSONL log at `runtime/adaptive/journal.jsonl`:

```json
{"loop": "code-quality", "action": "fix-lint", "category": "lint-autofix", "files": ["src/foo.ts"], "result": "success", "commit": "abc123", "timestamp": "2026-02-28T03:15:00Z", "duration_ms": 4200}
```

Source of truth for trust score computation, reporting, and history queries.

### 5. Regression Guard

After any commit from a loop, the engine runs a configurable verify command (default: `npm run build`). If it fails:
1. `git revert HEAD --no-edit`
2. Log regression to journal as failure
3. Demote the category

This ensures loops can never make the codebase worse.

### 6. Execution Model

All loops use **headless Claude Code** for AI reasoning:

```
Engine decides action needed
  → Check trust: category allowed? budget remaining?
  → YES: spawn `claude --print --max-turns N --allowedTools [...]`
  → Capture result (commit hash, files changed, success/fail)
  → Log to journal → Update trust scores
```

Each session gets scoped `--allowedTools` based on the loop's trusted categories.

### 7. `/ops-loops` Command

New slash command for lifecycle management:

| Sub-command | What it does |
|-------------|-------------|
| `/ops-loops status` | Show all loops: enabled/disabled, trust, budget, last run |
| `/ops-loops enable <loop>` | Enable a loop |
| `/ops-loops disable <loop>` | Disable a loop |
| `/ops-loops configure <loop> --budget N` | Set budget |
| `/ops-loops promote <loop> <category>` | Manually unlock a category |
| `/ops-loops history [loop]` | Show execution journal |
| `/ops-loops reset <loop>` | Reset trust scores to defaults |

### 8. Morning Report

Generated after each nightly run, saved to `runtime/adaptive/reports/YYYY-MM-DD.md`:

```
=== Adaptive Loops — Overnight Report ===
self-heal:      3 fixes (import-fixes x2, config-fixes x1)
code-quality:   7 lint fixes, 0 TODO resolutions
knowledge:      RAG reindex complete, 12 new files indexed
cmd-evolution:  /harden timeout hint added
Budget changes: code-quality 10->12 (promoted)
Failures:       0
```

### 9. Configuration

File: `config/system/adaptive_loops.yaml`

```yaml
engine:
  enabled: true
  nightly_time: "03:00"
  max_concurrent_sessions: 1
  session_timeout_minutes: 30
  journal_retention_days: 30
  verify_command: "npm run build"

loops:
  self-heal:
    enabled: true
    trigger: continuous
    interval_minutes: 5
    budget: 5
    budget_growth_rate: 1
    categories:
      import-fixes: { enabled: true, trust: 0.9 }
      config-fixes: { enabled: true, trust: 0.6 }
      logic-fixes: { enabled: true, trust: 0.3 }
      refactor-fixes: { enabled: false, trust: 0.0 }
  # ... (code-quality, command-evolution, knowledge-enrichment)
```

## Consequences

**Positive:**
- Augur evolves autonomously across code quality, command performance, and knowledge coverage
- Graduated trust prevents runaway autonomous changes — starts conservative, earns permissions
- Unified journal provides full audit trail of all autonomous actions
- Regression guard makes it impossible for loops to break the codebase
- `/ops-loops` gives the user complete control to enable/disable/configure at any time
- Cross-loop learning: self-heal patterns can inform command evolution

**Negative:**
- Headless Claude Code sessions have API cost — each loop cycle costs tokens
- Self-heal refactor to register with engine requires careful integration to avoid regressions
- Budget/trust system adds complexity to what was previously a simple scan-fix loop
- Morning reports may accumulate if not cleaned up (mitigated by journal retention config)

**Neutral:**
- Self-heal continues to work exactly as before — the wrapper only adds trust tracking
- Existing ADR-102 infrastructure is reused, not rewritten
- Nightly timing (3 AM default) is configurable but must be coordinated with existing nightly maintenance

## Implementation Order

```
Phase 1: Foundation (no deps)
├── Task 1: Execution Journal (journal.py + tests)
├── Task 2: Trust Ledger (trust_ledger.py + tests)
└── Task 3: Base Loop + LoopResult (base_loop.py + tests)

Phase 2: Engine (depends on Phase 1)
└── Task 4: Adaptive Loop Engine orchestrator (engine.py + tests)

Phase 3: Loop Implementations (depends on Phase 2, PARALLEL)
├── Task 5: Code Quality Loop (code_quality.py + tests)
├── Task 6: Command Evolution Loop (command_evolution.py + tests)
├── Task 7: Knowledge Enrichment Loop (knowledge_enrichment.py + tests)
└── Task 8: Self-Heal Wrapper (self_heal.py + tests)

Phase 4: Integration (depends on Phase 3)
├── Task 9: Config file + daemon executor + unified_daemon.py registration
├── Task 10: /ops-loops workflow + sync_agents
└── Task 11: Package __init__.py exports

Phase 5: Verification (depends on Phase 4)
├── Task 12: Integration test — full engine cycle
└── Task 13: Run full test suite + final verification
```

## Alternatives Considered

### A: Independent Loop Scripts

Each loop as a standalone Python script with its own launchd plist. Shared config format but no shared code.

**Rejected because:** Duplicates trust/budget logic in each script. No cross-loop learning. More launchd plists to manage. The hard problem is trust management — solving it once benefits all loops.

### B: Daemon Child Services (no engine)

Add each loop as a new child service in `unified_daemon.py` directly.

**Rejected because:** Each service reinvents trust/budget tracking. Harder to test in isolation. Daemon process grows heavier with 4 additional child services vs 1 engine service.

## References

- ADR-076: Self-Heal system architecture
- ADR-041: Daemon production monitoring
- ADR-102: Adaptive slash command infrastructure
- ADR-167: Browser error telemetry for self-heal
- Design doc: `docs/plans/2026-02-28-adaptive-loop-engine-design.md`
- Implementation plan: `docs/plans/2026-02-28-adaptive-loop-engine-plan.md`

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-176: Adaptive Loop Engine**.

Read the full ADR: `docs/decisions/ADR-176-adaptive-loop-engine.md`
Read the implementation plan: `docs/plans/2026-02-28-adaptive-loop-engine-plan.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-176-adaptive-loops", description="Implementing ADR-176: Adaptive Loop Engine")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-176-adaptive-loops", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-176 team.
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

**Team name**: `adr-176-adaptive-loops`

#### Phase 1: Foundation
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create execution journal with JSONL writer/reader, filtering, retention cleanup | `plugins/observability/skills/daemon/scripts/adaptive/journal.py`, `plugins/observability/skills/daemon/tests/test_adaptive_journal.py` |
| 1.2 | developer | medium | Create trust ledger with category states, promotion/demotion, persistence | `plugins/observability/skills/daemon/scripts/adaptive/trust_ledger.py`, `plugins/observability/skills/daemon/tests/test_adaptive_trust.py` |
| 1.3 | developer | low | Create base loop abstract class and LoopResult dataclass | `plugins/observability/skills/daemon/scripts/adaptive/loops/base_loop.py`, `plugins/observability/skills/daemon/tests/test_adaptive_base_loop.py` |

#### Phase 2: Engine Core
**Strategy**: PIPELINE (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | high | Build AdaptiveLoopEngine orchestrator with trust-gated execution, regression guard, morning report | `plugins/observability/skills/daemon/scripts/adaptive/engine.py`, `plugins/observability/skills/daemon/tests/test_adaptive_engine.py` |

#### Phase 3: Loop Implementations
**Strategy**: PARALLEL (depends on Phase 2)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Code quality loop: ESLint/Prettier auto-fix, TODO resolution via headless Claude | `plugins/observability/skills/daemon/scripts/adaptive/loops/code_quality.py`, `plugins/observability/skills/daemon/tests/test_adaptive_code_quality.py` |
| 3.2 | developer | medium | Command evolution loop: wrap ADR-102 infrastructure, scan execution logs, apply improvements | `plugins/observability/skills/daemon/scripts/adaptive/loops/command_evolution.py`, `plugins/observability/skills/daemon/tests/test_adaptive_cmd_evolution.py` |
| 3.3 | developer | medium | Knowledge enrichment loop: RAG reindex, data gap scanning, description generation | `plugins/observability/skills/daemon/scripts/adaptive/loops/knowledge_enrichment.py`, `plugins/observability/skills/daemon/tests/test_adaptive_knowledge.py` |
| 3.4 | developer | low | Self-heal wrapper: bridge existing ai_self_healer to BaseLoop interface | `plugins/observability/skills/daemon/scripts/adaptive/loops/self_heal.py`, `plugins/observability/skills/daemon/tests/test_adaptive_self_heal_wrapper.py` |

#### Phase 4: Integration
**Strategy**: PIPELINE (depends on Phase 3)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | devops | low | Create adaptive_loops.yaml config with all 4 loops and categories | `config/system/adaptive_loops.yaml` |
| 4.2 | developer | medium | Create daemon executor script with loop registration and scheduling | `plugins/observability/skills/daemon/scripts/adaptive_loop_executor.py` |
| 4.3 | developer | low | Register adaptive_loop_engine in unified_daemon.py CHILD_SERVICES | `plugins/observability/skills/daemon/scripts/unified_daemon.py` |
| 4.4 | devops | low | Create /ops-loops workflow and run sync_agents.py | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/ops-loops.md` |
| 4.5 | developer | low | Wire up package __init__.py exports for both adaptive/ and loops/ | `plugins/observability/skills/daemon/scripts/adaptive/__init__.py`, `plugins/observability/skills/daemon/scripts/adaptive/loops/__init__.py` |

#### Phase 5: Verification
**Strategy**: PIPELINE (depends on Phase 4)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | medium | Write integration test covering full engine cycle with all 4 loops | `plugins/observability/skills/daemon/tests/test_adaptive_integration.py` |
| 5.2 | validator | low | Run all adaptive tests: `cd plugins/observability/skills/daemon && python -m pytest tests/test_adaptive_*.py -v` | |
| 5.3 | validator | low | Run existing daemon tests to verify no regressions | |
| 5.4 | architect | low | Verify ADR-176 intent matches implementation: 4 loops, trust ledger, journal, regression guard, /ops-loops | |

### Completion Criteria
- [ ] All 13 tasks executed
- [ ] All adaptive tests pass (`python -m pytest tests/test_adaptive_*.py -v`)
- [ ] Existing daemon tests pass (no regressions)
- [ ] Config file loads correctly (`config/system/adaptive_loops.yaml`)
- [ ] `/ops-loops` appears in CLAUDE.md Ops section after sync_agents
- [ ] ADR status updated to "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-176-adaptive-loop-engine.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
