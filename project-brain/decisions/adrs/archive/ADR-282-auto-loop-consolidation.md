---
status: Implemented
date: '2026-03-05'
deciders:
- Gur Sannikov
- Claude
related: []
hub: null
tags:
- auto
- loop
- consolidation
- eliminate
- manual
superseded_by: null
---

# ADR-282: Auto-Loop Consolidation — Eliminate Manual/Auto Command Duplication

**Related ADRs**: ADR-176 (adaptive loop engine), ADR-200 (ops-loops auto-commands separation), ADR-181 (loop consolidation), ADR-163 (plugin decentralization)

## Context

14 manual commands duplicate work already handled by auto-loop commands or are prime candidates for autonomous execution. 6 of the 14 already have auto-* counterparts doing identical work (e.g., `ops-memory` duplicates `auto-memory-sync`, `review-markers` duplicates `auto-markers`). The remaining 8 are maintenance/validation tasks that run on predictable schedules and follow the scan-fix pattern.

This creates:
- **Command bloat**: 49 command entries for 35 actual operations
- **User confusion**: `/ops-memory` vs `auto-memory-sync` — which to use?
- **Missed automation**: Security audits, dependency checks, and code reviews only run when humans remember to invoke them

The adaptive engine (ADR-176) already provides trust-gated, budget-controlled autonomous execution with difficulty escalation and regression guards. All 14 commands fit this model.

Additionally, 3 commands (ops-audit, ops-perf, sync-repos) don't map cleanly to existing loops — they concern system observability rather than code quality, hardening, or knowledge.

## Decision

### 1. Create new `observability` loop

Add a 7th adaptive loop for system monitoring concerns:

```yaml
observability:
  budget: 10
  budget_growth_rate: 1
```

New BaseLoop deprecated stub at `plugins/observability/skills/daemon/scripts/adaptive/loops/observability.py` (ADR-200 pattern).

3 commands assigned:
- `auto-repo-sync` (tier 0, nightly) — check repos for uncommitted/unpushed changes
- `auto-context-audit` (tier 1, nightly) — measure MCP context token usage
- `auto-perf-profile` (tier 2, nightly) — check response times, flag regressions

### 2. Delete 14 manual commands entirely

No consolidation, no aliases. The auto-* command IS the command. Manual invocation via `/ops-loops run <name>`.

#### 6 deletions — existing auto-* already covers:

| Delete | Covered by | Loop |
|---|---|---|
| `ops-memory` | `auto-memory-sync` | knowledge-enrichment |
| `sync-agents` / `ops-sync` | `auto-agent-sync` | knowledge-enrichment |
| `documentation-sync` | `auto-docs` | knowledge-enrichment |
| `review-markers` | `auto-markers` | code-quality |
| `dev-improve` | `auto-command-evolution` | command-evolution |
| `test-security` | `auto-security-scan` | hardening |

#### 7 deletions — replaced by new auto-* commands:

| Delete | Replaced by | Loop | Tier |
|---|---|---|---|
| `dev-review` | `auto-code-review` | code-quality | 3 |
| `test-coverage` | `auto-test-coverage` | code-quality | 2 |
| `dependency-audit` | `auto-dependency-audit` | hardening | 3 |
| `test-heal` | `auto-heal-validate` | self-heal | 1 |
| `ops-audit` | `auto-context-audit` | observability | 1 |
| `ops-perf` | `auto-perf-profile` | observability | 2 |
| `sync-repos` | `auto-repo-sync` | observability | 0 |

### 3. Implement 7 new scan-fix modules

Each follows the OpsCommand protocol (`src/lib/ops_protocol.py`):
- Module-level `name` variable matching augur.yaml `id`
- `scan(ctx: OpsContext) -> ScanResult`
- `fix(ctx: OpsContext, issues: list[dict]) -> FixResult`
- Difficulty-gated behavior (report-only at low difficulty, action at higher)
- `dry_run` support

