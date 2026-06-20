---
status: Implemented
date: '2026-03-08'
deciders:
- User
related: []
hub: null
tags:
- remove
- executor
- skill
- backlog
- system
superseded_by: null
---

# ADR-261: Remove Executor Skill and Backlog System

## Context

The executor skill (`plugins/core/skills/executor/`) is legacy auto-generated code that serves as a task queue / backlog directory. It has no logic of its own — it's a data-only directory that accumulates timestamped `chain-plan-*.md` files from multiple producers (factory/validator, implement_feature.py, feature_machine.py, triage_inbox.py, epic_generator.py, channels/registry.py).

Problems:
- Chain-plan files pile up as untracked git artifacts (26+ in a single day)
- The backlog system is not actively used — no UI renders it as a primary feature
- `backlog.ts` (1235 lines) mixes two unrelated concerns: backlog task management AND agent capability/factory scanning
- `agentTasks` data path is declared in both `ai_bridge/augur.yaml` and `mcp-app-factory/augur.yaml` (conflict)
- Violates data separation rule — runtime artifacts stored in plugin source directory

## Decision

Remove everything: the executor skill directory, the backlog dashboard service, API routes, components, server actions, Python writer functions, type definitions, and data path declarations.

Preserve agent capability and factory status functions by extracting them from `backlog.ts` into a new `agents.ts` service file.

### What Gets Deleted

| Component | Path |
|-----------|------|
| Executor skill | `plugins/core/skills/executor/` |
| Validator reports | `factory/validator/reports/` |
| Backlog service | `src/dashboard/lib/services/backlog.ts` |
| Backlog API routes | `src/dashboard/app/api/agents/backlog/route.ts`, `src/dashboard/app/api/backlog/hierarchy/route.ts` |
| Backlog actions | `src/dashboard/app/actions/backlog.ts` |
| Backlog components | `src/dashboard/components/backlog/` (ActiveSprintTab, EpicsTab, FeaturesTab, index) |
| Agent components | `AgentCommandCenter.tsx`, `TriageTaskCard.tsx` |
| Backlog types | `AgentTask`, `AgentTaskSection`, `AgentBacklogSummary`, `BacklogItem`, `SprintMetrics`, `BacklogItemWithMaturity`, `QualityCriteria`, `EpicCategory`, `EpicEnhanced`, `FeatureWithMaturity`, `SprintHierarchy` in `shared-types.ts` |
| Python writers | `_create_task_from_plan()` in `implement_feature.py`, backlog functions in `feature_machine.py` |
| Data paths | `agentTasks` in `ai_bridge/augur.yaml` and `mcp-app-factory/augur.yaml` |

### What Gets Extracted (Preserved)

From `backlog.ts` → new `agents.ts`:
- `getAgentCapabilities()`, `getAgentDetails()`, `getFactoryStatus()`
- All agent scoring, telemetry, capability parsing, and factory status helpers

### What Stays Unchanged

- `ai_bridge/augur/hooks/executor.py` (ThreadPoolExecutor for hooks — unrelated)
- `AgentCapability`, `AgentTier`, `FactoryStatus` types (cleaned of backlog fields)
- `AgentCard.tsx`, `AgentSummaryCard.tsx` components

## Consequences

### Positive

- Eliminates 26+ untracked files per day from git status
- Removes 1235-line backlog.ts and replaces with focused agents.ts
- Resolves `agentTasks` data path conflict between ai_bridge and mcp-app-factory
- Fixes data separation violation (runtime data in source directory)
- Removes dead UI code (components, routes, actions nobody uses)

### Negative

- Any future task queue system would need to be built from scratch
- `feature_machine.py` loses its backlog integration (may need full deletion)

### Neutral

- Agent capability and factory status dashboards continue working unchanged

## Alternatives Considered

### Alternative 1: Move backlog data to runtime/

Keep the backlog system but relocate `data/agent-tasks/` to `runtime/agent-tasks/` per data separation rules. Rejected because the backlog system itself is unused — moving it just preserves dead code.

### Alternative 2: Keep executor skill, gitignore the artifacts

Add gitignore rules for chain-plan files. Rejected because it papers over the real problem — the executor skill and its producers are generating artifacts nobody consumes.

## References