| Module | File | Plugin |
|---|---|---|
| `auto-code-review` | `scripts/ops/code_review.py` | `plugins/dev/skills/devops/` |
| `auto-test-coverage` | `scripts/ops/test_coverage.py` | `plugins/dev/skills/devops/` |
| `auto-dependency-audit` | `scripts/ops/dependency_audit.py` | `plugins/dev/skills/devops/` |
| `auto-heal-validate` | `scripts/ops/heal_validate.py` | `plugins/observability/skills/daemon/` |
| `auto-context-audit` | `scripts/ops/context_audit.py` | `plugins/observability/skills/daemon/` |
| `auto-perf-profile` | `scripts/ops/perf_profile.py` | `plugins/observability/skills/daemon/` |
| `auto-repo-sync` | `scripts/ops/repo_sync.py` | `plugins/observability/skills/daemon/` |

### 4. Budget adjustments

| Loop | Before | After |
|---|---|---|
| code-quality | 15 | 18 |
| hardening | 10 | 12 |
| self-heal | 5 | 6 |
| observability | — | 10 |

### 5. Legacy naming audit

Post-migration grep-kill of all 14 deleted command names across:
- `plugins/*/skills/*/augur.yaml`
- `plugins/*/skills/*/SKILL.md`
- `config/`, `docs/agent-topics/`, `CLAUDE.md`, `agent-rules.md`
- `src/`, `scripts/`, `docs/generated/`

Plus naming consistency audit of all 42 auto-commands verifying: `auto-` prefix, `visibility: auto`, `protocol: scan-fix`, valid `loop.name`, callable exists with `scan()`+`fix()`.

## Consequences

### Positive

- Zero command duplication — 42 auto-commands, 0 manual overlaps
- All 14 operations now run autonomously on trust-gated schedules
- New `observability` loop provides dedicated budget for system monitoring
- Users still invoke any command manually via `/ops-loops run <name>`
- 7 net new capabilities (code review, coverage, dependency audit, heal validation, context audit, perf profiling, repo sync)

### Negative

- Users must learn `/ops-loops run <name>` instead of direct slash commands like `/ops-memory`
- 7 new Python modules to maintain (though they follow established patterns)
- `auto-repo-sync` at difficulty 3+ can push to remote — requires trust earned over time

### Neutral

- Trust state persists across daemon restarts via `runtime/adaptive/trust_state.json`
- New commands start at trust 0.0 (tier 1+) or enabled (tier 0)
- Existing auto-commands are unaffected

## Alternatives Considered

### Alternative A: Minimal — Fold everything into existing 6 loops

Stuff `ops-audit` and `ops-perf` into hardening, `sync-repos` into knowledge-enrichment. No new loops.

**Rejected**: Loops become semantically muddled. Budget contention increases. "Hardening" shouldn't own performance profiling.

### Alternative C: Two new loops — observability + testing

Create both `observability` and `testing` loops.

**Rejected**: Over-segmentation. `test-coverage` fits naturally in code-quality, `test-heal` fits in self-heal. Two new loops for only 2 commands each is thin.

### Alternative: Keep manual commands as aliases

Keep manual entries pointing to the same callable as auto-commands.

**Rejected by user**: Creates naming confusion and maintenance burden. "If I need to run something manually, I'll use auto-." Zero duplication is the goal.

## References

- [ADR-176: Adaptive Loop Engine](ADR-176-adaptive-loop-engine.md)
- [ADR-200: Ops-Loops Auto-Commands Separation](ADR-200-ops-loops-auto-commands-separation.md)
- [ADR-181: Adaptive Loops Consolidation](ADR-181-adaptive-loops-consolidation.md)
- ADR-163: Plugin Decentralization
- Design doc: `docs/plans/2026-03-05-auto-loop-consolidation-design.md`
- Implementation plan: `docs/plans/2026-03-05-auto-loop-consolidation-plan.md`
- OpsCommand protocol: `src/lib/ops_protocol.py`

## Impact Manifest

```yaml
impact:
  patterns_deprecated:
    - grep: "id: ops-memory"
      replacement: "Use auto-memory-sync (knowledge-enrichment loop)"
    - grep: "id: ops-sync"
      replacement: "Use auto-agent-sync (knowledge-enrichment loop)"
    - grep: "id: documentation-sync"
      replacement: "Use auto-docs (knowledge-enrichment loop)"
    - grep: "id: review-markers"
      replacement: "Use auto-markers (code-quality loop)"
    - grep: "id: dev-improve"
      replacement: "Use auto-command-evolution (command-evolution loop)"
    - grep: "id: test-security"
      replacement: "Use auto-security-scan (hardening loop)"
    - grep: "id: dev-review"
      replacement: "Use auto-code-review (code-quality loop)"
    - grep: "id: test-coverage"
      replacement: "Use auto-test-coverage (code-quality loop)"
    - grep: "id: dependency-audit"
      replacement: "Use auto-dependency-audit (hardening loop)"
    - grep: "id: test-heal"
      replacement: "Use auto-heal-validate (self-heal loop)"
    - grep: "id: ops-audit"
      replacement: "Use auto-context-audit (observability loop)"
    - grep: "id: ops-perf"
      replacement: "Use auto-perf-profile (observability loop)"
    - grep: "id: sync-repos"
      replacement: "Use auto-repo-sync (observability loop)"
  files_affected:
    - glob: "plugins/*/skills/*/augur.yaml"
    - glob: ".claude/skills/*/SKILL.md"
    - glob: "plugins/ai/skills/ai_bridge/augur/data/ide-integration/workflows/*.md"
    - glob: "plugins/ai/skills/ai_bridge/augur/data/agent-rules.md"
    - glob: "config/system/adaptive_loops.yaml"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-246-auto-loop-consolidation`

### Phase 1: Infrastructure
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | devops | low | Add observability loop to adaptive_loops.yaml, adjust budgets | `config/system/adaptive_loops.yaml` |
| 1.2 | devops | low | Create ObservabilityLoop BaseLoop stub with tests | `plugins/observability/skills/daemon/scripts/adaptive/loops/observability.py`, tests |
| 1.3 | devops | low | Add observability to all 3 symbols.yaml files | `plugins/observability/skills/daemon/*/loops/symbols.yaml` |

### Phase 2: New Auto-Command Modules
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create auto-repo-sync with tests | `plugins/observability/skills/daemon/scripts/ops/repo_sync.py`, tests |
| 2.2 | developer | medium | Create auto-context-audit with tests | `plugins/observability/skills/daemon/scripts/ops/context_audit.py`, tests |
| 2.3 | developer | medium | Create auto-perf-profile with tests | `plugins/observability/skills/daemon/scripts/ops/perf_profile.py`, tests |
| 2.4 | developer | medium | Create auto-heal-validate with tests | `plugins/observability/skills/daemon/scripts/ops/heal_validate.py`, tests |
| 2.5 | developer | medium | Create auto-code-review with tests | `plugins/dev/skills/devops/scripts/ops/code_review.py`, tests |
| 2.6 | developer | medium | Create auto-test-coverage with tests | `plugins/dev/skills/devops/scripts/ops/test_coverage.py`, tests |
| 2.7 | developer | medium | Create auto-dependency-audit with tests | `plugins/dev/skills/devops/scripts/ops/dependency_audit.py`, tests |

### Phase 3: Registration and Deletion
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | devops | low | Register 7 new auto-commands in augur.yaml files | `plugins/observability/skills/daemon/augur.yaml`, `plugins/dev/skills/devops/augur.yaml` |
| 3.2 | devops | low | Delete 14 manual command entries from augur.yaml files | 5 augur.yaml files |
| 3.3 | devops | low | Delete orphan SKILL.md and workflow files | `.claude/skills/`, `plugins/ai/skills/ai_bridge/augur/data/ide-integration/workflows/` |

### Phase 4: Documentation and Audit
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | devops | low | Update agent-rules.md slash command listings, regenerate CLAUDE.md | `agent-rules.md`, `CLAUDE.md` |
| 4.2 | validator | medium | Run legacy naming grep-kill across entire repo | all files |
| 4.3 | validator | medium | Run naming consistency audit of all 42 auto-commands | `scripts/audit_auto_commands.py` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | validator | low | Verify engine discovers exactly 42 auto-commands |
| V.3 | validator | low | TypeScript build check passes |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria
- [ ] All 7 new auto-command modules pass tests
- [ ] All 14 manual command entries deleted from augur.yaml
- [ ] All orphan SKILL.md and workflow files removed
- [ ] Agent-rules.md and CLAUDE.md updated
- [ ] Zero legacy name references (except docs/plans/ design doc)
- [ ] 42 auto-commands discovered by engine
- [ ] All 42 pass naming consistency audit
- [ ] TypeScript build passes
- [ ] ADR status updated to Implemented