- Design doc: `docs/plans/2026-03-08-remove-executor-skill-design.md`
- Data separation rule: CLAUDE.md critical rule #3
- Plugin decentralization: ADR-163

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - function: getAgentBacklogSummary
      module: src/dashboard/lib/services/backlog
      breaking: true
    - function: getAgentDetails
      module: src/dashboard/lib/services/backlog
      breaking: true  # moved to agents.ts
    - function: getAgentCapabilities
      module: src/dashboard/lib/services/backlog
      breaking: true  # moved to agents.ts
    - function: getFactoryStatus
      module: src/dashboard/lib/services/backlog
      breaking: true  # moved to agents.ts
  patterns_deprecated:
    - grep: "from.*services/backlog"
      replacement: "from services/agents (for agent functions) or remove (for backlog functions)"
    - grep: "executor/data/agent-tasks"
      replacement: "removed — no replacement"
    - grep: "agentTasks"
      replacement: "removed from data_paths"
  files_affected:
    - glob: "src/dashboard/lib/api.ts"
    - glob: "src/dashboard/app/api/dashboard/route.ts"
    - glob: "plugins/ai/skills/ai_bridge/augur.yaml"
    - glob: "plugins/dev/skills/mcp-app-factory/augur.yaml"
    - glob: "plugins/dev/skills/developer/scripts/implement_feature.py"
    - glob: "plugins/dev/skills/developer/scripts/feature_machine.py"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-261-remove-executor`

### Phase 1: Extract Agent Functions
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Extract agent capability, factory status, and all helper functions from backlog.ts into new agents.ts. Keep exports identical. | `src/dashboard/lib/services/agents.ts`, `src/dashboard/lib/services/backlog.ts` |
| 1.2 | validator | low | Verify agents.ts compiles with `npx tsc --noEmit` | `src/dashboard/lib/services/agents.ts` |

### Phase 2: Delete Backlog Infrastructure
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Delete backlog.ts, API routes, actions, components. Update api.ts and dashboard route.ts to remove backlog imports. Fix all broken imports. | `src/dashboard/lib/services/backlog.ts`, `src/dashboard/app/api/agents/backlog/`, `src/dashboard/app/api/backlog/`, `src/dashboard/app/actions/backlog.ts`, `src/dashboard/components/backlog/`, `src/dashboard/components/agents/AgentCommandCenter.tsx`, `src/dashboard/components/agents/TriageTaskCard.tsx`, `src/dashboard/lib/api.ts`, `src/dashboard/app/api/dashboard/route.ts` |
| 2.2 | developer | medium | Remove backlog types from shared-types.ts. Clean AgentCapability (remove items field) and FactoryStatus (remove sprint, critical_bugs). | `src/dashboard/lib/shared-types.ts` |

### Phase 3: Clean Python & Config
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Remove _create_task_from_plan, _normalize_plan_text from implement_feature.py. Remove plan-to-backlog branch in implement_feature(). | `plugins/dev/skills/developer/scripts/implement_feature.py` |
| 3.2 | developer | medium | Evaluate feature_machine.py — if entirely backlog-dependent, delete it. Otherwise remove only backlog functions. | `plugins/dev/skills/developer/scripts/feature_machine.py` |
| 3.3 | developer | low | Remove agentTasks from augur.yaml data_paths in ai_bridge and mcp-app-factory. Remove executor gitignore entry. | `plugins/ai/skills/ai_bridge/augur.yaml`, `plugins/dev/skills/mcp-app-factory/augur.yaml`, `.gitignore` |

### Phase 4: Delete & Verify
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | low | Delete plugins/core/skills/executor/ and factory/validator/reports/ | directories |
| 4.2 | validator | medium | Run npm run build, grep for dangling references, verify clean git status | all |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria
- [ ] agents.ts exports getAgentCapabilities, getAgentDetails, getFactoryStatus
- [ ] backlog.ts deleted, no imports reference it
- [ ] All backlog types removed from shared-types.ts
- [ ] No Python code references executor/data/agent-tasks
- [ ] No agentTasks in any augur.yaml
- [ ] plugins/core/skills/executor/ deleted
- [ ] factory/validator/reports/ deleted
- [ ] npm run build passes
- [ ] No dangling grep matches for removed symbols
- [ ] ADR status updated to Implemented
